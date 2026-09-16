import sys, logging
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env.neon', override=True)
from app import create_app, db
from sqlalchemy import text

app = create_app()

def migrar():
    with app.app_context():
        # state_metrics
        conn = db.engine.connect()
        try:
            conn.execute(text("ALTER TABLE state_metrics ADD COLUMN total_no_encontradas INTEGER DEFAULT 0;"))
            print("Agregado total_no_encontradas a state_metrics")
        except Exception as e:
            print(f"Omitido total_no_encontradas: {e}")

        try:
            conn.execute(text("ALTER TABLE state_metrics ADD COLUMN total_nombre_cambiado INTEGER DEFAULT 0;"))
            print("Agregado total_nombre_cambiado a state_metrics")
        except Exception as e:
            print(f"Omitido total_nombre_cambiado: {e}")
            
        try:
            conn.execute(text("ALTER TABLE state_metrics ADD COLUMN total_errores_tecnicos INTEGER DEFAULT 0;"))
            print("Agregado total_errores_tecnicos a state_metrics")
        except Exception as e:
            print(f"Omitido total_errores_tecnicos: {e}")

        # scan_results
        try:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN nombre_actual_portal VARCHAR(256);"))
            print("Agregado nombre_actual_portal a scan_results")
        except Exception as e:
            print(f"Omitido nombre_actual_portal: {e}")

        try:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN nombre_anterior_portal VARCHAR(256);"))
            print("Agregado nombre_anterior_portal a scan_results")
        except Exception as e:
            print(f"Omitido nombre_anterior_portal: {e}")
            
        try:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN event VARCHAR(256);"))
            print("Agregado event a scan_results")
        except Exception as e:
            print(f"Omitido event: {e}")

        try:
            conn.execute(text("ALTER TABLE scan_results ADD COLUMN scan_status VARCHAR(64);"))
            print("Agregado scan_status a scan_results")
        except Exception as e:
            print(f"Omitido scan_status: {e}")
            
        conn.commit()
        conn.close()
        print("Migracion de DB finalizada.")

if __name__ == '__main__':
    migrar()
