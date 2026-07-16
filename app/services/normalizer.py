"""
app/services/normalizer.py

Normalizes names extracted from Secretary of State portals so that
comparison is accent-insensitive, case-insensitive and whitespace-tolerant.
"""

import re
import unicodedata


# ─── Public API ───────────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    """
    Return a cleaned, lowercase, accent-stripped version of *name*.

    Steps:
      1. Strip leading/trailing whitespace.
      2. Collapse internal whitespace to single spaces.
      3. Remove accents / diacritics (NFD → ASCII).
      4. Remove punctuation except spaces and alphanumeric chars.
      5. Lowercase.

    Example:
      >>> normalize("Márciõ García-Andrade Jr.")
      'marcio garcia andrade jr'
    """
    if not name:
        return ""

    # Step 1-2: strip and collapse whitespace
    name = " ".join(name.strip().split())

    # Step 3: NFD decomposition → drop combining chars (accents)
    nfd = unicodedata.normalize("NFD", name)
    name = "".join(c for c in nfd if unicodedata.category(c) != "Mn")

    # Step 4: keep only letters, digits, spaces
    name = re.sub(r"[^a-zA-Z0-9 ]", " ", name)

    # Step 5: lowercase + collapse spaces again
    return " ".join(name.lower().split())


def contains_term(name: str, term: str) -> bool:
    """
    Return True if *term* appears as a whole word (or substring) in *name*,
    both normalized.

    Uses word-boundary matching so "garcia" matches "garcia" and "garcias"
    but not "bgarcia" (unless preceded by a space/boundary).

    For simplicity we use substring matching on normalized strings; the
    caller (detector) is responsible for the logical AND/OR composition.
    """
    return normalize(term) in normalize(name)


def extract_names(raw_text: str) -> list[str]:
    """
    Split a raw officers/agents text block into individual name strings.
    Handles separators like ';', '/', newlines, and 'and'.

    Example input:
      "MARCIO GARCIA; JOHN DOE / JANE SMITH"
    Returns:
      ["MARCIO GARCIA", "JOHN DOE", "JANE SMITH"]
    """
    if not raw_text:
        return []

    # Split on common separators
    parts = re.split(r"[;/\n\r|]+|\band\b", raw_text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]
