import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

print("Restaurando datos desde output/neon_backup_20260812_162020.sql ...")
with open("output/neon_backup_20260812_162020.sql", "r", encoding="utf-8") as f:
    sql = f.read()

# El backup tiene transacciones (BEGIN;)
try:
    cur.execute(sql)
    conn.commit()
    print("Datos restaurados correctamente.")
except Exception as e:
    conn.rollback()
    print(f"Error restaurando: {e}")
