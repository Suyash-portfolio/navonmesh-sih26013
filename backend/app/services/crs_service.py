"""
Geo-reference and coordinate transformation engine (SIH26013 requirement).

Responsibilities
----------------
* Detect the CRS of a dataset (vector, raster or GNSS observation table).
* Warn / fail loudly when a dataset carries no CRS instead of guessing.
* Normalise heterogeneous sources onto a single project CRS (default
  ``EPSG:32643`` - WGS 84 / UTM 43N) so that every downstream metric
  computation (area, buffer, snap) is exact and unit-safe.
* Report transformation status: source CRS, target CRS, axis order,
  transform method, vertices transformed and reprojection warnings.

If ``pyproj`` is unavailable the service degrades into an explicit
``identity-only`` mode and reports that fact; it never silently pretends a
reprojection happened.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from app.config import PROJECT_CRS, PROJECT_CRS_CANDIDATES, STORAGE_CRS

try:  # pragma: no cover - exercised implicitly
    from pyproj import CRS, Transformer
    from pyproj.exceptions import CRSError

    PYPROJ_AVAILABLE = True
except Exception:  # pragma: no cover
    CRS = None  # type: ignore
    Transformer = None  # type: ignore
    CRSError = Exception  # type: ignore
    PYPROJ_AVAILABLE = False


# Plausible projected/legacy CRSs commonly seen on Indian cadastral data.
# Used only to *propose* a CRS to the operator - never to silently assume one.
COMMON_INDIAN_CRS_HINTS: List[Dict[str, str]] = [
    {"code": "EPSG:4326", "label": "WGS 84 geographic", "why": "carried explicitly in the file"},
    {"code": "EPSG:32643", "label": "WGS 84 / UTM 43N", "why": "nearest UTM zone to the project extent"},
    {"code": "EPSG:32644", "label": "WGS 84 / UTM 44N", "why": "adjacent UTM zone to the project extent"},
    {"code": "EPSG:24378", "label": "Indian 1954 / UTM zone 43N", "why": "legacy Indian SOI topographic series"},
    {"code": "EPSG:7755", "label": "WGS 84 / India NSF LCC", "why": "national projected grid"},
    {"code": "EPSG:3857", "label": "WGS 84 / Pseudo-Mercator", "why": "web-mapping tiles"},
]


class CRSResolutionError(ValueError):
    """Raised when a dataset cannot be placed on a known coordinate system."""


# ---------------------------------------------------------------------------
# Low level helpers
# ---------------------------------------------------------------------------
def pyproj_available() -> bool:
    return PYPROJ_AVAILABLE


def describe_crs(code: str) -> Dict[str, Any]:
    """Return a human readable description of a CRS code."""
    if not code:
        return {"code": None, "label": "Undefined", "is_geographic": None, "units": None, "datum": None}

    if not PYPROJ_AVAILABLE:
        return {"code": code, "label": code, "is_geographic": None, "units": None, "datum": None,
                "note": "pyproj unavailable - CRS metadata not resolved"}

    try:
        crs = CRS.from_user_input(code)
    except Exception:
        return {"code": code, "label": f"{code} (unrecognised)", "is_geographic": None, "units": None, "datum": None}

    axis = crs.axis_info[0] if crs.axis_info else None
    return {
        "code": crs.to_string(),
        "label": crs.name,
        "is_geographic": bool(crs.is_geographic),
        "is_projected": bool(crs.is_projected),
        "units": getattr(axis, "unit_name", None) if axis else None,
        "datum": crs.datum.name if crs.datum else None,
    }


def is_valid_crs(code: Optional[str]) -> bool:
    if not code or not PYPROJ_AVAILABLE:
        return False
    try:
        CRS.from_user_input(code)
        return True
    except Exception:
        return False


def resolve_crs(code: Optional[str]) -> Optional[str]:
    if not code:
        return None
    if not PYPROJ_AVAILABLE:
        return code
    try:
        return CRS.from_user_input(code).to_string()
    except Exception:
        return None


def _make_transformer(source: str, target: str) -> Tuple[Optional[Any], str]:
    if not PYPROJ_AVAILABLE:
        return None, "identity-fallback (pyproj unavailable)"
    try:
        src = CRS.from_user_input(source)
        dst = CRS.from_user_input(target)
    except Exception as exc:  # unknown / unsupported CRS
        return None, f"unavailable ({exc.__class__.__name__})"
    return Transformer.from_crs(src, dst, always_xy=True), "pyproj.Transformer"


# ---------------------------------------------------------------------------
# Dataset level CRS detection
# ---------------------------------------------------------------------------
def detect_crs(
    *,
    declared_crs: Optional[str] = None,
    coordinates: Optional[Iterable[Sequence[float]]] = None,
    coordinate_hint: str = "lonlat",
    rasters: Optional[Sequence[Any]] = None,
    vectors: Optional[Sequence[Any]] = None,
) -> Dict[str, Any]:
    """
    Detect the coordinate reference system of a dataset.

    Returns a report with ``status`` in ``detected`` / ``declared`` /
    ``missing`` / ``inferred`` and the confidence of the decision.
    """
    report: Dict[str, Any] = {
        "status": "missing",
        "source_crs": None,
        "method": None,
        "confidence": 0.0,
        "description": "No coordinate reference system could be established.",
        "is_geographic": None,
        "unit": None,
        "warnings": [],
    }

    # 1. Raster headers are authoritative.
    for raster in rasters or []:
        code = getattr(getattr(raster, "crs", None), "to_string", lambda: None)()
        if code:
            info = describe_crs(code)
            report.update(
                status="detected",
                source_crs=code,
                method="raster header (Rasterio)",
                confidence=1.0,
                description=f"Read from raster header: {info['label']}",
                is_geographic=info["is_geographic"],
                unit=info["units"],
            )
            return report

    # 2. Vector layer CRS from the OGR/GPKG/Shapefile header.
    for vector in vectors or []:
        code = getattr(vector, "crs", None)
        code = code.to_string() if hasattr(code, "to_string") else code
        if code:
            info = describe_crs(code)
            report.update(
                status="detected",
                source_crs=code,
                method="vector layer header (GeoPandas/OGR)",
                confidence=1.0,
                description=f"Read from vector layer header: {info['label']}",
                is_geographic=info["is_geographic"],
                unit=info["units"],
            )
            return report

    # 3. An explicit declaration (sidecar .prj, upload form field, ...).
    if declared_crs:
        code = resolve_crs(declared_crs)
        if code:
            info = describe_crs(code)
            report.update(
                status="declared",
                source_crs=code,
                method="operator declaration",
                confidence=0.9,
                description=f"Operator declared {info['label']}.",
                is_geographic=info["is_geographic"],
                unit=info["units"],
            )
        else:
            report["warnings"].append(
                f"Declared CRS '{declared_crs}' is not a recognised code. Operator selection required."
            )
        return report

    # 4. Last resort: range-based inference - clearly flagged as inferred.
    pts = [tuple(p) for p in (coordinates or []) if p and len(p) >= 2]
    if pts:
        max_abs = max(max(abs(float(p[0])), abs(float(p[1]))) for p in pts)
        if max_abs > 180.0:
            inferred = None
            for candidate in ("EPSG:32643", "EPSG:32644", "EPSG:24378"):
                if is_valid_crs(candidate):
                    inferred = candidate
                    break
            info = describe_crs(inferred) if inferred else {}
            report.update(
                status="inferred",
                source_crs=inferred,
                method="coordinate range heuristic",
                confidence=0.35,
                description=(
                    f"Coordinates exceed geographic bounds (max |value| = {max_abs:.1f}); "
                    f"best-match projected CRS suggested: {info.get('label', 'unknown')}. "
                    "Operator confirmation required."
                ),
                is_geographic=False,
                unit=info.get("units"),
            )
            report["warnings"].append("CRS was inferred from coordinate magnitude only - confirm before use.")
            return report

        if max_abs <= 90.0:
            report.update(
                status="inferred",
                source_crs="EPSG:4326",
                method="coordinate range heuristic",
                confidence=0.55,
                description="All coordinates fall inside WGS 84 geographic bounds (|lat| <= 90).",
                is_geographic=True,
                unit="degree",
            )
            report["warnings"].append(
                "Assumed WGS 84 from coordinate bounds only. If the source is a local/SOI grid, select it explicitly."
            )
            return report

    report["warnings"].append(
        "CRS is missing. The dataset cannot be placed on the map and cannot be normalized. "
        "Operator must select a source CRS."
    )
    return report


def crs_options() -> List[Dict[str, Any]]:
    """Return the operator-selectable CRS list with resolved descriptions."""
    options: List[Dict[str, Any]] = []
    for candidate in PROJECT_CRS_CANDIDATES:
        info = describe_crs(candidate["code"])
        options.append(
            {
                "code": candidate["code"],
                "label": candidate["label"],
                "zone": candidate["zone"],
                "is_geographic": info.get("is_geographic"),
                "unit": info.get("units"),
                "is_project_crs": candidate["code"] == PROJECT_CRS,
            }
        )
    return options


def suggest_crs(coordinates: Sequence[Sequence[float]]) -> List[Dict[str, str]]:
    """Return ranked CRS suggestions for a coordinate set."""
    report = detect_crs(coordinates=coordinates)
    if report.get("source_crs"):
        primary = report["source_crs"]
    else:
        primary = STORAGE_CRS
    suggestions = [{"code": primary, "label": describe_crs(primary)["label"],
                    "why": report.get("description", "")}]
    for hint in COMMON_INDIAN_CRS_HINTS:
        if hint["code"] == primary:
            continue
        suggestions.append({"code": hint["code"], "label": hint["label"], "why": hint["why"]})
    return suggestions


# ---------------------------------------------------------------------------
# Coordinate normalization
# ---------------------------------------------------------------------------
def transform_points(
    points: Sequence[Sequence[float]],
    source_crs: str,
    target_crs: str = PROJECT_CRS,
) -> Tuple[List[Tuple[float, float]], Dict[str, Any]]:
    """
    Transform a list of ``(x, y)`` pairs from ``source_crs`` to ``target_crs``.

    Returns the transformed points and a full transformation report.
    """
    pts = [tuple(p) for p in points if p and len(p) >= 2]
    source_info = describe_crs(source_crs)
    target_info = describe_crs(target_crs)

    identical = bool(source_crs) and str(source_crs) == str(target_crs)

    report: Dict[str, Any] = {
        "source_crs": source_crs,
        "target_crs": target_crs,
        "source_label": source_info.get("label"),
        "target_label": target_info.get("label"),
        "axis_order": "always_xy (longitude/easting first)",
        "points_in": len(pts),
        "points_transformed": 0,
        "points_skipped": 0,
        "method": "identity",
        "status": "pending",
        "changed": not identical,
        "warnings": [],
    }

    if identical:
        report.update(points_transformed=len(pts), status="already_normalized",
                      method="none (source CRS equals project CRS)")
        return [(float(p[0]), float(p[1])) for p in pts], report

    if not source_crs:
        report.update(
            status="blocked",
            method="none",
            warnings=["Source CRS is unknown. Coordinate normalization is blocked until a CRS is selected."],
        )
        return [], report

    if not is_valid_crs(source_crs) or not is_valid_crs(target_crs):
        report.update(
            status="failed",
            method="none",
            warnings=[f"Cannot build a transformer from '{source_crs}' to '{target_crs}'."],
        )
        return [], report

    transformer, method = _make_transformer(source_crs, target_crs)
    if transformer is None:
        report.update(status="failed", method=method,
                      warnings=[f"Transformer unavailable: {method}. Geometry left untransformed."])
        return [], report

    out: List[Tuple[float, float]] = []
    skipped = 0
    for p in pts:
        try:
            x, y = transformer.transform(float(p[0]), float(p[1]))
            if x is None or y is None or not math.isfinite(x) or not math.isfinite(y):
                skipped += 1
                continue
            out.append((float(x), float(y)))
        except Exception:
            skipped += 1

    report.update(
        points_transformed=len(out),
        points_skipped=skipped,
        method=method,
        status="normalized" if out else "failed",
    )
    if skipped:
        report["warnings"].append(f"{skipped} coordinate(s) could not be transformed and were skipped.")
    if source_info.get("is_geographic") and target_info.get("is_projected"):
        report["warnings"].append("Geographic source reprojected to a metre-based projected CRS (area/length now exact).")
    if source_info.get("is_projected") and target_info.get("is_projected"):
        report["warnings"].append("Projected-to-projected transformation; verify the vertical/horizontal datums match.")
    return out, report


def normalize_geodataframe(gdf, source_crs: Optional[str], target_crs: str = PROJECT_CRS):
    """
    Reproject a GeoDataFrame onto the project CRS.

    Returns ``(gdf, report)``. The report always states whether a real
    transformation occurred.
    """
    import pandas as pd  # local import keeps the module importable without pandas

    if source_crs is None:
        empty = report_blocked()
        return gdf, empty

    if str(source_crs) == str(target_crs):
        return gdf.set_crs(target_crs, allow_override=True) if gdf.crs is None else gdf, {
            "source_crs": str(source_crs),
            "target_crs": target_crs,
            "status": "already_normalized",
            "method": "none (source CRS equals project CRS)",
            "features_transformed": int(len(gdf)),
            "changed": False,
            "warnings": [],
        }

    if not is_valid_crs(source_crs) or not is_valid_crs(target_crs):
        return gdf, report_blocked(f"Cannot transform from '{source_crs}' to '{target_crs}'.")

    transformer, method = _make_transformer(source_crs, target_crs)
    if transformer is None:
        return gdf, report_blocked(method)

    out = gdf.to_crs(target_crs)
    report = {
        "source_crs": str(source_crs),
        "target_crs": target_crs,
        "source_label": describe_crs(source_crs).get("label"),
        "target_label": describe_crs(target_crs).get("label"),
        "status": "normalized",
        "method": method,
        "features_transformed": int(len(out)),
        "changed": True,
        "warnings": [],
    }
    del pd
    return out, report


def report_blocked(reason: str = "Source CRS is unknown.") -> Dict[str, Any]:
    return {
        "source_crs": None,
        "target_crs": PROJECT_CRS,
        "status": "blocked",
        "method": "none",
        "features_transformed": 0,
        "changed": False,
        "warnings": [reason],
    }


def compatibility_report(source_crs: Optional[str], other_crs: Optional[str]) -> Dict[str, Any]:
    """
    Report whether two datasets may be combined without reprojection.
    Used to *prevent mixing incompatible geometries without warning*.
    """
    if not source_crs or not other_crs:
        return {
            "compatible": False,
            "severity": "warning",
            "message": "One or both datasets have no CRS. Overlays are not trustworthy until resolved.",
        }
    a, b = resolve_crs(source_crs), resolve_crs(other_crs)
    if a == b:
        return {
            "compatible": True,
            "severity": "ok",
            "message": f"Both datasets use {describe_crs(a).get('label')} - direct overlay is valid.",
        }
    a_info, b_info = describe_crs(a), describe_crs(b)
    mixed_units = a_info.get("is_geographic") != b_info.get("is_geographic")
    return {
        "compatible": False,
        "severity": "error" if mixed_units else "warning",
        "message": (
            f"CRS mismatch: '{a_info.get('label')}' vs '{b_info.get('label')}'. "
            + (
                "Geographic and projected geometry must not be overlaid directly - normalize first."
                if mixed_units
                else "Overlay requires a datum-aware transformation before it is reliable."
            )
        ),
    }
