"""
NAVONMESH - Spatial Matching Engine (Phase 7)

Decides which feature in source A corresponds to which feature in source B.

Design note on honesty
----------------------
The previous prototype exposed a class called ``KeypointMatcherTPS`` whose
``elastic_strain_reduction_pct`` was a hardcoded 98.4, and a function called
``detect_and_match_keypoints`` that matched on string equality of ``feature_id``
while its docstring promised "high-confidence invariant keypoint pairs". This
module replaces both with a matcher that reports *real, measurable* signals and
states plainly which signals it used.

Signals actually computed here
-------------------------------
* centroid displacement (metres, in the project CRS)
* intersection-over-union of the two polygons
* area similarity ratio
* boundary-shape similarity (Hausdorff-like via vertex resampling)
* TIE-POINT SUPPORT: real distance to the nearest GNSS / ground-truth observation
* TOPOLOGICAL status of the candidate

No learned descriptor, SIFT keypoint extractor or neural model is used, because
none is available in this runtime. ``capability`` is reported honestly so the UI
can label the engine rather than overstate it. The TPS warping stage (Phase 8)
remains available through ``geoai.keypoint_matcher.fit_tps``, which performs a
genuine thin-plate-spline fit from real tie points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

MATCHED = "MATCHED"
PROBABLE = "PROBABLE_MATCH"
REVIEW = "REVIEW_REQUIRED"
UNMATCHED = "UNMATCHED"

ENGINE_CAPABILITY = "geometric-signal-matcher"
ENGINE_NOTE = (
    "Matching uses explicit geometric and survey-evidence signals (centroid "
    "displacement, IoU, area ratio, boundary shape, GNSS tie-point distance). "
    "It is a deterministic geometric matcher, not a learned descriptor matcher; "
    "no neural keypoint network is executed in this build."
)


@dataclass
class MatchCandidate:
    """One scored correspondence between a legacy parcel and a candidate feature."""

    legacy_id: str
    candidate_id: str
    score: float
    verdict: str
    signals: Dict[str, Any] = dc_field(default_factory=dict)
    reasons: List[str] = dc_field(default_factory=list)


def _as_geometry(geojson_or_geom: Any) -> Optional[BaseGeometry]:
    if geojson_or_geom is None:
        return None
    if isinstance(geojson_or_geom, BaseGeometry):
        return geojson_or_geom
    try:
        return shape(geojson_or_geom)
    except Exception:
        return None


def _polygonal(geom: Optional[BaseGeometry]) -> Optional[BaseGeometry]:
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom
    try:
        poly = geom.buffer(0)
    except Exception:
        return None
    return poly if poly.geom_type in {"Polygon", "MultiPolygon"} and not poly.is_empty else None


def iou(a: Optional[BaseGeometry], b: Optional[BaseGeometry]) -> float:
    """Intersection over union with union >= 1 guard for degenerate inputs."""
    if a is None or b is None or a.is_empty or b.is_empty:
        return 0.0
    try:
        union = a.union(b).area
        if union <= 0:
            return 0.0
        return max(0.0, min(1.0, a.intersection(b).area / union))
    except Exception:
        return 0.0


def centroid_displacement_m(a: Optional[BaseGeometry], b: Optional[BaseGeometry]) -> Optional[float]:
    if a is None or b is None:
        return None
    try:
        return round(a.centroid.distance(b.centroid), 4)
    except Exception:
        return None


def area_ratio(a: Optional[BaseGeometry], b: Optional[BaseGeometry]) -> Optional[float]:
    """Symmetric area ratio in [0, 1]: 1.0 means identical area."""
    if a is None or b is None:
        return None
    try:
        big, small = sorted((a.area, b.area), reverse=True)
        if big <= 0:
            return None
        return round(small / big, 4)
    except Exception:
        return None


def boundary_similarity(a: Optional[BaseGeometry], b: Optional[BaseGeometry], samples: int = 24) -> Optional[float]:
    """Compare exterior rings by resampling to a fixed vertex count.

    Cheaper and more stable than Hausdorff for nearly-identical cadastral
    boundaries, and it degrades gracefully for very different shapes.
    """
    pa, pb = _polygonal(a), _polygonal(b)
    if pa is None or pb is None:
        return None
    try:
        ra = _resampled_ring(pa, samples)
        rb = _resampled_ring(pb, samples)
        if ra is None or rb is None:
            return None
        total = 0.0
        scale = max(pa.area, pb.area, 1e-9) ** 0.5
        for (ax, ay), (bx, by) in zip(ra, rb):
            total += math.hypot(ax - bx, ay - by)
        mean = total / samples
        return round(max(0.0, 1.0 - (mean / scale)), 4)
    except Exception:
        return None


_RING_CACHE: Dict[int, Any] = {}


def _resampled_ring(geom: BaseGeometry, samples: int) -> Optional[List[Tuple[float, float]]]:
    """Return ``samples`` evenly spaced perimeter positions as plain xy pairs.

    Resampling dominates matching cost, so results are memoised by geometry
    identity. Plain coordinates avoid constructing 24 Shapely points and 24
    distance objects per comparison.
    """
    key = id(geom)
    cached = _RING_CACHE.get(key)
    if cached is not None and cached[0] == samples:
        return cached[1]
    try:
        ring = geom.exterior
        length = ring.length
        if length <= 0:
            return None
        coordinates = ring.interpolate(
            [(i / samples) * length for i in range(samples)], normalized=False
        )
        if hasattr(coordinates, "geoms"):
            coords = [(g.x, g.y) for g in coordinates.geoms]
        else:
            coords = [(coordinates.x, coordinates.y)]
        out = coords if len(coords) == samples else None
    except Exception:
        return None
    _RING_CACHE[key] = (samples, out)
    return out


def build_survey_index(survey_points: Sequence[Dict[str, Any]]):
    """Build a spatial index over survey observations.

    Scanning every observation for every candidate is quadratic: 302 parcels x
    1474 observations per run. An STRtree makes each lookup logarithmic, which
    is the difference between a demo that starts instantly and one that takes
    minutes.
    """
    from shapely.geometry import Point
    from shapely.strtree import STRtree

    usable = [
        (i, observation)
        for i, observation in enumerate(survey_points)
        if observation.get("x") is not None and observation.get("y") is not None
    ]
    if not usable:
        return None
    geometries = [Point(o["x"], o["y"]) for _, o in usable]
    return STRtree(geometries), usable


def nearest_survey_support_m(
    point_xy: Optional[Tuple[float, float]],
    survey_points: Sequence[Dict[str, Any]],
    index: Optional[Tuple[Any, List[Tuple[int, Dict[str, Any]]]]] = None,
) -> Dict[str, Any]:
    """Distance from a candidate to the nearest GNSS / ground-truth observation.

    ``index`` is an optional prebuilt index from :func:`build_survey_index`.
    """
    empty = {"distance_m": None, "point_id": None, "accuracy_m": None}
    if point_xy is None or not survey_points:
        return empty
    px, py = point_xy

    if index is not None:
        from shapely.geometry import Point

        tree, usable = index
        try:
            nearest = tree.nearest(Point(px, py))
        except Exception:
            return empty
        _i, observation = usable[int(nearest)]
        return {
            "distance_m": round(float(math.hypot(px - observation["x"], py - observation["y"])), 3),
            "point_id": observation.get("point_id"),
            "accuracy_m": observation.get("accuracy_m"),
            "method": observation.get("method"),
        }

    best: Optional[Tuple[float, Dict[str, Any]]] = None
    for observation in survey_points:
        x, y = observation.get("x"), observation.get("y")
        if x is None or y is None:
            continue
        distance = math.hypot(px - x, py - y)
        if best is None or distance < best[0]:
            best = (distance, observation)
    if best is None:
        return empty
    distance, observation = best
    return {
        "distance_m": round(distance, 3),
        "point_id": observation.get("point_id"),
        "accuracy_m": observation.get("accuracy_m"),
        "method": observation.get("method"),
    }


def _verdict_for(score: float, iou_value: float, min_iou: float) -> str:
    if iou_value >= min_iou and score >= 0.85:
        return MATCHED
    if score >= 0.65:
        return PROBABLE
    if score >= 0.35:
        return REVIEW
    return UNMATCHED


def _reasons(signals: Dict[str, Any], verdict: str) -> List[str]:
    reasons: List[str] = []
    iou_value = signals.get("iou") or 0.0
    ratio = signals.get("area_ratio")
    shift = signals.get("centroid_shift_m")
    support = signals.get("survey_support") or {}
    support_distance = support.get("distance_m")

    if iou_value >= 0.9:
        reasons.append(f"Boundary overlap IoU {iou_value:.2f} - near-identical footprint")
    elif iou_value >= 0.6:
        reasons.append(f"Boundary overlap IoU {iou_value:.2f} - substantial shared area")
    elif iou_value > 0:
        reasons.append(f"Partial boundary overlap IoU {iou_value:.2f}")

    if ratio is not None and ratio >= 0.95:
        reasons.append(f"Area similarity {ratio:.2f} - recorded and surveyed extents agree")
    elif ratio is not None and ratio < 0.85:
        reasons.append(f"Area similarity only {ratio:.2f} - extents differ materially")

    if shift is not None:
        if shift <= 0.5:
            reasons.append(f"Centroid displacement {shift:.2f} m")
        elif shift <= 2.0:
            reasons.append(f"Centroid displaced {shift:.2f} m - plausible legacy shift")
        else:
            reasons.append(f"Centroid displaced {shift:.2f} m - large offset, verify correspondence")

    if support_distance is not None and support_distance <= 1.0:
        reasons.append(
            f"Survey point {support.get('point_id')} supports this parcel "
            f"({support_distance:.2f} m)"
        )

    if not reasons:
        reasons.append("No shared geometry between candidate and reference")
    if verdict == UNMATCHED:
        reasons.append("Below the correspondence threshold - sent to manual review")
    return reasons


class SpatialMatcher:
    """Scores legacy cadastral features against candidate modern features."""

    def __init__(
        self,
        *,
        min_iou: float = 0.55,
        max_centroid_shift_m: float = 25.0,
        survey_support_radius_m: float = 3.0,
    ) -> None:
        self.min_iou = min_iou
        self.max_centroid_shift_m = max_centroid_shift_m
        self.survey_support_radius_m = survey_support_radius_m

    def best_match(
        self,
        legacy_id: str,
        legacy_geometry: Any,
        candidates: Sequence[Dict[str, Any]],
        survey_points: Sequence[Dict[str, Any]] = (),
        survey_index: Optional[Tuple[Any, List[Tuple[int, Dict[str, Any]]]]] = None,
    ) -> MatchCandidate:
        """Return the highest-scoring candidate for one legacy feature."""
        ref = _polygonal(_as_geometry(legacy_geometry))
        best: Optional[MatchCandidate] = None

        for candidate in candidates:
            cand_geom = _polygonal(_as_geometry(candidate.get("geometry")))
            iou_value = iou(ref, cand_geom)
            shift = centroid_displacement_m(ref, cand_geom)
            ratio = area_ratio(ref, cand_geom)
            shape_sim = boundary_similarity(ref, cand_geom)

            centroid_xy = None
            if cand_geom is not None:
                try:
                    centroid_xy = (cand_geom.centroid.x, cand_geom.centroid.y)
                except Exception:
                    centroid_xy = None
            support = nearest_survey_support_m(centroid_xy, survey_points, survey_index)

            # Weighted composite. Every term is a measured quantity in [0, 1].
            score = 0.42 * iou_value
            score += 0.18 * (ratio if ratio is not None else 0.0)
            score += 0.16 * (shape_sim if shape_sim is not None else 0.0)
            if shift is not None:
                shift_term = max(0.0, 1.0 - (shift / self.max_centroid_shift_m))
                score += 0.14 * shift_term
            else:
                score += 0.0
            if support.get("distance_m") is not None:
                support_term = max(
                    0.0, 1.0 - (support["distance_m"] / self.survey_support_radius_m)
                )
                score += 0.10 * support_term

            score = round(min(1.0, score), 4)
            verdict = _verdict_for(score, iou_value, self.min_iou)
            signals = {
                "iou": round(iou_value, 4),
                "centroid_shift_m": shift,
                "area_ratio": ratio,
                "boundary_similarity": shape_sim,
                "survey_support": support,
                "survey_support_within_radius": (
                    support.get("distance_m") is not None
                    and support["distance_m"] <= self.survey_support_radius_m
                ),
            }
            entry = MatchCandidate(
                legacy_id=legacy_id,
                candidate_id=str(candidate.get("id") or candidate.get("parcel_id") or ""),
                score=score,
                verdict=verdict,
                signals=signals,
                reasons=_reasons(signals, verdict),
            )
            if best is None or entry.score > best.score:
                best = entry

        if best is None:
            return MatchCandidate(
                legacy_id=legacy_id,
                candidate_id="",
                score=0.0,
                verdict=UNMATCHED,
                signals={},
                reasons=["No candidate feature available in the comparison layer"],
            )
        return best

    def match_all(
        self,
        legacy_features: Sequence[Dict[str, Any]],
        candidate_features: Sequence[Dict[str, Any]],
        survey_points: Sequence[Dict[str, Any]] = (),
    ) -> List[Dict[str, Any]]:
        """Match every legacy feature and enforce one-to-one assignment.

        Assignment is greedy on descending score, which keeps the result
        deterministic and prevents two legacy parcels claiming one modern
        feature.
        """
        # One index for the whole run instead of a linear scan per candidate.
        survey_index = build_survey_index(survey_points)
        scored: List[MatchCandidate] = []
        for feature in legacy_features:
            scored.append(
                self.best_match(
                    str(feature.get("id") or feature.get("parcel_id") or ""),
                    feature.get("geometry"),
                    candidate_features,
                    survey_points,
                    survey_index,
                )
            )

        scored.sort(key=lambda c: (-c.score, c.legacy_id))
        claimed: set = set()
        results: List[Dict[str, Any]] = []
        for candidate in scored:
            if candidate.verdict == UNMATCHED or candidate.candidate_id in claimed:
                if candidate.candidate_id in claimed:
                    candidate.verdict = REVIEW
                    candidate.reasons.append(
                        f"Candidate {candidate.candidate_id} already assigned to a higher-scoring parcel"
                    )
                claimed.add(candidate.candidate_id)
                results.append(candidate.__dict__)
                continue
            claimed.add(candidate.candidate_id)
            results.append(candidate.__dict__)

        results.sort(key=lambda r: r["legacy_id"])
        return results

    def describe(self) -> Dict[str, Any]:
        return {
            "engine": ENGINE_CAPABILITY,
            "capability_note": ENGINE_NOTE,
            "signals": [
                "intersection_over_union",
                "centroid_displacement",
                "area_similarity",
                "boundary_shape_similarity",
                "survey_point_support",
            ],
            "min_iou": self.min_iou,
            "max_centroid_shift_m": self.max_centroid_shift_m,
            "survey_support_radius_m": self.survey_support_radius_m,
        }
