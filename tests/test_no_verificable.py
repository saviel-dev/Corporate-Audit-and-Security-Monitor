import pytest
from app import create_app, db
from app.models import Corporation, DailyRun, ScanResult, StateMetrics
from app.services.scanner import _execute_scan

@pytest.fixture
def test_app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "USE_STEALTH_MODE": False,
        "ESTADOS_PRIORITARIOS": ["XX"],
    })
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()

def test_no_verificable_does_not_count_as_alert_or_clean(test_app, monkeypatch):
    """
    Verifica que si un scraper falla (error=True), la corporación se cuenta como
    NO VERIFICABLE en StateMetrics, y NO suma a clean_count ni a alert_count.
    """
    with test_app.app_context():
        # Crear corp
        corp = Corporation(name="Test Corp", state="XX", status="Available", source_file="test")
        db.session.add(corp)
        run = DailyRun(triggered_by="test", status="running")
        db.session.add(run)
        db.session.commit()
        run_id = run.id

        # Mock del scraper
        class MockScraper:
            SUPPORTS_DISCOVERY = False
            def scrape(self, name, save_pdf=False):
                from app.scrapers.base import ScrapedRecord
                record = ScrapedRecord(success=False)
                record.error = True
                record.error_message = "Test error"
                return record

        def mock_get_scraper(*args, **kwargs):
            return MockScraper()

        monkeypatch.setattr("app.services.scanner.get_scraper", mock_get_scraper)

        # Ejecutar
        _execute_scan(run_id, test_app)

        # Verificar resultados
        run = db.session.get(DailyRun, run_id)
        assert run.total_processed == 1, "Debe contar como procesada"
        assert run.total_alerts == 0, "No debe contar como alerta (is_theft=False)"
        assert run.total_errors == 1, "Debe sumar a total_errors"
        
        # Calcular clean_count igual que en el dashboard
        warning_count = getattr(run, 'total_warnings', 0)
        clean_count = run.total_processed - run.total_alerts - warning_count - run.total_errors
        assert clean_count == 0, "No debe contar como limpia"

        # Verificar StateMetrics
        metrics = StateMetrics.query.filter_by(daily_run_id=run_id, estado="XX").first()
        assert metrics is not None, "Debe crear métricas para el estado"
        assert metrics.total_intentadas == 1
        assert metrics.total_no_verificables == 1
        assert metrics.total_extraidas == 0
        assert metrics.total_alertas == 0
        assert metrics.tasa_exito == 0.0

        # Verificar ScanResult
        result = ScanResult.query.filter_by(daily_run_id=run_id).first()
        assert result.error is True
        assert result.error_message == "Test error"
        assert result.alert is False
