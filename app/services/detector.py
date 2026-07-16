"""
app/services/detector.py

Detection engine for Corporate Cash Credit Monitor.

Rule (from process.md §4):
  Flag as "Potential Theft" when the officer/president name does NOT contain BOTH:
    - "Marcio"  (required)
    - "Garcia"  OR  "Andrade"  (at least one)

  CLEAR  → name contains "Marcio" AND ("Garcia" OR "Andrade")
  FLAGGED → anything else
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.normalizer import contains_term, extract_names, normalize


# ─── Result type ──────────────────────────────────────────────────────────────

@dataclass
class DetectionResult:
    is_theft: bool           # True = "Potential Theft"
    status: str              # "Clear" | "Flagged"
    reason: str              # Human-readable explanation
    matched_required: bool   # "Marcio" found?
    matched_alternate: bool  # "Garcia" or "Andrade" found?
    checked_names: list[str] # All name strings that were evaluated


# ─── Core detection ───────────────────────────────────────────────────────────

def detect(
    officer_name: str | None,
    registered_agent: str | None = None,
    required: str = "Marcio",
    alternates: list[str] | None = None,
) -> DetectionResult:
    """
    Apply the detection rule to a corporation's officer/agent data.

    Parameters
    ----------
    officer_name : str | None
        Raw officer/president name extracted from the portal.
    registered_agent : str | None
        Raw registered agent name (used as fallback / secondary check).
    required : str
        The term that MUST be present (default: "Marcio").
    alternates : list[str] | None
        At least one of these must be present (default: ["Garcia", "Andrade"]).

    Returns
    -------
    DetectionResult
    """
    if alternates is None:
        alternates = ["Garcia", "Andrade"]

    # Collect all name strings to check (officer + agent)
    raw_names: list[str] = []
    for raw in [officer_name, registered_agent]:
        if raw:
            raw_names.extend(extract_names(raw))

    if not raw_names:
        # No data at all — flag as theft (unknown officer = suspicious)
        return DetectionResult(
            is_theft=True,
            status="Flagged",
            reason="No se pudo extraer el nombre del oficial/agente del portal.",
            matched_required=False,
            matched_alternate=False,
            checked_names=[],
        )

    # Combine all names into one searchable string for global match
    combined = " ".join(raw_names)

    matched_required = contains_term(combined, required)
    matched_alternate = any(contains_term(combined, alt) for alt in alternates)

    is_clean = matched_required and matched_alternate
    is_theft = not is_clean

    if is_clean:
        reason = (
            f"Oficial válido detectado: '{required}' y "
            f"({' / '.join(alternates)}) encontrados en: {', '.join(raw_names)}"
        )
        status = "Clear"
    elif not matched_required:
        reason = (
            f"'{required}' NO encontrado en los nombres del oficial/agente. "
            f"Nombres detectados: {', '.join(raw_names)}"
        )
        status = "Flagged"
    else:
        # required found but no alternate
        alts_str = " / ".join(f"'{a}'" for a in alternates)
        reason = (
            f"'{required}' encontrado pero ninguno de {alts_str} presente. "
            f"Nombres detectados: {', '.join(raw_names)}"
        )
        status = "Flagged"

    return DetectionResult(
        is_theft=is_theft,
        status=status,
        reason=reason,
        matched_required=matched_required,
        matched_alternate=matched_alternate,
        checked_names=raw_names,
    )


# ─── Convenience wrapper ──────────────────────────────────────────────────────

def is_potential_theft(
    officer_name: str | None,
    registered_agent: str | None = None,
) -> tuple[bool, str]:
    """
    Simplified wrapper that returns (is_theft: bool, reason: str).

    Uses detection constants from app config when available; falls back
    to hardcoded defaults ("Marcio", ["Garcia", "Andrade"]).
    """
    try:
        from flask import current_app
        required   = current_app.config.get("DETECTION_REQUIRED", "Marcio")
        alternates = current_app.config.get("DETECTION_ALTERNATES", ["Garcia", "Andrade"])
    except RuntimeError:
        # No Flask app context (e.g., unit tests)
        required   = "Marcio"
        alternates = ["Garcia", "Andrade"]

    result = detect(officer_name, registered_agent, required, alternates)
    return result.is_theft, result.reason
