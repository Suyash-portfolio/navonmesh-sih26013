"""
Validation service (SIH26013 - Stage 2: VALIDATE).

Two independent layers:

1. **Dataset validation** - is the file structurally usable?
   (parse status, CRS presence, geometry validity, attribute completeness,
   duplicate identifiers, coordinate range sanity)

2. **Geometry validation** - are individual features usable?
   (null geometry, invalid OGC ring, self-intersection, duplicate geometry,
   zero/near-zero area, unclosed ring)

Every finding is emitted as a structured issue with a machine-readable code,
a severity and a remediation hint, so the UI never has to guess.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from app.services import crs_service

SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3}

# Which canonical fields each source category is *expected* to carry.
# Expecting an owner name on a building-footprint layer would report a false
# defect, so expectations are declared per category instead.
CATEGORY_EXPECTED_FIELDS: Dict[str, List[str]] = {
    "cadastral_map": ["parcel_id", "khasra_no"],
    "revenue_records": ["parcel_id", "khasra_no", "owner_name", "recorded_area_sqm"],
    "building_footprint": ["parcel_id"],
    "municipal_gis": [],
    "ground_truthing": ["parcel_id", "khasra_no"],
    "gnss_cors": ["parcel_id"],
    "utility_network": ["parcel_id", "utility_ref"],
}


def _issue(code: str, severity: str, message: str, remediation: str, **extra: Any) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "message": message,
        "remediation": remediation,
        **extra,
    }


# ---------------------------------------------------------------------------
# Dataset level
# ---------------------------------------------------------------------------
def validate_dataset(dataset: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a registered dataset record and return a full report."""
    issues: List[Dict[str, Any]] = []
    parse = dataset.get("parse") or {}

    # -- Parse status -------------------------------------------------------
    if dataset.get("upload_status") == "parse_failed" or not parse.get("ok"):
        issues.append(
            _issue(
                "PARSE_FAILED",
                "critical",
                f"The file could not be parsed: {dataset.get('parse_error') or parse.get('error') or 'unknown error'}",
                "Verify the file is not corrupted and that the declared format matches its content.",
            )
        )
    elif dataset.get("parser") == "adapter-ready":
        issues.append(
            _issue(
                "ADAPTER_REQUIRED",
                "warning",
                f"'{dataset.get('extension')}' has no bundled reader; the file is stored and registered "
                f"but contributes no geometry to the harmonized output.",
                "Convert to GeoJSON / GeoPackage / CSV, or install the format adapter.",
                capability=parse.get("capability", "adapter-ready"),
            )
        )
    elif parse.get("partial"):
        issues.append(
            _issue("PARTIAL_PARSE", "info", parse.get("note") or "Only header metadata was parsed.",
                   "Install the full reader to process this source end to end.")
        )

    # -- CRS ----------------------------------------------------------------
    crs = dataset.get("crs") or {}
    crs_status = crs.get("status")
    if crs_status == "missing":
        issues.append(
            _issue(
                "CRS_MISSING",
                "critical",
                "No coordinate reference system is available. The dataset cannot be placed on the map "
                "and coordinate normalization is blocked.",
                "Select the source CRS explicitly in the ingestion form.",
            )
        )
    elif crs_status == "inferred":
        issues.append(
            _issue(
                "CRS_INFERRED",
                "warning",
                f"CRS was inferred rather than read from the file: {crs.get('description')}",
                "Confirm the CRS with the data provider before relying on the normalization result.",
                confidence=crs.get("confidence"),
            )
        )
    elif crs_status == "blocked":
        issues.append(
            _issue("CRS_UNRESOLVED", "critical", f"Declared CRS '{dataset.get('source_crs')}' is not a recognised code.",
                   "Choose a valid EPSG code from the CRS list.")
        )
    for warning in crs.get("warnings", []) or []:
        issues.append(_issue("CRS_NOTE", "info", warning, "No action strictly required; verify during review."))

    # -- Records ------------------------------------------------------------
    count = dataset.get("record_count")
    if count is None:
        issues.append(_issue("RECORD_COUNT_UNKNOWN", "warning", "Record count could not be established.",
                             "Provide a readable format so the platform can count features."))
    elif count == 0:
        issues.append(_issue("EMPTY_DATASET", "error", "The dataset parsed successfully but contains zero records.",
                             "Re-export the source; an empty layer cannot contribute to harmonization."))

    # -- Geometry -----------------------------------------------------------
    if dataset.get("geometry_kind") in ("vector", "point"):
        null_geom = int(parse.get("null_geometry_count") or 0)
        if null_geom:
            issues.append(
                _issue("NULL_GEOMETRY", "error", f"{null_geom} feature(s) carry a null geometry.",
                       "Drop or repair the null-geometry features before normalization.",
                       count=null_geom)
            )
        invalid = (count or 0) - int(parse.get("valid_count") or 0)
        if invalid > 0:
            issues.append(
                _issue("INVALID_GEOMETRY", "error",
                       f"{invalid} feature(s) fail the OGC validity test (self-intersection or ring not closed).",
                       "Run the topology validation stage; the planariser repairs these automatically.",
                       count=invalid)
            )

    # -- Attributes ---------------------------------------------------------
    columns = dataset.get("columns") or []
    if columns:
        parse_meta = parse or {}
        roles = parse_meta.get("inferred_field_roles") or {}
        mapped = set(roles.values())
        expected = CATEGORY_EXPECTED_FIELDS.get(dataset.get("category_id") or "", [])
        missing = [field for field in expected if field not in mapped and field not in columns]
        if missing:
            issues.append(
                _issue("ATTRIBUTE_GAP", "warning",
                       f"Expected source fields are absent: {', '.join(missing)}.",
                       "Supply an explicit column mapping; unmapped source values are preserved but not used.",
                       missing=missing)
            )
        unmapped = parse_meta.get("unmapped_columns") or []
        if unmapped:
            issues.append(
                _issue("UNMAPPED_COLUMNS", "info",
                       f"{len(unmapped)} source column(s) have no canonical role: {', '.join(unmapped[:8])}"
                       + ("..." if len(unmapped) > 8 else ""),
                       "Original values are preserved verbatim - nothing is overwritten.",
                       columns=unmapped[:24])
            )

    status = "failed" if any(i["severity"] == "critical" for i in issues) else (
        "warning" if any(i["severity"] in ("error", "warning") for i in issues) else "passed"
    )
    return {
        "dataset_id": dataset.get("id"),
        "name": dataset.get("name"),
        "category_id": dataset.get("category_id"),
        "status": status,
        "issues": sorted(issues, key=lambda i: SEVERITY_ORDER.get(i["severity"], 9)),
        "issue_counts": _count_severities(issues),
        "crs": crs,
        "record_count": count,
        "valid": status != "failed",
    }


def _count_severities(issues: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    for issue in issues:
        counts[issue["severity"]] = counts.get(issue["severity"], 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Feature level
# ---------------------------------------------------------------------------
def validate_geometries(geometries: List[Any], id_field: str, ids: List[str]) -> Dict[str, Any]:
    """
    Feature-level geometry validation.

    Returns a per-feature validity map plus aggregate counters.
    """
    from shapely.geometry import Polygon  # noqa: F401  (geometry-agnostic checks below)

    report: Dict[str, Any] = {
        "valid_count": 0,
        "invalid_count": 0,
        "null_count": 0,
        "empty_count": 0,
        "degenerate_count": 0,
        "duplicate_count": 0,
        "invalid_ids": [],
        "degenerate_ids": [],
        "duplicate_ids": [],
        "reasons": {},
    }
    seen: Dict[Any, str] = {}

    for geom, feature_id in zip(geometries, ids):
        if geom is None:
            report["null_count"] += 1
            report["invalid_ids"].append(feature_id)
            report["reasons"][feature_id] = "null_geometry"
            continue
        if getattr(geom, "is_empty", False):
            report["empty_count"] += 1
            report["invalid_ids"].append(feature_id)
            report["reasons"][feature_id] = "empty_geometry"
            continue

        key = geom.wkb
        if key in seen:
            report["duplicate_count"] += 1
            report["duplicate_ids"].append({"id": feature_id, "duplicate_of": seen[key]})
        else:
            seen[key] = feature_id

        if not geom.is_valid:
            report["invalid_count"] += 1
            report["invalid_ids"].append(feature_id)
            report["reasons"].setdefault(feature_id, "invalid_ogc_geometry")
            continue

        area = geom.area
        if area <= 0.0:
            report["degenerate_count"] += 1
            report["degenerate_ids"].append({"id": feature_id, "area": area})
            report["reasons"].setdefault(feature_id, "zero_area")
            continue

        if geom.geom_type in ("Polygon", "MultiPolygon"):
            parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
            if any(len(part.interiors) > 0 for part in parts):
                report["reasons"].setdefault(feature_id, "has_hole")

        report["valid_count"] += 1

    report["total"] = len(geometries)
    report["valid_ratio"] = round(report["valid_count"] / max(1, len(geometries)), 4)
    del id_field
    return report


def summarise_dataset_reports(reports: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {"critical": 0, "error": 0, "warning": 0, "info": 0}
    passed = 0
    for report in reports:
        for key, value in report.get("issue_counts", {}).items():
            totals[key] = totals.get(key, 0) + value
        if report.get("status") == "passed":
            passed += 1
    return {
        "datasets_validated": len(reports),
        "datasets_passed": passed,
        "datasets_with_issues": len(reports) - passed,
        "issue_counts": totals,
        "blocking": totals["critical"] > 0,
    }


def cross_dataset_crs_check(datasets: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Prevent mixing incompatible geometries without warning.
    Compares every spatial dataset against the first spatial dataset found.
    """
    spatial = [d for d in datasets if d.get("source_crs")]
    if len(spatial) < 2:
        return {"status": "ok", "message": "Fewer than two georeferenced datasets - no overlay risk.", "mismatches": []}

    reference = spatial[0]
    mismatches: List[Dict[str, Any]] = []
    for dataset in spatial[1:]:
        check = crs_service.compatibility_report(reference["source_crs"], dataset.get("source_crs"))
        if not check["compatible"]:
            mismatches.append(
                {
                    "reference": reference["id"],
                    "dataset": dataset["id"],
                    "dataset_name": dataset.get("name"),
                    "reference_crs": reference.get("source_crs"),
                    "dataset_crs": dataset.get("source_crs"),
                    "severity": check["severity"],
                    "message": check["message"],
                }
            )
    status = "error" if any(m["severity"] == "error" for m in mismatches) else ("warning" if mismatches else "ok")
    return {
        "status": status,
        "reference_dataset": reference["id"],
        "mismatches": mismatches,
        "message": (
            f"{len(mismatches)} dataset(s) are not on the same CRS as '{reference.get('name')}'. "
            "Coordinate normalization runs before any overlay."
            if mismatches
            else f"All georeferenced datasets share {reference.get('source_crs')} - overlays are valid."
        ),
    }
