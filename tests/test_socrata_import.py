import unittest
from unittest.mock import patch
from app import create_app, db
from app.models import Corporation
from app.services.scanner import run_daily_scan

class TestSocrataImport(unittest.TestCase):
    def setUp(self):
        import os
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    @patch('app.services.co_discovery.run_co_discovery')
    def test_socrata_import_saves_corp_id(self, mock_run_co_discovery):
        """
        Verifica que al importar entidades vía Socrata (CO Discovery),
        el campo corp_id se guarda correctamente en la base de datos
        tanto en la creación como en la actualización.
        """
        from app.models import DailyRun
        run1 = DailyRun()
        db.session.add(run1)
        db.session.commit()
        
        run2 = DailyRun()
        db.session.add(run2)
        db.session.commit()
        # 1. Simular primera importación (creación)
        mock_run_co_discovery.return_value = [
            {
                "name": "TEST SOCRATA CORP",
                "state": "CO",
                "status": "Available",
                "source_file": "co-socrata-api",
                "corp_id": "20251234567",
                "agent_name": "JOHN DOE",
                "agent_first": "JOHN",
                "agent_last": "DOE",
            }
        ]
        
        self.app.config["SCRAPER_READY_STATES"] = ["CO"]
        
        with patch('app.models.StateConfig.get_discoverable_states') as mock_states:
            mock_states.return_value = [] # No other states
            run_daily_scan(1, self.app)
            
        corp = Corporation.query.filter_by(name="TEST SOCRATA CORP").first()
        self.assertIsNotNone(corp, "La corporación debe crearse")
        self.assertEqual(corp.corp_id, "20251234567", "El corp_id debe guardarse en la creación")
        self.assertEqual(corp.source_file, "co-socrata-api")

        # 2. Simular segunda importación (actualización)
        # Forzamos que no tenga corp_id primero (caso real de la BD ahora mismo)
        corp.corp_id = None
        db.session.commit()
        
        # Le cambiamos el status para que dispare el bloque update
        mock_run_co_discovery.return_value[0]["status"] = "Inactive"
        
        with patch('app.models.StateConfig.get_discoverable_states') as mock_states:
            mock_states.return_value = []
            run_daily_scan(2, self.app)
            
        corp_updated = Corporation.query.filter_by(name="TEST SOCRATA CORP").first()
        self.assertEqual(corp_updated.status, "Inactive", "Debe haber actualizado el status")
        self.assertEqual(corp_updated.corp_id, "20251234567", "Debe haber poblado el corp_id en el update")

if __name__ == '__main__':
    unittest.main()
