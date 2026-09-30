"""
NAVONMESH - Explainable Confidence Engine (Phase 17)

Produces a per-parcel confidence score together with the full derivation that
produced it. A confidence number without evidence is not acceptable in a land
record system, so every component here is a measured quantity and every score
carries a human-readable justification.

The previous prototype clamped scores into a band that guaranteed the label
(``min(99.4, max(92.0, ...))``) which meant the status could never contradict
the generator. This module has no such clamp: the score is what the evidence
supports, and the band is applied to the score *afterwards* as a routing
decision only.

Human-in-the-loop routing (Phase 13)
    >= AUTO_ACCEPT_THRESHOLD  -> AUTO_ACCEPTED   (workflow proceeds)
    >= REVIEW_THRESHOLD        -> REVIEW_RECOMMENDED
    otherwise                  -> FIELD_VERIFICATION_REQUIRED
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

AUTO_ACCEPT_THRESHOLD = 0.92
REVIEW_THRESHOLD = 0.75

AUTO_ACCEPTED = "AUTO_ACCEPTED"
REVIEW_RECOMMENDED = "REVIEW_RECOMMENDED"
FIELD_VERIFICATION_REQUIRED = "FIELD_VERIFICATION_REQUIRED"

# Component weights sum to 1.0 and are surfaced in the API so the UI can
# explain the composite instead of presenting an opaque number.
COMPONENT_WEIGHTS: Dict[str, float] = {
    "geometry_match": 0.30,
    "attribute_match": 0.25,
    "area_consistency": 0.20,
    "topology_validity": 0.15,
    "survey_support": 0.10,
}

COMPONENT_LABELS: Dict[str, str] = {
    "geometry_match": "Geometry Match",
    "attribute_match": "Attribute Match",
    "area_consistency": "Area Consistency",
    "topology_validity": "Topology Validity",
    "survey_support": "GNSS / Survey Support",
}


def route_for(score: float) -> str:
    """Map a confidence score onto a human-verification route."""
    if score >= AUTO_ACCEPT_THRESHOLD:
        return AUTO_ACCEPTED
    if score >= REVIEW_THRESHOLD:
        return REVIEW_RECOMMENDED
    return FIELD_VERIFICATION_REQUIRED


def evaluate(
    *,
    iou: Optional[float] = None,
    boundary_similarity: Optional[float] = None,
    attribute_score: Optional[float] = None,
    recorded_area_sqm: Optional[float] = None,
    surveyed_area_sqm: Optional[float] = None,
    area_tolerance_pct: float = 3.5,
    topology_issues: int = 0,
    survey_point_distance_m: Optional[float] = None,
    survey_support_radius_m: float = 3.0,
) -> Dict[str, Any]:
    """Compute a fully explained confidence score for one parcel."""

    components: Dict[str, float] = {}
    evidence: List[Dict[str, Any]] = []
    concerns: List[Dict[str, Any]] = []

    # -- Geometry match ---------------------------------------------------
    geom_terms = [t for t in (iou, boundary_similarity) if t is not None]
    if geom_terms:
        geometry_score = sum(geom_terms) / len(geom_terms)
        components["geometry_match"] = round(geometry_score, 4)
        if iou is not None:
            evidence.append(
                {
                    "signal": "Boundary similarity",
                    "value": f"IoU {iou:.2f}",
                    "passed": iou >= 0.75,
                }
            )
        if boundary_similarity is not None:
            evidence.append(
                {
                    "signal": "Boundary shape similarity",
                    "value": f"{boundary_similarity:.2f}",
                    "passed": boundary_similarity >= 0.70,
                }
            )
        if iou is not None and iou < 0.55:
            concerns.append(
                {
                    "signal": "Low boundary overlap",
                    "value": f"IoU {iou:.2f} below 0.55",
                }
            )
    else:
        components["geometry_match"] = 0.0
        concerns.append({"signal": "No comparable geometry", "value": "geometry_match unavailable"})

    # -- Attribute match --------------------------------------------------
    if attribute_score is not None:
        components["attribute_match"] = round(min(1.0, max(0.0, attribute_score)), 4)
        evidence.append(
            {
                "signal": "Attribute match",
                "value": f"{attribute_score * 100:.0f}% across owner, area and identifier",
                "passed": attribute_score >= 0.80,
            }
        )
        if attribute_score < 0.80:
            concerns.append(
                {"signal": "Attribute disagreement", "value": f"{attribute_score:.2f}"}
            )
    else:
        components["attribute_match"] = 0.0

    # -- Area consistency -------------------------------------------------
    if recorded_area_sqm and surveyed_area_sqm and recorded_area_sqm > 0:
        delta_pct = abs(recorded_area_sqm - surveyed_area_sqm) / recorded_area_sqm * 100.0
        # 0% difference -> 1.0, 2x tolerance -> 0.0, clamped.
        area_score = max(0.0, 1.0 - (delta_pct / (area_tolerance_pct * 2.0)))
        components["area_consistency"] = round(area_score, 4)
        evidence.append(
            {
                "signal": "Area difference",
                "value": f"{delta_pct:.1f}% (tolerance {area_tolerance_pct}%)",
                "passed": delta_pct <= area_tolerance_pct,
            }
        )
        if delta_pct > area_tolerance_pct:
            concerns.append(
                {"signal": "Area difference", "value": f"{delta_pct:.1f}% exceeds tolerance"}
            )
    else:
        components["area_consistency"] = 0.0
        concerns.append({"signal": "Area comparison unavailable", "value": "missing area"})

    # -- Topology validity ------------------------------------------------
    topology_score = max(0.0, 1.0 - (topology_issues / 3.0))
    components["topology_validity"] = round(topology_score, 4)
    if topology_issues == 0:
        evidence.append({"signal": "Valid topology", "value": "no outstanding issues", "passed": True})
    else:
        concerns.append(
            {"signal": "Topology issues", "value": f"{topology_issues} outstanding"}
        )

    # -- Survey support ---------------------------------------------------
    if survey_point_distance_m is not None:
        support_score = max(0.0, 1.0 - (survey_point_distance_m / survey_support_radius_m))
        components["survey_support"] = round(support_score, 4)
        evidence.append(
            {
                "signal": "Survey point support",
                "value": f"nearest observation {survey_point_distance_m:.2f} m",
                "passed": survey_point_distance_m <= survey_support_radius_m,
            }
        )
        if survey_point_distance_m > survey_support_radius_m:
            concerns.append(
                {
                    "signal": "Weak survey support",
                    "value": f"nearest observation {survey_point_distance_m:.2f} m",
                }
            )
    else:
        components["survey_support"] = 0.0

    overall = sum(components[name] * weight for name, weight in COMPONENT_WEIGHTS.items())
    overall = round(min(1.0, max(0.0, overall)), 4)

    return {
        "overall": overall,
        "overall_pct": round(overall * 100.0, 1),
        "route": route_for(overall),
        "components": components,
        "component_labels": COMPONENT_LABELS,
        "weights": COMPONENT_WEIGHTS,
        "breakdown": [
            {
                "key": name,
                "label": COMPONENT_LABELS[name],
                "weight": COMPONENT_WEIGHTS[name],
                "score": components[name],
                "contribution": round(components[name] * COMPONENT_WEIGHTS[name], 4),
            }
            for name in COMPONENT_WEIGHTS
        ],
        "evidence": evidence,
        "concerns": concerns,
        "thresholds": {
            "auto_accept": AUTO_ACCEPT_THRESHOLD,
            "review": REVIEW_THRESHOLD,
        },
        "explanation": _explain(overall, evidence, concerns),
    }


def _explain(overall: float, evidence: List[Dict[str, Any]], concerns: List[Dict[str, Any]]) -> str:
    passing = [e["signal"] for e in evidence if e.get("passed")]
    failing = [c["signal"] for c in concerns]
    parts = [f"Overall confidence {overall * 100:.1f}%."]
    if passing:
        parts.append("Supported by: " + ", ".join(passing) + ".")
    if failing:
        parts.append("Concerns: " + ", ".join(failing) + ".")
    return " ".join(parts)


def distribution(scores: List[float]) -> Dict[str, Any]:
    """Histogram for the confidence distribution chart."""
    buckets = {"90-100": 0, "75-90": 0, "50-75": 0, "0-50": 0}
    for score in scores:
        pct = score * 100.0
        if pct >= 90:
            buckets["90-100"] += 1
        elif pct >= 75:
            buckets["75-90"] += 1
        elif pct >= 50:
            buckets["50-75"] += 1
        else:
            buckets["0-50"] += 1
    mean = round(sum(scores) / len(scores), 4) if scores else 0.0
    return {
        "buckets": buckets,
        "mean": mean,
        "mean_pct": round(mean * 100.0, 1),
        "min": round(min(scores), 4) if scores else 0.0,
        "max": round(max(scores), 4) if scores else 0.0,
        "count": len(scores),
        "auto_accepted": sum(1 for s in scores if s >= AUTO_ACCEPT_THRESHOLD),
        "review_recommended": sum(
            1 for s in scores if REVIEW_THRESHOLD <= s < AUTO_ACCEPT_THRESHOLD
        ),
        "field_verification_required": sum(1 for s in scores if s < REVIEW_THRESHOLD),
    }
