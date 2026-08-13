import os
import sys

# Script seguro - usa config de DB para extraer reporte y verificacion
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")
import psycopg2
from psycopg2.extras import RealDictCursor

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor(cursor_factory=RealDictCursor)

print("=== VERIFICACION INDEPENDIENTE (POST-REPARACION) ===")

cur.execute("SELECT status, COUNT(*) as count FROM corporations GROUP BY status ORDER BY status;")
print("1. Status Count:")
for row in cur.fetchall():
    print(f"   - {row['status']}: {row['count']}")

cur.execute("SELECT COUNT(*) as total FROM corporations;")
total = cur.fetchone()['total']
print(f"2. Total Corporations: {total}")

cur.execute("SELECT COUNT(*) as total FROM corporations WHERE source_file = 'test';")
total_test = cur.fetchone()['total']
print(f"3. Filas basura (source_file = 'test'): {total_test}")

print("\n=== REPORTE P3: AUDITORIA DEL INVENTARIO REAL ===")

print("\n1. Corporaciones por estado y con ID de entidad estatal:")
cur.execute("""
    SELECT 
        state, 
        COUNT(*) as total_corps,
        SUM(CASE WHEN corp_id IS NOT NULL AND corp_id != '' THEN 1 ELSE 0 END) as con_corp_id
    FROM corporations
    GROUP BY state
    ORDER BY total_corps DESC;
""")
for row in cur.fetchall():
    print(f"   {row['state']}: {row['total_corps']} corps (Con ID: {row['con_corp_id']})")

print("\n2. Resultados de extraccion por estado (agente NO nulo):")
cur.execute("""
    SELECT 
        c.state, 
        COUNT(s.id) as total_scans,
        SUM(CASE WHEN s.registered_agent_raw IS NOT NULL AND s.registered_agent_raw != '' THEN 1 ELSE 0 END) as con_agente
    FROM scan_results s
    JOIN corporations c ON c.id = s.corporation_id
    GROUP BY c.state
    ORDER BY total_scans DESC;
""")
res = cur.fetchall()
if not res:
    print("   (No hay datos en scan_results)")
for row in res:
    print(f"   {row['state']}: {row['total_scans']} scans (Agente NO nulo: {row['con_agente']})")

conn.close()
