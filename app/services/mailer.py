"""
app/services/mailer.py

Sends the daily email alert summary via Gmail SMTP (or any SMTP server).

Configuration (from .env / config.py):
  MAIL_SERVER     smtp.gmail.com
  MAIL_PORT       587
  MAIL_USERNAME   your@gmail.com
  MAIL_PASSWORD   app-password-here
  MAIL_FROM       your@gmail.com
  MAIL_RECIPIENTS comma,separated,recipients
"""

from __future__ import annotations

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


# ─── Public API ───────────────────────────────────────────────────────────────

def send_daily_summary(run_id: int, flagged_results: list) -> bool:
    """
    Send a daily summary email.

    Parameters
    ----------
    run_id : int
        The DailyRun ID being reported.
    flagged_results : list[ScanResult]
        All ScanResult objects with alert=True for this run.

    Returns True on success, False on failure.
    """
    try:
        from flask import current_app
        cfg = current_app.config
    except RuntimeError:
        logger.error("No Flask app context for mailer.")
        return False

    recipients = cfg.get("MAIL_RECIPIENTS", [])
    if not recipients or recipients == [""]:
        logger.info("No MAIL_RECIPIENTS configured — skipping email.")
        return False

    username = cfg.get("MAIL_USERNAME", "")
    password = cfg.get("MAIL_PASSWORD", "")
    if not username or not password:
        logger.warning("MAIL_USERNAME or MAIL_PASSWORD not set — skipping email.")
        return False

    from app.models import DailyRun
    run = DailyRun.query.get(run_id)
    if not run:
        logger.error("DailyRun #%d not found for email.", run_id)
        return False

    subject, html_body, text_body = _build_email_content(run, flagged_results)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = cfg.get("MAIL_FROM", username)
    msg["To"]      = ", ".join(recipients)

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html",  "utf-8"))

    try:
        server = cfg.get("MAIL_SERVER", "smtp.gmail.com")
        port   = cfg.get("MAIL_PORT", 587)

        with smtplib.SMTP(server, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(username, password)
            smtp.sendmail(msg["From"], recipients, msg.as_string())

        logger.info("Daily summary email sent to: %s", ", ".join(recipients))
        return True

    except Exception as exc:
        logger.error("Email send failed: %s", exc)
        return False


# ─── Email content builder ────────────────────────────────────────────────────

def _build_email_content(run, flagged_results: list) -> tuple[str, str, str]:
    """Build subject + HTML + plain-text versions of the summary email."""
    run_date  = (run.started_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
    n_flagged = len(flagged_results)
    n_total   = run.total_processed or 0

    subject = (
        f"⚠️ Corporate Monitor Alert — {n_flagged} alerta(s) detectada(s) — {run_date}"
        if n_flagged > 0
        else f"✅ Corporate Monitor — Sin alertas — {run_date}"
    )

    # ── HTML body ────────────────────────────────────────────────────────────
    flagged_rows = ""
    for r in flagged_results:
        corp_name = r.corporation.name if r.corporation else "Unknown"
        state     = r.corporation.state if r.corporation else "?"
        officer   = r.officer_name_raw or "—"
        agent     = r.registered_agent_raw or "—"
        reason    = r.alert_reason or "—"
        pdf_link  = r.cloud_link or (f"file:///{r.pdf_path}" if r.pdf_path else None)
        pdf_cell  = f'<a href="{pdf_link}" style="color:#4F8EF7;">Ver PDF</a>' if pdf_link else "—"

        flagged_rows += f"""
        <tr>
          <td style="padding:8px;border:1px solid #252B3B;color:#F85149;font-weight:bold;">{corp_name}</td>
          <td style="padding:8px;border:1px solid #252B3B;color:#8B949E;">{state}</td>
          <td style="padding:8px;border:1px solid #252B3B;color:#8B949E;">{officer}</td>
          <td style="padding:8px;border:1px solid #252B3B;color:#8B949E;">{agent}</td>
          <td style="padding:8px;border:1px solid #252B3B;color:#D29922;">{reason[:120]}</td>
          <td style="padding:8px;border:1px solid #252B3B;">{pdf_cell}</td>
        </tr>"""

    no_alerts_section = (
        '<p style="color:#3FB950;font-size:16px;">✅ Todas las corporaciones revisadas están en orden. '
        'No se detectaron alertas de robo potencial.</p>'
        if n_flagged == 0 else ""
    )

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="background:#0F1117;color:#E6EDF3;font-family:Arial,sans-serif;padding:24px;">
      <h2 style="color:#E6EDF3;border-bottom:2px solid #252B3B;padding-bottom:8px;">
        🔍 Corporate Cash Credit Monitor — Reporte Diario
      </h2>
      <table style="width:100%;margin-bottom:16px;">
        <tr>
          <td style="color:#4A5366;">Fecha:</td>
          <td style="color:#8B949E;font-weight:bold;">{run_date}</td>
          <td style="color:#4A5366;">Run #:</td>
          <td style="color:#8B949E;">{run.id}</td>
        </tr>
        <tr>
          <td style="color:#4A5366;">Procesadas:</td>
          <td style="color:#8B949E;">{n_total}</td>
          <td style="color:#4A5366;">Alertas:</td>
          <td style="color:{'#F85149' if n_flagged else '#3FB950'};font-weight:bold;">{n_flagged}</td>
        </tr>
      </table>

      {no_alerts_section}

      {'<h3 style="color:#F85149;">⚠️ Corporaciones Flagged (Robo Potencial)</h3>' if n_flagged else ''}

      {f"""
      <table style="width:100%;border-collapse:collapse;background:#161B22;">
        <thead>
          <tr style="background:#252B3B;">
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">Corp Name</th>
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">State</th>
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">Officer</th>
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">Agent</th>
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">Reason</th>
            <th style="padding:10px;border:1px solid #252B3B;color:#E6EDF3;text-align:left;">PDF</th>
          </tr>
        </thead>
        <tbody>{flagged_rows}</tbody>
      </table>
      """ if n_flagged else ""}

      <p style="color:#4A5366;font-size:11px;margin-top:24px;border-top:1px solid #252B3B;padding-top:8px;">
        Corporate Cash Credit Monitor — Automated daily scan. Do not reply to this email.
      </p>
    </body>
    </html>"""

    # ── Plain text fallback ───────────────────────────────────────────────────
    lines = [
        f"Corporate Cash Credit Monitor — {run_date}",
        f"Run #{run.id} | Processed: {n_total} | Alerts: {n_flagged}",
        "",
    ]
    if n_flagged == 0:
        lines.append("No alerts detected. All corporations are in order.")
    else:
        lines.append("FLAGGED CORPORATIONS:")
        for r in flagged_results:
            corp_name = r.corporation.name if r.corporation else "Unknown"
            state     = r.corporation.state if r.corporation else "?"
            lines.append(f"  [{state}] {corp_name}")
            lines.append(f"       Officer: {r.officer_name_raw or '—'}")
            lines.append(f"       Agent:   {r.registered_agent_raw or '—'}")
            lines.append(f"       Reason:  {r.alert_reason or '—'}")
            lines.append("")

    return subject, html, "\n".join(lines)
