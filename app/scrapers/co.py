"""
app/scrapers/co.py

Colorado Secretary of State scraper.
Portal: https://www.sos.state.co.us/biz/BusinessEntityCriteriaExt.do

IMPORTANT FINDINGS from portal inspection:
- Basic search field ID: `searchCriteria`
- Result links: `a[href^="BusinessEntityDetail.do"]`
- Detail page uses TABLE-BASED layout with two tables:
    1. "Details" table: th->td pairs for Status, Name, ID, Formation date
    2. "Registered Agent" table: th->td pairs for Name, Address
- Officers/Directors: NOT on detail page. They are in filed documents (PDFs).
  Strategy: use the "Principal office" address + registered agent as the check.
  For officers, we check the REGISTERED AGENT name against the detection rule.

- Advanced search (https://www.sos.state.co.us/biz/AdvancedSearchCriteria.do)
  has Registered Agent Last Name field BUT triggers reCAPTCHA when automated.
  SUPPORTS_DISCOVERY is therefore False for production use.

Pipeline B (Individual scrape):
  Search by entity name → click first result → extract agent + status.
"""

from __future__ import annotations

import logging

from app.scrapers.base import BaseScraper, ScrapedRecord

logger = logging.getLogger(__name__)

SEARCH_URL = "https://www.sos.state.co.us/biz/BusinessEntityCriteriaExt.do"


class ColoradoScraper(BaseScraper):
    STATE_CODE = "CO"
    SEARCH_URL = SEARCH_URL

    # Advanced search triggers reCAPTCHA → auto-discovery disabled
    SUPPORTS_DISCOVERY = False

    # ── Individual scrape (Pipeline B) ───────────────────────────────────────

    def _do_scrape(self, page, corp_name: str, record: ScrapedRecord) -> None:
        page.goto(SEARCH_URL, wait_until="domcontentloaded")

        # Wait for the main search input to appear
        try:
            page.wait_for_selector("#searchCriteria", timeout=15_000)
        except Exception:
            pass

        self._fill_entity_search(page, corp_name)
        clicked = self._click_best_result(page, corp_name)

        if not clicked:
            record.error = True
            record.error_message = f"No se encontró '{corp_name}' en el portal de Colorado."
            return

        self._extract_details(page, record)

    # ── Search form ───────────────────────────────────────────────────────────

    def _fill_entity_search(self, page, corp_name: str) -> None:
        """Fill the basic search field and submit."""
        name_fields = [
            "#searchCriteria",
            "input[name='searchCriteria']",
            "input[type='text']:first-of-type",
        ]
        used = self._try_fill(page, name_fields, corp_name)
        if not used:
            raise RuntimeError("No se encontró el campo de búsqueda en Colorado.")

        submitted = self._try_click(page, [
            "a[aria-label='Search'] input",
            "input.button[value='Search']",
            "a:has-text('Search') input",
        ])
        if not submitted:
            page.keyboard.press("Enter")

        try:
            page.wait_for_load_state("domcontentloaded", timeout=20_000)
            page.wait_for_timeout(1_500)
        except Exception:
            pass

    # ── Result selection ──────────────────────────────────────────────────────

    def _click_best_result(self, page, corp_name: str) -> bool:
        """Click the first result link. Returns True on success."""
        # Check for error/no-results messages first
        content = page.inner_text("body").lower()
        if "exceeded record count" in content:
            # Try a more specific search
            logger.warning("[CO] Record count exceeded for '%s'. Trying with LLC.", corp_name)
            return False
        if "no matching records" in content or "no results" in content:
            return False

        # CO uses `a[href^="BusinessEntityDetail.do"]` for all entity links
        link_selectors = [
            "a[href^='BusinessEntityDetail.do']",
            "a[href*='masterFileId']",
            "table tbody tr td a:first-of-type",
        ]

        # First try to find exact name match
        try:
            all_links = page.query_selector_all("a[href^='BusinessEntityDetail.do']")
            corp_upper = corp_name.upper()
            for link in all_links:
                text = link.inner_text().strip().upper()
                if text == corp_upper or corp_upper in text:
                    logger.info("[CO] Exact match: '%s'", text)
                    link.click()
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=20_000)
                        page.wait_for_timeout(1_500)
                    except Exception:
                        pass
                    return True
        except Exception:
            pass

        # Fallback: click first available entity link
        for sel in link_selectors:
            try:
                link = page.wait_for_selector(sel, timeout=8_000)
                if link:
                    logger.info("[CO] Clicking first result: '%s'", link.inner_text().strip())
                    link.click()
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=20_000)
                        page.wait_for_timeout(1_500)
                    except Exception:
                        pass
                    return True
            except Exception:
                continue

        return False

    # ── Detail page extraction ────────────────────────────────────────────────

    def _extract_details(self, page, record: ScrapedRecord) -> None:
        """
        Extract data from CO entity detail page.

        CO detail page has two tables:
          1. "Details" table:  <th>Status</th><td>VALUE</td>
          2. "Registered Agent" table: <th>Name</th><td>AGENT_NAME</td>

        NOTE: Officers/Directors are NOT on the detail page in CO.
        They are embedded in filed PDFs. We extract the Registered Agent
        and use that as both the officer and agent field for detection.
        The detection rule checks: officer_name + registered_agent combined.
        """
        # Status: in "Details" table
        record.portal_status = self._extract_by_th_text(page, "Status")

        # Corp ID
        record.corp_id = self._extract_by_th_text(page, "ID number")

        # Registered Agent Name: in "Registered Agent" table
        # Strategy: the "Registered Agent" section has a <th>Name</th>
        # We need the SECOND occurrence of <th>Name</th> (first is entity name)
        record.registered_agent = self._extract_registered_agent(page)

        # Officers not on page — set to None, flag will be based on agent
        # The scanner/detector will check both fields together
        record.officer_name = None

        logger.info("[CO] Extracted — Status: %s | Agent: %s",
                    record.portal_status, record.registered_agent)

    def _extract_registered_agent(self, page) -> str | None:
        """
        Extract registered agent name from the 'Registered Agent' section.
        CO layout: <td class="entity_conf_table_header">Registered Agent</td>
                   followed by <th>Name</th><td>AGENT NAME</td>
        """
        try:
            # Most specific: find the Registered Agent table and get its Name td
            agent_name = page.evaluate("""
                () => {
                    const headers = document.querySelectorAll('td.entity_conf_table_header');
                    for (const header of headers) {
                        if (header.textContent.includes('Registered Agent')) {
                            const table = header.closest('table');
                            if (table) {
                                const ths = table.querySelectorAll('th');
                                for (const th of ths) {
                                    if (th.textContent.trim() === 'Name') {
                                        const td = th.nextElementSibling;
                                        if (td) return td.textContent.trim();
                                    }
                                }
                            }
                        }
                    }
                    return null;
                }
            """)
            if agent_name:
                return agent_name
        except Exception:
            pass

        # Fallback: second occurrence of th "Name" (first is entity name)
        try:
            name_ths = page.query_selector_all("th")
            name_count = 0
            for th in name_ths:
                if th.inner_text().strip() == "Name":
                    name_count += 1
                    if name_count == 2:  # second "Name" th = agent
                        td = page.evaluate(
                            "(el) => el.nextElementSibling ? el.nextElementSibling.innerText.trim() : null",
                            th
                        )
                        if td:
                            return td
        except Exception:
            pass

        return None

    def _extract_by_th_text(self, page, label: str) -> str | None:
        """Find <th>label</th> and return the text of the next <td>."""
        try:
            result = page.evaluate(f"""
                () => {{
                    const ths = document.querySelectorAll('th');
                    for (const th of ths) {{
                        if (th.textContent.trim() === '{label}') {{
                            const td = th.nextElementSibling;
                            if (td) return td.textContent.trim();
                        }}
                    }}
                    return null;
                }}
            """)
            return result
        except Exception:
            return None
