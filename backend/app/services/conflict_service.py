"""
NAVONMESH - Spatial & Attribute Conflict Engine (Phase 12)

Detects every class of disagreement between departmental layers and files each
one as an auditable conflict record with an explicit status lifecycle.

Conflict types (from ``config.CONFLICT_TYPES``)
    parcel_vs_road_row        parcel_vs_drainage      parcel_vs_utility
    building_vs_parcel        legacy_vs_modern        area_mismatch
    duplicate_parcel          boundary_shift          missing_parcel
    attribute_conflict

Status lifecycle
    OPEN  ->  UNDER_REVIEW  ->  VERIFIED  ->  RESOLVED
                     |
                     +-------------->  REQUIRES_FIELD_SURVEY

This module detects and describes. It never resolves by fiat: accepting a
harmonized geometry is an explicit human action recorded in the audit log.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence

from shapely.geometry.base import BaseGeometry

from app.services import matching_service as matching

OPEN = "OPEN"
UNDER_REVIEW = "UNDER_REVIEW"
VERIFIED = "VERIFIED"
RESOLVED = "RESOLVED"
REQUIRES_FIELD_SURVEY = "REQUIRES_FIELD_SURVEY"

VALID_TRANSITIONS: Dict[str, List[str]] = {
    OPEN: [UNDER_REVIEW, VERIFIED, RESOLVED, REQUIRES_FIELD_SURVEY],
    UNDER_REVIEW: [VERIFIED, RESOLVED, REQUIRES_FIELD_SURVEY, OPEN],
    VERIFIED: [RESOLVED, REQUIRES_FIELD_SURVEY, UNDER_REVIEW],
    REQUIRES_FIELD_SURVEY: [UNDER_REVIEW, VERIFIED, RESOLVED],
    RESOLVED: [UNDER_REVIEW],
}

CONFLICT_ACTIONS = [
    "review_on_map",
    "compare_sources",
    "accept_harmonized_geometry",
    "retain_existing_geometry",
    "send_for_field_verification",
]


def _severity(overlap_ratio: float, area_sqm: float) -> str:
    """Severity from measured overlap, not from a fixed severity table."""
    if area_sqm >= 50 or overlap_ratio >= 0.25:
        return "HIGH"
    if area_sqm >= 10 or overlap_ratio >= 0.05:
        return "MEDIUM"
    return "LOW"


def detect_linear_encroachment(
    *,
    parcel_id: str,
    parcel_geometry: BaseGeometry,
    line_geometry: BaseGeometry,
    line_layer: str,
    conflict_type: str,
    buffer_m: float,
    parcel_area_sqm: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Detect a parcel intersecting a buffered linear asset (road ROW, drain, utility).

    Returns ``None`` when the buffered line does not touch the parcel, so that
    the conflict count reflects real detections rather than a target number.
    """
    if parcel_geometry is None or parcel_geometry.is_empty or line_geometry is None:
        return None
    intersection = _safe_intersection(parcel_geometry, line_geometry.buffer(buffer_m))
    if intersection is None or intersection.is_empty or intersection.area <= 0:
        return None

    # Projected CRS assumed - area is already in square metres.
    overlap_sqm = round(float(intersection.area), 2)
    parcel_area = parcel_area_sqm if parcel_area_sqm else float(parcel_geometry.area)
    overlap_ratio = round(overlap_sqm / parcel_area, 4) if parcel_area > 0 else 0.0

    return {
        "parcel_id": parcel_id,
        "conflict_type": conflict_type,
        "severity": _severity(overlap_ratio, overlap_sqm),
        "source_layers": [line_layer],
        "buffer_m": buffer_m,
        "overlap_sqm": overlap_sqm,
        "overlap_ratio": overlap_ratio,
        "geometry_difference": _to_geojson(intersection),
        "status": OPEN,
        "detail": (
            f"Parcel overlaps the {buffer_m} m statutory buffer of the "
            f"{line_layer} by {overlap_sqm} sq m "
            f"({overlap_ratio * 100:.1f}% of the parcel)"
        ),
        "confidence": round(min(0.99, 0.55 + 0.4 * min(1.0, overlap_ratio * 3)), 4),
    }


def detect_building_relation(
    *,
    parcel_id: str,
    parcel_geometry: BaseGeometry,
    building_geometry: BaseGeometry,
    building_id: str,
    parcel_area_sqm: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Classify a building footprint against its parcel (Phase 15).

    Verdict vocabulary is deliberately descriptive, not legal:
    INSIDE / INTERSECTS / CROSSES_BOUNDARY / OUTSIDE.
    """
    if parcel_geometry is None or building_geometry is None:
        return None
    inter = _safe_intersection(parcel_geometry, building_geometry)
    if inter is None:
        return None
    inter_area = float(inter.area)
    try:
        build_area = float(building_geometry.area)
    except Exception:
        return None
    if build_area <= 0:
        return None

    coverage = inter_area / build_area
    tolerance = 0.02  # 2% tolerance for survey digitising noise

    if coverage >= 1.0 - tolerance:
        verdict = "INSIDE"
    elif coverage <= tolerance:
        verdict = "OUTSIDE"
    else:
        # Crosses only if the building actually straddles the parcel edge.
        ring = _safe_difference(parcel_geometry.buffer(0.05), parcel_geometry)
        straddles = ring is not None and not ring.is_empty
        verdict = "CROSSES_BOUNDARY" if straddles else "INTERSECTS"

    is_conflict = verdict in {"CROSSES_BOUNDARY"}
    return {
        "parcel_id": parcel_id,
        "building_id": building_id,
        "relation": verdict,
        "building_coverage": round(coverage, 4),
        "intersection_sqm": round(inter_area, 2),
        "is_conflict": is_conflict,
        "geometry_difference": _to_geojson(
            _safe_difference(building_geometry, parcel_geometry)
            if verdict == "CROSSES_BOUNDARY"
            else None
        ),
    }


def detect_boundary_shift(
    *,
    parcel_id: str,
    legacy_geometry: BaseGeometry,
    modern_geometry: BaseGeometry,
    shift_threshold_m: float = 0.5,
    area_threshold_pct: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """Phase 16: quantify how far a boundary has moved between two epochs."""
    if legacy_geometry is None or modern_geometry is None:
        return None
    iou_value = matching.iou(legacy_geometry, modern_geometry)
    shift = matching.centroid_displacement_m(legacy_geometry, modern_geometry)
    area_ratio = matching.area_ratio(legacy_geometry, modern_geometry)
    area_delta_pct = round((1.0 - (area_ratio or 0.0)) * 100.0, 2)

    shifted = (shift is not None and shift > shift_threshold_m) or (
        area_delta_pct > area_threshold_pct
    )
    if not shifted:
        return None

    return {
        "parcel_id": parcel_id,
        "iou": round(iou_value, 4),
        "centroid_shift_m": shift,
        "area_delta_pct": area_delta_pct,
        "shift_threshold_m": shift_threshold_m,
        "geometry_difference": _to_geojson(
            _safe_symmetric_difference(legacy_geometry, modern_geometry)
        ),
        "verdict": "POSSIBLE_CHANGE",
        "note": "Detected difference between two survey epochs - requires verification",
    }


def detect_duplicates(
    features: Sequence[Dict[str, Any]],
    *,
    iou_threshold: float = 0.80,
) -> List[Dict[str, Any]]:
    """Flag near-coincident parcels that may be the same landholding recorded twice."""
    duplicates: List[Dict[str, Any]] = []
    for i in range(len(features)):
        for j in range(i + 1, len(features)):
            a, b = features[i], features[j]
            ga, gb = a.get("geometry"), b.get("geometry")
            if ga is None or gb is None:
                continue
            score = matching.iou(ga, gb)
            if score >= iou_threshold:
                duplicates.append(
                    {
                        "parcel_ids": [a.get("id"), b.get("id")],
                        "iou": round(score, 4),
                        "threshold": iou_threshold,
                        "detail": (
                            f"Parcels {a.get('id')} and {b.get('id')} overlap by "
                            f"{score * 100:.1f}% - possible duplicate record"
                        ),
                    }
                )
    return duplicates


def from_attribute_check(
    *,
    parcel_id: str,
    check: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Turn a Phase 11 attribute conflict into a conflict record."""
    if check.get("status") != "CONFLICT":
        return None
    sources = check.get("source_records") or {}
    layers = sorted(
        {
            v.get("layer")
            for v in sources.values()
            if isinstance(v, dict) and v.get("layer")
        }
    )
    return {
        "parcel_id": parcel_id,
        "conflict_type": "attribute_conflict",
        "severity": "MEDIUM",
        "source_layers": layers,
        "field": check.get("field"),
        "status": OPEN,
        "detail": check.get("reason"),
        "confidence": check.get("confidence"),
        "source_records": sources,
    }


def _to_geojson(geom: Optional[BaseGeometry]) -> Optional[Dict[str, Any]]:
    if geom is None or geom.is_empty:
        return None
    try:
        from shapely.geometry import mapping

        return mapping(geom)
    except Exception:
        return None


def _safe_difference(a: BaseGeometry, b: BaseGeometry) -> Optional[BaseGeometry]:
    """``a - b`` that repairs inputs first.

    Legacy cadastral rings are frequently self-intersecting, and GEOS raises
    TopologyException on set operations against them. Repairing here means one
    invalid ring cannot abort detection for a whole ward.
    """
    from app.services.topology_service import make_valid

    left = a if (a is not None and a.is_valid) else make_valid(a)
    right = b if (b is not None and b.is_valid) else make_valid(b)
    if left is None or right is None:
        return None
    try:
        return left.difference(right)
    except Exception:
        return None


def _safe_symmetric_difference(a: BaseGeometry, b: BaseGeometry) -> Optional[BaseGeometry]:
    from app.services.topology_service import make_valid

    left = a if (a is not None and a.is_valid) else make_valid(a)
    right = b if (b is not None and b.is_valid) else make_valid(b)
    if left is None or right is None:
        return None
    try:
        return left.symmetric_difference(right)
    except Exception:
        return None


def _safe_intersection(a: BaseGeometry, b: BaseGeometry) -> Optional[BaseGeometry]:
    from app.services.topology_service import make_valid

    left = a if (a is not None and a.is_valid) else make_valid(a)
    right = b if (b is not None and b.is_valid) else make_valid(b)
    if left is None or right is None:
        return None
    try:
        return left.intersection(right)
    except Exception:
        return None


def summarise(conflicts: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Distribution statistics for the conflict dashboard."""
    items = list(conflicts)
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    for item in items:
        by_type[item.get("conflict_type", "unknown")] = by_type.get(item.get("conflict_type", "unknown"), 0) + 1
        by_severity[item.get("severity", "UNKNOWN")] = by_severity.get(item.get("severity", "UNKNOWN"), 0) + 1
        by_status[item.get("status", OPEN)] = by_status.get(item.get("status", OPEN), 0) + 1
    return {
        "total": len(items),
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "by_severity": by_severity,
        "by_status": by_status,
    }


def transition_allowed(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])


def transition_error(current: str, target: str) -> str:
    allowed = VALID_TRANSITIONS.get(current, [])
    return (
        f"Cannot move a conflict from '{current}' to '{target}'. "
        f"Allowed next states: {', '.join(allowed) if allowed else 'none'}."
    )
