"""
Migracion manual: agrega las columnas nuevas del inventario Excel al modelo Corporation.

Uso:
    python scripts/migrar_columnas_inventario.py

Requiere DATABASE_URL en el entorno (.env).
Verifica primero si la columna ya existe antes de crearla (idempotente).
Funciona en SQLite (local) y PostgreSQL (Neon).
"""
import os
import sys
from pathlib import Path

# Permite importar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_config import obtener_url_conexion

import sqlalchemy as sa
from sqlalchemy import inspect, text

DATABASE_URL = obtener_url_conexion("produccion")
if not DATABASE_URL:
    print("[ERROR] DATABASE_URL no esta definida en el entorno.", file=sys.stderr)
    sys.exit(1)

# SQLite no admite NUMERIC(12,2) directamente con esa sintaxis en ALTER TABLE;
# usamos REAL para SQLite y NUMERIC(12,2) para Postgres
es_sqlite = DATABASE_URL.startswith("sqlite")

engine = sa.create_engine(DATABASE_URL)

# Columnas nuevas: (nombre, definicion_postgres, definicion_sqlite)
COLUMNAS_NUEVAS = [
    ("auditado_robado",    "BOOLEAN",        "INTEGER"),        # NULL/0/1 en SQLite
    ("url_prueba",         "TEXT",           "TEXT"),
    ("nota",               "TEXT",           "TEXT"),
    ("age_raw",            "VARCHAR(64)",    "VARCHAR(64)"),
    ("precio_cliente",     "NUMERIC(12,2)",  "REAL"),
    ("numero_registro_sf", "VARCHAR(128)",   "VARCHAR(128)"),
    ("fecha_constitucion_sf", "DATE",        "DATE"),
    ("fuente_importacion", "VARCHAR(64)",    "VARCHAR(64)"),
    ("fecha_importacion",  "TIMESTAMP",      "TIMESTAMP"),
]

TABLA = "corporations"


def obtener_columnas_existentes(conn) -> set:
    """Devuelve el conjunto de nombres de columnas actuales de la tabla."""
    insp = inspect(conn)
    return {c["name"] for c in insp.get_columns(TABLA)}


def migrar() -> None:
    print(f"Conectando a: {DATABASE_URL[:40]}...")
    with engine.begin() as conn:
        columnas_existentes = obtener_columnas_existentes(conn)
        print(f"Columnas actuales en '{TABLA}': {len(columnas_existentes)}")

        aniadidas = 0
        omitidas = 0
        for nombre, def_pg, def_sqlite in COLUMNAS_NUEVAS:
            if nombre in columnas_existentes:
                print(f"  [OMITIR] {nombre} — ya existe")
                omitidas += 1
                continue

            tipo = def_sqlite if es_sqlite else def_pg
            sql = f"ALTER TABLE {TABLA} ADD COLUMN {nombre} {tipo}"
            print(f"  [ADD]    {nombre} {tipo}")
            conn.execute(text(sql))
            aniadidas += 1

        print(f"\nResultado: {aniadidas} columnas añadidas, {omitidas} ya existian.")
        if aniadidas > 0:
            print("Migracion completada. Verifica con: SELECT * FROM corporations LIMIT 1;")
        else:
            print("Nada que migrar — base de datos ya actualizada.")


if __name__ == "__main__":
    migrar()
