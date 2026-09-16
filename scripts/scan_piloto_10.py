"""
scripts/scan_piloto_10.py

Prueba controlada: escanea exactamente 10 corporaciones de CO del inventario
del cliente. Usa el flujo real (launch_scan_thread) con persistencia en
produccion.

IDs seleccionados:
  No robadas (auditado_robado=False): 10951-10958
  Robadas (auditado_robado=True):     10969, 10976

Uso:
    venv\Scripts\python.exe scripts\scan_piloto_10.py
"""

import os
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cargar .env.neon para que create_app() use la DB de produccion (Neon)
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.neon"), override=True)
print("  [Config] .env.neon cargado. DATABASE_URL apunta a Neon.")

CORP_IDS_PILOTO = [10951, 10952, 10953, 10954, 10955, 10956, 10957, 10958, 10969, 10976]

AGENTES_CRUDOS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scratch", "agentes_crudos.txt"
)


def main():
    from app import create_app, db
    from app.models import Corporation, DailyRun, ScanResult, StateMetrics
    import app.services.scanner as scanner_mod

    app = create_app()

    with app.app_context():
        # 1. Listar las 10 corps y advertir sobre excluidas
        corps = Corporation.query.filter(Corporation.id.in_(CORP_IDS_PILOTO)).all()
        corps_by_id = {c.id: c for c in corps}

        cfg_excluidos = [e.lower() for e in app.config.get("ESTADOS_ENTIDAD_EXCLUIDOS", [])]

        print("\n=== PILOTO: 10 corporaciones seleccionadas ===")
        excluidas_preventivo = []
        for cid in CORP_IDS_PILOTO:
            c = corps_by_id.get(cid)
            if not c:
                print(f"  [FALTA] id={cid} no encontrado en DB")
                continue
            estado_reg = (c.estado_entidad_registro or "").strip().lower()
            excluida = bool(estado_reg and estado_reg in cfg_excluidos)
            if excluida:
                excluidas_preventivo.append(c)
            marca = "[EXCLUIDA]" if excluida else "[  OK   ]"
            print(f"  {marca} id={c.id} | {c.name:<45} | robada={c.auditado_robado} | estado_reg='{c.estado_entidad_registro}'")

        if excluidas_preventivo:
            print(f"\n  ADVERTENCIA: {len(excluidas_preventivo)} corp(s) seran excluidas por estado entidad:")
            for c in excluidas_preventivo:
                print(f"    - {c.name}: '{c.estado_entidad_registro}'")

        # 2. Forzar status=Available para que el scanner no las descarte por status
        estados_originales = {}
        for c in corps:
            estados_originales[c.id] = c.status
            c.status = "Available"
        db.session.commit()
        print(f"\n  Status forzado a 'Available' para {len(corps)} corps.")

        # 3. Monkey-patch: limitar la cola EXACTAMENTE a estos 10 IDs
        def _patched_execute(run_id, app_obj):
            from app import db as _db
            from app.models import Corporation as _Corp, DailyRun as _DR, ScanResult as _SR, StateConfig, StateMetrics as _SM
            from app.services.detector import detect
            import logging as _log
            import datetime as _dt

            _logger = _log.getLogger("scan_piloto")

            run = _db.session.get(_DR, run_id)
            if not run:
                return

            scanner_mod.SCAN_CANCEL_FLAGS[run_id] = False
            run.status = "running"
            _db.session.commit()
            print(f"\n  [Scanner] DailyRun #{run_id} iniciado.")

            cfg = app_obj.config
            pdf_dir = cfg.get("OUTPUT_FOLDER", "output") + "/pdfs"
            timeout_ms = cfg.get("SCRAPER_TIMEOUT", 30_000)
            retries = cfg.get("SCRAPER_RETRIES", 3)
            delay_s = 4.0  # pausa 4s como indicado

            corps_piloto = _Corp.query.filter(_Corp.id.in_(CORP_IDS_PILOTO)).all()

            # Filtrar excluidas por estado de entidad (reportar en vez de silenciar)
            est_excluidos = [e.lower() for e in cfg.get("ESTADOS_ENTIDAD_EXCLUIDOS", [])]
            corps_cola = []
            for c in corps_piloto:
                er = (c.estado_entidad_registro or "").strip().lower()
                if er and er in est_excluidos:
                    print(f"  [EXCLUIDA] {c.name}: estado '{c.estado_entidad_registro}' en ESTADOS_ENTIDAD_EXCLUIDOS")
                    continue
                corps_cola.append(c)

            print(f"  [Scanner] Cola: {len(corps_cola)} corps a escanear.\n")

            total_processed = 0
            total_alerts = 0
            total_warnings = 0
            total_errors = 0
            state_metrics_map = {}

            for corp in corps_cola:
                if scanner_mod.SCAN_CANCEL_FLAGS.get(run_id):
                    run.status = "cancelled"
                    break

                scraper = scanner_mod.get_scraper(
                    corp.state, output_dir=pdf_dir,
                    timeout_ms=timeout_ms, retries=retries, delay_s=delay_s,
                )
                if not scraper:
                    print(f"  [SKIP] Sin scraper para estado '{corp.state}'")
                    continue

                if corp.state not in state_metrics_map:
                    m = _SM(daily_run_id=run_id, estado=corp.state,
                            total_intentadas=0, total_extraidas=0,
                            total_no_verificables=0, total_alertas=0,
                            total_bloqueos_waf=0)
                    _db.session.add(m)
                    state_metrics_map[corp.state] = m
                metrics = state_metrics_map[corp.state]

                # Circuit breaker
                sc = StateConfig.query.filter_by(state_code=corp.state).first()
                if sc and sc.waf_blocked_until:
                    if _dt.datetime.now(_dt.timezone.utc) < sc.waf_blocked_until.replace(tzinfo=_dt.timezone.utc):
                        print(f"  [WAF COOLDOWN] {corp.name}: saltado")
                        continue

                print(f"  Escaneando: {corp.name}...")
                scraped = scraper.scrape(corp.name, save_pdf=True)
                metrics.total_intentadas += 1

                # Rama ERROR
                if scraped.error:
                    result = _SR(
                        daily_run_id=run_id, corporation_id=corp.id,
                        officer_name_raw=None, registered_agent_raw=None,
                        portal_status=None, alert=False, is_vulnerable=False,
                        alert_reason=None, status_changed=False, pdf_path=None,
                        error=True, error_message=scraped.error_message,
                    )
                    _db.session.add(result)
                    total_processed += 1
                    total_errors += 1
                    run.total_processed = total_processed
                    run.total_errors = total_errors
                    _db.session.commit()
                    print(f"    ERROR: {scraped.error_message}")
                    continue

                # Rama EXITO
                metrics.total_extraidas += 1

                dic_agentes = cfg.get("AGENTE_ESPERADO_POR_ESTADO", {})
                expected_agent = dic_agentes.get(corp.state, "Marcio Andrade")
                campos_esp = cfg.get("CAMPOS_ESPERADOS_POR_ESTADO", {}).get(corp.state)

                result_detect = detect(
                    scraped.officer_name, scraped.registered_agent,
                    expected_agent=expected_agent, campos_esperados=campos_esp,
                )
                is_theft = result_detect.is_theft
                reason = result_detect.reason

                # No verificable
                if not result_detect.is_verifiable:
                    metrics.total_no_verificables += 1
                    result = _SR(
                        daily_run_id=run_id, corporation_id=corp.id,
                        officer_name_raw=scraped.officer_name,
                        registered_agent_raw=scraped.registered_agent,
                        portal_status=scraped.portal_status,
                        alert=False, is_vulnerable=False, alert_reason=None,
                        status_changed=False, pdf_path=scraped.pdf_path,
                        error=True, error_message=reason,
                    )
                    _db.session.add(result)
                    total_processed += 1
                    total_errors += 1
                    run.total_processed = total_processed
                    run.total_errors = total_errors
                    _db.session.commit()
                    print(f"    NO VERIFICABLE: {reason}")
                    continue

                # Vulnerabilidad
                is_vulnerable = False
                est_alertas = [e.lower() for e in cfg.get("ESTADOS_ENTIDAD_ALERTA", [])]
                er = (corp.estado_entidad_registro or scraped.portal_status or "").strip().lower()
                if er in est_alertas:
                    is_vulnerable = True
                    reason = f"VULNERABILIDAD: Sin agente asignado ({er.title()})"

                if is_theft:
                    metrics.total_alertas += 1
                if is_vulnerable:
                    metrics.total_warnings = getattr(metrics, 'total_warnings', 0) + 1

                # Cambio vs scan anterior
                prev = _SR.query.filter_by(corporation_id=corp.id).order_by(_SR.scanned_at.desc()).first()
                status_changed = bool(prev and prev.alert != is_theft)

                result = _SR(
                    daily_run_id=run_id, corporation_id=corp.id,
                    officer_name_raw=scraped.officer_name,
                    registered_agent_raw=scraped.registered_agent,
                    portal_status=scraped.portal_status,
                    alert=is_theft, is_vulnerable=is_vulnerable,
                    alert_reason=reason if (is_theft or is_vulnerable) else None,
                    status_changed=status_changed, pdf_path=scraped.pdf_path,
                    error=False, error_message=None,
                )
                _db.session.add(result)
                total_processed += 1
                if is_theft:
                    total_alerts += 1
                if is_vulnerable:
                    total_warnings += 1

                run.total_processed = total_processed
                run.total_alerts = total_alerts
                run.total_warnings = total_warnings
                run.total_errors = total_errors
                _db.session.commit()

                estado_detector = "ALERTA" if is_theft else ("VULNERABILIDAD" if is_vulnerable else "LIMPIO")
                print(f"    agente='{scraped.registered_agent}' | detector={estado_detector}")

            run.status = "completed"
            run.finished_at = _dt.datetime.now(_dt.timezone.utc)
            _db.session.commit()
            print(f"\n  [Scanner] DailyRun #{run_id} completado.")

        scanner_mod._execute_scan = _patched_execute

        # 4. Crear DailyRun y lanzar
        run = DailyRun(
            status="pending",
            started_at=datetime.datetime.now(datetime.timezone.utc),
            triggered_by="manual_pilot_10",
        )
        db.session.add(run)
        db.session.commit()
        run_id = run.id
        print(f"\n  DailyRun.id = {run_id}  <--- ANOTAR PARA ROLLBACK SI NECESARIO")
        print(f"  Inicio      = {run.started_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("\n  Lanzando escaneo real (hilo bloqueante)...\n")

        t_inicio = time.time()
        from app.services.scanner import launch_scan_thread
        hilo = launch_scan_thread(run_id, app)
        hilo.join()
        t_total = time.time() - t_inicio

        # 5. Restaurar status originales
        for c in corps:
            c.status = estados_originales[c.id]
        db.session.commit()
        print("  Status de las 10 corps restaurado al original.")

        # 6. Leer resultados y generar reporte
        results = ScanResult.query.filter_by(daily_run_id=run_id).all()
        results_by_corp = {r.corporation_id: r for r in results}

        sm = StateMetrics.query.filter_by(daily_run_id=run_id, estado="CO").first()

        print("\n" + "=" * 72)
        print(f"REPORTE PILOTO — DailyRun #{run_id}")
        print("=" * 72)

        lineas_agentes = []
        falsos_negativos = []
        falsos_positivos = []

        for cid in CORP_IDS_PILOTO:
            corp = corps_by_id.get(cid)
            res = results_by_corp.get(cid)

            if not corp:
                print(f"\n  [{cid}] CORP NO ENCONTRADA")
                continue

            if not res:
                er = (corp.estado_entidad_registro or "").strip().lower()
                if er in cfg_excluidos:
                    motivo = f"EXCLUIDA — estado '{corp.estado_entidad_registro}' en lista de excluidos"
                else:
                    motivo = "SIN RESULTADO — revisar logs"
                print(f"\n  [{cid}] {corp.name}")
                print(f"    resultado: {motivo}")
                lineas_agentes.append(f"CO | (no escaneada) | {corp.name}")
                continue

            # Clasificar resultado
            if res.error:
                em = res.error_message or ""
                if "sin verificar" in em.lower():
                    estado_scan = "NO VERIFICABLE"
                else:
                    estado_scan = f"ERROR"
            elif res.alert:
                estado_scan = "ALERTA"
            elif res.is_vulnerable:
                estado_scan = "VULNERABILIDAD"
            else:
                estado_scan = "LIMPIO"

            robada_str = "ROBADA (cliente)" if corp.auditado_robado else "limpia (cliente)"
            agente = res.registered_agent_raw or "(sin agente)"
            portal_status = res.portal_status or "(no disponible)"

            print(f"\n  [{cid}] {corp.name}")
            print(f"    auditado_robado : {robada_str}")
            print(f"    estado_portal   : {portal_status}")
            print(f"    agente_crudo    : {agente}")
            print(f"    oficial_crudo   : {res.officer_name_raw or '(vacio - no_publicado)'}")
            print(f"    detector        : {estado_scan}")
            if res.alert_reason:
                print(f"    motivo          : {res.alert_reason}")
            if res.error_message and res.error:
                print(f"    error_message   : {res.error_message}")

            # Alertas de discrepancia
            if corp.auditado_robado and not res.alert and not res.error:
                print(f"    *** FALSO NEGATIVO: cliente ROBADA, detector LIMPIO ***")
                falsos_negativos.append(corp.name)
            if corp.auditado_robado is False and res.alert:
                print(f"    *** POSIBLE FALSO POSITIVO: cliente LIMPIA, detector ALERTA ***")
                falsos_positivos.append(corp.name)

            lineas_agentes.append(f"CO | {agente}")

        print("\n" + "-" * 72)
        print("StateMetrics CO:")
        if sm:
            print(f"  total_intentadas      : {sm.total_intentadas}")
            print(f"  total_extraidas       : {sm.total_extraidas}")
            print(f"  total_alertas         : {sm.total_alertas}")
            print(f"  total_no_verificables : {sm.total_no_verificables}")
            tasa = (sm.total_extraidas / sm.total_intentadas * 100) if sm.total_intentadas else 0
            print(f"  tasa_extraccion       : {tasa:.0f}%")
        else:
            print("  (sin StateMetrics)")

        print(f"\n  Tiempo total   : {t_total:.1f}s ({t_total/60:.1f} min)")
        print(f"  DailyRun.id    : {run_id}  <--- ANOTAR PARA ROLLBACK")

        if falsos_negativos:
            print(f"\n  FALSOS NEGATIVOS ({len(falsos_negativos)}): {falsos_negativos}")
        if falsos_positivos:
            print(f"\n  FALSOS POSITIVOS ({len(falsos_positivos)}): {falsos_positivos}")

        print("=" * 72)

        # 7. Guardar agentes crudos
        os.makedirs(os.path.dirname(AGENTES_CRUDOS_PATH), exist_ok=True)
        with open(AGENTES_CRUDOS_PATH, "w", encoding="utf-8") as f:
            f.write(f"# Piloto 10 corps CO — DailyRun #{run_id}\n")
            f.write(f"# {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            for linea in lineas_agentes:
                f.write(linea + "\n")
        print(f"\nAgentes crudos guardados en: {AGENTES_CRUDOS_PATH}")

        # Alerta de parada si CYBER SECURITY sale limpia
        if "CYBER SECURITY NETWORK INC" in falsos_negativos:
            print("\n" + "!" * 72)
            print("STOP — CYBER SECURITY NETWORK INC salio LIMPIA pero el cliente la")
            print("confirmó como ROBADA. Falso negativo critico. No continuar con mas")
            print("escaneos hasta entender la causa.")
            print("!" * 72)


if __name__ == "__main__":
    main()


