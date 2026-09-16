import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_config import obtener_url_conexion
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

def run_migration():
    env = os.environ.get('FLASK_ENV', 'development')
    target = 'produccion' if env == 'production' else 'local'
    db_url = obtener_url_conexion(target)
    print(f"Migrando {target}...")
    
    from app.models import db, HistoryEvent
    from app import create_app
    app = create_app()
    with app.app_context():
        inspector = sa.inspect(db.engine)
        if not inspector.has_table('history_events'):
            print("Creando tabla history_events...")
            HistoryEvent.__table__.create(db.engine)
            print("Tabla creada.")
        else:
            print("La tabla ya existe.")

if __name__ == '__main__':
    run_migration()
