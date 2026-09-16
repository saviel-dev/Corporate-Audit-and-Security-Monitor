import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db_config import obtener_url_conexion
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

def run_migration():
    db_url = obtener_url_conexion('produccion')
    print(f"Migrando produccion usando SQLAlchemy directamente a {db_url.split('@')[1]}...")
    
    engine = sa.create_engine(db_url)
    
    from app.models import HistoryEvent
    
    inspector = sa.inspect(engine)
    if not inspector.has_table('history_events'):
        print("Creando tabla history_events...")
        HistoryEvent.__table__.create(engine)
        print("Tabla creada.")
    else:
        print("La tabla ya existe.")

if __name__ == '__main__':
    run_migration()
