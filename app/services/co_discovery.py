"""
app/services/co_discovery.py

Colorado Auto-Discovery via Socrata Open Data API.

Dataset: "Business Entities in Colorado"
  URL: https://data.colorado.gov/Business/Business-Entities-in-Colorado/4ykn-tg5h
  ID:  4ykn-tg5h
  Updated: Daily after midnight by CDOS (Colorado Dept of State)
  License: Public Domain — no API key required

Why Socrata instead of portal scraping:
  - The CO SoS portal advanced search triggers reCAPTCHA when automated
  - This API returns structured JSON directly with all needed fields
  - Updated daily so data is always current
  - No rate limiting on public domain datasets

Fields available:
  entityid, entityname, entitystatus, entityformdate,
  agentfirstname, agentmiddlename, agentlastname, agentsuffix,
  agentorganizationname, (+ full agent/principal addresses)

Query strategy:
  Search by agentfirstname + agentlastname (exact match, case-insensitive)
  OR by agentlastname only for surname-only terms
  OR by agentorganizationname for org-agent searches
"""

from __future__ import annotations

import logging
import urllib.parse
import urllib.request
import json
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── API Config ────────────────────────────────────────────────────────────────
DATASET_ID = "4ykn-tg5h"
BASE_URL = f"https://data.colorado.gov/resource/{DATASET_ID}.json"

# Fields to retrieve in each API call
SELECT_FIELDS = (
    "entityid,entityname,entitystatus,entityformdate,"
    "agentfirstname,agentmiddlename,agentlastname,agentsuffix,"
    "agentorganizationname"
)

# Default discovery terms (overridden by config in app)
DEFAULT_TERMS = [
    {"first": "Marcio", "last": "Garcia"},
    {"first": "Marcio", "last": "Andrade"},
    {"first": "Marcio", "last": None},   # all Marcios (broader)
]

# Statuses to EXCLUDE (these are definitively inactive)
SKIP_STATUSES = {
    "administratively dissolved",
    "judicially dissolved",
    "voluntarily dissolved",
    "revoked",
    "withdrawn",
    "expired",
}


# ── Data container ────────────────────────────────────────────────────────────

class COEntityRecord:
    """A business entity record from the Colorado Socrata API."""

    def __init__(self, row: dict):
        self.entity_id    = row.get("entityid", "").strip()
        self.entity_name  = row.get("entityname", "").strip()
        self.entity_status = row.get("entitystatus", "").strip()
        self.form_date    = row.get("entityformdate", "")
        self.agent_first  = row.get("agentfirstname", "").strip()
        self.agent_middle = row.get("agentmiddlename", "").strip()
        self.agent_last   = row.get("agentlastname", "").strip()
        self.agent_suffix = row.get("agentsuffix", "").strip()
        self.agent_org    = row.get("agentorganizationname", "").strip()

    @property
    def agent_full_name(self) -> str:
        parts = [self.agent_first, self.agent_middle, self.agent_last, self.agent_suffix]
        return " ".join(p for p in parts if p).strip() or self.agent_org

    @property
    def is_active(self) -> bool:
        return self.entity_status.lower() not in SKIP_STATUSES

    @property
    def clean_entity_name(self) -> str:
        """Strip status annotations appended to entity name by CDOS."""
        name = self.entity_name
        for marker in [", Dissolved", ", Delinquent", ", Revoked", ", Withdrawn"]:
            if marker in name:
                name = name[:name.index(marker)]
        return name.strip()

    def __repr__(self):
        return (f"<COEntity id={self.entity_id} "
                f"name='{self.clean_entity_name}' "
                f"status='{self.entity_status}' "
                f"agent='{self.agent_full_name}'>")


# ── API client ────────────────────────────────────────────────────────────────

def _socrata_query(params: dict, limit: int = 1000) -> list[dict]:
    """
    Execute a Socrata SODA API query and return rows as list of dicts.

    params: dict of field=value filters (exact match)
    limit:  max rows to return (default 1000; Socrata cap is 50000)
    """
    query_params = {**params, "$limit": str(limit), "$select": SELECT_FIELDS}
    qs = urllib.parse.urlencode(query_params)
    url = f"{BASE_URL}?{qs}"

    logger.debug("[CO-API] GET %s", url)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "CorporateCashCreditMonitor/1.0",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list):
                return data
            logger.warning("[CO-API] Unexpected response type: %s", type(data))
            return []
    except Exception as exc:
        logger.error("[CO-API] Request failed: %s | URL: %s", exc, url)
        return []


def _soql_query(where_clause: str, limit: int = 1000) -> list[dict]:
    """
    Execute a SoQL (Socrata Query Language) query for complex filters.
    Example: where_clause = "upper(agentlastname)='GARCIA'"
    """
    query_params = {
        "$where": where_clause,
        "$limit": str(limit),
        "$select": SELECT_FIELDS,
    }
    qs = urllib.parse.urlencode(query_params)
    url = f"{BASE_URL}?{qs}"

    logger.debug("[CO-API-SoQL] GET %s", url)
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "CorporateCashCreditMonitor/1.0",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data if isinstance(data, list) else []
    except Exception as exc:
        logger.error("[CO-API-SoQL] Request failed: %s", exc)
        return []


# ── Discovery functions ───────────────────────────────────────────────────────

def discover_by_agent_name(first: Optional[str], last: Optional[str],
                           include_inactive: bool = False,
                           limit: int = 500) -> list[COEntityRecord]:
    """
    Find all CO entities where agent first/last name matches.

    Examples:
      discover_by_agent_name("Marcio", "Garcia")   → exact first+last
      discover_by_agent_name("Marcio", None)        → all agents named Marcio
      discover_by_agent_name(None,     "Andrade")   → all agents surnamed Andrade
    """
    if not first and not last:
        return []

    conditions = []
    if first:
        conditions.append(f"upper(agentfirstname)='{first.upper()}'")
    if last:
        conditions.append(f"upper(agentlastname)='{last.upper()}'")

    where = " AND ".join(conditions)
    rows = _soql_query(where, limit=limit)

    records = [COEntityRecord(r) for r in rows]

    if not include_inactive:
        records = [r for r in records if r.is_active]

    logger.info("[CO-API] '%s %s' → %d entities (%d total before filter)",
                first or "*", last or "*", len(records), len(rows))
    return records


def discover_all_targets(terms: Optional[list[dict]] = None,
                         include_inactive: bool = False) -> list[COEntityRecord]:
    """
    Run discovery for all configured search terms.
    Returns deduplicated list of COEntityRecord sorted by form_date.

    terms format: [{"first": "Marcio", "last": "Garcia"}, ...]
    """
    if terms is None:
        terms = DEFAULT_TERMS

    seen_ids: set[str] = set()
    all_records: list[COEntityRecord] = []

    for term in terms:
        first = term.get("first")
        last  = term.get("last")
        logger.info("[CO-Discovery] Searching: first='%s' last='%s'", first, last)

        records = discover_by_agent_name(
            first=first,
            last=last,
            include_inactive=include_inactive,
        )
        for rec in records:
            if rec.entity_id not in seen_ids:
                seen_ids.add(rec.entity_id)
                all_records.append(rec)

    # Sort: active first, then by form date (oldest → newest)
    all_records.sort(key=lambda r: (
        0 if r.is_active else 1,
        r.form_date or "9999",
    ))

    logger.info("[CO-Discovery] Total unique entities found: %d", len(all_records))
    return all_records


def lookup_by_name(entity_name: str, limit: int = 10) -> list[COEntityRecord]:
    """
    Search for a specific entity name in the CO dataset.
    Uses LIKE query for partial match.
    Used by the scraper to verify/enrich a known entity name.
    """
    safe_name = entity_name.upper().replace("'", "''")
    where = f"upper(entityname) like '%{safe_name}%'"
    rows = _soql_query(where, limit=limit)
    return [COEntityRecord(r) for r in rows]


# ── Integration helper for scanner.py ────────────────────────────────────────

def run_co_discovery(discovery_terms: Optional[list[dict]] = None,
                     include_inactive: bool = False) -> list[dict]:
    """
    Entry point for the scanner.
    Returns list of dicts suitable for Corporation.upsert().

    Each dict has: name, state, status, source_file, corp_id, date_registered,
                   agent_name, agent_first, agent_last
    """
    terms = discovery_terms or DEFAULT_TERMS
    records = discover_all_targets(terms=terms, include_inactive=include_inactive)

    results = []
    for rec in records:
        results.append({
            "name":            rec.clean_entity_name,
            "state":           "CO",
            "status":          "Disponible" if rec.is_active else "Vendida",
            "source_file":     "co-socrata-api",
            "corp_id":         rec.entity_id,
            "agent_name":      rec.agent_full_name,
            "agent_first":     rec.agent_first,
            "agent_last":      rec.agent_last,
        })

    return results
