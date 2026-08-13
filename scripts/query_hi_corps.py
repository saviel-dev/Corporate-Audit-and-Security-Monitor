import os
import sys
# Guardia de SQLite para scripts locales
os.environ["DATABASE_URL"] = "sqlite:///instance/monitor_dev.db"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Corporation
app = create_app()
with app.app_context():
    print("--- HI CORPS ---")
    corps = Corporation.query.filter_by(state='HI').all()
    for c in corps:
        print(f"[{c.id}] {c.name} | Status: {c.status}")
