import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()
DB_URL = os.environ.get("DATABASE_URL")
print(DB_URL)
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
tables = cur.fetchall()
print(f"Tables: {tables}")

for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t[0]};")
    print(f"Table {t[0]} has {cur.fetchone()[0]} rows.")
