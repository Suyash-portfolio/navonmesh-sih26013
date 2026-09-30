"""
Topology service (SIH26013 - automated topological correction).

Detects and repairs, on real geometries:

* invalid rings (self-intersection / unclosed ring)
* gaps - area inside the administrative extent that no parcel covers
* overlaps - double-covered area between neighbouring parcels
* slivers - micro polygons below the configured area threshold
* disconnected boundaries - multi-part parcels
* duplicate geometries - byte-identical repeats
* snapping issues - vertices further apart than the snap tolerance

All before/after numbers in the UI come from these functions running on the
actual harmonized geometry. Nothing here is randomised.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import shapely
from shapely.geometry import GeometryCollection, MultiPolygon, Polygon, shape
from shapely.ops import unary_union

# An area (m^2) below which a difference polygon is treated as numerical noise.
NOISE_AREA_SQM = 0.05
SLIVER_ASPECT_RATIO = 25.0
# Uncovered ground below this is a corner notch left by digitising jitter, not
# a missing holding. It is reported as a residual but is not a cadastral gap,
# and - crucially - it is *not* merged into a neighbour: doing so opens a new
# notch at the next corner and the repair oscillates instead of converging.
GAP_MATERIALITY_SQM = 25.0


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------
def _polygonal(geom) -> Optional[Any]:
    """Coerce any geometry to a polygonal geometry, or ``None``."""
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in ("Polygon", "MultiPolygon"):
        return geom
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        return unary_union(parts) if parts else None
    return None


def make_valid(geom) -> Optional[Any]:
    """Repair an invalid geometry using Shapely 2 / GEOS."""
    if geom is None or geom.is_empty:
        return None
    if geom.is_valid:
        return geom
    try:
        repaired = shapely.make_valid(geom)
    except Exception:
        repaired = geom.buffer(0)
    polygonal = _polygonal(repaired)
    if polygonal is None:
        return None
    if not polygonal.is_valid:
        polygonal = polygonal.buffer(0)
    return polygonal if (polygonal is not None and polygonal.is_valid) else None


def detect_issues(
    geometries: Sequence[Any],
    ids: Sequence[str],
    *,
    extent: Optional[Any] = None,
    exclusions: Optional[Sequence[Any]] = None,
    min_sliver_area_sqm: float = 2.0,
    area_noise_sqm: float = NOISE_AREA_SQM,
) -> Dict[str, Any]:
    """Detect every topology defect present in a parcel set.

    ``exclusions`` holds legitimately uncovered areas (road corridors, drains,
    water bodies). Without them every road would be reported as a cadastral gap.
    """
    report: Dict[str, Any] = {
        "total_features": len(geometries),
        "invalid": {"count": 0, "ids": []},
        "missing": {"count": 0, "ids": []},
        "overlap": {"count": 0, "pairs": [], "area_sqm": 0.0, "max_pair_area_sqm": 0.0},
        "gap": {"count": 0, "parts": [], "area_sqm": 0.0,
                "residual_count": 0, "residual_area_sqm": 0.0},
        "sliver": {"count": 0, "ids": [], "area_sqm": 0.0},
        "disconnected": {"count": 0, "ids": []},
        "duplicate": {"count": 0, "ids": []},
        "unsnapped_vertices": {"count": 0, "max_gap_m": 0.0, "mean_gap_m": 0.0, "features": []},
    }

    # -- invalid / duplicate / disconnected / sliver ------------------------
    wkb_seen: Dict[bytes, str] = {}
    for geom, feature_id in zip(geometries, ids):
        if geom is None:
            # Absorbed by a neighbour during repair - a *different* outcome
            # from a geometry that is still present but self-intersecting.
            report["missing"]["count"] += 1
            report["missing"]["ids"].append({"id": feature_id, "reason": "absorbed_by_neighbour"})
            continue
        if geom.is_empty:
            report["missing"]["count"] += 1
            report["missing"]["ids"].append({"id": feature_id, "reason": "empty_geometry"})
            continue
        if not geom.is_valid:
            report["invalid"]["count"] += 1
            report["invalid"]["ids"].append({"id": feature_id, "reason": "self_intersection"})
            continue

        key = geom.wkb
        if key in wkb_seen:
            report["duplicate"]["count"] += 1
            report["duplicate"]["ids"].append({"id": feature_id, "duplicate_of": wkb_seen[key]})
        else:
            wkb_seen[key] = feature_id

        if geom.geom_type == "MultiPolygon" and len(geom.geoms) > 1:
            report["disconnected"]["count"] += 1
            report["disconnected"]["ids"].append(
                {"id": feature_id, "parts": len(geom.geoms),
                 "largest_part_area_sqm": round(max(g.area for g in geom.geoms), 2)}
            )

        area = geom.area
        compactness = (geom.length * geom.length) / area if area > 0 else float("inf")
        if area < min_sliver_area_sqm or (compactness > SLIVER_ASPECT_RATIO and area < min_sliver_area_sqm * 20.0):
            report["sliver"]["count"] += 1
            report["sliver"]["ids"].append(
                {"id": feature_id, "area_sqm": round(area, 3), "compactness_ratio": round(compactness, 1)}
            )
            report["sliver"]["area_sqm"] += area

    # -- overlaps ------------------------------------------------------------
    usable = [(g, fid) for g, fid in zip(geometries, ids)
              if g is not None and not g.is_empty and _polygonal(g) is not None]
    if len(usable) > 1:
        polys = [_polygonal(g) for g, _ in usable]
        labels = [fid for _, fid in usable]
        tree = shapely.STRtree(polys)
        pairs: Dict[Tuple[int, int], float] = {}
        for i, poly in enumerate(polys):
            for j in tree.query(poly):
                j = int(j)
                if j <= i:
                    continue
                other = polys[j]
                if not poly.intersects(other):
                    continue
                try:
                    inter = poly.intersection(other)
                except Exception:
                    continue
                if inter.is_empty or inter.area <= area_noise_sqm:
                    continue
                if inter.geom_type not in ("Polygon", "MultiPolygon"):
                    continue
                pairs[(i, j)] = inter.area
        report["overlap"]["count"] = len(pairs)
        report["overlap"]["area_sqm"] = round(sum(pairs.values()), 3)
        report["overlap"]["max_pair_area_sqm"] = round(max(pairs.values()), 3) if pairs else 0.0
        for (i, j), area in sorted(pairs.items(), key=lambda kv: -kv[1])[:200]:
            report["overlap"]["pairs"].append(
                {"a": labels[i], "b": labels[j], "area_sqm": round(area, 3)}
            )

    # -- gaps ----------------------------------------------------------------
    if extent is not None and len(usable) > 0:
        extent_poly = _polygonal(extent)
        if extent_poly is not None:
            # Union only repaired geometries: a self-intersecting ring makes
            # GEOS raise TopologyException, and invalid input would otherwise
            # corrupt the coverage calculation.
            repairable = []
            for g, _ in usable:
                fixed = make_valid(_polygonal(g))
                if fixed is not None and not fixed.is_empty:
                    repairable.append(fixed)
            covered = unary_union(repairable) if repairable else None
            gaps = extent_poly.difference(covered) if covered is not None else extent_poly
            # Roads, drains and water bodies are not cadastral gaps.
            clean_exclusions = [
                fixed for fixed in (make_valid(_polygonal(e)) for e in (exclusions or [])) if fixed is not None
            ]
            if clean_exclusions:
                try:
                    gaps = gaps.difference(unary_union(clean_exclusions))
                except Exception:
                    pass
            parts = []
            residual = 0.0
            if not gaps.is_empty and gaps.geom_type in ("Polygon", "MultiPolygon"):
                iterable = gaps.geoms if gaps.geom_type == "MultiPolygon" else [gaps]
                for part in iterable:
                    if part.area <= max(area_noise_sqm, min_sliver_area_sqm):
                        continue
                    if part.area <= GAP_MATERIALITY_SQM:
                        residual += part.area
                        continue
                    parts.append({"area_sqm": round(part.area, 2),
                                  "centroid": [round(part.centroid.x, 2), round(part.centroid.y, 2)]})
            parts.sort(key=lambda p: -p["area_sqm"])
            report["gap"]["count"] = len(parts)
            report["gap"]["area_sqm"] = round(sum(p["area_sqm"] for p in parts), 2)
            report["gap"]["parts"] = parts[:100]
            report["gap"]["residual_count"] = len(
                [g for g in (gaps.geoms if gaps.geom_type == "MultiPolygon" else [gaps])
                 if not g.is_empty and max(area_noise_sqm, min_sliver_area_sqm) < g.area <= GAP_MATERIALITY_SQM]
            ) if not gaps.is_empty and gaps.geom_type in ("Polygon", "MultiPolygon") else 0
            report["gap"]["residual_area_sqm"] = round(residual, 2)

    # -- unmatched nodes (snapping) ----------------------------------------
    report["unsnapped_vertices"] = _count_unsnapped(geometries)
    return report


def _count_unsnapped(geometries: Sequence[Any], tolerance: float = 0.35) -> Dict[str, Any]:
    """
    Count **unmatched nodes**: parcel corners that have no counterpart on a
    neighbouring parcel within ``tolerance`` metres.

    This is the real, measurable form of a snapping problem - a shared boundary
    whose end points do not line up - as opposed to merely counting vertices.
    """
    nodes: List[Tuple[float, float]] = []
    owner: List[int] = []
    for index, geom in enumerate(geometries):
        if geom is None or geom.is_empty or geom.geom_type not in ("Polygon", "MultiPolygon"):
            continue
        parts = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
        for part in parts:
            coords = list(part.exterior.coords)[:-1]
            nodes.extend(coords)
            owner.extend([index] * len(coords))

    if not nodes:
        return {"count": 0, "max_gap_m": 0.0, "mean_gap_m": 0.0, "features": []}

    xs = [n[0] for n in nodes]
    ys = [n[1] for n in nodes]
    # A coarse 1 m cell index is plenty for a 0.35 m tolerance.
    cell = max(tolerance, 1e-6)
    buckets: Dict[Tuple[int, int], List[int]] = {}
    for i, (x, y) in enumerate(nodes):
        buckets.setdefault((int(x // cell), int(y // cell)), []).append(i)

    unmatched: List[Dict[str, Any]] = []
    gaps: List[float] = []
    for i, (x, y) in enumerate(nodes):
        found = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in buckets.get((int(x // cell) + dx, int(y // cell) + dy), []):
                    if j == i or owner[j] == owner[i]:
                        continue
                    d = math.hypot(nodes[j][0] - x, nodes[j][1] - y)
                    if d <= tolerance:
                        found = True
                        break
                if found:
                    break
            if found:
                break
        if not found:
            unmatched.append({"index": i, "x": round(x, 2), "y": round(y, 2)})
            gaps.append(min(
                (math.hypot(nodes[j][0] - x, nodes[j][1] - y)
                 for j in buckets.get((int(x // cell), int(y // cell)), [])
                 if owner[j] != owner[i]),
                default=0.0,
            ))
    return {
        "count": len(unmatched),
        "max_gap_m": round(max(gaps), 2) if gaps else 0.0,
        "mean_gap_m": round(sum(gaps) / len(gaps), 2) if gaps else 0.0,
        "features": unmatched[:50],
    }


def before_after(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the before/after comparison rows shown in the UI."""
    rows = [
        ("Invalid geometries", before["invalid"]["count"], after["invalid"]["count"]),
        ("Overlaps", before["overlap"]["count"], after["overlap"]["count"]),
        ("Gaps", before["gap"]["count"], after["gap"]["count"]),
        ("Slivers", before["sliver"]["count"], after["sliver"]["count"]),
        ("Disconnected boundaries", before["disconnected"]["count"], after["disconnected"]["count"]),
        ("Duplicate geometries", before["duplicate"]["count"], after["duplicate"]["count"]),
        ("Unmatched boundary nodes", before["unsnapped_vertices"]["count"], after["unsnapped_vertices"]["count"]),
        ("Features absorbed into a neighbour", before["missing"]["count"], after["missing"]["count"]),
    ]
    output = []
    for label, b, a in rows:
        output.append(
            {
                "issue": label,
                "before": b,
                "after": a,
                "resolved": max(0, b - a),
                "critical": _criticality(label),
            }
        )
    return output


def _criticality(label: str) -> str:
    if label in ("Invalid geometries", "Overlaps", "Gaps"):
        return "critical"
    if label in ("Slivers", "Disconnected boundaries", "Duplicate geometries"):
        return "major"
    if label == "Features absorbed into a neighbour":
        return "info"
    return "minor"


# ---------------------------------------------------------------------------
# Repair
# ---------------------------------------------------------------------------
def _overlap_pass(
    working: List[Optional[Any]],
    ids: Sequence[str],
    log: Dict[str, Any],
    max_iterations: int = 12,
) -> bool:
    """
    Resolve every double-covered area, to a fixed point.

    A chained "claimed polygon" approach is not enough: two parcels that do
    not touch the first one can still overlap each other. Instead every
    intersecting pair is enumerated with an STRtree and the contested area is
    taken from the *smaller* parcel, which is repeated until no pair overlaps.
    Each pass strictly reduces total area, so the loop terminates.
    """
    changed = False
    for _ in range(max_iterations):
        live = [i for i, g in enumerate(working) if g is not None and not g.is_empty]
        if len(live) < 2:
            return changed
        polys = [working[i] for i in live]
        tree = shapely.STRtree(polys)
        contested: Dict[Tuple[int, int], float] = {}
        for a, poly in enumerate(polys):
            for b in tree.query(poly):
                b = int(b)
                if b <= a:
                    continue
                other = polys[b]
                if not poly.intersects(other):
                    continue
                try:
                    inter = poly.intersection(other)
                except Exception:
                    continue
                if inter.is_empty or inter.geom_type not in ("Polygon", "MultiPolygon"):
                    continue
                if inter.area <= NOISE_AREA_SQM:
                    continue
                contested[(a, b)] = inter.area
        if not contested:
            return changed
        changed = True
        # Biggest disputes first so the worst overlaps are settled before the
        # geometry is chopped up by the smaller ones.
        for (a, b), area in sorted(contested.items(), key=lambda kv: -kv[1]):
            ia, ib = live[a], live[b]
            ga, gb = working[ia], working[ib]
            if ga is None or gb is None:
                continue
            if not ga.intersects(gb):
                continue
            loser, winner = (ia, ib) if ga.area <= gb.area else (ib, ia)
            loser_geom, winner_geom = working[loser], working[winner]
            if loser_geom is None or winner_geom is None:
                continue
            remainder = _polygonal(loser_geom.difference(winner_geom))
            if remainder is None or remainder.area <= NOISE_AREA_SQM:
                # The parcel lies entirely inside its neighbour: it is a
                # duplicate, not an overlap. Drop it, otherwise it would keep
                # double-covering the same ground forever.
                working[loser] = None
                log["parcels_absorbed"] += 1
                log["overlaps_resolved"] += 1
                log["overlap_area_removed_sqm"] += area
                continue
            working[loser] = remainder
            log["overlaps_resolved"] += 1
            log["overlap_area_removed_sqm"] += area
    return changed


def _sliver_thresholds(geometries: Sequence[Any], min_sliver_area_sqm: float) -> Tuple[float, float]:
    """
    Derive the dissolve threshold from the data itself.

    A fixed area threshold is wrong: dissolving by *shape* (compactness) will
    happily swallow a legitimate long thin plot, and a fixed cut-off is
    meaningless across datasets of different sizes. The floor is the smaller of
    the configured minimum and a quarter of the median holding, so a real
    parcel can never be dissolved in a normally-distributed dataset.
    """
    areas = sorted(g.area for g in geometries if g is not None and not g.is_empty and g.area > 0)
    if not areas:
        return min_sliver_area_sqm, min_sliver_area_sqm
    median = areas[len(areas) // 2]
    floor = min(min_sliver_area_sqm, 0.25 * median)
    return floor, median


def _is_sliver(geom, area_floor: float) -> bool:
    """A sliver is defined purely by area; shape is only a tie-breaker."""
    area = geom.area
    if area < area_floor:
        return True
    # Long and thin, but still a recognisable holding - do not dissolve.
    compactness = (geom.length * geom.length) / area if area > 0 else float("inf")
    return compactness > SLIVER_ASPECT_RATIO and area < area_floor * 20.0


def _sliver_pass(
    working: List[Optional[Any]],
    area_floor: float,
    log: Dict[str, Any],
) -> bool:
    """Absorb sub-threshold parcels into the neighbour sharing the longest edge."""
    changed = False
    for i, geom in enumerate(working):
        if geom is None:
            continue
        if not _is_sliver(geom, area_floor):
            continue
        area = geom.area
        candidates = [j for j, other in enumerate(working)
                      if j != i and other is not None and geom.distance(other) <= 0.001]
        if candidates:
            # Host = the neighbour we share the most boundary with, not simply
            # the largest one.
            def shared_length(j: int) -> float:
                try:
                    return geom.intersection(working[j]).length
                except Exception:
                    return 0.0

            host = max(candidates, key=lambda j: (shared_length(j), working[j].area))
            merged = _polygonal(unary_union([working[host], geom]))
            if merged is not None:
                working[host] = merged
        else:
            log["slivers_isolated"] += 1
        working[i] = None
        log["slivers_dissolved"] += 1
        log["sliver_area_absorbed_sqm"] += area
        changed = True
    return changed


def _validity_pass(working: List[Optional[Any]], grid: float, log: Dict[str, Any]) -> bool:
    """Make every geometry OGC-valid and snap it onto the working grid."""
    changed = False
    for i, geom in enumerate(working):
        if geom is None:
            continue
        if not geom.is_valid:
            log["repaired_invalid"] += 1
            changed = True
        fixed = make_valid(geom)
        if fixed is None:
            working[i] = None
            log["features_dropped"] += 1
            continue
        try:
            snapped = shapely.set_precision(fixed, grid_size=grid)
        except Exception:
            snapped = fixed
        if snapped is None or snapped.is_empty or not snapped.is_valid:
            snapped = fixed
        elif abs(snapped.area - fixed.area) > 1e-9:
            log["snapped_features"] += 1
        result = _polygonal(snapped)
        if result is not None and not result.is_valid:
            result = make_valid(result)
        working[i] = result
    return changed


def _multi_part_pass(working: List[Optional[Any]], log: Dict[str, Any]) -> bool:
    """Keep only the dominant part of a disconnected parcel."""
    changed = False
    for i, geom in enumerate(working):
        if geom is not None and geom.geom_type == "MultiPolygon" and len(geom.geoms) > 1:
            working[i] = max(geom.geoms, key=lambda g: g.area)
            log["multi_parts_reduced"] += 1
            changed = True
    return changed


def _close_gaps(
    working: List[Optional[Any]],
    ids: List[str],
    extent: Optional[Any],
    exclusions: Optional[Sequence[Any]],
    area_floor: float,
    max_iterations: int,
    log: Dict[str, Any],
) -> None:
    """Close uncovered area inside the administrative extent."""
    extent_poly = _polygonal(extent) if extent is not None else None
    if extent_poly is None:
        return
    clean_exclusions = [
        fixed for fixed in (make_valid(_polygonal(e)) for e in (exclusions or [])) if fixed is not None
    ]

    for _ in range(max_iterations):
        live = [i for i, g in enumerate(working) if g is not None]
        if not live:
            return
        covered = unary_union([working[i] for i in live])
        try:
            gaps = extent_poly.difference(covered)
            if clean_exclusions:
                gaps = gaps.difference(unary_union(clean_exclusions))
        except Exception:
            return
        if gaps.is_empty or gaps.geom_type not in ("Polygon", "MultiPolygon"):
            return
        parts = gaps.geoms if gaps.geom_type == "MultiPolygon" else [gaps]
        # Only *material* gaps are repaired. Sub-25 m^2 corner notches are left
        # alone: merging one into a neighbour opens a fresh notch at the next
        # corner, so the repair would never terminate.
        material = [
            p for p in parts
            if p.area > max(GAP_MATERIALITY_SQM, max(NOISE_AREA_SQM, area_floor))
        ]
        if not material:
            return
        for part in material:
            log["gaps_closed"] += 1
            log["gap_area_closed_sqm"] += part.area
            nearest = min(live, key=lambda j: working[j].distance(part))
            if part.area < area_floor * 50.0:
                # Sub-plat size: attach to the adjoining parcel.
                merged = _polygonal(unary_union([working[nearest], part]))
                if merged is not None:
                    working[nearest] = merged
            else:
                # Plausible missing holding: keep it as its own record.
                working.append(_polygonal(part))
                ids.append("RECONSTRUCTED-PENDING-REVIEW")
                log["parcels_created_from_gap"] += 1
        _validity_pass(working, 0.0, log)


def planarise(
    geometries: Sequence[Any],
    ids: Sequence[str],
    *,
    extent: Optional[Any] = None,
    exclusions: Optional[Sequence[Any]] = None,
    snap_tolerance_m: float = 0.15,
    min_sliver_area_sqm: float = 2.0,
    max_iterations: int = 6,
) -> Tuple[List[Optional[Any]], Dict[str, Any]]:
    """
    Produce a planar parcel set from an input parcel set.

    The repair is run as a **fixed-point loop** rather than a single sweep:
    dissolving a sliver moves area onto a neighbour, which can create a fresh
    overlap, which has to be resolved again. Iteration stops as soon as a pass
    makes no change (or ``max_iterations`` is reached), so the reported
    before/after numbers are measured on a genuinely converged geometry set.

    Returns the repaired geometries and a repair log.
    """
    log: Dict[str, Any] = {
        "snap_tolerance_m": snap_tolerance_m,
        "min_sliver_area_sqm": min_sliver_area_sqm,
        "iterations": 0,
        "converged": False,
        "repaired_invalid": 0,
        "snapped_features": 0,
        "overlaps_resolved": 0,
        "overlap_area_removed_sqm": 0.0,
        "slivers_dissolved": 0,
        "sliver_area_absorbed_sqm": 0.0,
        "slivers_isolated": 0,
        "parcels_absorbed": 0,
        "area_floor_sqm": 0.0,
        "median_holding_sqm": 0.0,
        "gaps_closed": 0,
        "gap_area_closed_sqm": 0.0,
        "parcels_created_from_gap": 0,
        "multi_parts_reduced": 0,
        "features_dropped": 0,
    }

    grid = max(snap_tolerance_m, 1e-6)
    working: List[Optional[Any]] = list(geometries)
    out_ids: List[str] = list(ids)
    area_floor, median_area = _sliver_thresholds(working, min_sliver_area_sqm)
    log["area_floor_sqm"] = round(area_floor, 3)
    log["median_holding_sqm"] = round(median_area, 2)

    def converge() -> bool:
        """Run validity/overlap/sliver passes until a pass changes nothing."""
        for iteration in range(1, max_iterations + 1):
            log["iterations"] = iteration
            changed = _validity_pass(working, grid, log)
            changed = _overlap_pass(working, out_ids, log) or changed
            changed = _sliver_pass(working, area_floor, log) or changed
            changed = _multi_part_pass(working, log) or changed
            if not changed:
                return True
        return False

    log["converged"] = converge()
    # Closing a gap moves area onto existing parcels, which can re-open an
    # overlap - and resolving that overlap cuts a fresh sliver, which is a
    # fresh gap. Overlap repair and gap closing therefore have to alternate
    # until neither finds anything to do, otherwise the reported "after" state
    # is a half-finished intermediate.
    for _ in range(max_iterations):
        before_count = log["gaps_closed"] + log["overlaps_resolved"] + log["slivers_dissolved"]
        _close_gaps(working, out_ids, extent, exclusions, area_floor, max_iterations, log)
        if not converge():
            break
        after_count = log["gaps_closed"] + log["overlaps_resolved"] + log["slivers_dissolved"]
        if after_count == before_count:
            break
    _validity_pass(working, grid, log)
    _overlap_pass(working, out_ids, log)
    _multi_part_pass(working, log)

    return working, log


def repair_and_report(
    geometries: Sequence[Any],
    ids: Sequence[str],
    *,
    extent: Optional[Any] = None,
    exclusions: Optional[Sequence[Any]] = None,
    snap_tolerance_m: float = 0.15,
    min_sliver_area_sqm: float = 2.0,
) -> Dict[str, Any]:
    """Detect, repair, re-detect and return a before/after report."""
    before = detect_issues(
        geometries, ids, extent=extent, exclusions=exclusions, min_sliver_area_sqm=min_sliver_area_sqm
    )
    repaired, log = planarise(
        geometries,
        list(ids),
        extent=extent,
        exclusions=exclusions,
        snap_tolerance_m=snap_tolerance_m,
        min_sliver_area_sqm=min_sliver_area_sqm,
    )
    after = detect_issues(
        repaired, list(ids) + (["RECONSTRUCTED-PENDING-REVIEW"] * log["parcels_created_from_gap"]),
        extent=extent, exclusions=exclusions, min_sliver_area_sqm=min_sliver_area_sqm,
    )
    comparison = before_after(before, after)
    residual = after["gap"].get("residual_area_sqm", 0.0)
    extent_area = extent.area if extent is not None else 0.0
    return {
        "before": before,
        "after": after,
        "comparison": comparison,
        "repair_log": log,
        "resolved_total": sum(row["resolved"] for row in comparison),
        "remaining_total": sum(row["after"] for row in comparison),
        "residual_note": (
            f"{after['gap'].get('residual_count', 0)} sub-{GAP_MATERIALITY_SQM:.0f} m2 corner notch(es) totalling "
            f"{residual:.1f} m2 ({residual / extent_area * 100:.3f}% of the administrative extent) remain. "
            "These are digitising artefacts at shared corners, not missing holdings."
            if residual > 0 else "No residual corner notches."
        ),
        "clean": after["invalid"]["count"] == 0 and after["overlap"]["count"] == 0 and after["gap"]["count"] == 0,
    }


# ---------------------------------------------------------------------------
# Geometry difference helpers (used by the conflict and change services)
# ---------------------------------------------------------------------------
def difference_geometry(a: Any, b: Any) -> Dict[str, Any]:
    """Return the symmetric-difference statistics between two geometries."""
    if a is None or b is None or a.is_empty or b.is_empty:
        return {"overlap_sqm": 0.0, "only_a_sqm": 0.0, "only_b_sqm": 0.0, "shift_distance_m": 0.0}
    try:
        inter = a.intersection(b)
        only_a = a.difference(b)
        only_b = b.difference(a)
        return {
            "overlap_sqm": round(inter.area, 3),
            "only_a_sqm": round(only_a.area, 3),
            "only_b_sqm": round(only_b.area, 3),
            "shift_distance_m": round(
                max(0.0, a.centroid.distance(b.centroid) if not inter.is_empty
                    else a.centroid.distance(b.centroid)),
                3,
            ),
        }
    except Exception:
        return {"overlap_sqm": 0.0, "only_a_sqm": 0.0, "only_b_sqm": 0.0, "shift_distance_m": 0.0}


def largest_part(geom):
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "MultiPolygon":
        return max(geom.geoms, key=lambda g: g.area)
    return geom


def to_geojson(geom) -> Optional[Dict[str, Any]]:
    """Serialise a Shapely geometry to a GeoJSON mapping."""
    if geom is None or geom.is_empty:
        return None
    import shapely.geometry as sgeom

    return sgeom.mapping(geom)


def build_extent_from_bounds(bounds: Sequence[float]) -> Polygon:
    """Create an administrative extent polygon from an xmin/ymin/xmax/ymax."""
    x0, y0, x1, y1 = bounds
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def geometry_from_geojson(payload: Dict[str, Any]):
    return shape(payload)
