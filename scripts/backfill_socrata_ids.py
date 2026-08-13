import os
import sys

# Cargar configuración desde .env para apuntar a producción (Neon)
from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app, db
from app.models import Corporation
from app.services.co_discovery import lookup_by_name
import sqlalchemy

def run_backfill():
    app = create_app()
    with app.app_context():
        print(f"[{'='*20}]")
        print(f"DATABASE CONNECTED: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"[{'='*20}]\n")
        
        # Obtener entidades de Socrata (CO)
        corps = Corporation.query.filter(
            Corporation.source_file == 'co-socrata-api',
            Corporation.state == 'CO'
        ).all()
        
        print(f"Iniciando backfill para {len(corps)} corporaciones de Socrata en DB local...")
        
        procesadas = 0
        pobladas = 0
        ya_tenian = 0
        no_encontrado = 0
        errores = 0
        
        for corp in corps:
            procesadas += 1
            if corp.corp_id:
                ya_tenian += 1
                continue
                
            try:
                # Usar lookup_by_name que consulta a Socrata por nombre
                records = lookup_by_name(corp.name, limit=1)
                if records:
                    rec = records[0]
                    if rec.entity_id:
                        # Asignar como cadena tal cual viene
                        corp.corp_id = str(rec.entity_id).strip()
                        
                        # Intento de commit individual para manejar IntegrityError sin abortar todo
                        try:
                            db.session.commit()
                            print(f"[{corp.id}] {corp.name} -> ID Poblado: {rec.entity_id}")
                            pobladas += 1
                        except sqlalchemy.exc.IntegrityError as e:
                            db.session.rollback()
                            print(f"[{corp.id}] {corp.name} -> Error de Integridad (ID duplicado?): {rec.entity_id}")
                            errores += 1
                    else:
                        print(f"[{corp.id}] {corp.name} -> Socrata devolvio el registro sin entity_id")
                        no_encontrado += 1
                else:
                    print(f"[{corp.id}] {corp.name} -> No encontrado en Socrata")
                    no_encontrado += 1
            except Exception as e:
                db.session.rollback()
                print(f"[{corp.id}] {corp.name} -> Error en API/BD: {e}")
                errores += 1
                
        print("\n--- RESUMEN BACKFILL ---")
        print(f"Procesadas:     {procesadas}")
        print(f"Ya tenian ID:   {ya_tenian}")
        print(f"ID Pobladas:    {pobladas}")
        print(f"Sin ID (Vacio): {no_encontrado}")
        print(f"Con Errores:    {errores}")

if __name__ == "__main__":
    run_backfill()
