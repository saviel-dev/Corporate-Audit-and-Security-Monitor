"""
app/scrapers/base.py

Abstract base class for all Secretary of State scrapers.

Two main entry points:
  1. discover(terms)  → list of corp names (Pipeline A: auto-discovery)
  2. scrape(corp_name) → ScrapedRecord  (for all states, Pipeline A+B)

Each state subclass implements:
  - _do_discover(page, term)  → list[str]   (optional, if is_officer_searchable)
  - _do_scrape(page, corp_name, record)      (required)
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class WafBlockException(Exception):
    """Lanzada cuando se detecta un bloqueo por WAF (Cloudflare/Imperva)."""
    pass


# ─── Data containers ──────────────────────────────────────────────────────────

@dataclass
class ScrapedRecord:
    """Raw data extracted from a Secretary of State portal."""
    corp_name: str
    state: str
    search_url: str

    officer_name: str | None = None
    registered_agent: str | None = None
    portal_status: str | None = None
    corp_id: str | None = None
    pdf_path: str | None = None

    error: bool = False
    error_message: str | None = None

    scraped_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success(self) -> bool:
        return not self.error and (
            self.officer_name is not None or
            self.registered_agent is not None
        )


# ─── Base class ───────────────────────────────────────────────────────────────

class BaseScraper(ABC):
    """
    Abstract base for all state scrapers.

    Subclasses must implement `_do_scrape()`.
    Optionally implement `_do_discover()` for states that support
    officer/agent-name search (Pipeline A auto-discovery).
    """

    STATE_CODE: str = ""
    SEARCH_URL: str = ""

    # Set to True in subclass if the portal supports officer/agent name search
    SUPPORTS_DISCOVERY: bool = False

    def __init__(self, timeout_ms: int = 30_000, retries: int = 3,
                 delay_s: float = 2.0, output_dir: str = "output/pdfs"):
        self.timeout_ms = timeout_ms
        self.retries = retries
        self.delay_s = delay_s
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    # ── Pipeline A: Auto-discovery ────────────────────────────────────────────

    def discover(self, terms: list[str]) -> list[str]:
        """
        Search the portal by officer/agent terms and return corp names found.

        Parameters
        ----------
        terms : list[str]
            Search terms (e.g. ["Marcio Garcia", "Garcia", "Andrade"]).

        Returns
        -------
        list[str] — unique corporation names found across all terms.
        """
        if not self.SUPPORTS_DISCOVERY:
            logger.debug("[%s] Discovery not supported for this state.", self.STATE_CODE)
            return []

        all_names: set[str] = set()
        for term in terms:
            names = self._discover_with_retry(term)
            all_names.update(names)

        logger.info("[%s] Discovery found %d unique corps: %s",
                    self.STATE_CODE, len(all_names),
                    ", ".join(list(all_names)[:5]))
        return list(all_names)

    def _discover_with_retry(self, term: str) -> list[str]:
        """Run discovery for one term with retry logic."""
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                return self._run_discover_session(term)
            except Exception as exc:
                last_error = exc
                logger.warning("[%s] Discovery attempt %d failed for '%s': %s",
                               self.STATE_CODE, attempt, term, exc)
                if attempt < self.retries:
                    time.sleep(self.delay_s * attempt)
        logger.error("[%s] Discovery failed for '%s' after %d retries: %s",
                     self.STATE_CODE, term, self.retries, last_error)
        return []

    def _run_discover_session(self, term: str) -> list[str]:
        """Open a Playwright session and call _do_discover."""
        from flask import current_app
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        use_stealth = current_app.config.get("USE_STEALTH_MODE", True)
        pw_cm = Stealth().use_sync(sync_playwright()) if use_stealth else sync_playwright()

        with pw_cm as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                user_agent=self._ua(),
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                return self._do_discover(page, term)
            finally:
                context.close()
                browser.close()

    def _do_discover(self, page, term: str) -> list[str]:
        """
        Override in subclass if SUPPORTS_DISCOVERY = True.
        Return list of corporation names that match the search term.
        """
        return []

    # ── Pipeline A+B: Individual scrape ───────────────────────────────────────

    def scrape(self, corp_name: str, save_pdf: bool = True) -> ScrapedRecord:
        """
        Scrape the portal for *corp_name* with retry logic.
        Returns a ScrapedRecord with officer/agent data and optional pdf_path.
        """
        record = ScrapedRecord(
            corp_name=corp_name,
            state=self.STATE_CODE,
            search_url=self.SEARCH_URL,
        )
        last_error = None
        for attempt in range(1, self.retries + 1):
            try:
                logger.info("[%s] Scraping '%s' (attempt %d/%d)",
                            self.STATE_CODE, corp_name, attempt, self.retries)
                self._attempt(record, corp_name, save_pdf)
                if record.success:
                    # Pausa dinámica configurable
                    from flask import current_app
                    delay = current_app.config.get("SCRAPER_DELAY_SECONDS", 4)
                    if delay > 0:
                        time.sleep(delay)
                    return record
            except WafBlockException as exc:
                # Abort all retries immediately if WAF blocks us
                record.error = True
                record.error_message = str(exc)
                logger.error("[%s] WAF Block detected for '%s'. Aborting retries.", self.STATE_CODE, corp_name)
                return record
            except Exception as exc:
                last_error = exc
                logger.warning("[%s] Attempt %d failed for '%s': %s",
                               self.STATE_CODE, attempt, corp_name, exc)
                if attempt < self.retries:
                    time.sleep(self.delay_s * attempt)

        record.error = True
        if not record.error_message:
            record.error_message = str(last_error) if last_error else "Unknown error"
        logger.error("[%s] All retries failed for '%s': %s",
                     self.STATE_CODE, corp_name, record.error_message)
        
        # Pausa final incluso si fallan los reintentos
        from flask import current_app
        delay = current_app.config.get("SCRAPER_DELAY_SECONDS", 4)
        if delay > 0:
            time.sleep(delay)
            
        return record

    def _attempt(self, record: ScrapedRecord, corp_name: str, save_pdf: bool) -> None:
        from flask import current_app
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        use_stealth = current_app.config.get("USE_STEALTH_MODE", True)
        pw_cm = Stealth().use_sync(sync_playwright()) if use_stealth else sync_playwright()

        with pw_cm as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                user_agent=self._ua(),
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                self._do_scrape(page, corp_name, record)
                if save_pdf:
                    record.pdf_path = self._save_pdf(page, corp_name)
            except Exception as e:
                # Detección WAF tras cualquier fallo (ej. timeout esperando selector)
                try:
                    content = page.content().lower()
                    waf_patterns = current_app.config.get(
                        "PATRONES_BLOQUEO_WAF", 
                        ["you have been blocked", "attention required", "sorry, you have been blocked"]
                    )
                    for pattern in waf_patterns:
                        if pattern in content:
                            raise WafBlockException("BLOQUEADO_POR_WAF") from e
                except WafBlockException:
                    raise
                except Exception:
                    pass # Ignorar fallos al chequear el WAF
                raise # Relanzar error original si no es WAF
            finally:
                context.close()
                browser.close()

    # ── Screenshot Evidence ───────────────────────────────────────────────────

    def _save_pdf(self, page, corp_name: str) -> str | None:
        """Saves a full page screenshot instead of a PDF (reusing the pdf_path field)."""
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            safe = "".join(
                c if c.isalnum() or c in " -_" else "_" for c in corp_name
            ).strip().replace(" ", "_")[:80]
            # Use .png extension
            path = os.path.join(self.output_dir, f"{date_str}_{self.STATE_CODE}_{safe}.png")
            # Save as full page screenshot
            page.screenshot(path=path, full_page=True)
            logger.info("[%s] Screenshot saved: %s", self.STATE_CODE, path)
            return path
        except Exception as exc:
            logger.warning("[%s] Screenshot save failed: %s", self.STATE_CODE, exc)
            return None

    # ── Abstract method ───────────────────────────────────────────────────────

    @abstractmethod
    def _do_scrape(self, page, corp_name: str, record: ScrapedRecord) -> None:
        """Implement state-specific scraping logic. Populate record fields."""
        pass

    # ── Diagnostic Utility ────────────────────────────────────────────────────
    
    def run_diagnostic(self, callback) -> None:
        """
        Public method for diagnostic scripts to run custom code safely using 
        the scraper's context, stealth, and pauses, without instantiating Playwright directly.
        callback should accept a `page` parameter.
        """
        from flask import current_app
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        use_stealth = current_app.config.get("USE_STEALTH_MODE", True)
        pw_cm = Stealth().use_sync(sync_playwright()) if use_stealth else sync_playwright()

        with pw_cm as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                device_scale_factor=2,
                user_agent=self._ua(),
            )
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                callback(page)
            finally:
                context.close()
                browser.close()
                
        # Mandatory pause after diagnostic
        delay = current_app.config.get("SCRAPER_DELAY_SECONDS", 4)
        if delay > 0:
            time.sleep(delay)

    # ── Shared helpers ────────────────────────────────────────────────────────

    def _ua(self) -> str:
        return ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36")

    def _safe_text(self, page, selector: str, timeout: int = 5_000) -> str | None:
        try:
            el = page.wait_for_selector(selector, timeout=timeout)
            return el.inner_text().strip() if el else None
        except Exception:
            return None

    def _try_selectors(self, page, selectors: list[str],
                       timeout: int = 5_000) -> str | None:
        """Try multiple CSS selectors, return first match text."""
        for sel in selectors:
            val = self._safe_text(page, sel, timeout=timeout)
            if val:
                return val
        return None

    def _try_fill(self, page, selectors: list[str], value: str) -> str | None:
        """Try filling multiple selectors, return the one that worked."""
        for sel in selectors:
            try:
                page.wait_for_selector(sel, timeout=5_000)
                page.fill(sel, value)
                return sel
            except Exception:
                continue
        return None

    def _try_click(self, page, selectors: list[str]) -> bool:
        """Try clicking multiple selectors, return True if any worked."""
        for sel in selectors:
            try:
                page.click(sel, timeout=5_000)
                return True
            except Exception:
                continue
        return False

    def _query_all_text(self, page, selector: str) -> list[str]:
        """Return inner text of all elements matching selector."""
        try:
            els = page.query_selector_all(selector)
            return [el.inner_text().strip() for el in els if el.inner_text().strip()]
        except Exception:
            return []
