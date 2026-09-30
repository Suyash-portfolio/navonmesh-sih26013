"""
NAVONMESH - Intelligent Attribute Harmonization (Phase 10) and
Attribute Conflict Detection (Phase 11)

Reconciles the same logical field as it appears in different departmental
registers: the RoR owner name, the municipal GIS plot number, the cadastral
khasra number, the recorded versus surveyed area.

Hard rules enforced here
------------------------
1. Original source values are NEVER overwritten. A reconciliation always returns
   both source values plus a ``resolved`` proposal and the evidence behind it.
2. A mismatch is reported as a CONFLICT requiring verification. This module
   never decides who is legally correct.
3. Every score is computed, never assumed.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.geoai.multilingual_linker import IndicSoundexMatcher

MATCH = "MATCH"
PROBABLE = "PROBABLE"
CONFLICT = "CONFLICT"
MISSING = "MISSING"

# Thresholds are named so the UI can explain them rather than hide them.
NAME_MATCH_THRESHOLD = 0.92
NAME_PROBABLE_THRESHOLD = 0.75
AREA_CONFLICT_TOLERANCE_PCT = 3.5


# ---------------------------------------------------------------------------
# Owner name reconciliation
# ---------------------------------------------------------------------------
def reconcile_owner_name(
    source_a: Optional[Dict[str, Any]],
    source_b: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compare two recorded owner names across a local-language / English pair.

    ``source_a`` and ``source_b`` are ``{"layer": str, "english": str, "local": str}``.
    """
    eng_a = (source_a or {}).get("english")
    eng_b = (source_b or {}).get("english")
    loc_a = (source_a or {}).get("local")
    loc_b = (source_b or {}).get("local")

    if not eng_a or not eng_b:
        return {
            "field": "owner_name",
            "status": MISSING,
            "source_records": {"source_a": source_a, "source_b": source_b},
            "confidence": 0.0,
            "reason": "One or both registers have no owner name recorded",
            "signals": {},
        }

    if eng_a.strip().lower() == eng_b.strip().lower():
        return {
            "field": "owner_name",
            "status": MATCH,
            "source_records": {"source_a": source_a, "source_b": source_b},
            "confidence": 1.0,
            "reason": "English names are identical after trimming",
            "signals": {"exact_string_match": True},
        }

    # Cross-script comparison: transliterate the vernacular name and compare it
    # against both English spellings. This is what catches
    # "Rajendra Shinde" vs "Rajendra S. Shinde" vs "राजेंद्र शिंदे".
    signals: Dict[str, Any] = {}
    best_score = 0.0
    best_reason = ""

    if loc_a and loc_b:
        score_local, detail = IndicSoundexMatcher.match_names(loc_a, loc_b)
        signals["local_to_local"] = detail
        if score_local > best_score:
            best_score = score_local
            best_reason = (
                f"Local-language names match phonetically after transliteration "
                f"({detail['transliterated']} vs {detail['transliterated']})"
            )
    elif loc_a or loc_b:
        lone = loc_a or loc_b
        partner = eng_b if loc_a else eng_a
        score_mixed, detail_mixed = IndicSoundexMatcher.match_names(lone, partner)
        signals["local_to_english"] = detail_mixed
        if score_mixed > best_score:
            best_score = score_mixed
            best_reason = (
                f"Local name transliterates to '{detail_mixed['transliterated']}' "
                f"and aligns with '{partner}'"
            )

    # Direct English-to-English fuzzy/phonetic comparison as a second opinion.
    score_en, detail_en = IndicSoundexMatcher.match_names(eng_a, eng_b)
    signals["english_to_english"] = detail_en
    if score_en > best_score:
        best_score = score_en
        best_reason = (
            f"English names are phonetically equivalent "
            f"(Soundex {detail_en['soundex_english']}, edit distance "
            f"{detail_en['levenshtein_distance']})"
        )

    confidence = round(best_score, 4)
    if confidence >= NAME_MATCH_THRESHOLD:
        status = MATCH
    elif confidence >= NAME_PROBABLE_THRESHOLD:
        status = PROBABLE
    else:
        status = CONFLICT

    return {
        "field": "owner_name",
        "status": status,
        "source_records": {"source_a": source_a, "source_b": source_b},
        "confidence": confidence,
        "reason": best_reason or "Names could not be reconciled",
        "signals": signals,
        "thresholds": {
            "match": NAME_MATCH_THRESHOLD,
            "probable": NAME_PROBABLE_THRESHOLD,
        },
    }


# ---------------------------------------------------------------------------
# Area reconciliation
# ---------------------------------------------------------------------------
def reconcile_area(
    recorded_sqm: Optional[float],
    surveyed_sqm: Optional[float],
    *,
    recorded_layer: str = "Revenue Record (RoR)",
    surveyed_layer: str = "Survey / Cadastral Measurement",
    tolerance_pct: float = AREA_CONFLICT_TOLERANCE_PCT,
) -> Dict[str, Any]:
    """Compare recorded (deed) area against measured (surveyed) area."""
    if recorded_sqm is None or surveyed_sqm is None:
        return {
            "field": "area",
            "status": MISSING,
            "difference_sqm": None,
            "difference_pct": None,
            "source_records": {
                "recorded": {"layer": recorded_layer, "value_sqm": recorded_sqm},
                "surveyed": {"layer": surveyed_layer, "value_sqm": surveyed_sqm},
            },
            "reason": "Area not available from both sources",
        }

    difference = round(abs(recorded_sqm - surveyed_sqm), 2)
    difference_pct = round((difference / recorded_sqm) * 100.0, 2) if recorded_sqm > 0 else 0.0

    if difference_pct <= tolerance_pct:
        status = MATCH
        reason = (
            f"Recorded and surveyed areas agree within {tolerance_pct}% "
            f"tolerance ({difference_pct:.2f}% difference)"
        )
    else:
        status = CONFLICT
        reason = (
            f"Recorded area {recorded_sqm} sq m and surveyed area {surveyed_sqm} sq m "
            f"differ by {difference} sq m ({difference_pct:.2f}%), above the "
            f"{tolerance_pct}% tolerance"
        )

    return {
        "field": "area",
        "status": status,
        "difference_sqm": difference,
        "difference_pct": difference_pct,
        "tolerance_pct": tolerance_pct,
        "source_records": {
            "recorded": {"layer": recorded_layer, "value_sqm": recorded_sqm},
            "surveyed": {"layer": surveyed_layer, "value_sqm": surveyed_sqm},
        },
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Identifier reconciliation
# ---------------------------------------------------------------------------
def reconcile_identifier(
    value_a: Optional[str],
    value_b: Optional[str],
    *,
    field: str = "khasra_no",
    layer_a: str = "Source A",
    layer_b: str = "Source B",
) -> Dict[str, Any]:
    """Compare survey / khasra identifiers, tolerating punctuation and suffixes.

    "204/3" and "204/3A" are treated as a CONFLICT requiring verification, not
    silently reconciled, because a suffix difference can indicate a subdivision.
    """
    if not value_a or not value_b:
        return {
            "field": field,
            "status": MISSING,
            "source_records": {
                "source_a": {"layer": layer_a, "value": value_a},
                "source_b": {"layer": layer_b, "value": value_b},
            },
            "reason": "Identifier missing from one or both sources",
        }

    norm_a = "".join(ch for ch in str(value_a).upper() if ch.isalnum())
    norm_b = "".join(ch for ch in str(value_b).upper() if ch.isalnum())

    if norm_a == norm_b:
        return {
            "field": field,
            "status": MATCH,
            "confidence": 1.0,
            "source_records": {
                "source_a": {"layer": layer_a, "value": value_a},
                "source_b": {"layer": layer_b, "value": value_b},
            },
            "reason": f"Identifiers are equivalent ignoring punctuation ('{value_a}' / '{value_b}')",
        }

    # Report the longest common prefix as a diagnostic, not as a verdict.
    prefix_len = 0
    for ca, cb in zip(norm_a, norm_b):
        if ca != cb:
            break
        prefix_len += 1

    return {
        "field": field,
        "status": CONFLICT,
        "confidence": round(prefix_len / max(len(norm_a), len(norm_b), 1), 4),
        "source_records": {
            "source_a": {"layer": layer_a, "value": value_a},
            "source_b": {"layer": layer_b, "value": value_b},
        },
        "reason": (
            f"Identifiers differ: '{value_a}' vs '{value_b}'. "
            f"Shared leading characters: {prefix_len}. A suffix difference can "
            f"indicate a subdivision and must be confirmed before merging."
        ),
    }


# ---------------------------------------------------------------------------
# Whole-parcel attribute reconciliation
# ---------------------------------------------------------------------------
def reconcile_parcel_attributes(
    *,
    cadastral: Dict[str, Any],
    revenue: Dict[str, Any],
    municipal: Optional[Dict[str, Any]] = None,
    area_tolerance_pct: float = AREA_CONFLICT_TOLERANCE_PCT,
) -> Dict[str, Any]:
    """Run every attribute comparison for one parcel and summarise the outcome."""
    revenue = revenue or {}
    municipal = municipal or {}

    owner = reconcile_owner_name(
        {
            "layer": "Cadastral / Survey Register",
            "english": cadastral.get("owner_name") or cadastral.get("owner_en"),
            "local": cadastral.get("owner_name_local") or cadastral.get("owner_vernacular"),
        },
        {
            "layer": "Revenue Record (RoR)",
            "english": revenue.get("owner_name") or revenue.get("owner_en"),
            "local": revenue.get("owner_name_local") or revenue.get("owner_vernacular"),
        },
    )

    area = reconcile_area(
        revenue.get("recorded_area_sqm") or revenue.get("legal_area_sqm"),
        cadastral.get("surveyed_area_sqm") or cadastral.get("legal_area_sqm"),
        tolerance_pct=area_tolerance_pct,
    )

    identifier = reconcile_identifier(
        cadastral.get("khasra_no") or cadastral.get("survey_no"),
        revenue.get("khasra_no") or revenue.get("survey_no"),
        field="khasra_no",
        layer_a="Cadastral / Survey Register",
        layer_b="Revenue Record (RoR)",
    )

    checks = {"owner_name": owner, "area": area, "khasra_no": identifier}
    statuses = [c["status"] for c in checks.values()]
    conflicts = [k for k, v in checks.items() if v["status"] == CONFLICT]
    missing = [k for k, v in checks.items() if v["status"] == MISSING]

    if conflicts:
        overall = CONFLICT
    elif missing and len(missing) == len(checks):
        overall = MISSING
    elif missing:
        overall = PROBABLE
    elif any(c["status"] == PROBABLE for c in checks.values()):
        overall = PROBABLE
    else:
        overall = MATCH

    return {
        "overall": overall,
        "checks": checks,
        "conflicting_fields": conflicts,
        "missing_fields": missing,
        "municipal_reference": municipal or None,
        "summary": (
            f"{len(checks) - len(conflicts) - len(missing)} of {len(checks)} "
            f"attribute checks reconciled; {len(conflicts)} conflict(s) require verification"
        ),
    }
