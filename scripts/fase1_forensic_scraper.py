"""
scripts/fase1_forensic_scraper.py
==================================
Fase 1 - Auditoria Forense
Extrae el historial de las 11 corporaciones vulneradas del portal CO,
descarga PDFs de documentos criticos e inserta en history_events.
"""
from __future__ import annotations
import datetime, logging, os, re, sys, time
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
import pdfplumber
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db_config import obtener_conexion

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Entidades a procesar  (DB_ID | nombre original | Socrata entityid actual)
# pendiente=True => socrata_id aun no confirmado, se salta
# ---------------------------------------------------------------------------
TARGETS = [
    {"db_id": 10969, "nombre": "CYBER SECURITY NETWORK INC",      "socrata_id": "20201828941"},
    {"db_id": 10976, "nombre": "MAJOR BUSINESS MARKETING INC",    "socrata_id": "20201831756"},
    {"db_id": 11000, "nombre": "VIRTUAL COMPUTER SERVICES INC",   "socrata_id": "20201826050"},
    {"db_id": 11015, "nombre": "CSS CYBER SECURITY SYSTEM INC",   "socrata_id": "20201828856"},
    {"db_id": 11017, "nombre": "WEBBOX GLOBAL TECHNOLOGY INC",    "socrata_id": "20201823057"},
    {"db_id": 11389, "nombre": "WEBANGLE TECHNOLOGY SUPPORT INC", "socrata_id": "20201857180"},
    {"db_id": 11408, "nombre": "SEADROP SOFTWARE SOLUTIONS INC",  "socrata_id": "20201857464"},
    {"db_id": 11459, "nombre": "USERLINE DYNAMIC TECHNOLOGY INC", "socrata_id": "20201870386"},
    {"db_id": 11532, "nombre": "EVERPLUS BEAUTY SALON INC",       "socrata_id": "20201867499"},
    {"db_id": 11677, "nombre": "PLUSACT CONSULTING GROUP LLC",    "socrata_id": "20201876839"},
    {"db_id": 11707, "nombre": "EVOLINK VALUE MANAGEMENT LLC",    "socrata_id": "20201875487"},
]

# corp_ids confirmados para UPDATE (solo los no pendientes)
CORP_ID_UPDATES = [
    (10969, "20201828941"),
    (10976, "20201831756"),
    (11015, "20201828856"),
    (11017, "20201823057"),
    (11389, "20201857180"),
    (11408, "20201857464"),
    (11532, "20201867499"),
    (11707, "20201875487"),
    (11000, "20201826050"),
    (11459, "20201870386"),
    (11677, "20201876839"),
]

PDF_DIR      = Path("output/pdfs/forensic")
PAUSE_S      = 10
ENTITY_PAUSE = 15
CRITICAL_KW  = ["statement", "curing", "amended", "change of name", "articles"]


def parse_date(s: str):
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            pass
    return None


def extract_text(pdf_path: Path) -> str:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception as exc:
        log.warning("PDF ilegible %s: %s", pdf_path, exc)
        return ""


def find_firmante(texto: str):
    lines = [l.strip() for l in texto.split("\n") if l.strip()]
    for i, line in enumerate(lines):
        if "LeFever" in line or "Brodie" in line:
            for j in range(1, 8):
                if i + j < len(lines):
                    c = lines[i + j]
                    if "LeFever" not in c and "Brodie" not in c and len(c) > 3:
                        return c
            break
    for i, line in enumerate(lines):
        if "causing document" in line.lower():
            for j in range(1, 5):
                if i + j < len(lines) and len(lines[i + j]) > 3:
                    return lines[i + j]
    return None


def scrape_entity(page, target: dict, conn) -> dict:
    cur = conn.cursor()
    res = {"db_id": target["db_id"], "nombre": target["nombre"],
           "eventos": 0, "pdfs": [], "firmantes": [], "errores": []}

    detail_url = (f"https://www.sos.state.co.us/biz/BusinessEntityDetail.do"
                  f"?quit=true&masterFileId={target['socrata_id']}")
    log.info("[%s] -> %s", target["nombre"], detail_url)
    page.goto(detail_url, wait_until="domcontentloaded")
    time.sleep(2)

    hist_link = page.locator("a", has_text=re.compile(r"filing history", re.IGNORECASE)).first
    if not hist_link.count():
        res["errores"].append("No se encontro link Filing history")
        return res

    log.info("  Abriendo historial (%ds)...", PAUSE_S)
    hist_link.click()
    page.wait_for_load_state("domcontentloaded")
    time.sleep(PAUSE_S)

    cur.execute("DELETE FROM history_events WHERE corporation_id = %s", (target["db_id"],))

    rows = page.locator("table tr").all()
    events = []
    for row in rows:
        tds = row.locator("td").all()
        if len(tds) < 6:
            continue
        ev_type  = tds[1].inner_text().strip().replace("\n", " ")
        date_str = tds[2].inner_text().strip()
        doc_num  = tds[5].inner_text().strip()
        if not ev_type or ev_type.lower().startswith("event"):
            continue
        href = None
        lnk  = tds[1].locator("a")
        if lnk.count():
            href = urljoin(page.url, lnk.first.get_attribute("href"))
        events.append({"ev_type": ev_type[:100], "date": parse_date(date_str),
                       "doc_num": doc_num[:50] if doc_num else None, "href": href})
        log.info("  Evento: %-12s | %s", doc_num, ev_type[:60])

    for ev in events:
        pdf_path_str = None
        firmante     = None
        texto        = None
        is_critical  = any(k in ev["ev_type"].lower() for k in CRITICAL_KW)

        if is_critical and ev["href"] and ev["doc_num"]:
            pdf_file = PDF_DIR / f"{ev['doc_num']}.pdf"
            log.info("  Descargando PDF %s...", ev["doc_num"])
            try:
                with page.expect_download() as dl_info:
                    page.goto(ev["href"])
                dl_info.value.save_as(str(pdf_file))
                pdf_path_str = str(pdf_file)
                res["pdfs"].append(ev["doc_num"])
                texto    = extract_text(pdf_file)
                firmante = find_firmante(texto)
                if firmante:
                    res["firmantes"].append({"doc": ev["doc_num"], "firmante": firmante})
                    log.info("  Firmante: %s", firmante)
                page.go_back()
                page.wait_for_load_state("domcontentloaded")
                time.sleep(3)
            except Exception as exc:
                err = f"PDF {ev['doc_num']}: {exc}"
                res["errores"].append(err)
                log.error("  %s", err)

        try:
            cur.execute(
                """INSERT INTO history_events
                   (corporation_id,event_type,date_filed,document_number,
                    firmante,texto_extraido,pdf_path,pdf_url,created_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW())""",
                (target["db_id"], ev["ev_type"], ev["date"], ev["doc_num"],
                 firmante, texto, pdf_path_str, ev["href"]),
            )
            res["eventos"] += 1
        except Exception as exc:
            res["errores"].append(f"BD {ev['doc_num']}: {exc}")
            log.error("  BD Error: %s", exc)
            conn.rollback()

    return res


def update_corp_ids(conn):
    cur = conn.cursor()
    ok = 0
    for db_id, corp_id in CORP_ID_UPDATES:
        cur.execute("UPDATE corporations SET corp_id=%s WHERE id=%s AND corp_id IS NULL",
                    (corp_id, db_id))
        if cur.rowcount:
            ok += 1
            log.info("  corp_id OK: DB_ID=%d -> %s", db_id, corp_id)
    log.info("corp_ids actualizados: %d / %d", ok, len(CORP_ID_UPDATES))


def main():
    log.info("=" * 60)
    log.info("FASE 1 - AUDITORIA FORENSE CORPORACIONES VULNERADAS")
    log.info("=" * 60)

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    conn      = obtener_conexion("produccion", escritura=True)
    resultados = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False, args=["--disable-blink-features=AutomationControlled"])
        ctx  = browser.new_context(user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"))
        page = ctx.new_page()

        for i, target in enumerate(TARGETS):
            log.info("-" * 50)
            log.info("[%d/%d] %s (DB_ID=%d)", i+1, len(TARGETS), target["nombre"], target["db_id"])

            if target.get("pendiente"):
                log.warning("  PENDIENTE - saltando (socrata_id no confirmado)")
                resultados.append({**target, "status": "PENDIENTE",
                                   "eventos": 0, "firmantes": [], "errores": ["Sin socrata_id"]})
                continue

            try:
                res = scrape_entity(page, target, conn)
                conn.commit()
                res["status"] = "OK" if not res["errores"] else "PARCIAL"
                resultados.append(res)
            except Exception as exc:
                conn.rollback()
                log.error("  ERROR FATAL: %s", exc)
                resultados.append({**target, "status": "ERROR",
                                   "eventos": 0, "firmantes": [], "errores": [str(exc)]})

            if i < len(TARGETS) - 1:
                log.info("  Pausa %ds entre entidades...", ENTITY_PAUSE)
                time.sleep(ENTITY_PAUSE)

        browser.close()

    # --- Paso 2: actualizar corp_ids ---
    log.info("=" * 60)
    log.info("PASO 2 - ACTUALIZACION corp_id")
    update_corp_ids(conn)
    conn.commit()
    conn.close()

    # --- Resumen ---
    log.info("=" * 60)
    log.info("RESUMEN FINAL")
    log.info("=" * 60)
    total_ev  = sum(r.get("eventos", 0) for r in resultados)
    todos_f   = [f for r in resultados for f in r.get("firmantes", [])]
    for r in resultados:
        log.info("  [%-8s] DB=%-5d | %-40s | ev=%d | firm=%d | err=%d",
                 r.get("status","?"), r["db_id"], r["nombre"][:40],
                 r.get("eventos",0), len(r.get("firmantes",[])), len(r.get("errores",[])))
    log.info("Total eventos insertados: %d", total_ev)
    log.info("Firmantes encontrados:")
    for f in todos_f:
        log.info("  Doc %-14s -> %s", f["doc"], f["firmante"])
    log.info("=" * 60)


if __name__ == "__main__":
    main()

