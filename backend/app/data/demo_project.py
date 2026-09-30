"""
NAVONMESH - Multi-Source Demo Dataset
"Demo Dataset - Pune Urban Cadastral Area" (synthetic, non-official)

This module materialises a *real* multi-source scenario on disk so that the
ingestion, CRS and harmonization services parse genuine files (GeoPackage,
GeoJSON, GeoTIFF, CSV) instead of fabricated in-memory payloads.

Sources materialised
--------------------
A. Legacy Cadastral Map   -> GeoPackage, EPSG:32643 (metre based, distorted,
                             contains real gaps / overlaps / slivers / invalid
                             rings so topology repair is a genuine operation)
B. Orthorectified (ORI)   -> GeoTIFF, EPSG:32643
C. DSM / DTM              -> GeoTIFF, EPSG:32643
D. Revenue Records / RoR  -> CSV (non-spatial, joined on survey number)
E. Municipal GIS Layers   -> GeoJSON, EPSG:4326 (needs normalization)
F. Building Footprints    -> GeoJSON, EPSG:4326 (needs normalization)
G. GNSS / CORS + GT       -> CSV observation tables, EPSG:4326

Nothing in this dataset is official government data. All owner names, area
figures and survey numbers are synthetic and generated deterministically.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from app.config import DEMO_RASTER_DIR, STORAGE_DIR, PROJECT_CRS, STORAGE_CRS

VECTOR_DIR = STORAGE_DIR / "demo_vectors"
TABLE_DIR = STORAGE_DIR / "demo_tables"
for _d in (VECTOR_DIR, TABLE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Project definition
# ---------------------------------------------------------------------------
DEMO_PROJECT_ID = "pune-ward-14-urban"
DEMO_PROJECT_NAME = "Pune Urban Cadastral Demo"
DEMO_PROJECT_SUBTITLE = "Demo Dataset - Pune Urban Cadastral Area (synthetic)"

CENTER_LAT = 18.5204
CENTER_LON = 73.8567

GRID_COLS = 21
GRID_ROWS = 20
CELL_W_M = 26.0
CELL_H_M = 22.0
STREET_EVERY = 7      # every 7th column band is a road corridor (no parcels)
STREET_EVERY_ROW = 6  # every 6th row band is a lane
STREET_COLUMN_INDEX = 3  # column bands that carry a road (matches enumerate_cells)
STREET_ROW_INDEX = 4     # row bands that carry a lane (matches enumerate_cells)

RANDOM_SEED = 20260213

# Defect seeds (deterministic) used to create genuine topology problems.
_GAP_CELLS = {(3, 4), (4, 4), (7, 11), (12, 2), (13, 2), (15, 16), (6, 18), (17, 5)}
_OVERLAP_CELLS = {(2, 9), (5, 14), (9, 3), (11, 12), (14, 8), (16, 15), (4, 6), (18, 10)}
_SLIVER_CELLS = {(1, 7), (8, 17), (10, 5), (16, 3), (13, 18), (19, 12)}
_INVALID_CELLS = {(6, 9), (12, 15), (18, 6)}

_FIRST_NAMES_V = ["रमेश", "सुरेश", "गणेश", "अनिता", "दत्तात्रय", "प्रकाश", "सुनीता", "विजय", "दीपक", "संजय"]
_MIDDLE_NAMES_V = ["शंकरराव", "महादेव", "विठ्ठल", "बाबुराव", "रामचंद्र", "गोविंद", "भास्कर", "नारायण"]
_LAST_NAMES_V = ["कुलकर्णी", "पाटील", "जोशी", "जाधव", "देशमुख", "शिंदे", "पाटील", "सावंत", "गायकवाड", "मोरे"]
_FIRST_NAMES_E = ["Ramesh", "Suresh", "Ganesh", "Anita", "Dattatraya", "Prakash", "Sunita", "Vijay", "Deepak", "Sanjay"]
_MIDDLE_NAMES_E = ["S.", "M.", "V.", "B.", "R.", "G.", "Bhaskar", "N."]
_LAST_NAMES_E = ["Kulkarni", "Patil", "Joshi", "Jadhav", "Deshmukh", "Shinde", "Patil", "Sawant", "Gaikwad", "More"]

_LAND_USE = ["Residential", "Residential", "Residential", "Commercial", "Agricultural", "Institutional"]
_PROPERTY_TYPE = ["Private", "Private", "Private", "Ownership", "Leasehold"]


# ---------------------------------------------------------------------------
# Coordinate helpers
# ---------------------------------------------------------------------------
def _utm_transformers():
    """Return (to_project, to_lonlat) transformers, or (None, None) if pyproj is absent."""
    try:
        from pyproj import Transformer

        return (
            Transformer.from_crs("EPSG:4326", PROJECT_CRS, always_xy=True),
            Transformer.from_crs(PROJECT_CRS, "EPSG:4326", always_xy=True),
        )
    except Exception:  # pragma: no cover - pyproj always present in this project
        return None, None


_TO_PROJECT, _TO_LONLAT = _utm_transformers()
_LAT_REF = math.radians(CENTER_LAT)
_M_PER_DEG_LAT = 111_320.0
_M_PER_DEG_LON = 111_320.0 * math.cos(_LAT_REF)


def lonlat_to_project(lon: float, lat: float) -> Tuple[float, float]:
    """Geographic (deg) -> project CRS metres."""
    if _TO_PROJECT is not None:
        x, y = _TO_PROJECT.transform(float(lon), float(lat))
        return float(x), float(y)
    return (float(lon)) * _M_PER_DEG_LON, float(lat) * _M_PER_DEG_LAT  # pragma: no cover


def project_to_lonlat(x: float, y: float) -> Tuple[float, float]:
    """Project CRS metres -> geographic (deg)."""
    if _TO_LONLAT is not None:
        lon, lat = _TO_LONLAT.transform(float(x), float(y))
        return float(lon), float(lat)
    return (float(x)) / _M_PER_DEG_LON, (float(y)) / _M_PER_DEG_LAT  # pragma: no cover


_ORIGIN_X, _ORIGIN_Y = lonlat_to_project(CENTER_LON, CENTER_LAT)
_HALF_W = (GRID_COLS * CELL_W_M) / 2.0
_HALF_H = (GRID_ROWS * CELL_H_M) / 2.0
ORIGIN_X = _ORIGIN_X - _HALF_W
ORIGIN_Y = _ORIGIN_Y - _HALF_H


def cell_bounds(r: int, c: int) -> Tuple[float, float, float, float]:
    x0 = ORIGIN_X + c * CELL_W_M
    y0 = ORIGIN_Y + r * CELL_H_M
    return x0, y0, x0 + CELL_W_M, y0 + CELL_H_M


def project_extent() -> Tuple[float, float, float, float]:
    return (
        ORIGIN_X - 120.0,
        ORIGIN_Y - 120.0,
        ORIGIN_X + GRID_COLS * CELL_W_M + 120.0,
        ORIGIN_Y + GRID_ROWS * CELL_H_M + 120.0,
    )


def ward_extent() -> Tuple[float, float, float, float]:
    """
    Administrative boundary of the demo ward.

    This - not ``project_extent`` - is the area that must be fully covered by
    cadastral parcels. ``project_extent`` adds a 120 m map margin that is
    deliberately outside the ward and must never be reported as a gap.
    """
    return (
        ORIGIN_X,
        ORIGIN_Y,
        ORIGIN_X + GRID_COLS * CELL_W_M,
        ORIGIN_Y + GRID_ROWS * CELL_H_M,
    )


def road_corridors() -> List[Dict[str, float]]:
    """
    The road and lane bands left out of the cadastral grid.

    Public right-of-way is not privately held land, so these bands are passed
    to the topology service as *exclusions*; without them every road would be
    mis-reported as a cadastral gap.
    """
    corridors: List[Dict[str, float]] = []
    # These MUST use the same predicate as ``enumerate_cells`` below, otherwise
    # the exclusion bands will not line up with the un-parcellised cells and
    # every road will be mis-reported as a cadastral gap.
    for c in range(GRID_COLS):
        if c % STREET_EVERY != STREET_COLUMN_INDEX:
            continue
        x0 = ORIGIN_X + c * CELL_W_M
        corridors.append(
            {
                "name": f"Row {c // STREET_EVERY + 1} Road",
                "x0": x0,
                "y0": ORIGIN_Y,
                "x1": x0 + CELL_W_M,
                "y1": ORIGIN_Y + GRID_ROWS * CELL_H_M,
            }
        )
    for r in range(GRID_ROWS):
        if r % STREET_EVERY_ROW != STREET_ROW_INDEX:
            continue
        y0 = ORIGIN_Y + r * CELL_H_M
        corridors.append(
            {
                "name": f"Cross Lane {r // STREET_EVERY_ROW + 1}",
                "x0": ORIGIN_X,
                "y0": y0,
                "x1": ORIGIN_X + GRID_COLS * CELL_W_M,
                "y1": y0 + CELL_H_M,
            }
        )
    return corridors


def ward_extent_geometry():
    """Shapely polygon for the administrative boundary (project CRS)."""
    from shapely.geometry import Polygon

    x0, y0, x1, y1 = ward_extent()
    return Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)])


def road_corridor_geometry() -> List[Any]:
    """Shapely polygons for every public right-of-way band."""
    from shapely.geometry import Polygon

    return [
        Polygon([(c["x0"], c["y0"]), (c["x1"], c["y0"]), (c["x1"], c["y1"]), (c["x0"], c["y1"]), (c["x0"], c["y0"])])
        for c in road_corridors()
    ]


# ---------------------------------------------------------------------------
# Grid enumeration (shared by every source)
# ---------------------------------------------------------------------------
def enumerate_cells() -> List[Dict[str, int]]:
    """Enumerate the buildable grid cells that carry a cadastral parcel."""
    cells: List[Dict[str, int]] = []
    for r in range(GRID_ROWS):
        for c in range(GRID_COLS):
            if c % STREET_EVERY == STREET_COLUMN_INDEX:
                continue
            if r % STREET_EVERY_ROW == STREET_ROW_INDEX:
                continue
            cells.append({"r": r, "c": c, "seq": len(cells) + 1})
    return cells


CELLS = enumerate_cells()
PARCEL_COUNT = len(CELLS)


def survey_number(r: int, c: int) -> str:
    return f"{(r * GRID_COLS) + c + 101}/{(c % 9) + 1}{'-A' if (r + c) % 3 == 0 else ''}"


def parcel_id(r: int, c: int) -> str:
    return f"MH-PUN-{(r * GRID_COLS) + c + 101}/{(c % 9) + 1}"


# ---------------------------------------------------------------------------
# Source A - Legacy Cadastral Map (GeoPackage, EPSG:32643, deliberately defective)
# ---------------------------------------------------------------------------
def _ring(x0: float, y0: float, x1: float, y1: float) -> List[Tuple[float, float]]:
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def build_legacy_cadastral(rng: np.random.Generator) -> List[Dict[str, Any]]:
    """Legacy digitised cadastre: shear, scale drift, plus real topology defects."""
    records: List[Dict[str, Any]] = []
    for cell in CELLS:
        r, c = cell["r"], cell["c"]
        x0, y0, x1, y1 = cell_bounds(r, c)

        shear = 0.35 * math.sin(r * 0.7 + c * 0.11)
        shrink_x = 1.0 - 0.012 - 0.010 * abs(math.cos(c * 0.55))
        shrink_y = 1.0 - 0.010 - 0.012 * abs(math.sin(r * 0.48))
        jitter = 0.12

        lx0 = x0 + shear + float(rng.uniform(-jitter, jitter))
        ly0 = y0 + shear * 0.6 + float(rng.uniform(-jitter, jitter))
        lx1 = x0 + (x1 - x0) * shrink_x - shear * 0.4 + float(rng.uniform(-jitter, jitter))
        ly1 = y0 + (y1 - y0) * shrink_y + shear * 0.5 + float(rng.uniform(-jitter, jitter))

        props = {
            "parcel_id": parcel_id(r, c),
            "survey_no": survey_number(r, c),
            "ward_no": "14",
            "digitised_on": "1968-04-11",
            "source_sheet": f"SHEET-14-{r // 5 + 1:02d}",
        }

        if (r, c) in _GAP_CELLS:
            # A genuine gap: the cell is part of the ward extent and carries
            # survey evidence, but the legacy digitisation simply lost it.
            continue

        if (r, c) in _INVALID_CELLS:
            # Bow-tie ring: a genuine invalid polygon (self-intersecting).
            coords = _ring(lx0, ly0, lx1, ly1)
            coords = [coords[0], coords[2], coords[1], coords[3], coords[4]]
            records.append({"geometry": {"type": "Polygon", "coordinates": [[list(p) for p in coords]]},
                            "properties": {**props, "defect": "self_intersection"}})
            continue

        if (r, c) in _OVERLAP_CELLS:
            # Inflated by 0.7 m on two sides -> real overlap with the neighbour.
            lx1 += 0.7
            ly1 += 0.7
            props["defect"] = "overlap"

        records.append({"geometry": {"type": "Polygon", "coordinates": [[list(p) for p in _ring(lx0, ly0, lx1, ly1)]]},
                        "properties": props})

        if (r, c) in _SLIVER_CELLS:
            # A genuine sub-2 m^2 sliver along the southern boundary.
            sw = 0.075
            s_coords = _ring(lx0, ly0, lx0 + sw, ly0)
            s_coords = _ring(lx0, ly0, lx0 + sw, ly1 - 0.5)
            records.append({"geometry": {"type": "Polygon", "coordinates": [[list(p) for p in s_coords]]},
                            "properties": {**props, "defect": "sliver"}})

    return records


def write_legacy_cadastral_gpkg(records: List[Dict[str, Any]]) -> Path:
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import shape

    path = VECTOR_DIR / "pune_w14_legacy_cadastre.gpkg"
    if path.exists():
        path.unlink()

    gdf = gpd.GeoDataFrame(
        [rec["properties"] for rec in records],
        geometry=[shape(rec["geometry"]) for rec in records],
        crs=PROJECT_CRS,
    )
    gdf.to_file(path, layer="legacy_cadastre", driver="GPKG")
    del pd
    return path


# ---------------------------------------------------------------------------
# Source G - GNSS / CORS + Ground Truthing observation tables (CSV, EPSG:4326)
# ---------------------------------------------------------------------------
def build_gnss_observations(rng: np.random.Generator) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Survey-grade corner observations referenced to a CORS base station.

    The observations are what makes georeferencing real: the pipeline snaps
    legacy vertices onto independently surveyed corners. A configurable share
    of corners is intentionally missing, so some parcels must fall back to
    the legacy geometry and be flagged for verification.
    """
    gnss_rows: List[Dict[str, Any]] = []
    gt_rows: List[Dict[str, Any]] = []
    obs_index = 0

    for cell in CELLS:
        r, c = cell["r"], cell["c"]
        x0, y0, x1, y1 = cell_bounds(r, c)
        pid = parcel_id(r, c)
        corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]

        for corner_idx, (cx, cy) in enumerate(corners):
            # ~9 % of corners were never observed (occluded monuments etc.)
            if rng.random() < 0.09:
                continue
            obs_index += 1
            # Observation noise: 1.5 - 4 cm horizontal, RTK quality grade.
            sigma = float(rng.uniform(0.015, 0.045))
            ox = cx + float(rng.normal(0.0, sigma))
            oy = cy + float(rng.normal(0.0, sigma))
            lon, lat = project_to_lonlat(ox, oy)
            gnss_rows.append(
                {
                    "obs_id": f"OBS{obs_index:06d}",
                    "parcel_id": pid,
                    "corner": f"C{corner_idx + 1}",
                    "easting_m": f"{ox:.3f}",
                    "northing_m": f"{oy:.3f}",
                    "lon": f"{lon:.8f}",
                    "lat": f"{lat:.8f}",
                    "ellipsoidal_height_m": f"{548.0 + float(rng.normal(0, 0.08)):.3f}",
                    "method": "RTK-Network",
                    "base_station": "CORS-PUN-KASBA",
                    "pdop": f"{float(rng.uniform(0.7, 1.6)):.2f}",
                    "rms_horizontal_m": f"{sigma * 1.4:.3f}",
                    "cors_fixed": "1",
                }
            )

            # Ground truthing evidence classes for a subset of corners.
            if rng.random() < 0.34:
                evidence = rng.choice(["stone_monument", "compound_corner", "pillar", "nail_plate", "wall_bracket"])
                gt_rows.append(
                    {
                        "gt_id": f"GT{len(gt_rows) + 1:05d}",
                        "parcel_id": pid,
                        "corner": f"C{corner_idx + 1}",
                        "evidence": str(evidence),
                        "lon": f"{lon:.8f}",
                        "lat": f"{lat:.8f}",
                        "recorded_by": f"REV-FIELD-{r % 4 + 1}",
                        "observed_on": "2025-11-2%d" % (c % 9 + 1),
                        "condition": str(rng.choice(["intact", "intact", "damaged", "missing_marker"])),
                        "accuracy_m": f"{float(rng.uniform(0.05, 0.35)):.2f}",
                    }
                )
    return gnss_rows, gt_rows


def write_gnss_csv(rows: List[Dict[str, Any]], filename: str) -> Path:
    path = TABLE_DIR / filename
    if not rows:
        return path
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Source E - Municipal GIS layers (GeoJSON, EPSG:4326)
# ---------------------------------------------------------------------------
def build_municipal_gis() -> Dict[str, Any]:
    x0, y0, x1, y1 = project_extent()

    # East-west arterial road centreline (metres) -> widened to a 14 m ROW.
    road_axis_x = [x0 + 60, (x0 + x1) / 2, x1 - 60]
    road_axis_y = [ORIGIN_Y + 6 * CELL_H_M + 3.0, ORIGIN_Y + 6 * CELL_H_M - 1.5, ORIGIN_Y + 6 * CELL_H_M + 1.0]

    # Stormwater drainage channel running north-east.
    drain_axis_x = [x0 + 90, (x0 + x1) / 2 + 40, x1 - 40]
    drain_axis_y = [y0 + 40, ORIGIN_Y + 11 * CELL_H_M, y1 - 70]

    # Trunk utility corridor (water main) running north-west.
    util_axis_x = [x0 + 150, (x0 + x1) / 2 - 30, x1 - 120]
    util_axis_y = [y1 - 60, ORIGIN_Y + 9 * CELL_H_M, y0 + 55]

    def to_lonlat_ring(points: Sequence[Tuple[float, float]]) -> List[List[float]]:
        return [list(project_to_lonlat(px, py)) for px, py in points]

    def to_lonlat_line(points: Sequence[Tuple[float, float]]) -> List[List[float]]:
        return [list(project_to_lonlat(px, py)) for px, py in points]

    road_ring = [
        (road_axis_x[0], road_axis_y[0] - 7.0),
        (road_axis_x[1], road_axis_y[1] - 7.0),
        (road_axis_x[2], road_axis_y[2] - 7.0),
        (road_axis_x[2], road_axis_y[2] + 7.0),
        (road_axis_x[1], road_axis_y[1] + 7.0),
        (road_axis_x[0], road_axis_y[0] + 7.0),
        (road_axis_x[0], road_axis_y[0] - 7.0),
    ]

    ward_ring = [
        (x0 - 40, y0 - 40),
        (x1 + 40, y0 - 40),
        (x1 + 40, y1 + 40),
        (x0 - 40, y1 + 40),
        (x0 - 40, y0 - 40),
    ]

    return {
        "type": "FeatureCollection",
        "name": "Pune Ward 14 Municipal GIS (synthetic)",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "layer": "road_row",
                    "name": "14 m Municipal Road Right-of-Way",
                    "row_width_m": 14.0,
                    "authority": "Pune Municipal Corporation",
                    "class": "Arterial",
                },
                "geometry": {"type": "Polygon", "coordinates": [to_lonlat_ring(road_ring)]},
            },
            {
                "type": "Feature",
                "properties": {
                    "layer": "drainage",
                    "name": "Primary Stormwater Drainage Channel",
                    "buffer_m": 3.0,
                    "authority": "Pune Municipal Corporation",
                    "class": "Stormwater",
                },
                "geometry": {"type": "LineString", "coordinates": to_lonlat_line(list(zip(drain_axis_x, drain_axis_y)))},
            },
            {
                "type": "Feature",
                "properties": {
                    "layer": "utility",
                    "name": "Trunk Water Transmission Main (400 mm)",
                    "buffer_m": 2.0,
                    "authority": "Pune Water Supply",
                    "class": "Water",
                },
                "geometry": {"type": "LineString", "coordinates": to_lonlat_line(list(zip(util_axis_x, util_axis_y)))},
            },
            {
                "type": "Feature",
                "properties": {
                    "layer": "ward_boundary",
                    "name": "Ward 14 Administrative Boundary",
                    "ward_no": "14",
                    "authority": "Pune Municipal Corporation",
                    "class": "Administrative",
                },
                "geometry": {"type": "Polygon", "coordinates": [to_lonlat_ring(ward_ring)]},
            },
        ],
    }


def write_municipal_geojson(collection: Dict[str, Any]) -> Path:
    path = VECTOR_DIR / "pune_w14_municipal_gis.geojson"
    payload = dict(collection)
    payload["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


# ---------------------------------------------------------------------------
# Source F - Building footprints (GeoJSON, EPSG:4326)
# ---------------------------------------------------------------------------
def build_building_footprints(rng: np.random.Generator) -> Dict[str, Any]:
    """
    Structure outlines derived from the harmonized (survey-anchored) cell
    footprint. A small share deliberately cross the parcel boundary so the
    building-vs-parcel conflict detector has real work to do.
    """
    features: List[Dict[str, Any]] = []
    idx = 0
    for cell in CELLS:
        r, c = cell["r"], cell["c"]
        x0, y0, x1, y1 = cell_bounds(r, c)

        roll = rng.random()
        if roll < 0.24:
            continue  # vacant plot - no structure

        idx += 1
        coverage = float(rng.uniform(0.30, 0.78))
        inset = 1.0 + (1.0 - coverage) * 8.0
        bx0, by0 = x0 + inset, y0 + inset
        bx1, by1 = x1 - inset, y1 - inset

        crossing = 0.0
        if rng.random() < 0.14:
            # Structure projects beyond the parcel boundary (possible encroachment).
            crossing = float(rng.uniform(0.6, 2.4))
            bx1 += crossing
            by0 -= crossing * 0.4

        ring = [(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1), (bx0, by0)]
        lon_lat = [list(project_to_lonlat(px, py)) for px, py in ring]
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "bf_id": f"BF{idx:05d}",
                    "parcel_id_hint": parcel_id(r, c),
                    "source": "ORI building extraction",
                    "usage": str(rng.choice(["Residential", "Commercial", "Mixed", "Industrial"])),
                    "storeys": int(rng.integers(1, 9)),
                    "confidence": round(float(rng.uniform(0.86, 0.99)), 3),
                },
                "geometry": {"type": "Polygon", "coordinates": [lon_lat]},
            }
        )

    return {"type": "FeatureCollection", "name": "Pune Ward 14 Building Footprints (synthetic)", "features": features}


def write_building_geojson(collection: Dict[str, Any]) -> Path:
    path = VECTOR_DIR / "pune_w14_building_footprints.geojson"
    payload = dict(collection)
    payload["crs"] = {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}}
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)
    return path


# ---------------------------------------------------------------------------
# Source D - Revenue records / RoR (CSV, non-spatial)
# ---------------------------------------------------------------------------
def build_revenue_records(rng: np.random.Generator) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    road_names = ["Laxmi Road", "Jangali Maharaj Road", "Kelkar Road", "Tandale Road", "Mangalwar Peth"]
    for cell in CELLS:
        r, c = cell["r"], cell["c"]
        fn = _FIRST_NAMES_V[(r * 5 + c * 3) % len(_FIRST_NAMES_V)]
        mn = _MIDDLE_NAMES_V[(r * 3 + c * 5) % len(_MIDDLE_NAMES_V)]
        ln = _LAST_NAMES_V[(r * 7 + c * 11) % len(_LAST_NAMES_V)]
        fn_e = _FIRST_NAMES_E[(r * 5 + c * 3) % len(_FIRST_NAMES_E)]
        mn_e = _MIDDLE_NAMES_E[(r * 3 + c * 5) % len(_MIDDLE_NAMES_E)]
        ln_e = _LAST_NAMES_E[(r * 7 + c * 11) % len(_LAST_NAMES_E)]

        # Recorded area carries a genuine, sometimes material, variance from
        # the surveyed area (old chain-survey error + later subdivisions).
        variance = float(rng.normal(0.0, 0.028))
        if rng.random() < 0.06:
            variance += float(rng.choice([-1.0, 1.0]) * rng.uniform(0.08, 0.17))
        recorded = round(CELL_W_M * CELL_H_M * (1.0 - variance), 2)

        rows.append(
            {
                "survey_no": survey_number(r, c),
                "parcel_ref": parcel_id(r, c),
                "owner_name": f"{fn_e} {mn_e} {ln_e}",
                "owner_name_local": f"{fn} {mn} {ln}",
                "owner_father_name": f"{mn_e} {ln_e}",
                "property_type": _PROPERTY_TYPE[(r + c) % len(_PROPERTY_TYPE)],
                "land_use": _LAND_USE[(r * 3 + c) % len(_LAND_USE)],
                "recorded_area": recorded,
                "area_unit": "sq.m",
                "ward": "14",
                "village": "Kasba Peth",
                "zone": str(rng.choice(["ZR", "ZM", "ZMC", "ZI"])),
                "road_ref": road_names[c % len(road_names)],
                "utility_ref": f"WS-{400 + (r % 20)}",
                "ror_year": 1971,
                "revision": str(rng.integers(1, 4)),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Sources B & C - ORI and DSM/DTM rasters (GeoTIFF, EPSG:32643)
# ---------------------------------------------------------------------------
def _write_geotiff(path: Path, array: np.ndarray, affine: Sequence[float], crs: str) -> Path:
    """Write a single-band GeoTIFF with an explicit 6-element affine transform."""
    import rasterio
    from rasterio.transform import Affine

    height, width = array.shape
    transform = Affine(*affine)
    if path.exists():
        path.unlink()
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32" if array.dtype.kind == "f" else "uint8",
        "crs": crs,
        "transform": transform,
        "compress": "deflate",
        "tiled": True,
        "blockxsize": 256,
        "blockysize": 256,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(array, 1)
        dataset.set_band_description(1, path.stem)
    return path


def build_rasters(rng: np.random.Generator) -> Dict[str, Path]:
    """
    Materialise a real orthorectified raster (ORI) plus DSM and DTM at 0.5 m GSD.

    These are synthetic rasters (procedural urban texture), not aerial
    photography. Their purpose is to exercise a genuine raster ingestion,
    CRS and band-statistics path.
    """
    ex_x0, ex_y0, ex_x1, ex_y1 = project_extent()
    res = 0.5
    width = int((ex_x1 - ex_x0) / res)
    height = int((ex_y1 - ex_y0) / res)
    width = min(width, 1400)
    height = min(height, 1400)

    transform_tuple = (res, 0.0, ex_x0, 0.0, -res, ex_y1)

    xs = ex_x0 + (np.arange(width) + 0.5) * res
    ys = ex_y1 - (np.arange(height) + 0.5) * res
    xx, yy = np.meshgrid(xs, ys)

    # Procedural "built-up" texture: block pattern following the street grid.
    block = (
        (np.sin(xx / (CELL_W_M * 0.5)) * 0.5 + 0.5)
        * (np.cos(yy / (CELL_H_M * 0.5)) * 0.5 + 0.5)
    )
    texture = 70 + 90 * block + rng.normal(0, 12, size=(height, width))
    texture = np.clip(texture, 0, 255).astype("uint8")

    dtm = (548.0 + 4.0 * np.sin(xx / 420.0) + 3.0 * np.cos(yy / 380.0)
           + rng.normal(0, 0.35, size=(height, width))).astype("float32")

    building_mask = (block > 0.42).astype("float32")
    height_field = building_mask * (4.0 + 11.0 * rng.random(size=(height, width)))
    dsm = (dtm + height_field).astype("float32")

    ori_path = _write_geotiff(DEMO_RASTER_DIR / "pune_w14_ori_5cm_ortho.tif", texture, transform_tuple, PROJECT_CRS)
    dsm_path = _write_geotiff(DEMO_RASTER_DIR / "pune_w14_dsm.tif", dsm, transform_tuple, PROJECT_CRS)
    dtm_path = _write_geotiff(DEMO_RASTER_DIR / "pune_w14_dtm.tif", dtm, transform_tuple, PROJECT_CRS)
    return {"ori": ori_path, "dsm": dsm_path, "dtm": dtm_path}


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
_BOOTSTRAPPED: Optional[Dict[str, Any]] = None


def bootstrap_demo_project(force: bool = False) -> Dict[str, Any]:
    """
    Materialise (once) and return the demo project descriptor.

    The returned descriptor contains *file paths* - ingestion re-reads them,
    so the pipeline is exercised against genuine on-disk data.
    """
    global _BOOTSTRAPPED
    if _BOOTSTRAPPED is not None and not force:
        return _BOOTSTRAPPED

    rng = np.random.default_rng(RANDOM_SEED)

    legacy_records = build_legacy_cadastral(rng)
    legacy_path = write_legacy_cadastral_gpkg(legacy_records)

    gnss_rows, gt_rows = build_gnss_observations(rng)
    gnss_path = write_gnss_csv(gnss_rows, "pune_w14_gnss_cors_observations.csv")
    gt_path = write_gnss_csv(gt_rows, "pune_w14_ground_truthing.csv")

    municipal_path = write_municipal_geojson(build_municipal_gis())
    building_path = write_building_geojson(build_building_footprints(rng))

    ror_rows = build_revenue_records(rng)
    ror_path = write_gnss_csv(ror_rows, "pune_w14_revenue_ror.csv")

    rasters = build_rasters(rng)

    lon_c, lat_c = project_to_lonlat((ORIGIN_X + GRID_COLS * CELL_W_M / 2), (ORIGIN_Y + GRID_ROWS * CELL_H_M / 2))

    descriptor = {
        "project_id": DEMO_PROJECT_ID,
        "name": DEMO_PROJECT_NAME,
        "subtitle": DEMO_PROJECT_SUBTITLE,
        "dataset_notice": (
            "Synthetic demonstration dataset generated for SIH26013 evaluation. "
            "Not official government data. No record here confers legal title."
        ),
        "is_demo": True,
        "generated_at": None,
        "center": [round(lon_c, 6), round(lat_c, 6)],
        "zoom": 18.2,
        "crs": PROJECT_CRS,
        "storage_crs": STORAGE_CRS,
        "grid": {
            "cols": GRID_COLS,
            "rows": GRID_ROWS,
            "cell_width_m": CELL_W_M,
            "cell_height_m": CELL_H_M,
            "buildable_parcels": PARCEL_COUNT,
        },
        "files": {
            "legacy_cadastre": {"path": str(legacy_path), "crs": PROJECT_CRS, "category": "cadastral_map"},
            "municipal_gis": {"path": str(municipal_path), "crs": STORAGE_CRS, "category": "municipal_gis"},
            "building_footprints": {"path": str(building_path), "crs": STORAGE_CRS, "category": "building_footprint"},
            "revenue_ror": {"path": str(ror_path), "crs": None, "category": "revenue_records"},
            "gnss_cors": {"path": str(gnss_path), "crs": STORAGE_CRS, "category": "gnss_cors"},
            "ground_truthing": {"path": str(gt_path), "crs": STORAGE_CRS, "category": "ground_truthing"},
            "ori": {"path": str(rasters["ori"]), "crs": PROJECT_CRS, "category": "ortho_ori"},
            "dsm": {"path": str(rasters["dsm"]), "crs": PROJECT_CRS, "category": "dsm_dtm"},
            "dtm": {"path": str(rasters["dtm"]), "crs": PROJECT_CRS, "category": "dsm_dtm"},
        },
    }

    _BOOTSTRAPPED = descriptor
    return descriptor


def demo_file_list() -> List[Dict[str, Any]]:
    """Return the file manifest used to seed the ingestion registry."""
    descriptor = bootstrap_demo_project()
    return [
        {"key": key, **value, "name": Path(value["path"]).name}
        for key, value in descriptor["files"].items()
    ]


def project_bounds_lonlat() -> List[List[float]]:
    x0, y0, x1, y1 = project_extent()
    ring = [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]
    return [list(project_to_lonlat(px, py)) for px, py in ring]
