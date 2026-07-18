"""
app/scrapers/hi.py

Hawaii Business Registry scraper.
NEW Portal (2025): https://hbe.dcca.hawaii.gov/
OLD Portal (deprecated): https://hbe.ehawaii.gov/documents/search.html
  → Old URL now redirects to new portal.

Portal type: Salesforce Lightning Web Components SPA
  - Requires Playwright with JS execution (not simple HTTP fetch)
  - Page uses LWC components, data is loaded asynchronously via Apex
  - Search results and detail data are rendered client-side

Pipeline A (Auto-Discovery): NOT SUPPORTED
  - HI portal only allows entity name search (no officer/agent search field)
  - Corporations must be provided via CSV upload
  - SUPPORTS_DISCOVERY = False

Pipeline B (Individual scrape):
  1. Navigate to hbe.dcca.hawaii.gov
  2. Wait for the search input to appear in the LWC component
  3. Type entity name, submit
  4. Wait for LWC results to render
  5. Click matching entity link
  6. Wait for detail page LWC to render
  7. Extract: registered agent name, officer names, status
"""

from __future__ import annotations

import logging

from app.scrapers.base import BaseScraper, ScrapedRecord

logger = logging.getLogger(__name__)

NEW_SEARCH_URL = "https://hbe.dcca.hawaii.gov/"
# Fallback: direct search URL if home page does not render search immediately
SEARCH_FRAGMENT = "https://hbe.dcca.hawaii.gov/"


class HawaiiScraper(BaseScraper):
    STATE_CODE = "HI"
    SEARCH_URL = NEW_SEARCH_URL
    SUPPORTS_DISCOVERY = False  # Portal only supports entity name search

    # ── Pipeline B: Individual scrape ─────────────────────────────────────────

    def _do_scrape(self, page, corp_name: str, record: ScrapedRecord) -> None:
        """
        Navigate to HI Business Registry and search for corp_name.
        The portal is a Salesforce LWC SPA - we use extended waits.
        """
        page.goto(NEW_SEARCH_URL, wait_until="domcontentloaded")

        # LWC SPA: wait for the main app shell to render
        try:
            page.wait_for_timeout(3_000)  # Initial JS bundle load
            page.wait_for_selector(
                "input[type='search'], input[type='text'], input[placeholder*='search' i], "
                "input[placeholder*='name' i], input[placeholder*='business' i], "
                "lightning-input input, [data-id='search'] input",
                timeout=20_000
            )
        except Exception:
            logger.warning("[HI] Search input not found after 20s. Proceeding anyway.")

        if not self._fill_search(page, corp_name):
            record.error = True
            record.error_message = "No se encontró el campo de búsqueda en el portal de Hawaii."
            return

        clicked = self._click_best_result(page, corp_name)
        if not clicked:
            record.error = True
            record.error_message = f"No se encontró '{corp_name}' en el portal de Hawaii."
            return

        # Wait for LWC detail component to render
        try:
            page.wait_for_timeout(2_000)
        except Exception:
            pass

        self._extract_details(page, record)

    # ── Search helpers ────────────────────────────────────────────────────────

    def _fill_search(self, page, corp_name: str) -> bool:
        """Fill the LWC search input and trigger search."""
        try:
            # LWC often uses Shadow DOM. get_by_placeholder pierces it reliably.
            loc = page.get_by_placeholder("Enter a Business Name", exact=False)
            if loc.count() > 0:
                el = loc.first
                el.click()
                page.wait_for_timeout(300)
                el.fill(corp_name)
                page.wait_for_timeout(500)
                logger.info("[HI] Typed '%s' into search box via placeholder", corp_name)

                # Submit: press Enter since finding the button can also be tricky
                page.keyboard.press("Enter")

                # Wait for LWC to re-render results
                try:
                    page.wait_for_timeout(3_000)
                except Exception:
                    pass
                return True
        except Exception as e:
            logger.warning("[HI] Failed to fill search via placeholder: %s", e)

        # Fallback to old selector logic if placeholder fails
        selectors = [
            "input[placeholder*='search' i]",
            "input[placeholder*='business' i]",
            "input[placeholder*='name' i]",
            "lightning-input input",
            "[data-id='searchInput'] input",
            "input[type='search']",
            "input[type='text']:first-of-type",
        ]

        for sel in selectors:
            try:
                el = page.wait_for_selector(sel, timeout=5_000)
                if el:
                    el.click()
                    page.wait_for_timeout(300)
                    el.fill(corp_name)
                    page.wait_for_timeout(500)
                    logger.info("[HI] Typed '%s' into '%s'", corp_name, sel)

                    # Submit: try button first, then Enter
                    submitted = self._try_click(page, [
                        "button[type='submit']",
                        "button:has-text('Search')",
                        "button:has-text('Go')",
                        "[data-id='searchButton']",
                        "lightning-button button",
                    ])
                    if not submitted:
                        page.keyboard.press("Enter")

                    # Wait for LWC to re-render results
                    try:
                        page.wait_for_timeout(3_000)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue

        return False

    # ── Result selection ──────────────────────────────────────────────────────

    def _click_best_result(self, page, corp_name: str) -> bool:
        """Find and click the best matching entity in results."""
        # Give LWC extra time to render
        page.wait_for_timeout(2_000)

        corp_upper = corp_name.upper()

        # Try to find exact/partial text match in result links
        link_selectors = [
            "a[href*='entity'], a[href*='business'], a[href*='detail']",
            "table tbody tr td:first-child a",
            "lightning-datatable tbody tr td a",
            ".slds-table tbody tr td a",
            "ul li a",
            "a[data-id='entityName']",
            "[data-entity-name]",
            "a",  # last resort
        ]

        for sel in link_selectors:
            try:
                links = page.query_selector_all(sel)
                if not links:
                    continue
                # Look for exact/partial match first
                for link in links:
                    text = link.inner_text().strip().upper()
                    if text == corp_upper or (corp_upper[:8] in text and len(text) < 100):
                        logger.info("[HI] Matched result: '%s'", text)
                        link.click()
                        try:
                            page.wait_for_timeout(3_000)
                        except Exception:
                            pass
                        return True
                # No exact match: click first non-empty result
                for link in links:
                    text = link.inner_text().strip()
                    if text and len(text) > 3:
                        logger.info("[HI] Clicking first result: '%s'", text)
                        link.click()
                        try:
                            page.wait_for_timeout(3_000)
                        except Exception:
                            pass
                        return True
            except Exception:
                continue

        # No-results check
        content = page.inner_text("body").lower()
        if any(x in content for x in ["no results", "no records", "not found", "0 results"]):
            logger.info("[HI] No results found for '%s'", corp_name)
            return False

        return False

    # ── Detail extraction ─────────────────────────────────────────────────────

    def _extract_details(self, page, record: ScrapedRecord) -> None:
        """
        Extract entity details from HI LWC detail page.
        Salesforce LWC renders data in:
          - <lightning-formatted-text> elements
          - <dd> elements next to <dt> labels
          - <td> cells in <lightning-datatable>
        """
        # Extract status
        record.portal_status = self._extract_status(page)

        # Extract registered agent
        record.registered_agent = self._extract_agent(page)

        # Extract officers/directors
        record.officer_name = self._extract_officers(page)

        # If no officer found separately, use agent as fallback
        if not record.officer_name and record.registered_agent:
            logger.info("[HI] No officer found, using agent as officer fallback")
            record.officer_name = record.registered_agent

        logger.info("[HI] Status: %s | Officer: %s | Agent: %s",
                    record.portal_status, record.officer_name, record.registered_agent)

    def _extract_status(self, page) -> str | None:
        """Find entity status - common labels in HI portal."""
        status_selectors = [
            # LWC formatted text after "Status" label
            "dt:has-text('Status') + dd",
            "dt:has-text('Standing') + dd",
            "th:has-text('Status') + td",
            "[data-label='Status']",
            "lightning-formatted-text[data-id='status']",
        ]
        val = self._try_selectors(page, status_selectors, timeout=3_000)
        if val:
            return val

        # Scan body for common status words
        return self._scan_text_for_status(page)

    def _extract_agent(self, page) -> str | None:
        """Find registered agent name in LWC detail page."""
        selectors = [
            "dt:has-text('Registered Agent') + dd",
            "dt:has-text('Agent Name') + dd",
            "th:has-text('Registered Agent') + td",
            "[data-label='Registered Agent Name']",
            "[data-label='Agent Name']",
        ]
        val = self._try_selectors(page, selectors, timeout=3_000)
        if val:
            return val

        return self._find_label_value(page, ["Registered Agent", "Agent Name", "Agent"])

    def _extract_officers(self, page) -> str | None:
        """Find officer/director names in LWC detail page."""
        selectors = [
            # Officers usually in a table or list
            "dt:has-text('President') + dd",
            "dt:has-text('Director') + dd",
            "dt:has-text('Officer') + dd",
            "[data-label='President']",
            "[data-label='Director']",
            "table:has(th:has-text('Officer')) tbody tr td:first-child",
            "table:has(th:has-text('Director')) tbody tr td:first-child",
            ".slds-table:has(th:has-text('Officer')) tbody tr td:first-child",
        ]
        for sel in selectors:
            names = self._query_all_text(page, sel)
            if names:
                return "; ".join(names)

        return self._find_label_value(
            page,
            ["President", "Director", "Officer", "Manager", "Member", "Chairman"]
        )

    def _find_label_value(self, page, labels: list[str]) -> str | None:
        """Scan DOM for label → next element value pattern."""
        for label in labels:
            try:
                # dt/dd pattern (LWC uses this frequently)
                result = page.evaluate(f"""
                    () => {{
                        const dts = document.querySelectorAll('dt, th, label, span, p, div');
                        for (const el of dts) {{
                            const txt = el.textContent.trim();
                            if (txt === '{label}' || txt.includes('{label}')) {{
                                const next = el.nextElementSibling;
                                if (next) {{
                                    const t = next.textContent.trim();
                                    if (t && t.length > 1 && t.length < 150) return t;
                                }}
                            }}
                        }}
                        return null;
                    }}
                """)
                if result:
                    return result
            except Exception:
                continue
        return None

    def _scan_text_for_status(self, page) -> str | None:
        """Scan body text for known status keywords."""
        try:
            text = page.inner_text("body").lower()
            for status in ["active", "good standing", "inactive",
                           "dissolved", "expired", "delinquent", "cancelled"]:
                if status in text:
                    return status.title()
        except Exception:
            pass
        return None
