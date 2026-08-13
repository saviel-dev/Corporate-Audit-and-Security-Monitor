import os
import unittest
from datetime import datetime, timezone, timedelta
from app import create_app, db
from app.models import StateConfig, Corporation, DailyRun, ScanResult, StateMetrics
from app.scrapers.base import BaseScraper, ScrapedRecord, WafBlockException
from app.services.scanner import _execute_scan
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    MAX_WAF_BLOCKS = 2
    WAF_COOLDOWN_MINUTOS = 120
    PATRONES_BLOQUEO_WAF = [
        "you have been blocked",
        "attention required",
        "sorry, you have been blocked"
    ]
    SCRAPER_READY_STATES = ["HI", "CO", "XX"]
    SUPPORTED_STATES = ["HI", "CO", "XX"]
    ESTADOS_PRIORITARIOS = ["XX", "HI", "CO"]

class DummyScraper(BaseScraper):
    STATE_CODE = "XX"
    SEARCH_URL = "http://example.com"
    
    def _do_scrape(self, page, corp_name, record):
        pass

class MockPage:
    def __init__(self, content_str):
        self._content = content_str
        
    def content(self):
        return self._content

class TestWafProtection(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_waf_detection_with_exception(self):
        # HTML containing the pattern should raise WafBlockException
        scraper = DummyScraper(timeout_ms=1000)
        
        # Override _attempt to simulate exception inside Playwright with MockPage
        def mock_attempt(record, corp_name, save_pdf):
            page = MockPage("<html><body>you have been blocked</body></html>")
            try:
                # simulate a timeout during _do_scrape
                raise Exception("Timeout error")
            except Exception as e:
                content = page.content().lower()
                for pattern in self.app.config["PATRONES_BLOQUEO_WAF"]:
                    if pattern in content:
                        raise WafBlockException("BLOQUEADO_POR_WAF") from e
                raise
        
        scraper._attempt = mock_attempt
        
        record = scraper.scrape("Test Corp")
        self.assertTrue(record.error)
        self.assertEqual(record.error_message, "BLOQUEADO_POR_WAF")
        
    def test_waf_false_positive_cloudflare_word(self):
        # HTML containing just 'cloudflare' shouldn't raise if not in PATRONES_BLOQUEO_WAF
        scraper = DummyScraper(timeout_ms=1000)
        
        def mock_attempt(record, corp_name, save_pdf):
            page = MockPage("<html><body>cloudflare is our CDN provider</body></html>")
            try:
                raise Exception("Timeout error")
            except Exception as e:
                content = page.content().lower()
                for pattern in self.app.config["PATRONES_BLOQUEO_WAF"]:
                    if pattern in content:
                        raise WafBlockException("BLOQUEADO_POR_WAF") from e
                raise
                
        scraper._attempt = mock_attempt
        
        record = scraper.scrape("Test Corp")
        self.assertTrue(record.error)
        # It shouldn't be WAF block, just the original error
        self.assertNotEqual(record.error_message, "BLOQUEADO_POR_WAF")

    def test_circuit_breaker(self):
        # Setup run and state config
        run = DailyRun(started_at=datetime.now(timezone.utc), status="running")
        db.session.add(run)
        
        state_cfg = StateConfig(state_name="TestState", state_code="XX", search_url="http", active=True, scraper_supported=True)
        db.session.add(state_cfg)
        
        # Add 3 corporations to trigger breaker
        for i in range(3):
            corp = Corporation(name=f"Corp {i}", state="XX", status="Available", source_file="test")
            db.session.add(corp)
            
        db.session.commit()
        
        # Mock scraper in get_scraper
        from app.services import scanner
        
        class BlockedScraper:
            def scrape(self, name, save_pdf=False):
                r = ScrapedRecord(corp_name=name, state="XX", search_url="http")
                r.error = True
                r.error_message = "BLOQUEADO_POR_WAF"
                return r

        original_get = scanner.get_scraper
        scanner.get_scraper = lambda state, **kwargs: BlockedScraper()
        
        try:
            # First execution should scan the first 2 and then trigger circuit breaker
            # The 3rd corp should be skipped
            _execute_scan(run.id, self.app)
            
            metrics = StateMetrics.query.filter_by(estado="XX").first()
            self.assertEqual(metrics.total_bloqueos_waf, 2)
            self.assertEqual(metrics.total_intentadas, 2) # third one was skipped
            
            # Verify cooldown was set
            cfg = StateConfig.query.filter_by(state_code="XX").first()
            self.assertIsNotNone(cfg.waf_blocked_until)
            
            # Now test cooldown skip logic directly in a second run
            # Add one more corp to test skipping
            corp4 = Corporation(name="Corp 4", state="XX", status="Available", source_file="test")
            db.session.add(corp4)
            db.session.commit()
            
            # Scan again, this time it should just skip all due to cooldown
            _execute_scan(run.id, self.app)
            
            # total_intentadas should still be 2, because it was skipped
            db.session.refresh(metrics)
            self.assertEqual(metrics.total_intentadas, 2)
            
        finally:
            scanner.get_scraper = original_get

    def test_ci_no_playwright_imports(self):
        # Check that no Python file outside app/scrapers/ imports playwright directly
        import glob
        
        root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        allowed_dirs = [os.path.join(root_dir, "app", "scrapers")]
        
        violating_files = []
        
        # Check all .py files in app, scripts, tests, scratch
        for folder in ["app", "scripts", "scratch", "tests"]:
            folder_path = os.path.join(root_dir, folder)
            if not os.path.exists(folder_path):
                continue
                
            for filepath in glob.iglob(os.path.join(folder_path, "**", "*.py"), recursive=True):
                if any(filepath.startswith(allowed_dir) for allowed_dir in allowed_dirs):
                    continue
                # For scratch, only test active .py files (skip .py.bak and scratch/_archivo)
                if "_archivo" in filepath:
                    continue
                    
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    # Use a split string to avoid this file matching itself
                    if "sync_" + "playwright" in content:
                        violating_files.append(filepath)
                        
        self.assertEqual(
            len(violating_files), 0,
            f"Found direct imports of Playwright outside app/scrapers/: {violating_files}. "
            f"Use BaseScraper.run_diagnostic() instead."
        )

if __name__ == "__main__":
    unittest.main()
