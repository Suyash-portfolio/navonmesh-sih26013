"""
NAVONMESH - Data Standardization Service (Phase 2, stage: standardize)

Maps heterogeneous source columns onto the canonical unified land-record schema
declared in ``config.CANONICAL_PARCEL_SCHEMA``.

This is the stage that makes multi-source integration possible at all. The
legacy cadastre calls it ``Khasra``, the RoR export calls it ``Survey No``, the
municipal layer calls it ``Plot Number`` and the GNSS ledger calls it
``Parcel Ref``. All four are the same identity field; without this mapping step
no cross-source join is possible.

Every mapping decision is recorded and returned, because an unmapped field is
a gap in the record and must never be silently dropped.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import (
    CANONICAL_ALIASES,
    CANONICAL_FIELD_BY_ALIAS,
    CANONICAL_PARCEL_SCHEMA,
)

REQUIRED_FIELDS = [f["field"] for f in CANONICAL_PARCEL_SCHEMA if f.get("required")]

_NUMERIC_FIELDS = {"recorded_area_sqm", "surveyed_area_sqm"}
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalise_column(name: str) -> str:
    """Fold a raw header into the alias dictionary's key space."""
    folded = _WHITESPACE.sub(" ", str(name or "").strip().lower())
    return _NON_ALNUM.sub("_", folded).strip("_")


def match_column(column: str) -> Optional[str]:
    """Return the canonical field a raw column maps to, or None."""
    folded = normalise_column(column)
    if not folded:
        return None
    if folded in CANONICAL_FIELD_BY_ALIAS:
        return CANONICAL_FIELD_BY_ALIAS[folded]
    spaced = _WHITESPACE.sub(" ", str(column or "").strip().lower())
    if spaced in CANONICAL_FIELD_BY_ALIAS:
        return CANONICAL_FIELD_BY_ALIAS[spaced]
    # Last resort: token containment (e.g. "owner_name_english" -> owner_name).
    for alias, canonical in CANONICAL_FIELD_BY_ALIAS.items():
        if len(alias) > 3 and alias in folded:
            return canonical
    return None


def build_column_map(columns: List[str]) -> Dict[str, str]:
    """Map canonical field -> the raw column that supplies it.

    First writer wins, and the mapping is deterministic (input order), so two
    runs over the same file always produce the same map.
    """
    mapping: Dict[str, str] = {}
    for column in columns:
        canonical = match_column(column)
        if canonical and canonical not in mapping:
            mapping[canonical] = column
    return mapping


def coerce_number(value: Any) -> Optional[float]:
    """Parse an area-like value that may carry units or Indian digit grouping."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    # Strip Indian lakh/crore grouping and any trailing unit.
    text = text.replace(",", "").replace("sq.m", "").replace("sqm", "").replace("m2", "")
    text = re.sub(r"[^\d.\-]", "", text)
    if not text or text in {"-", ".", "-."}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def standardise_record(
    record: Dict[str, Any],
    column_map: Dict[str, str],
) -> Dict[str, Any]:
    """Project one raw record onto the canonical schema.

    Unknown source columns are preserved under ``_extra`` rather than dropped,
    so no source value is ever destroyed (Phase 10 requirement).
    """
    out: Dict[str, Any] = {}
    consumed: set = set()

    for canonical, source_column in column_map.items():
        raw = record.get(source_column)
        consumed.add(source_column)
        if canonical in _NUMERIC_FIELDS:
            out[canonical] = coerce_number(raw)
        else:
            text = None if raw is None else str(raw).strip()
            out[canonical] = text or None

    for key, value in record.items():
        if key not in consumed and not str(key).startswith("geometry"):
            out.setdefault("_extra", {})[key] = value
    return out


def standardise_frame(
    records: List[Dict[str, Any]],
    source_layer: str,
) -> Dict[str, Any]:
    """Standardise a whole tabular layer and report what could not be resolved."""
    columns: List[str] = []
    for record in records:
        for key in record:
            if key not in columns and not str(key).startswith("geometry"):
                columns.append(key)

    column_map = build_column_map(columns)
    rows = [standardise_record(r, column_map) for r in records]

    missing = [f for f in REQUIRED_FIELDS if not any(r.get(f) for r in rows)]
    unmapped = [c for c in columns if c not in column_map]

    # Fill per-field fill-rate so the quality gate can compute completeness.
    fill_rate: Dict[str, float] = {}
    for field in CANONICAL_PARCEL_SCHEMA:
        name = field["field"]
        present = sum(1 for r in rows if r.get(name) not in (None, ""))
        fill_rate[name] = round(present / len(rows), 4) if rows else 0.0

    return {
        "source_layer": source_layer,
        "column_map": column_map,
        "mapped_fields": sorted(column_map),
        "unmapped_columns": unmapped,
        "missing_required_fields": missing,
        "field_fill_rate": fill_rate,
        "row_count": len(rows),
        "rows": rows,
    }


def describe_schema() -> List[Dict[str, Any]]:
    """The canonical schema, annotated with every accepted source alias."""
    described = []
    for field in CANONICAL_PARCEL_SCHEMA:
        name = field["field"]
        described.append(
            {
                **field,
                "accepted_aliases": CANONICAL_ALIASES.get(name, []),
            }
        )
    return described


def schema_compatibility(columns: List[str]) -> Dict[str, Any]:
    """Phase 6 gate input: how well does a layer match the canonical schema?"""
    column_map = build_column_map(columns)
    required_hit = [f for f in REQUIRED_FIELDS if f in column_map]
    optional_fields = [f["field"] for f in CANONICAL_PARCEL_SCHEMA if not f.get("required")]
    optional_hit = [f for f in optional_fields if f in column_map]

    total = len(CANONICAL_PARCEL_SCHEMA)
    score = (len(required_hit) + len(optional_hit)) / total if total else 0.0
    if not required_hit:
        verdict = "INCOMPATIBLE"
    elif len(required_hit) < len(REQUIRED_FIELDS):
        verdict = "PARTIAL"
    elif len(optional_hit) >= len(optional_fields) * 0.5:
        verdict = "COMPATIBLE"
    else:
        verdict = "USABLE"

    return {
        "score": round(score, 4),
        "verdict": verdict,
        "required_present": required_hit,
        "required_missing": [f for f in REQUIRED_FIELDS if f not in column_map],
        "optional_present": optional_hit,
        "column_map": column_map,
    }
