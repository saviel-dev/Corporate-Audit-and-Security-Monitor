"""
Script para eliminar las filas ficticias de la plantilla (D-07, D-12)
Requiere haber hecho un pg_dump de Neon antes (D-05).
"""
import sys
from pathlib import Path

# Permite importar desde la raiz del proyecto
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app, db
from app.models import Corporation

def limpiar_ficticias():
    app = create_app()
    with app.app_context():
        print(f"Conectado a DB: {app.config['SQLALCHEMY_DATABASE_URI'][:40]}...")
        
        # Conteo antes
        total_antes = Corporation.query.count()
        ficticias_antes = Corporation.query.filter(Corporation.source_file.like("%user_templates%")).count()
        
        print(f"Total corporaciones antes : {total_antes}")
        print(f"Filas ficticias a borrar  : {ficticias_antes}")
        
        # 1. Encontrar los IDs de las corporaciones ficticias
        ficticias_ids = [c.id for c in Corporation.query.filter(Corporation.source_file.like("%user_templates%")).all()]
        
        if not ficticias_ids:
            print("No se encontraron filas ficticias. Saliendo.")
            return

        print(f"IDs a borrar: {ficticias_ids}")

        try:
            from app.models import ScanResult
            
            # 2. Borrar scan_results dependientes
            borrados_scans = ScanResult.query.filter(ScanResult.corporation_id.in_(ficticias_ids)).delete(synchronize_session=False)
            
            # 3. Borrar corporations
            borradas_corps = Corporation.query.filter(Corporation.id.in_(ficticias_ids)).delete(synchronize_session=False)
            
            if borradas_corps != len(ficticias_ids):
                print(f"[ERROR] Intentamos borrar {len(ficticias_ids)} corporaciones pero el delete devolvió {borradas_corps}. Rollback.")
                db.session.rollback()
                return
                
            db.session.commit()
            
            # Conteo despues
            total_despues = Corporation.query.count()
            ficticias_despues = Corporation.query.filter(Corporation.source_file.like("%user_templates%")).count()
            
            print(f"\nOperacion completada con exito.")
            print(f"ScanResults borrados: {borrados_scans}")
            print(f"Corporations borradas: {borradas_corps}")
            print(f"Total corporaciones despues: {total_despues}")
            print(f"Filas ficticias restantes  : {ficticias_despues}")
            
        except Exception as e:
            print(f"[ERROR] Excepcion durante el borrado: {e}")
            db.session.rollback()

if __name__ == "__main__":
    limpiar_ficticias()
