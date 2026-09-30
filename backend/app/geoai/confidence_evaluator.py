"""
NAVONMESH - Module 5: Confidence Scoring & Encroachment Auditing
FR-5 Specification:
- Confidence Matrix Formula:
  Confidence Score = (0.40 * IoU) + (0.35 * [1 - DeltaArea]) + (0.15 * T_validity) + (0.10 * S_text)
- Encroachment Intersector: Performs real-time polygon intersection against municipal drainage and road right-of-way buffers.
"""

from typing import Dict, Any, List, Optional, Tuple
from shapely.geometry import Polygon, LineString, MultiPolygon, shape
import numpy as np


class ConfidenceAuditor:
    def __init__(self):
        pass

    @staticmethod
    def calculate_iou(poly1: Polygon, poly2: Polygon) -> float:
        """Computes Intersection-over-Union (IoU) between legacy and surveyed geometries."""
        if not poly1.is_valid:
            poly1 = poly1.buffer(0)
        if not poly2.is_valid:
            poly2 = poly2.buffer(0)

        if poly1.is_empty or poly2.is_empty:
            return 0.0

        intersection_area = poly1.intersection(poly2).area
        union_area = poly1.union(poly2).area

        if union_area <= 0:
            return 0.0
        return round(float(intersection_area / union_area), 4)

    @staticmethod
    def compute_composite_confidence_score(
        iou: float,
        delta_area: float,
        t_validity: float,
        s_text: float
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Computes composite confidence score based on the official PRD formula:
        Confidence Score = (0.40 * IoU) + (0.35 * [1 - DeltaArea]) + (0.15 * T_validity) + (0.10 * S_text)
        """
        clamped_iou = max(0.0, min(1.0, iou))
        clamped_area_factor = max(0.0, min(1.0, 1.0 - delta_area))
        clamped_t = max(0.0, min(1.0, t_validity))
        clamped_s = max(0.0, min(1.0, s_text))

        score = (
            (0.40 * clamped_iou) +
            (0.35 * clamped_area_factor) +
            (0.15 * clamped_t) +
            (0.10 * clamped_s)
        )
        final_score = round(float(score * 100.0), 2)  # Return as 0 - 100%

        # Classification
        if final_score >= 90.0:
            status = "Approved"
            status_chip = "APPROVED"
        elif final_score >= 70.0:
            status = "Review"
            status_chip = "REVIEW"
        else:
            status = "Encroachment"
            status_chip = "ENCROACHMENT"

        return final_score, {
            "confidence_score_pct": final_score,
            "status": status,
            "status_chip": status_chip,
            "breakdown": {
                "iou_contribution_pct": round(0.40 * clamped_iou * 100, 2),
                "area_delta_contribution_pct": round(0.35 * clamped_area_factor * 100, 2),
                "topology_contribution_pct": round(0.15 * clamped_t * 100, 2),
                "text_match_contribution_pct": round(0.10 * clamped_s * 100, 2),
                "raw_iou": clamped_iou,
                "raw_delta_area": round(delta_area, 4),
                "t_validity": clamped_t,
                "s_text": clamped_s
            }
        }

    @staticmethod
    def audit_encroachments(
        parcel_polygon: Polygon,
        drainage_lines: List[LineString],
        road_right_of_ways: List[Polygon],
        drainage_buffer_meters: float = 3.0
    ) -> Dict[str, Any]:
        """
        Performs spatial intersection against municipal drainage and road ROW buffers.
        drainage_buffer_meters: standard 3m safety offset for municipal stormwater canals.
        """
        # Convert meters to approximate degrees
        drainage_buffer_deg = drainage_buffer_meters * 0.000009
        
        is_encroaching = False
        encroachment_type = None
        encroached_area_sqm = 0.0
        details = []

        # 1. Drainage Buffer Intersection
        for idx, drain in enumerate(drainage_lines):
            drain_buffer = drain.buffer(drainage_buffer_deg)
            if parcel_polygon.intersects(drain_buffer):
                overlap = parcel_polygon.intersection(drain_buffer)
                overlap_sqm = overlap.area * (111000**2)
                if overlap_sqm >= 1.0:  # Ignore micro numerical tolerance
                    is_encroaching = True
                    encroachment_type = "Stormwater Drainage Canal Encroachment"
                    encroached_area_sqm += overlap_sqm
                    details.append({
                        "asset_type": "Drainage",
                        "asset_id": f"DRAIN-SEC14-{idx+1:02d}",
                        "overlap_area_sqm": round(overlap_sqm, 2),
                        "legal_violation": "Section 248 of Maharashtra Land Revenue Code (MLRC)"
                    })

        # 2. Road Right-of-Way Intersection
        for idx, road_row in enumerate(road_right_of_ways):
            if parcel_polygon.intersects(road_row):
                overlap = parcel_polygon.intersection(road_row)
                overlap_sqm = overlap.area * (111000**2)
                if overlap_sqm >= 1.0:
                    is_encroaching = True
                    encroachment_type = "Municipal Road Right-of-Way (RoW) Encroachment" if not encroachment_type else "Road & Drainage Buffer Encroachment"
                    encroached_area_sqm += overlap_sqm
                    details.append({
                        "asset_type": "Road_ROW",
                        "asset_id": f"ROAD-ROW-14M-{idx+1:02d}",
                        "overlap_area_sqm": round(overlap_sqm, 2),
                        "legal_violation": "Maharashtra Municipal Corporations Act Sec 231"
                    })

        return {
            "is_encroaching": is_encroaching,
            "encroachment_type": encroachment_type,
            "total_encroached_area_sqm": round(encroached_area_sqm, 2),
            "intersections": details
        }
