"""
Flask routes for Corporate Cash Credit Monitor.

Blueprint: main_bp
  GET  /                  → Dashboard
  GET  /upload            → CSV upload form (corporations)
  POST /upload            → Process corporations CSV
  GET  /states            → State portal configurations
  POST /states/import     → Import state-URL CSV (tab-separated)
  POST /states/<code>/delete → Remove a state config
  GET  /runs              → Daily run history
  GET  /runs/<id>         → Detail of a single run
  POST /scan/manual       → Trigger a manual scan
  GET  /api/stats         → JSON stats
"""

import os
import csv
from datetime import datetime, timezone

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, flash, jsonify, current_app, send_from_directory, session, make_response
)
from flask_babel import gettext as _
import os
from werkzeug.utils import secure_filename

from app import db
from app.models import Corporation, DailyRun, ScanResult, StateConfig, STATE_ABBR

main_bp = Blueprint("main", __name__)


# ─────────────────────────────────────────────────────────────────────────────
# Authentication Hook
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.before_request
def require_login():
    # Only endpoints in 'main' that need protection, plus allow static
    allowed_endpoints = ["main.login", "static"]
    if request.endpoint not in allowed_endpoints and not session.get("logged_in"):
        return redirect(url_for("main.login"))


@main_bp.after_request
def set_default_language(response):
    """If no lang cookie exists, set it to English (the app default)."""
    if not request.cookies.get('lang'):
        response.set_cookie('lang', 'en', max_age=60 * 60 * 24 * 365)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Auth Routes
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/login", methods=["GET", "POST"])
def login():
    # If already logged in, skip the login page and loader entirely
    if request.method == "GET" and session.get("logged_in"):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        # Handle AJAX login for the loader effect
        if request.is_json:
            data = request.get_json()
            username = data.get("username", "").strip()
            password = data.get("password", "")
            
            if username == "admin" and password == current_app.config.get("ADMIN_PASSWORD", "admin123"):
                session.permanent = True
                session["logged_in"] = True
                return jsonify({"success": True})
            else:
                return jsonify({"success": False, "message": str(_("Usuario o contraseña incorrectos."))}), 401

        # Fallback for standard form submission
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if username == "admin" and password == current_app.config.get("ADMIN_PASSWORD", "admin123"):
            session.permanent = True
            session["logged_in"] = True
            flash(_("Sesión iniciada correctamente."), "success")
            return redirect(url_for("main.dashboard"))
        else:
            flash(_("Usuario o contraseña incorrectos."), "error")

    return render_template("login.html")


@main_bp.route("/logout")
def logout():
    session.clear()
    flash(_("Has cerrado sesión."), "info")
    return redirect(url_for("main.login"))


@main_bp.route("/set_language/<lang>")
def set_language(lang):
    if lang not in ['es', 'en']:
        lang = 'es'
    response = make_response(redirect(request.referrer or url_for('main.dashboard')))
    response.set_cookie('lang', lang, max_age=60*60*24*365)
    return response


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def allowed_file(filename: str) -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def parse_date(value: str):
    """Try multiple date formats, return date or None."""
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/")
def dashboard():
    total_corps = Corporation.query.count()
    pending = Corporation.query.filter(
        Corporation.status.ilike("disponible")
    ).count()

    last_run = DailyRun.query.order_by(DailyRun.started_at.desc()).first()
    
    clean_count = 0
    alert_count = 0
    if last_run:
        alert_count = last_run.total_alerts
        clean_count = last_run.total_processed - alert_count

    # Recent alerts
    recent_alerts = (
        ScanResult.query
        .filter_by(alert=True)
        .order_by(ScanResult.scanned_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "index.html",
        total_corps=total_corps,
        pending=pending,
        clean_count=clean_count,
        alert_count=alert_count,
        last_run=last_run,
        recent_alerts=recent_alerts,
    )


@main_bp.route("/corporations")
def corporations_list():
    page = request.args.get("page", 1, type=int)
    state_filter = request.args.get("state", "")
    status_filter = request.args.get("status", "")

    query = Corporation.query
    if state_filter:
        query = query.filter_by(state=state_filter.upper())
    if status_filter:
        query = query.filter(Corporation.status.ilike(f"%{status_filter}%"))

    corporations = query.order_by(
        Corporation.priority.desc(),
        Corporation.date_registered.asc()
    ).paginate(page=page, per_page=25, error_out=False)

    return render_template(
        "corporations.html",
        corporations=corporations,
        state_filter=state_filter,
        status_filter=status_filter,
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSV Upload
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/upload", methods=["GET"])
def upload_form():
    return render_template("upload.html")


@main_bp.route("/upload", methods=["POST"])
def upload_csv():
    if "file" not in request.files:
        flash(_("No se seleccionó ningún archivo."), "error")
        return redirect(url_for("main.upload_form"))

    file = request.files["file"]

    if file.filename == "":
        flash(_("El archivo no tiene nombre."), "error")
        return redirect(url_for("main.upload_form"))

    if not allowed_file(file.filename):
        flash(_("Solo se permiten archivos CSV (.csv)."), "error")
        return redirect(url_for("main.upload_form"))

    filename = secure_filename(file.filename)
    upload_path = os.path.join(current_app.config["UPLOAD_FOLDER"], filename)
    file.save(upload_path)

    inserted = 0
    skipped = 0
    errors = []

    try:
        with open(upload_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            reader.fieldnames = [h.strip().lower().replace(" ", "_")
                                  for h in (reader.fieldnames or [])]

            for i, row in enumerate(reader, start=2):
                try:
                    name = (row.get("name") or row.get("corporation_name") or
                            row.get("company_name") or row.get("nombre") or 
                            row.get("corporation") or "").strip()
                    raw_state = (row.get("state") or row.get("estado") or "").strip()
                    # Accept full name ("Hawaii") or abbreviation ("HI")
                    if len(raw_state) > 2:
                        state = STATE_ABBR.get(raw_state.title(), raw_state.upper()[:2])
                    else:
                        state = raw_state.upper()

                    if not name or not state:
                        skipped += 1
                        continue

                    status = (row.get("status") or row.get("estatus") or
                              row.get("estado_venta") or "Disponible").strip()
                    corp_id = (row.get("corp_id") or row.get("registry_id") or
                               row.get("id") or "").strip() or None
                    date_str = (row.get("date_registered") or
                                row.get("fecha_registro") or "").strip()
                    registered = parse_date(date_str) if date_str else None
                    priority = int(row.get("priority") or row.get("prioridad") or 0)
                    req1 = (row.get("required_term_1") or row.get("termino_1") or "").strip() or None
                    req2 = (row.get("required_term_2") or row.get("termino_2") or "").strip() or None

                    corp = None
                    if corp_id:
                        corp = Corporation.query.filter_by(corp_id=corp_id).first()
                    if not corp:
                        corp = Corporation.query.filter_by(name=name, state=state).first()

                    if corp:
                        corp.status = status
                        corp.priority = priority
                        corp.date_registered = registered
                        corp.required_term_1 = req1
                        corp.required_term_2 = req2
                        corp.source_file = filename
                    else:
                        corp = Corporation(
                            name=name, state=state, corp_id=corp_id,
                            status=status, priority=priority,
                            date_registered=registered,
                            required_term_1=req1, required_term_2=req2,
                            source_file=filename,
                        )
                        db.session.add(corp)
                        inserted += 1

                except Exception as row_err:
                    errors.append(f"Fila {i}: {row_err}")
                    continue

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(_("Error al procesar el archivo: %(e)s", e=e), "error")
        return redirect(url_for("main.upload_form"))

    summary = f"Importación completada: {inserted} nuevas, {skipped} omitidas."
    if errors:
        summary += f" {len(errors)} error(es) de fila."
        for err in errors[:5]:
            flash(err, "warning")

    flash(summary, "success")
    return redirect(url_for("main.dashboard"))


# ─────────────────────────────────────────────────────────────────────────────
# Daily Runs
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/runs")
def runs_list():
    runs = DailyRun.query.order_by(DailyRun.started_at.desc()).paginate(
        page=request.args.get("page", 1, type=int), per_page=20, error_out=False
    )
    return render_template("runs.html", runs=runs)


@main_bp.route("/runs/<int:run_id>")
def run_detail(run_id):
    run = DailyRun.query.get_or_404(run_id)
    results = (
        ScanResult.query
        .filter_by(daily_run_id=run_id)
        .order_by(ScanResult.alert.desc(), ScanResult.scanned_at.asc())
        .all()
    )
    return render_template("run_detail.html", run=run, results=results)


@main_bp.route("/reports")
def reports():
    runs = DailyRun.query.filter(DailyRun.report_excel_path.isnot(None)).order_by(DailyRun.started_at.desc()).all()
    return render_template("reports.html", runs=runs)


@main_bp.route("/reports/generate")
def generate_report():
    import io
    import openpyxl
    from flask import Response, send_file
    
    state = request.args.get("state", "").strip()
    start_date_str = request.args.get("start_date", "").strip()
    end_date_str = request.args.get("end_date", "").strip()
    fmt = request.args.get("format", "xlsx").strip()

    # Parse dates
    start_date = None
    end_date = None
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        if end_date_str:
            end_date = datetime.strptime(end_date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except ValueError as e:
        flash(_("Formato de fecha inválido: %(e)s", e=e), "error")
        return redirect(url_for("main.reports"))

    # Query scan results
    query = db.session.query(ScanResult).join(Corporation)
    if state:
        query = query.filter(Corporation.state == state.upper())
    if start_date:
        query = query.filter(ScanResult.scanned_at >= start_date)
    if end_date:
        query = query.filter(ScanResult.scanned_at <= end_date)
    
    results = query.order_by(ScanResult.scanned_at.desc()).all()

    if not results:
        flash(_("No se encontraron registros para los filtros seleccionados."), "warning")
        return redirect(url_for("main.reports"))

    # Generate format
    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ID Registro", "Corporación", "Estado", "Oficial Oficial", "Agente Registrado", "Estatus Portal", "Alerta", "Fecha Escaneo"])
        for r in results:
            writer.writerow([
                r.id,
                r.corporation.name,
                r.corporation.state,
                r.officer_name_raw or "",
                r.registered_agent_raw or "",
                r.portal_status or "",
                "SÍ" if r.alert else "NO",
                r.scanned_at.strftime("%d/%m/%Y %H:%M")
            ])
        output.seek(0)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=reporte_corporaciones.csv"}
        )
    elif fmt == "pdf":
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        return render_template(
            "reports_print.html",
            results=results,
            state=state,
            start_date=start_date_str,
            end_date=end_date_str,
            now=now_str
        )
    else:
        # Excel format using openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reporte de Escaneo"
        
        # Headers
        headers = ["ID Registro", "Corporación", "Estado", "Oficial Oficial", "Agente Registrado", "Estatus Portal", "Alerta", "Fecha Escaneo"]
        ws.append(headers)
        
        # Styling headers
        for col_num, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_num)
            cell.font = openpyxl.styles.Font(bold=True)
            
        for r in results:
            ws.append([
                r.id,
                r.corporation.name,
                r.corporation.state,
                r.officer_name_raw or "",
                r.registered_agent_raw or "",
                r.portal_status or "",
                "SÍ" if r.alert else "NO",
                r.scanned_at.strftime("%d/%m/%Y %H:%M")
            ])
            
        file_stream = io.BytesIO()
        wb.save(file_stream)
        file_stream.seek(0)
        
        return send_file(
            file_stream,
            as_attachment=True,
            download_name="reporte_corporaciones.xlsx",
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Manual Scan (placeholder — wired in Phase 2)
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/scan/manual", methods=["POST"])
def manual_scan():
    """Trigger a real scan in a background thread."""
    from app.services.scanner import launch_scan_thread

    run = DailyRun(triggered_by="manual", status="running")
    db.session.add(run)
    db.session.commit()

    # Launch real scan in background thread
    launch_scan_thread(run.id, current_app._get_current_object())

    flash(
        f"Escaneo iniciado — Run #{run.id}. "
        f"Los resultados aparecerán en Ejecuciones en unos minutos.",
        "success"
    )
    return redirect(url_for("main.runs_list"))


# ─────────────────────────────────────────────────────────────────────────────
# JSON API
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/api/scan_status")
def scan_status():
    last_run = DailyRun.query.order_by(DailyRun.started_at.desc()).first()
    if not last_run:
        return jsonify({"running": False})
    
    # Estimate total expected based on currently available corps
    # If the scanner is currently running Pipeline A (discovery), total_expected will grow,
    # but that's fine for a progress bar, it just adjusts.
    total_expected = Corporation.query.filter(
        ~Corporation.status.ilike("%vendida%")
    ).count()
    
    return jsonify({
        "running": last_run.status == "running",
        "processed": last_run.total_processed,
        "expected": total_expected,
        "status": last_run.status
    })


@main_bp.route("/api/stats")
def api_stats():
    total = Corporation.query.count()
    available = Corporation.query.filter(Corporation.status.ilike("disponible")).count()
    sold = Corporation.query.filter(Corporation.status.ilike("vendida")).count()
    last_run = DailyRun.query.order_by(DailyRun.started_at.desc()).first()
    alerts_today = 0
    if last_run:
        alerts_today = ScanResult.query.filter_by(
            daily_run_id=last_run.id, alert=True
        ).count()

    return jsonify({
        "total_corporations": total,
        "available": available,
        "sold": sold,
        "alerts_today": alerts_today,
        "last_run": last_run.started_at.isoformat() if last_run else None,
        "last_run_status": last_run.status if last_run else None,
    })


# ─────────────────────────────────────────────────────────────────────────────
# State Portal Configuration
# ─────────────────────────────────────────────────────────────────────────────

@main_bp.route("/states")
def states_list():
    """Show all configured state portals."""
    states = StateConfig.query.order_by(StateConfig.state_name).all()
    return render_template("states.html", states=states)


@main_bp.route("/states/import", methods=["POST"])
def states_import():
    """
    Import CSV with columns: State, Business Search URL
    Accepts tab-separated or comma-separated.
    Handles header rows automatically (State / Business Search URL).
    """
    import io

    if "file" not in request.files:
        flash(_("No se seleccionó ningún archivo."), "error")
        return redirect(url_for("main.states_list"))

    file = request.files["file"]
    if file.filename == "":
        flash(_("Nombre de archivo vacío."), "error")
        return redirect(url_for("main.states_list"))

    inserted = 0
    updated = 0
    skipped = 0
    errors = []

    try:
        content = file.read().decode("utf-8-sig")

        # Detect delimiter (tab vs comma)
        first_line = content.splitlines()[0] if content.strip() else ""
        delimiter = "\t" if "\t" in first_line else ","

        # Check if first line is a header
        has_header = "state" in first_line.lower() or "estado" in first_line.lower()

        if has_header:
            reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
            # Normalize column names
            if reader.fieldnames:
                reader.fieldnames = [
                    h.strip().lower().replace(" ", "_") for h in reader.fieldnames
                ]
        else:
            # No header, assume State \t URL
            reader = csv.DictReader(
                io.StringIO(content), 
                delimiter=delimiter, 
                fieldnames=["state", "business_search_url"]
            )

        for i, row in enumerate(reader, start=1 if not has_header else 2):
            # Accept both "state" and "business_search_url"
            state_raw  = (row.get("state") or "").strip()
            url_raw    = (row.get("business_search_url") or
                          row.get("url") or
                          row.get("search_url") or "").strip().strip('"')

            if not state_raw or not url_raw:
                skipped += 1
                continue

            state_name = state_raw.title()

            # Resolve to 2-letter abbreviation
            state_code = STATE_ABBR.get(state_name)
            if not state_code:
                errors.append(f"Línea {i}: estado desconocido — '{state_name}'")
                skipped += 1
                continue

            existing = StateConfig.query.filter_by(state_code=state_code).first()
            if existing:
                existing.search_url = url_raw
                existing.state_name = state_name
                updated += 1
            else:
                db.session.add(StateConfig(
                    state_name=state_name,
                    state_code=state_code,
                    search_url=url_raw,
                    scraper_supported=state_code in ("HI", "CO"),
                ))
                inserted += 1

        db.session.commit()

    except Exception as e:
        db.session.rollback()
        flash(_("Error procesando archivo: %(e)s", e=e), "error")
        return redirect(url_for("main.states_list"))

    msg = f"Estados importados: {inserted} nuevos, {updated} actualizados, {skipped} omitidos."
    if errors:
        msg += f" {len(errors)} error(es)."
        for err in errors[:5]:
            flash(err, "warning")
    flash(msg, "success")
    return redirect(url_for("main.states_list"))




@main_bp.route("/states/<string:code>/toggle", methods=["POST"])
def state_toggle(code):
    """Enable / disable a state portal."""
    sc = StateConfig.query.filter_by(state_code=code.upper()).first_or_404()
    sc.active = not sc.active
    db.session.commit()
    status = "activado" if sc.active else "desactivado"
    flash(_("%(state)s %(status)s.", state=sc.state_name, status=status), "success")
    return redirect(url_for("main.states_list"))


@main_bp.route("/output/<path:filename>")
def download_output(filename):
    """Serve output files (reports and pdfs)."""
    # Clean up absolute paths that might be stored in the DB
    filename = filename.replace("\\", "/")
    if "output/" in filename:
        filename = filename.split("output/")[-1]
        
    if filename.lower().endswith('.pdf'):
        if not filename.startswith("pdfs/"):
            filename = f"pdfs/{os.path.basename(filename)}"
        return send_from_directory(current_app.config["OUTPUT_FOLDER"], filename, mimetype='application/pdf')
        
    # For Excel reports, send as attachment
    if not filename.startswith("reports/"):
        filename = f"reports/{os.path.basename(filename)}"
    return send_from_directory(current_app.config["OUTPUT_FOLDER"], filename, as_attachment=True)
