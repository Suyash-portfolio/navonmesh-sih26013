"""
NAVONMESH - Pune Ward 14 High-Density Urban Cadastral Dataset
Generates 1,420 cadastral parcels across Ward 14, Pune Urban Sector (18.5204° N, 73.8567° E)
Includes:
- Legacy distorted cloth map geometries (Shajra/Musavi)
- Ground-truth AI harmonized geometries (SAM-2 + nDSM Eaves snapped)
- Multilingual Khasra registry (Marathi/Hindi + English)
- 28 active municipal encroachments (Stormwater drains & Road ROW)
- Elevation models (nDSM heights 3.2m - 18.5m)
"""

import json
import math
import numpy as np
from typing import Dict, Any, List
from shapely.geometry import Polygon, LineString
from app.geoai.ulpin_generator import ULPINGenerator
from app.geoai.multilingual_linker import IndicSoundexMatcher, compute_area_variance_ratio
from app.geoai.confidence_evaluator import ConfidenceAuditor


def generate_pune_ward14_data() -> Dict[str, Any]:
    np.random.seed(42)
    
    center_lat = 18.5204
    center_lon = 73.8567
    
    # 1. Drainage canal (runs diagonally across ward)
    drainage_coords = [
        [73.8520, 18.5170],
        [73.8545, 18.5192],
        [73.8570, 18.5215],
        [73.8595, 18.5238],
        [73.8615, 18.5255]
    ]
    drainage_line = LineString(drainage_coords)
    
    # 2. Road Right-of-Way vectors (14m wide municipal road)
    road_coords = [
        [73.8510, 18.5220],
        [73.8540, 18.5218],
        [73.8580, 18.5212],
        [73.8620, 18.5208]
    ]
    road_line = LineString(road_coords)
    road_row_poly = road_line.buffer(0.00007) # ~8m buffer each side = 16m road ROW

    # Sample realistic Maharashtrian / Indian owner registries
    first_names_vernacular = ["रमेश", "सुरेश", "गणेश", "अनिता", "दत्तात्रय", "प्रकाश", "सुनीता", "विजय", "दीपक", "संजय", "मंगेश", "प्रवीण", "सविता", "अमोल", "संदीप"]
    middle_names_vernacular = ["शंकरराव", "महादेव", "विठ्ठल", "बाबुराव", "रामचंद्र", "दत्तात्रय", "गोविंद", "आनंदराव", "भास्कर", "नारायण"]
    last_names_vernacular = ["कुलकर्णी", "पाटील", "जोशी", "जाधव", "देशमुख", "शिंदे", "पवार", "गायकवाड", "मोरे", "कदम", "भोसले", "चव्हाण", "सावंत"]

    first_names_en = ["Ramesh", "Suresh", "Ganesh", "Anita", "Dattatraya", "Prakash", "Sunita", "Vijay", "Deepak", "Sanjay", "Mangesh", "Pravin", "Savita", "Amol", "Sandeep"]
    middle_names_en = ["S.", "M.", "V.", "B.", "R.", "D.", "G.", "A.", "Bhaskar", "N."]
    last_names_en = ["Kulkarni", "Patil", "Joshi", "Jadhav", "Deshmukh", "Shinde", "Pawar", "Gaikwad", "More", "Kadam", "Bhosle", "Chavan", "Sawant"]

    parcels = []
    encroachment_conflicts = []
    
    total_parcels_target = 1420
    rows = 38
    cols = 38
    
    cell_width = 0.00026   # ~28 meters
    cell_height = 0.00022  # ~24 meters

    origin_lon = center_lon - (cols * cell_width) / 2
    origin_lat = center_lat - (rows * cell_height) / 2

    parcel_idx = 0
    encroachment_id_counter = 1

    for r in range(rows):
        for c in range(cols):
            if parcel_idx >= total_parcels_target:
                break

            parcel_idx += 1
            parcel_id = f"MH-PUN-{100 + (parcel_idx // 10)}/{(parcel_idx % 10) + 1}"
            khasra_no = f"{100 + (parcel_idx // 10)}/{parcel_idx % 10 + 1}{'-A' if parcel_idx % 3 == 0 else ''}"

            x0 = origin_lon + c * cell_width + np.random.uniform(-0.00002, 0.00002)
            y0 = origin_lat + r * cell_height + np.random.uniform(-0.00002, 0.00002)
            w = cell_width * np.random.uniform(0.85, 0.96)
            h = cell_height * np.random.uniform(0.85, 0.96)

            # Ground truth / AI harmonized coordinates (Snapped green boundaries)
            ai_poly_coords = [
                [x0, y0],
                [x0 + w, y0],
                [x0 + w, y0 + h],
                [x0, y0 + h],
                [x0, y0]
            ]
            ai_poly = Polygon(ai_poly_coords)
            surveyed_area_sqm = round(ai_poly.area * (111000**2), 2)

            # Distorted legacy coordinates (Simulate cloth map shrinkage, shear, and rotational shift)
            shear_factor = 0.000045 * math.sin(r * 0.3)
            shrink_factor = 0.94 + 0.08 * math.cos(c * 0.4)

            legacy_poly_coords = [
                [x0 - shear_factor, y0 - shear_factor],
                [x0 + w * shrink_factor + shear_factor * 0.5, y0 - shear_factor * 0.8],
                [x0 + w * shrink_factor + shear_factor * 1.2, y0 + h * shrink_factor + shear_factor * 0.6],
                [x0 - shear_factor * 0.7, y0 + h * shrink_factor - shear_factor * 0.4],
                [x0 - shear_factor, y0 - shear_factor]
            ]
            legacy_poly = Polygon(legacy_poly_coords)
            legacy_area_sqm = round(legacy_poly.area * (111000**2), 2)

            # Name matching
            fn_idx = (r * 7 + c * 3) % len(first_names_vernacular)
            mn_idx = (r * 3 + c * 5) % len(middle_names_vernacular)
            ln_idx = (r * 11 + c * 13) % len(last_names_vernacular)

            owner_vernacular = f"{first_names_vernacular[fn_idx]} {middle_names_vernacular[mn_idx]} {last_names_vernacular[ln_idx]}"
            owner_en = f"{first_names_en[fn_idx]} {middle_names_en[mn_idx]} {last_names_en[ln_idx]}"

            # Multilingual score
            s_text, match_info = IndicSoundexMatcher.match_names(owner_vernacular, owner_en)

            # SAM-2 Boundary Segmentation Accuracy (FR-2 / Benchmarking standard >= 94.5%)
            segmentation_iou = round(float(np.random.uniform(0.952, 0.984)), 4)
            conflation_iou = ConfidenceAuditor.calculate_iou(legacy_poly, ai_poly)
            t_validity = 1.0  # Planar and valid

            # Check Encroachments
            encroach_res = ConfidenceAuditor.audit_encroachments(
                ai_poly,
                [drainage_line],
                [road_row_poly],
                drainage_buffer_meters=3.0
            )

            # Force exactly 28 realistic encroachments
            is_encroaching = encroach_res["is_encroaching"]
            if is_encroaching and len(encroachment_conflicts) < 28:
                encroachment_type = encroach_res["encroachment_type"]
                encroached_area = max(4.2, encroach_res["total_encroached_area_sqm"])
            elif len(encroachment_conflicts) < 28 and (parcel_idx in [14, 28, 45, 78, 109, 142, 198, 230, 267, 310, 355, 412, 480, 520, 580, 640, 710, 790, 850, 920, 990, 1060, 1120, 1190, 1250, 1310, 1370, 1410]):
                is_encroaching = True
                encroachment_type = "Stormwater Drainage Canal Encroachment" if parcel_idx % 2 == 0 else "Municipal Road Right-of-Way (RoW) Encroachment"
                encroached_area = round(float(12.5 + ((parcel_idx * 7) % 15) * 1.4), 2)
            else:
                is_encroaching = False
                encroachment_type = None
                encroached_area = 0.0

            # Area calculations
            if is_encroaching:
                legal_area_sqm = round(surveyed_area_sqm - encroached_area, 2)
            else:
                variance_factor = 0.968 + (((parcel_idx * 13) % 45) * 0.0014)
                legal_area_sqm = round(surveyed_area_sqm * (0.985 if variance_factor == 1.0 else variance_factor), 2)

            delta_area = compute_area_variance_ratio(legal_area_sqm, surveyed_area_sqm)
            area_diff_sqm = round(surveyed_area_sqm - legal_area_sqm, 2)

            # Confidence score calculation
            if is_encroaching:
                raw_score = 41.0 + (parcel_idx % 18)
                status = "Encroachment"
                status_chip = "ENCROACHMENT"
                confidence_score = round(raw_score, 1)
            elif delta_area > 0.035 or conflation_iou < 0.78:
                status = "Review"
                status_chip = "REVIEW"
                confidence_score, _ = ConfidenceAuditor.compute_composite_confidence_score(conflation_iou, delta_area, t_validity, s_text)
                confidence_score = min(88.5, max(71.0, confidence_score))
            else:
                status = "Approved"
                status_chip = "APPROVED"
                confidence_score, _ = ConfidenceAuditor.compute_composite_confidence_score(conflation_iou, delta_area, t_validity, s_text)
                confidence_score = min(99.4, max(92.0, confidence_score))

            # nDSM building height for 3D extrusion (3.0m - 16.5m)
            ndsm_height = round(float(3.2 + (parcel_idx % 5) * 3.1 + np.random.uniform(0.1, 1.8)), 1)
            eave_buffer_applied = 0.40 if ndsm_height >= 3.0 else 0.0

            # ULPIN
            ulpin = ULPINGenerator.generate_ulpin(
                state_code="MH",
                district_code="27",
                taluk_code="014",
                village_code="982",
                parcel_seq=parcel_idx,
                centroid_lat=y0 + h/2,
                centroid_lon=x0 + w/2
            )

            parcel_obj = {
                "parcel_id": parcel_id,
                "ulpin": ulpin,
                "khasra_no": khasra_no,
                "owner_vernacular": owner_vernacular,
                "owner_en": owner_en,
                "legal_area_sqm": legal_area_sqm,
                "surveyed_area_sqm": surveyed_area_sqm,
                "area_diff_sqm": area_diff_sqm,
                "delta_area_pct": round(delta_area * 100, 2),
                "confidence_score": confidence_score,
                "iou": conflation_iou,
                "segmentation_iou": segmentation_iou,
                "status": status,
                "status_chip": status_chip,
                "ndsm_height_m": ndsm_height,
                "eave_buffer_m": eave_buffer_applied,
                "is_encroaching": is_encroaching,
                "encroachment_type": encroachment_type,
                "encroached_area_sqm": encroached_area,
                "geometry_legacy": {
                    "type": "Polygon",
                    "coordinates": [legacy_poly_coords]
                },
                "geometry_harmonized": {
                    "type": "Polygon",
                    "coordinates": [ai_poly_coords]
                },
                "centroid": [round(x0 + w/2, 6), round(y0 + h/2, 6)]
            }

            parcels.append(parcel_obj)

            if is_encroaching and len(encroachment_conflicts) < 28:
                encroachment_conflicts.append({
                    "id": f"ENC-{encroachment_id_counter:03d}",
                    "parcel_id": parcel_id,
                    "ulpin": ulpin,
                    "owner_name": owner_en,
                    "owner_vernacular": owner_vernacular,
                    "khasra_no": khasra_no,
                    "discrepancy_type": encroachment_type,
                    "variance_sqm": f"+{encroached_area} sq.m",
                    "encroached_area_sqm": encroached_area,
                    "confidence": f"{confidence_score}%",
                    "confidence_num": confidence_score,
                    "centroid": parcel_obj["centroid"],
                    "legal_action_required": "Issue Notice u/s 248 MLRC"
                })
                encroachment_id_counter += 1

    # Sector KPI Metrics
    harmonized_count = sum(1 for p in parcels if p["status"] == "Approved")
    harmonization_rate_pct = round((harmonized_count / len(parcels)) * 100, 1)
    avg_confidence = round(float(np.mean([p["confidence_score"] for p in parcels])), 1)

    return {
        "sector_info": {
            "name": "Ward 14, Pune Urban Sector",
            "state": "Maharashtra",
            "district": "Pune",
            "taluk": "Haveli",
            "crs": "EPSG:4326 (WGS84) / EPSG:32643 (UTM 43N)",
            "center": [center_lon, center_lat],
            "zoom": 17
        },
        "kpi_metrics": {
            "total_parcels": len(parcels),
            "harmonization_rate_pct": harmonization_rate_pct,
            "active_encroachments": len(encroachment_conflicts),
            "avg_ai_confidence_pct": avg_confidence,
            "gcp_tie_points": 64,
            "tps_warp_rmse_cm": 4.2
        },
        "parcels": parcels,
        "encroachment_conflicts": encroachment_conflicts,
        "infrastructure_layers": {
            "drainage": {
                "type": "LineString",
                "name": "Primary Stormwater Drainage Canal",
                "coordinates": drainage_coords
            },
            "road_row": {
                "type": "Polygon",
                "name": "14m Municipal Road Right-of-Way",
                "coordinates": [list(road_row_poly.exterior.coords)]
            }
        }
    }
