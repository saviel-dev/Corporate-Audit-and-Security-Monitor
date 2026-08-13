import os
import sys
# Guardia de SQLite para scripts locales
os.environ["DATABASE_URL"] = "sqlite:///instance/monitor_dev.db"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import StateMetrics, DailyRun, ScanResult
app = create_app()
with app.app_context():
    print("--- STATE METRICS ---")
    metrics = StateMetrics.query.order_by(StateMetrics.id.desc()).limit(10).all()
    for m in metrics:
        print(f"Run {m.daily_run_id} | {m.estado}: Intentadas={m.total_intentadas}, Extraidas={m.total_extraidas}, No Verificables={m.total_no_verificables}, Tasa={m.tasa_exito:.2f}")

    print("\n--- SCAN RESULTS ---")
    results = ScanResult.query.order_by(ScanResult.id.desc()).limit(20).all()
    for r in results:
        print(f"{r.state} | {r.corp_name} -> {r.raw_agent_name} (Status: {r.portal_status})")
