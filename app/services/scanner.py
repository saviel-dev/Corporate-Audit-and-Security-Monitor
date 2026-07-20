"""
app/services/scanner.py

Orchestrates a full daily scan (DailyRun).

Two-pipeline architecture:
  Pipeline A — Auto-Discovery (states with officer/agent name search)
    → Searches by "Marcio Garcia", "Garcia", "Andrade" etc.
    → Discovers corp names, upserts into DB with source="auto"

  Pipeline B — CSV Fallback (states without officer search support)
    → Reads corporations already in DB (imported via CSV upload)
    → State: HI falls here since its portal is entity-name-only

Then:
  → Loads all "Disponible" corps for SCRAPER_READY_STATES
  → Orders by state priority + age
  → Runs individual scrape for each
  → Applies detection rule (Marcio + Garcia/Andrade)
  → Saves results, generates Excel, uploads, emails
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# State priority: lower index = higher priority
STATE_PRIORITY = ["HI", "CO", "NM", "MS", "NY", "FL", "CA", "DE", "WY"]

# Default discovery terms (can be overridden by StateConfig.discovery_terms)
DEFAULT_DISCOVERY_TERMS = ["Marcio Garcia", "Garcia", "Andrade", "Marcio"]

# Global flags for cancellation
SCAN_CANCEL_FLAGS: dict[int, bool] = {}

def cancel_scan(run_id: int):
    """Signals a running scan thread to stop."""
    SCAN_CANCEL_FLAGS[run_id] = True


# ─── Scraper registry ─────────────────────────────────────────────────────────

def get_scraper(state_code: str, output_dir: str = "output/pdfs",
                timeout_ms: int = 30_000, retries: int = 3,
                delay_s: float = 2.0):
    """Return a scraper instance for *state_code*, or None if unsupported."""
    from app.scrapers.hi import HawaiiScraper
    from app.scrapers.co import ColoradoScraper

    registry = {
        "HI": HawaiiScraper,
        "CO": ColoradoScraper,
    }
    cls = registry.get(state_code.upper())
    if cls is None:
        return None
    return cls(
        timeout_ms=timeout_ms,
        retries=retries,
        delay_s=delay_s,
        output_dir=output_dir,
    )


# ─── Main orchestrator ────────────────────────────────────────────────────────

def run_daily_scan(run_id: int, app) -> None:
    """Execute a full daily scan inside app's context."""
    with app.app_context():
        _execute_scan(run_id, app)


def _execute_scan(run_id: int, app) -> None:
    from app import db
    from app.models import Corporation, DailyRun, ScanResult, StateConfig
    from app.services.detector import is_potential_theft
    from app.services.reporter import generate_excel

    run = db.session.get(DailyRun, run_id)
    if not run:
        logger.error("DailyRun #%d not found.", run_id)
        return

    SCAN_CANCEL_FLAGS[run_id] = False
    run.status = "running"
    db.session.commit()
    logger.info("=== DailyRun #%d started ===", run_id)

    cfg = app.config
    output_dir = cfg.get("OUTPUT_FOLDER", "output")
    pdf_dir    = f"{output_dir}/pdfs"
    timeout_ms = cfg.get("SCRAPER_TIMEOUT", 30_000)
    retries    = cfg.get("SCRAPER_RETRIES", 3)
    delay_s    = float(cfg.get("SCRAPER_DELAY", 2.0))
    supported  = cfg.get("SCRAPER_READY_STATES", ["HI", "CO"])

    detection_required   = cfg.get("DETECTION_REQUIRED", "Marcio")
    detection_alternates = cfg.get("DETECTION_ALTERNATES", ["Garcia", "Andrade"])
    # Build Socrata discovery terms for CO
    co_discovery_terms = [
        {"first": detection_required, "last": alt}
        for alt in detection_alternates
    ] + [{"first": detection_required, "last": None}]  # broad: all Marcios

    # String terms for scraper-based discovery (other states)
    discovery_terms = [detection_required] + detection_alternates + DEFAULT_DISCOVERY_TERMS
    seen = set()
    discovery_terms = [t for t in discovery_terms if not (t in seen or seen.add(t))]

    # ── PIPELINE A-CO: Colorado auto-discovery via Socrata API ───────────────
    # No reCAPTCHA, no Playwright — direct REST API call to data.colorado.gov
    if "CO" in supported:
        logger.info("Pipeline A (CO): Socrata API discovery...")
        try:
            from app.services.co_discovery import run_co_discovery
            co_entities = run_co_discovery(discovery_terms=co_discovery_terms)
            logger.info("[CO-API] Found %d entities from Socrata.", len(co_entities))

            for entity in co_entities:
                existing = Corporation.query.filter_by(
                    name=entity["name"], state="CO"
                ).first()
                if not existing:
                    corp = Corporation(
                        name=entity["name"],
                        state="CO",
                        status=entity["status"],
                        source_file=entity["source_file"],
                    )
                    db.session.add(corp)
                    logger.info("[CO-API] New corp discovered: '%s' (agent: %s)",
                                entity["name"],
                                f"{entity['agent_first']} {entity['agent_last']}")
                else:
                    # Update status if it changed
                    if existing.status != entity["status"]:
                        existing.status = entity["status"]
            db.session.commit()
        except Exception as exc:
            logger.error("[CO-API] Discovery failed: %s", exc)

    # ── PIPELINE A-OTHER: Scraper-based discovery for other states ────────────
    logger.info("Pipeline A (other states): Scraper-based discovery...")
    discoverable_states = StateConfig.get_discoverable_states()

    for state_cfg in discoverable_states:
        if state_cfg.state_code not in supported or state_cfg.state_code == "CO":
            continue  # CO handled above via Socrata

        terms = (
            [t.strip() for t in state_cfg.discovery_terms.split(",")]
            if state_cfg.discovery_terms
            else discovery_terms
        )

        scraper = get_scraper(
            state_cfg.state_code, output_dir=pdf_dir,
            timeout_ms=timeout_ms, retries=retries, delay_s=delay_s
        )
        if not scraper or not scraper.SUPPORTS_DISCOVERY:
            continue

        logger.info("[%s] Auto-discovering with terms: %s", state_cfg.state_code, terms)
        corp_names = scraper.discover(terms)

        for name in corp_names:
            existing = Corporation.query.filter_by(
                name=name, state=state_cfg.state_code
            ).first()
            if not existing:
                db.session.add(Corporation(
                    name=name,
                    state=state_cfg.state_code,
                    status="Disponible",
                    source_file="auto-discovery",
                ))
                logger.info("[%s] Auto-discovered new corp: '%s'",
                            state_cfg.state_code, name)
        db.session.commit()

    # ── PIPELINE B: CSV corporations already in DB ────────────────────────────
    # (HI and other CSV-only states already have their corps in DB via upload)
    logger.info("Pipeline B: Loading CSV-sourced corporations from DB...")

    # ── LOAD + SORT all processable corporations ──────────────────────────────
    corps = (
        Corporation.query
        .filter(
            Corporation.status.isnot(None),
            Corporation.state.in_(supported),
        )
        .all()
    )

    # Filter out sold/vendida
    corps = [c for c in corps if c.status.strip().lower() not in ("vendida", "sold")]

    # Sort: state priority first, then date_registered ASC (oldest first)
    def sort_key(c):
        try:
            state_rank = STATE_PRIORITY.index(c.state)
        except ValueError:
            state_rank = 99
        age = c.date_registered or datetime(9999, 12, 31).date()
        return (state_rank, age, c.name or "")

    corps = sorted(corps, key=sort_key)
    
    # Allow resuming: skip already scanned corporations for this run_id
    already_scanned = db.session.query(ScanResult.corporation_id).filter_by(daily_run_id=run_id).all()
    already_scanned_ids = {r[0] for r in already_scanned}
    
    corps = [c for c in corps if c.id not in already_scanned_ids]
    logger.info("Scanning %d corporations (after filtering Vendidas and already scanned).", len(corps))

    total_processed = run.total_processed or 0
    total_alerts    = run.total_alerts or 0
    total_errors    = run.total_errors or 0

    # ── SCAN each corporation ─────────────────────────────────────────────────
    for corp in corps:
        if SCAN_CANCEL_FLAGS.get(run_id):
            logger.info("Scan #%d cancelled by user.", run_id)
            run.status = "cancelled"
            break

        scraper = get_scraper(
            corp.state, output_dir=pdf_dir,
            timeout_ms=timeout_ms, retries=retries, delay_s=delay_s
        )
        if not scraper:
            logger.warning("No scraper for state '%s' (corp: %s)",
                           corp.state, corp.name)
            continue

        logger.info("Scanning [%s] %s", corp.state, corp.name)
        scraped = scraper.scrape(corp.name, save_pdf=True)

        # Detect potential theft
        is_theft, reason = is_potential_theft(
            scraped.officer_name,
            scraped.registered_agent,
        )

        # Detect change vs. previous scan
        prev = (
            ScanResult.query
            .filter_by(corporation_id=corp.id)
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        status_changed = False
        if prev:
            status_changed = (
                prev.officer_name_raw  != scraped.officer_name or
                prev.portal_status     != scraped.portal_status
            )

        # Delete evidence if it's a clean scan to save storage
        if not is_theft and scraped.pdf_path:
            import os
            try:
                os.remove(scraped.pdf_path)
                scraped.pdf_path = None
            except OSError:
                pass

        # Save result
        result = ScanResult(
            daily_run_id         = run_id,
            corporation_id       = corp.id,
            officer_name_raw     = scraped.officer_name,
            registered_agent_raw = scraped.registered_agent,
            portal_status        = scraped.portal_status,
            alert                = is_theft,
            alert_reason         = reason,
            status_changed       = status_changed,
            pdf_path             = scraped.pdf_path,
            error                = scraped.error,
            error_message        = scraped.error_message,
        )
        db.session.add(result)

        total_processed += 1
        if scraped.error:
            total_errors += 1
        elif is_theft:
            total_alerts += 1

        run.total_processed = total_processed
        run.total_alerts = total_alerts
        run.total_errors = total_errors

        db.session.commit()
        
        from app import socketio
        socketio.emit('scan_progress', {
            'run_id': run.id,
            'running': True,
            'processed': total_processed,
            'expected': len(corps),
            'alerts': total_alerts,
            'errors': total_errors,
            'status': run.status
        })

    # ── Finalize run ──────────────────────────────────────────────────────────
    run.finished_at     = datetime.now(timezone.utc)
    run.total_processed = total_processed
    run.total_alerts    = total_alerts
    run.total_errors    = total_errors
    
    if not SCAN_CANCEL_FLAGS.get(run_id):
        run.status = "done"
    
    db.session.commit()
    from app import socketio
    socketio.emit('scan_progress', {
        'run_id': run.id,
        'running': False,
        'processed': total_processed,
        'expected': len(corps),
        'alerts': total_alerts,
        'errors': total_errors,
        'status': run.status
    })

    # ── Generate Excel report ─────────────────────────────────────────────────
    try:
        excel_path = generate_excel(run_id, output_dir=f"{output_dir}/reports")
        run.report_excel_path = excel_path
        logger.info("Excel report: %s", excel_path)
    except Exception as exc:
        logger.error("Excel generation failed: %s", exc)

    db.session.commit()

    # ── Upload to cloud ───────────────────────────────────────────────────────
    _upload_run_files(run, app)

    # ── Send email ────────────────────────────────────────────────────────────
    _send_email_summary(run_id, app)

    logger.info(
        "=== DailyRun #%d complete — %d processed, %d alerts, %d errors ===",
        run_id, total_processed, total_alerts, total_errors
    )


def _upload_run_files(run, app) -> None:
    try:
        from app.services.storage import upload_run
        upload_run(run, app)
    except Exception as exc:
        logger.error("Cloud upload failed: %s", exc)


def _send_email_summary(run_id: int, app) -> None:
    try:
        from app.services.mailer import send_daily_summary
        from app.models import ScanResult
        with app.app_context():
            flagged = ScanResult.query.filter_by(
                daily_run_id=run_id, alert=True
            ).all()
            send_daily_summary(run_id, flagged)
    except Exception as exc:
        logger.error("Email send failed: %s", exc)


# ─── Background thread launcher ───────────────────────────────────────────────

def launch_scan_thread(run_id: int, app) -> threading.Thread:
    """Start a background thread for the scan (manual trigger from Flask route)."""
    t = threading.Thread(
        target=run_daily_scan,
        args=(run_id, app),
        daemon=True,
        name=f"scan-run-{run_id}",
    )
    t.start()
    logger.info("Scan thread started for DailyRun #%d", run_id)
    return t
