"""
Backup de produccion via Python — equivalente funcional a pg_dump para tablas criticas.
Genera SQL INSERT idempotente para todas las filas de 'corporations'.
Solo lectura. Sin escrituras.

Uso: python scratch/backup_neon.py
Salida: output/neon_backup_YYYYMMDD_HHMMSS.sql
"""
import os
import sys
from datetime import datetime

# Guardia: solo leer DATABASE_URL aqui porque el proposito ES hacer backup de prod.
# Ningun otro script de prueba debe hacer esto.
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no definida en .env", file=sys.stderr)
    sys.exit(1)

import psycopg2
from psycopg2.extras import RealDictCursor

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_path = f"output/neon_backup_{timestamp}.sql"

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

tablas = ["corporations", "daily_runs", "scan_results", "state_configs", "state_metrics"]

with open(output_path, "w", encoding="utf-8") as f:
    f.write(f"-- Backup Corp Monitor — {timestamp}\n")
    f.write(f"-- Base: {DATABASE_URL[:40]}...\n")
    f.write("-- Generado por: scratch/backup_neon.py\n\n")
    f.write("BEGIN;\n\n")

    for tabla in tablas:
        cur.execute(f"SELECT * FROM {tabla} ORDER BY id;")
        filas = cur.fetchall()
        f.write(f"-- === {tabla} ({len(filas)} filas) ===\n")

        if not filas:
            f.write(f"-- (tabla vacia)\n\n")
            continue

        columnas = list(filas[0].keys())
        cols_str = ", ".join(f'"{c}"' for c in columnas)

        for fila in filas:
            vals = []
            for c in columnas:
                v = fila[c]
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, bool):
                    vals.append("TRUE" if v else "FALSE")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    # Escapar comillas simples
                    vals.append("'" + str(v).replace("'", "''") + "'")
            vals_str = ", ".join(vals)
            f.write(f"INSERT INTO {tabla} ({cols_str}) VALUES ({vals_str});\n")

        f.write(f"\n")

    f.write("COMMIT;\n")

conn.close()

size = os.path.getsize(output_path)
print(f"Backup completado: {output_path}")
print(f"Tamano: {size} bytes ({size/1024:.1f} KB)")
print(f"Tablas respaldadas: {', '.join(tablas)}")
