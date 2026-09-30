"""
NAVONMESH - Change Detection (Phase 16)

Compares two survey epochs and classifies what changed, using measured
geometry rather than assumptions.

Change vocabulary is deliberately non-accusatory
-----------------------------------------------
    NEW / REMOVED / MODIFIED / BOUNDARY_SHIFT / POSSIBLE_ENCROACHMENT /
    LAND_USE_CHANGE

Nothing here is labelled "illegal". Every detection carries a
"requires verification" flag, because a difference between two survey epochs is
a fact about the data, not a determination about the people living on it.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from shapely.geometry.base import BaseGeometry

from app.services import matching_service as matching

NEW = "NEW"
REMOVED = "REMOVED"
MODIFIED = "MODIFIED"
BOUNDARY_SHIFT = "BOUNDARY_SHIFT"
POSSIBLE_ENCROACHMENT = "POSSIBLE_ENCROACHMENT"
LAND_USE_CHANGE = "LAND_USE_CHANGE"

CHANGE_TYPES = [NEW, REMOVED, MODIFIED, BOUNDARY_SHIFT, POSSIBLE_ENCROACHMENT, LAND_USE_CHANGE]

DESCRIPTION = {
    NEW: "Parcel present in the later epoch but absent from the earlier epoch",
    REMOVED: "Parcel present in the earlier epoch but absent from the later epoch",
    MODIFIED: "Parcel footprint materially different between epochs",
    BOUNDARY_SHIFT: "Parcel centroid or extent moved beyond the survey tolerance",
    POSSIBLE_ENCROACHMENT: "Later footprint overlaps a statutory corridor - requires verification",
    LAND_USE_CHANGE: "Land-use classification differs between epochs",
}


def detect_building_change(
    *,
    parcel_id: str,
    previous_geometry: Optional[BaseGeometry],
    current_geometry: Optional[BaseGeometry],
    shift_threshold_m: float = 0.5,
    area_threshold_pct: float = 2.0,
) -> Optional[Dict[str, Any]]:
    """Compare a building footprint across epochs (Phase 15 'changed since survey')."""
    if previous_geometry is None and current_geometry is None:
        return None
    if previous_Geometry is None:
        return {
            "parcel_id": parcel_id,
            "change_type": NEW,
            "confidence": 1.0,
            "description": DESCRIPTION[NEW],
            "requires_verification": True,
            "area_delta_pct": 100.0,
        }
    if current_geometry is None:
        return {
            "parcel_id": parcel_id,
            "change_type": REMOVED,
            "confidence": 1.0,
            "description": DESCRIPTION[REMOVED],
            "requires_verification": True,
            "area_delta_pct": -100.0,
        }

    iou_value = matching.iou(previous_geometry, current_geometry)
    shift = matching.centroid_displacement_m(previous_geometry, current_geometry)
    ratio = matching.area_ratio(previous_geometry, current_geometry)
    area_delta_pct = round((1.0 - (ratio or 0.0)) * 100.0, 2)

    if iou_value >= 0.98 and (shift or 0.0) <= shift_threshold_m and area_delta_pct <= area_threshold_pct:
        return None  # unchanged within survey tolerance

    change_type = MODIFIED if iou_value >= 0.5 else BOUNDARY_SHIFT
    if (shift or 0.0) > shift_threshold_m and iou_value < 0.5:
        change_type = BOUNDARY_SHIFT

    return {
        "parcel_id": parcel_id,
        "change_type": change_type,
        "confidence": round(min(0.99, 0.5 + 0.5 * (1.0 - iou_value)), 4),
        "iou": round(iou_value, 4),
        "centroid_shift_m": shift,
        "area_delta_pct": area_delta_pct,
        "description": DESCRIPTION[change_type],
        "geometry_difference": _to_geojson(
            _safe_symmetric_difference(previous_geometry, current_geometry)
        ),
        "requires_verification": True,
    }


def detect_land_use_change(
    *,
    parcel_id: str,
    previous_land_use: Optional[str],
    current_land_use: Optional[str],
) -> Optional[Dict[str, Any]]:
    if not previous_land_use or not current_land_use:
        return None
    if str(previous_land_use).strip().lower() == str(current_land_use).strip().lower():
        return None
    return {
        "parcel_id": parcel_id,
        "change_type": LAND_USE_CHANGE,
        "confidence": 0.9,
        "previous_value": previous_land_use,
        "current_value": current_land_use,
        "description": (
            f"Land use changed from '{previous_land_use}' to '{current_land_use}' "
            f"between survey epochs"
        ),
        "requires_verification": True,
    }


def detect_parcel_presence(
    *,
    previous_ids: Sequence[str],
    current_ids: Sequence[str],
) -> List[Dict[str, Any]]:
    """NEW / REMOVED parcels by identifier, reported separately so each is auditable."""
    previous_set, current_set = set(previous_ids), set(current_ids)
    changes: List[Dict[str, Any]] = []
    for parcel_id in sorted(current_set - previous_set):
        changes.append(
            {
                "parcel_id": parcel_id,
                "change_type": NEW,
                "confidence": 1.0,
                "description": DESCRIPTION[NEW],
                "requires_verification": True,
            }
        )
    for parcel_id in sorted(previous_set - current_set):
        changes.append(
            {
                "parcel_id": parcel_id,
                "change_type": REMOVED,
                "confidence": 1.0,
                "description": DESCRIPTION[REMOVED],
                "requires_verification": True,
            }
        )
    return changes


def summarise(changes: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_type: Dict[str, int] = {}
    for change in changes:
        by_type[change.get("change_type", "UNKNOWN")] = by_type.get(
            change.get("change_type", "UNKNOWN"), 0
        ) + 1
    return {
        "total": len(changes),
        "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        "all_require_verification": True,
        "vocabulary": CHANGE_TYPES,
        "descriptions": DESCRIPTION,
    }


def _to_geojson(geom: Optional[BaseGeometry]) -> Optional[Dict[str, Any]]:
    if geom is None or geom.is_empty:
        return None
    try:
        from shapely.geometry import mapping

        return mapping(geom)
    except Exception:
        return None


def _safe_symmetric_difference(a: BaseGeometry, b: BaseGeometry) -> Optional[BaseGeometry]:
    """Symmetric difference that repairs invalid rings first.

    Epoch datasets are digitised independently, so both inputs can carry
    self-intersections that make GEOS raise. Repair keeps one bad ring from
    aborting change detection for the ward.
    """
    from app.services.topology_service import make_valid

    left = a if (a is not None and a.is_valid) else make_valid(a)
    right = b if (b is not None and b.is_valid) else make_valid(b)
    if left is None or right is None:
        return None
    try:
        return left.symmetric_difference(right)
    except Exception:
        return None
