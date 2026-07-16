"""
app/services/reporter.py

Generates daily report files:
  - Excel (.xlsx) with all scan results for a DailyRun
  - PDF snapshots are handled by BaseScraper._save_pdf()

Excel columns (from process.md §5):
  Corp Name | State | Officer/Agent Names | Status | PDF Link | Date Checked | Notes
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ─── Excel report ─────────────────────────────────────────────────────────────

def generate_excel(run_id: int, output_dir: str = "output/reports") -> str:
    """
    Generate an Excel report for *run_id*.

    Returns the absolute file path of the generated .xlsx file.
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError as e:
        raise RuntimeError("openpyxl not installed. Run: pip install openpyxl") from e

    from app.models import DailyRun, ScanResult, Corporation

    run = DailyRun.query.get(run_id)
    if not run:
        raise ValueError(f"DailyRun #{run_id} not found.")

    results = (
        ScanResult.query
        .filter_by(daily_run_id=run_id)
        .order_by(ScanResult.alert.desc(), ScanResult.scanned_at.asc())
        .all()
    )

    # ── Workbook setup ────────────────────────────────────────────────────────
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Scan Results"

    # ── Color palette (flat / solid, no gradients) ────────────────────────────
    COLOR_HEADER_BG   = "0F1117"   # dark background
    COLOR_HEADER_FG   = "E6EDF3"   # light text
    COLOR_FLAG_BG     = "2A0E0D"   # dark red for flagged rows
    COLOR_FLAG_FG     = "F85149"
    COLOR_CLEAR_BG    = "0E2A14"   # dark green for clear rows
    COLOR_CLEAR_FG    = "3FB950"
    COLOR_ERROR_BG    = "2A1F09"   # dark amber for errors
    COLOR_ERROR_FG    = "D29922"
    COLOR_ALT_BG      = "181C27"   # alternate row
    COLOR_DEFAULT_BG  = "0F1117"

    thin = Side(style="thin", color="252B3B")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def header_cell(cell, value):
        cell.value = value
        cell.font = Font(bold=True, color=COLOR_HEADER_FG, name="Calibri", size=10)
        cell.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    def data_cell(cell, value, fg_color=None, bg_color=None, bold=False, link=None):
        cell.value = value
        cell.font = Font(color=fg_color or "8B949E", name="Calibri", size=9, bold=bold,
                         underline="single" if link else None)
        if bg_color:
            cell.fill = PatternFill("solid", fgColor=bg_color)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
        cell.border = border
        if link and value:
            cell.hyperlink = link

    # ── Header row ────────────────────────────────────────────────────────────
    headers = [
        "Corp Name", "State", "Officer / Agent Names",
        "Status", "PDF Link", "Date Checked", "Notes"
    ]
    ws.row_dimensions[1].height = 32
    for col, h in enumerate(headers, start=1):
        header_cell(ws.cell(row=1, column=col), h)

    # ── Summary sub-header ────────────────────────────────────────────────────
    run_date = run.started_at.strftime("%Y-%m-%d") if run.started_at else "?"
    ws.insert_rows(1)
    summary_text = (
        f"Corporate Cash Credit Monitor  |  Run #{run_id}  |  {run_date}  |  "
        f"Processed: {run.total_processed}  |  Alerts: {run.total_alerts}  |  "
        f"Errors: {run.total_errors}"
    )
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1)
    title_cell.value = summary_text
    title_cell.font = Font(bold=True, color=COLOR_HEADER_FG, name="Calibri", size=11)
    title_cell.fill = PatternFill("solid", fgColor="252B3B")
    title_cell.alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 24

    # ── Data rows ─────────────────────────────────────────────────────────────
    for idx, r in enumerate(results, start=3):
        row = idx
        is_alt = (idx % 2 == 0)

        if r.error:
            bg = COLOR_ERROR_BG
            status_fg = COLOR_ERROR_FG
            status_val = "Error"
        elif r.alert:
            bg = COLOR_FLAG_BG
            status_fg = COLOR_FLAG_FG
            status_val = "Flagged"
        else:
            bg = COLOR_CLEAR_BG if not is_alt else COLOR_ALT_BG
            status_fg = COLOR_CLEAR_FG if not r.error else COLOR_DEFAULT_BG
            status_val = "Clear"

        corp_name  = r.corporation.name if r.corporation else "Unknown"
        state      = r.corporation.state if r.corporation else "?"
        names      = _format_names(r.officer_name_raw, r.registered_agent_raw)
        pdf_link   = r.cloud_link or (f"file:///{r.pdf_path}" if r.pdf_path else None)
        pdf_label  = "Ver PDF" if pdf_link else "—"
        date_str   = r.scanned_at.strftime("%Y-%m-%d %H:%M") if r.scanned_at else "?"
        notes      = r.alert_reason if r.alert else (r.error_message or r.notes or "")

        ws.row_dimensions[row].height = 22
        data_cell(ws.cell(row=row, column=1), corp_name,  fg_color="E6EDF3", bg_color=bg, bold=True)
        data_cell(ws.cell(row=row, column=2), state,      fg_color="8B949E", bg_color=bg)
        data_cell(ws.cell(row=row, column=3), names,      fg_color="8B949E", bg_color=bg)
        data_cell(ws.cell(row=row, column=4), status_val, fg_color=status_fg, bg_color=bg, bold=True)
        data_cell(ws.cell(row=row, column=5), pdf_label,  fg_color="4F8EF7", bg_color=bg, link=pdf_link)
        data_cell(ws.cell(row=row, column=6), date_str,   fg_color="4A5366", bg_color=bg)
        data_cell(ws.cell(row=row, column=7), notes,      fg_color="4A5366", bg_color=bg)

    # ── Column widths ─────────────────────────────────────────────────────────
    widths = [40, 8, 45, 12, 14, 18, 60]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ── Freeze header rows ────────────────────────────────────────────────────
    ws.freeze_panes = "A3"

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(output_dir, exist_ok=True)
    date_tag = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"report_{date_tag}_run{run_id}.xlsx"
    filepath = os.path.join(output_dir, filename)
    wb.save(filepath)
    logger.info("Excel report saved: %s", filepath)
    return filepath


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_names(officer: str | None, agent: str | None) -> str:
    """Format officer + agent names for display in report."""
    parts = []
    if officer:
        parts.append(f"Officer: {officer}")
    if agent:
        parts.append(f"Agent: {agent}")
    return " | ".join(parts) if parts else "—"
