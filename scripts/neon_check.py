import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app import create_app, db
from app.models import Corporation, ScanResult, DailyRun

app = create_app()
with app.app_context():
    print(f"[{'='*20}]")
    print(f"DATABASE CONNECTED: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"[{'='*20}]\n")
    
    # Conteo
    count_null = Corporation.query.filter(
        (Corporation.corp_id == None) | (Corporation.corp_id == '')
    ).count()
    print(f"CONTEO PREVIO: {count_null} corporaciones con corp_id NULL en Neon.")
    
    # Backup
    import datetime
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"output/neon_backup_{timestamp}.sql"
    
    with open(backup_file, "w", encoding="utf-8") as f:
        f.write("-- BACKUP MANUAL POR SQLALCHEMY\n\n")
        
        # Corporation
        for c in Corporation.query.all():
            vals = (c.id, c.name, c.state, c.status, c.source_file, c.corp_id, c.date_registered, c.priority, c.created_at, c.updated_at)
            f.write(f"INSERT INTO corporations VALUES {vals};\n")
            
        # ScanResult
        for s in ScanResult.query.all():
            vals = (s.id, s.corporation_id, s.scan_date, s.status, s.agent_name, s.agent_first, s.agent_last, s.extracted_data, s.error_message, s.source_file)
            f.write(f"INSERT INTO scan_results VALUES {vals};\n")
            
        # DailyRun
        for d in DailyRun.query.all():
            vals = (d.id, d.run_date, d.status, d.total_processed, d.total_success, d.total_failed, d.duration_seconds)
            f.write(f"INSERT INTO daily_runs VALUES {vals};\n")
            
    size = os.path.getsize(backup_file)
    print(f"Volcado SQLAlchemy completado. Tamaño: {size} bytes. Ruta: {backup_file}")
