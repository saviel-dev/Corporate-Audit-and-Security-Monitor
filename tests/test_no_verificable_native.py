from app import create_app, db
from app.models import Corporation, DailyRun, ScanResult, StateMetrics
from app.services.scanner import _execute_scan

class MockScraper:
    SUPPORTS_DISCOVERY = False
    def scrape(self, name, save_pdf=False):
        from app.scrapers.base import ScrapedRecord
        record = ScrapedRecord(corp_name=name, state="XX", search_url="http://test")
        record.error = True
        record.error_message = "Test error"
        return record

def run_test():
    from config import Config
    class TestConfig(Config):
        TESTING = True
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        WTF_CSRF_ENABLED = False
        USE_STEALTH_MODE = False
        ESTADOS_PRIORITARIOS = ["XX"]
        SCRAPER_READY_STATES = ["XX"]
        SCHEDULER_ENABLED = False

    flask_app = create_app(TestConfig)
    
    with flask_app.app_context():
        db.create_all()
        
        corp = Corporation(name="Test Corp", state="XX", status="Available", source_file="test")
        db.session.add(corp)
        run = DailyRun(triggered_by="test", status="running")
        db.session.add(run)
        db.session.commit()
        run_id = run.id

        import app.services.scanner
        app.services.scanner.get_scraper = lambda *args, **kwargs: MockScraper()

        _execute_scan(run_id, flask_app)

        run = db.session.get(DailyRun, run_id)
        assert run.total_processed == 1, "Debe contar como procesada"
        assert run.total_alerts == 0, "No debe contar como alerta (is_theft=False)"
        assert run.total_errors == 1, "Debe sumar a total_errors"
        warning_count = getattr(run, 'total_warnings', 0)
        clean_count = run.total_processed - run.total_alerts - warning_count - run.total_errors
        assert clean_count == 0, "No debe contar como limpia"

        metrics = StateMetrics.query.filter_by(daily_run_id=run_id, estado="XX").first()
        assert metrics is not None, "Debe crear métricas para el estado"
        assert metrics.total_intentadas == 1
        assert metrics.total_no_verificables == 1
        assert metrics.total_extraidas == 0
        assert metrics.total_alertas == 0
        assert metrics.tasa_exito == 0.0

        result = ScanResult.query.filter_by(daily_run_id=run_id).first()
        assert result.error is True
        assert result.error_message == "Test error"
        assert result.alert is False
        
        print("ALL TESTS PASSED: NO VERIFICABLE handled correctly")

if __name__ == "__main__":
    run_test()
