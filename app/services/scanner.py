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
  → Loads all corporations with status 'Available' for SCRAPER_READY_STATES
  → Orders by state priority + age
  → Runs individual scrape for each
  → Applies detection rule (Marcio + Garcia/Andrade)
  → Saves results, generates Excel, uploads, emails
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Terminos de descubrimiento por defecto (sobreescribibles por StateConfig.discovery_terms)
DEFAULT_DISCOVERY_TERMS = ["Marcio Garcia", "Garcia", "Andrade", "Marcio"]

# Flags globales de cancelacion de escaneo
SCAN_CANCEL_FLAGS: dict[int, bool] = {}


def cancel_scan(run_id: int):
    """Signals a running scan thread to stop."""
    SCAN_CANCEL_FLAGS[run_id] = True


# ─── Scraper registry ─────────────────────────────────────────────────────────


def get_scraper(
    state_code: str,
    output_dir: str = "output/pdfs",
    timeout_ms: int = 30_000,
    retries: int = 3,
    delay_s: float = 2.0,
):
    """Return a scraper instance for *state_code*, or None if unsupported."""
    from app.scrapers.co import ColoradoScraper
    from app.scrapers.hi import HawaiiScraper

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
    pdf_dir = f"{output_dir}/pdfs"
    timeout_ms = cfg.get("SCRAPER_TIMEOUT", 30_000)
    retries = cfg.get("SCRAPER_RETRIES", 3)
    delay_s = float(cfg.get("SCRAPER_DELAY", 2.0))
    supported = cfg.get("SCRAPER_READY_STATES", ["HI", "CO"])

    detection_required = cfg.get("DETECTION_REQUIRED", "Marcio")
    detection_alternates = cfg.get("DETECTION_ALTERNATES", ["Garcia", "Andrade"])
    # Build Socrata discovery terms for CO
    co_discovery_terms = [
        {"first": detection_required, "last": alt} for alt in detection_alternates
    ] + [
        {"first": detection_required, "last": None}
    ]  # broad: all Marcios

    # String terms for scraper-based discovery (other states)
    discovery_terms = (
        [detection_required] + detection_alternates + DEFAULT_DISCOVERY_TERMS
    )
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
                        corp_id=entity.get("corp_id"),
                        estado_entidad_registro=entity.get("estado_entidad_registro"),
                        fecha_ultima_verificacion_estado=entity.get("fecha_ultima_verificacion_estado")
                    )
                    db.session.add(corp)
                    logger.info(
                        "[CO-API] New corp discovered: '%s' (agent: %s)",
                        entity["name"],
                        f"{entity['agent_first']} {entity['agent_last']}",
                    )
                else:
                    # Actualizar estado si ya existía
                    existing.estado_entidad_registro = entity.get("estado_entidad_registro")
                    existing.fecha_ultima_verificacion_estado = entity.get("fecha_ultima_verificacion_estado")
                    # Update status if it changed
                    if existing.status != entity["status"]:
                        existing.status = entity["status"]
                    # Update corp_id if missing
                    new_corp_id = entity.get("corp_id")
                    if new_corp_id:
                        if not existing.corp_id:
                            existing.corp_id = new_corp_id
                            logger.info("[CO-API] Updated missing corp_id for '%s' -> %s", existing.name, new_corp_id)
                        elif existing.corp_id != new_corp_id:
                            logger.warning("[CO-API] DISCREPANCY: existing corp_id '%s' != new corp_id '%s' for '%s'. Not overwriting.", existing.corp_id, new_corp_id, existing.name)
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
            state_cfg.state_code,
            output_dir=pdf_dir,
            timeout_ms=timeout_ms,
            retries=retries,
            delay_s=delay_s,
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
                db.session.add(
                    Corporation(
                        name=name,
                        state=state_cfg.state_code,
                        status="Available",
                        source_file="auto-discovery",
                    )
                )
                logger.info(
                    "[%s] Auto-discovered new corp: '%s'", state_cfg.state_code, name
                )
        db.session.commit()

    # ── PIPELINE B: Corporaciones cargadas via CSV ya en la BD ──────────────
    # (HI y otros estados CSV-only ya tienen sus corps en BD por la subida del archivo)
    logger.info("Pipeline B: Cargando corporaciones desde la BD...")

    # ── CARGAR + ORDENAR todas las corporaciones elegibles ───────────────────
    estados_prioritarios: list[str] = cfg.get(
        "ESTADOS_PRIORITARIOS", ["CO", "HI", "NM"]
    )
    estado_elegible: str = cfg.get("ESTADO_ELEGIBLE", "Available")

    # Cargamos TODAS las corps de los estados con scraper para poder loguear descartes
    todas_en_scope = Corporation.query.filter(Corporation.state.in_(supported)).all()

    # Aplicar is_processable() — lista blanca por status y estado soportado
    corps_elegibles = []
    excluded_status_breakdown = {}
    descartadas_inventario = 0

    est_excluidos = [e.lower() for e in cfg.get("ESTADOS_ENTIDAD_EXCLUIDOS", [])]

    for c in todas_en_scope:
        if not c.is_processable(estado_elegible=estado_elegible, supported_states=supported):
            descartadas_inventario += 1
            continue
            
        estado_reg = (c.estado_entidad_registro or "").strip().lower()
        if estado_reg and estado_reg in est_excluidos:
            # Excluida por estar disuelta/muerta (estado en registro)
            orig_estado = c.estado_entidad_registro
            excluded_status_breakdown[orig_estado] = excluded_status_breakdown.get(orig_estado, 0) + 1
            continue
            
        corps_elegibles.append(c)

    descartadas = len(todas_en_scope) - len(corps_elegibles)
    logger.info(
        "Ciclo de escaneo: %d corps en scope, %d descartadas por status != '%s', %d descartadas por estado muerto, %d en cola.",
        len(todas_en_scope),
        descartadas_inventario,
        estado_elegible,
        sum(excluded_status_breakdown.values()),
        len(corps_elegibles),
    )

    # Ordenar: prioridad estatal primero, luego fecha de registro ASC (mas antigua primero)
    def sort_key(c: Corporation):
        try:
            estado_rank = estados_prioritarios.index(c.state)
        except ValueError:
            # Estados fuera de ESTADOS_PRIORITARIOS van despues, en orden alfabetico
            estado_rank = (
                len(estados_prioritarios) + sorted(supported).index(c.state)
                if c.state in supported
                else 999
            )
        age = c.date_registered or datetime(9999, 12, 31).date()
        return (estado_rank, age, c.name or "")

    corps = sorted(corps_elegibles, key=sort_key)

    # Log de posicion en cola por estado (T-02)
    for pos, corp in enumerate(corps, start=1):
        logger.debug(
            "Cola[%d/%d] estado=%s corp='%s'",
            pos,
            len(corps),
            corp.state,
            corp.name,
        )

    # Allow resuming: skip already scanned corporations for this run_id
    already_scanned = (
        db.session.query(ScanResult.corporation_id).filter_by(daily_run_id=run_id).all()
    )
    already_scanned_ids = {r[0] for r in already_scanned}

    corps = [c for c in corps if c.id not in already_scanned_ids]
    logger.info(
        "Escaneando %d corporaciones (excluidas las ya procesadas en esta ejecucion).",
        len(corps),
    )

    total_processed = run.total_processed or 0
    total_alerts = run.total_alerts or 0
    total_warnings = run.total_warnings or 0
    total_errors = run.total_errors or 0

    state_metrics_map = {}
    waf_blocks = {}

    # ── SCAN each corporation ─────────────────────────────────────────────────
    for corp in corps:
        if SCAN_CANCEL_FLAGS.get(run_id):
            logger.info("Scan #%d cancelled by user.", run_id)
            run.status = "cancelled"
            break

        scraper = get_scraper(
            corp.state,
            output_dir=pdf_dir,
            timeout_ms=timeout_ms,
            retries=retries,
            delay_s=delay_s,
        )
        if not scraper:
            logger.warning(
                "No scraper for state '%s' (corp: %s)", corp.state, corp.name
            )
            continue

        if corp.state not in state_metrics_map:
            from app.models import StateMetrics
            metrics = StateMetrics(daily_run_id=run_id, estado=corp.state, 
                                   total_intentadas=0, total_extraidas=0, 
                                   total_no_verificables=0, total_alertas=0,
                                   total_bloqueos_waf=0)
            db.session.add(metrics)
            state_metrics_map[corp.state] = metrics
        metrics = state_metrics_map[corp.state]
        
        # 1. Comprobar Circuit Breaker (enfriamiento WAF) antes de intentar
        state_cfg = StateConfig.query.filter_by(state_code=corp.state).first()
        if state_cfg and state_cfg.waf_blocked_until:
            if datetime.now(timezone.utc) < state_cfg.waf_blocked_until.replace(tzinfo=timezone.utc):
                logger.warning("[%s] Skipped due to WAF cooldown (until %s)", corp.state, state_cfg.waf_blocked_until)
                continue
            else:
                state_cfg.waf_blocked_until = None
                db.session.commit()

        logger.info("Scanning [%s] %s", corp.state, corp.name)
        scraped = scraper.scrape(corp.name, save_pdf=True)

        metrics.total_intentadas += 1

        is_theft = False
        reason = ""

        if scraped.error:
            if scraped.error_message == "BLOQUEADO_POR_WAF":
                metrics.total_bloqueos_waf += 1
                waf_blocks[corp.state] = waf_blocks.get(corp.state, 0) + 1
                max_blocks = cfg.get("MAX_WAF_BLOCKS", 2)
                if waf_blocks[corp.state] >= max_blocks:
                    logger.critical("[%s] MAX WAF BLOCKS REACHED. Triggering Circuit Breaker.", corp.state)
                    cooldown = cfg.get("WAF_COOLDOWN_MINUTOS", 120)
                    if state_cfg:
                        state_cfg.waf_blocked_until = datetime.now(timezone.utc) + timedelta(minutes=cooldown)
                        db.session.commit()
            else:
                metrics.total_no_verificables += 1
            reason = f"NO VERIFICABLE: {scraped.error_message}"
        else:
            metrics.total_extraidas += 1
            # Detect potential theft only if successfully extracted
            is_theft, reason = is_potential_theft(
                scraped.officer_name,
                scraped.registered_agent,
            )
            
            is_vulnerable = False
            # Check high priority alert status
            est_alertas = [e.lower() for e in cfg.get("ESTADOS_ENTIDAD_ALERTA", [])]
            estado_reg = (corp.estado_entidad_registro or scraped.portal_status or "").strip().lower()
            if estado_reg in est_alertas:
                is_vulnerable = True
                reason = f"VULNERABILIDAD: Sin agente asignado ({estado_reg.title()})"

            if is_theft:
                metrics.total_alertas += 1
            if is_vulnerable:
                metrics.total_warnings = getattr(metrics, 'total_warnings', 0) + 1

        # Detect change vs. previous scan
        prev = (
            ScanResult.query.filter_by(corporation_id=corp.id)
            .order_by(ScanResult.scanned_at.desc())
            .first()
        )
        status_changed = False
        if prev:
            status_changed = (
                prev.officer_name_raw != scraped.officer_name
                or prev.portal_status != scraped.portal_status
            )

        # Delete evidence if it's a clean scan to save storage
        if not is_theft and not scraped.error and scraped.pdf_path:
            import os

            try:
                os.remove(scraped.pdf_path)
                scraped.pdf_path = None
            except OSError:
                pass

        # Save result
        result = ScanResult(
            daily_run_id=run_id,
            corporation_id=corp.id,
            officer_name_raw=scraped.officer_name,
            registered_agent_raw=scraped.registered_agent,
            portal_status=scraped.portal_status,
            alert=is_theft,
            is_vulnerable=is_vulnerable,
            alert_reason=reason,
            status_changed=status_changed,
            pdf_path=scraped.pdf_path,
            error=scraped.error,
            error_message=scraped.error_message,
        )
        db.session.add(result)

        total_processed += 1
        if scraped.error:
            total_errors += 1
        elif is_theft:
            total_alerts += 1
        elif is_vulnerable:
            total_warnings += 1

        run.total_processed = total_processed
        run.total_alerts = total_alerts
        run.total_warnings = total_warnings
        run.total_errors = total_errors

        db.session.commit()

        from app import socketio

        socketio.emit(
            "scan_progress",
            {
                "run_id": run.id,
                "running": True,
                "processed": total_processed,
                "expected": len(corps),
                "alerts": total_alerts,
                "warnings": total_warnings,
                "errors": total_errors,
                "status": run.status,
            },
        )

    # ─── Finalize run ───────────────────────────────────────────────────────────
    run.finished_at = datetime.now(timezone.utc)
    run.total_processed = total_processed
    run.total_alerts = total_alerts
    run.total_warnings = total_warnings
    run.total_errors = total_errors
    run.excluded_status_breakdown = json.dumps(excluded_status_breakdown)

    if not SCAN_CANCEL_FLAGS.get(run_id):
        run.status = "done"

    db.session.commit()
    from app import socketio

    socketio.emit(
        "scan_progress",
        {
            "run_id": run.id,
            "running": False,
            "processed": total_processed,
            "expected": len(corps),
            "alerts": total_alerts,
            "errors": total_errors,
            "status": run.status,
        },
    )

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
        run_id,
        total_processed,
        total_alerts,
        total_errors,
    )


def _upload_run_files(run, app) -> None:
    try:
        from app.services.storage import upload_run

        upload_run(run, app)
    except Exception as exc:
        logger.error("Cloud upload failed: %s", exc)


def _send_email_summary(run_id: int, app) -> None:
    try:
        from app.models import ScanResult
        from app.services.mailer import send_daily_summary

        with app.app_context():
            flagged = ScanResult.query.filter_by(daily_run_id=run_id, alert=True).all()
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
