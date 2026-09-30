"""
NAVONMESH - Platform Configuration & Domain Constants
SIH26013 | Ministry of Rural Development | Department of Land Resources (DoLR)

Single source of truth for branding metadata, the reference coordinate
reference system, the canonical land-record schema and the SIH26013
multi-source category registry.

Disclaimer: this platform produces *decision-support* output. It never
certifies legal title, never issues an official ULPIN and never replaces
a statutory authority.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[1]
STORAGE_DIR = Path(os.environ.get("NAVONMESH_STORAGE_DIR", BACKEND_ROOT / ".storage"))
UPLOAD_DIR = STORAGE_DIR / "uploads"
DEMO_RASTER_DIR = STORAGE_DIR / "demo_rasters"
EXPORT_DIR = STORAGE_DIR / "exports"

for _directory in (STORAGE_DIR, UPLOAD_DIR, DEMO_RASTER_DIR, EXPORT_DIR):
    _directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Branding / Problem Statement metadata
# ---------------------------------------------------------------------------
PLATFORM: Dict[str, Any] = {
    "product_name": "NAVONMESH",
    "short_name": "NAVONMESH",
    "full_title": "Navonmesh - Intelligent Multi-Source Geospatial Harmonization Platform",
    "tagline": "One Land Parcel. Multiple Sources. One Intelligent View.",
    "problem_title": (
        "Automated Integration and Intelligent Harmonization of Multi-source "
        "Geospatial Data for Urban Land Record Management"
    ),
    "department": "Department of Land Resources (DoLR)",
    "theme": "Smart Automation",
    "core_message": "One Land Parcel. Multiple Sources. One Intelligent View.",
    "capability_line": (
        "Automated Integration and Intelligent Harmonization of Multi-source "
        "Geospatial Data for Urban Land Record Management"
    ),
    "problem_statement_id": "SIH26013",
    "organization": "Ministry of Rural Development (MoRD)",
    "version": "2.0.0",
    "demo_mode": True,
    "official_status": "PROTOTYPE - not an official Government of India system",
    "disclaimer": (
        "AI-assisted harmonization output for decision support only. This "
        "platform does not certify legal title, does not issue official ULPIN "
        "numbers, does not create official government records and is not "
        "connected to any government or NAKSHA service. Statutory verification "
        "by the competent land record authority is required."
    ),
}

# ---------------------------------------------------------------------------
# Reference CRS
# ---------------------------------------------------------------------------
# The project CRS is a projected, metre-based CRS so that every metric
# computation (area, distance, topology snapping, conflict buffers) is exact.
# Storage/transport CRS is geographic WGS84 for browser interoperability.
PROJECT_CRS = "EPSG:32643"  # WGS 84 / UTM zone 43N - covers Pune (73.85E)
PROJECT_CRS_LABEL = "WGS 84 / UTM 43N"
STORAGE_CRS = "EPSG:4326"  # WGS 84 geographic

# Candidate project CRSs offered to the operator during CRS normalization.
PROJECT_CRS_CANDIDATES: List[Dict[str, str]] = [
    {"code": "EPSG:32643", "label": "WGS 84 / UTM 43N", "zone": "43N", "datum": "WGS84"},
    {"code": "EPSG:32644", "label": "WGS 84 / UTM 44N", "zone": "44N", "datum": "WGS84"},
    {"code": "EPSG:32743", "label": "WGS 84 / UTM 43S", "zone": "43S", "datum": "WGS84"},
    {"code": "EPSG:32642", "label": "WGS 84 / UTM 42N", "zone": "42N", "datum": "WGS84"},
    {"code": "EPSG:3857", "label": "WGS 84 / Pseudo-Mercator", "zone": "n/a", "datum": "WGS84"},
    {"code": "EPSG:7755", "label": "WGS 84 / India NSF LCC", "zone": "n/a", "datum": "WGS84"},
    {"code": "EPSG:24378", "label": "Indian 1954 / UTM zone 43N", "zone": "43N", "datum": "Indian 1954"},
    {"code": "EPSG:4326", "label": "WGS 84 (geographic)", "zone": "n/a", "datum": "WGS84"},
]


# ---------------------------------------------------------------------------
# SIH26013 multi-source category registry
# ---------------------------------------------------------------------------
# `capability` is honest: it states exactly which parser is wired in.
#   "native"        -> full server-side parsing implemented
#   "demo-parser"   -> deterministic demonstration parser implemented here
#   "adapter-ready" -> interface defined, model/reader not bundled
SOURCE_CATEGORIES: List[Dict[str, Any]] = [
    {
        "id": "drone_imagery",
        "label": "Drone Imagery",
        "description": "Unmanned aerial vehicle RGB capture flown over the project extent.",
        "geometry": "raster",
        "default_format": "GeoTIFF",
        "formats": ["GeoTIFF", "COG", "JPEG2000", "PNG (with worldfile)"],
        "capability": "adapter-ready",
        "capability_note": (
            "Raster metadata (CRS, extent, band count, GSD) is read natively. "
            "Photogrammetric alignment requires a bundle/lift adapter."
        ),
    },
    {
        "id": "ortho_ori",
        "label": "Orthorectified Imagery (ORI)",
        "description": "Survey-grade orthophoto with an authoritative CRS and tie-point ledger.",
        "geometry": "raster",
        "default_format": "COG",
        "formats": ["COG", "GeoTIFF", "MBTiles"],
        "capability": "native",
        "capability_note": "Raster header, CRS, GSD and band statistics are read with Rasterio.",
    },
    {
        "id": "dsm_dtm",
        "label": "DSM / DTM",
        "description": "Surface and terrain elevation models used for nDSM and eave correction.",
        "geometry": "raster",
        "default_format": "GeoTIFF",
        "formats": ["GeoTIFF", "IMG", "ASCII Grid"],
        "capability": "native",
        "capability_note": "Band statistics, vertical unit and surface classification are read with Rasterio.",
    },
    {
        "id": "cadastral_map",
        "label": "Existing Cadastral Maps",
        "description": "Digitised legacy cadastre (Shajra / Musavi / paper map traces).",
        "geometry": "vector",
        "default_format": "GeoPackage",
        "formats": ["GeoPackage", "Shapefile", "GeoJSON", "DXF", "PDF (vector)"],
        "capability": "native",
        "capability_note": "Full vector parse (GPKG / SHP / GeoJSON) with OGR; DXF and PDF are adapter-ready.",
    },
    {
        "id": "revenue_records",
        "label": "Revenue Records / RoR",
        "description": "Record of Rights register: survey number, owner, recorded area, land use.",
        "geometry": "table",
        "default_format": "CSV",
        "formats": ["CSV", "XLSX", "JSON", "SQL dump"],
        "capability": "native",
        "capability_note": "Tabular parse with header auto-detection and column-role inference.",
    },
    {
        "id": "municipal_gis",
        "label": "Municipal GIS Layers",
        "description": "Ward boundaries, roads / ROW, drainage, land-use zoning, utility network.",
        "geometry": "vector",
        "default_format": "GeoJSON",
        "formats": ["GeoJSON", "Shapefile", "GeoPackage", "GML"],
        "capability": "native",
        "capability_note": "Full vector parse; GML requires an OGR schema adapter.",
    },
    {
        "id": "utility_network",
        "label": "Utility Network Data",
        "description": "Water, sewer and power corridor alignments with statutory buffer widths.",
        "geometry": "vector",
        "default_format": "GeoJSON",
        "formats": ["GeoJSON", "Shapefile", "GeoPackage", "Shapefile (Network)"],
        "capability": "native",
        "capability_note": "Line geometry parsed; statutory buffer width supplied as a project parameter.",
    },
    {
        "id": "ground_truthing",
        "label": "Ground Truthing (GT)",
        "description": "Field-observed boundary evidence: monuments, stones, compound corners.",
        "geometry": "point",
        "default_format": "CSV",
        "formats": ["CSV", "GeoJSON", "KML", "DXF"],
        "capability": "native",
        "capability_note": "Point parse with evidence class and accuracy attributes.",
    },
    {
        "id": "gnss_cors",
        "label": "GNSS / CORS Survey Data",
        "description": "Static / RTK observations referenced to a CORS base station.",
        "geometry": "point",
        "default_format": "CSV",
        "formats": ["CSV", "RINEX obs", "GCP text", "LAS (adjusted)"],
        "capability": "native",
        "capability_note": "Observation text parsed; RINEX decoding is adapter-ready.",
    },
    {
        "id": "building_footprint",
        "label": "Building Footprints",
        "description": "Municipal / ORI derived structure outlines for physical boundary evidence.",
        "geometry": "vector",
        "default_format": "GeoJSON",
        "formats": ["GeoJSON", "Shapefile", "GeoPackage", "CSV+WKT"],
        "capability": "native",
        "capability_note": "Full polygon parse; CSV+WKT column is detected automatically.",
    },
]

SOURCE_CATEGORY_BY_ID = {item["id"]: item for item in SOURCE_CATEGORIES}


# ---------------------------------------------------------------------------
# Canonical unified land-record schema (SIH26013 target data model)
# ---------------------------------------------------------------------------
CANONICAL_PARCEL_SCHEMA: List[Dict[str, Any]] = [
    {"field": "parcel_id", "label": "Parcel ID", "type": "string", "required": True},
    {"field": "ulpin", "label": "ULPIN", "type": "string", "required": True},
    {"field": "khasra_no", "label": "Khasra / Survey Number", "type": "string", "required": True},
    {"field": "owner_name", "label": "Owner Name", "type": "string", "required": True},
    {"field": "owner_name_local", "label": "Owner Name (Local Language)", "type": "string", "required": True},
    {"field": "property_type", "label": "Property Type", "type": "string", "required": False},
    {"field": "land_use", "label": "Land Use", "type": "string", "required": False},
    {"field": "recorded_area_sqm", "label": "Recorded Area (sq m)", "type": "float", "required": True},
    {"field": "surveyed_area_sqm", "label": "Surveyed Area (sq m)", "type": "float", "required": True},
    {"field": "ward", "label": "Ward", "type": "string", "required": False},
    {"field": "village", "label": "Village / Locality", "type": "string", "required": False},
    {"field": "zone", "label": "Zone", "type": "string", "required": False},
    {"field": "road_ref", "label": "Road Reference", "type": "string", "required": False},
    {"field": "utility_ref", "label": "Utility Reference", "type": "string", "required": False},
]

# Alias dictionary used by the attribute standardisation stage.
CANONICAL_ALIASES: Dict[str, List[str]] = {
    "parcel_id": ["parcel_id", "parcelid", "parcel id", "unique id", "object id", "shape id", "feature_id", "id",
                  "parcel_id_hint", "parcel hint", "parcel no", "parcel number", "cadastral id", "lp no", "lp_no"],
    "ulpin": ["ulpin", "ulpin_code", "land id", "bhu aadhaar", "bhu_aadhaar", "parcel ulpin", "luin", "uid"],
    "khasra_no": ["khasra_no", "khasra", "khasra number", "survey_no", "survey number", "plot_no", "plot number",
                  "no", "s.no", "number", "tp no", "tp_no", "part no", "parcel_ref", "parcel reference",
                  "survey_ref", "survey number (old)", "old survey no"],
    "owner_name": ["owner_name", "owner", "owner_en", "owner name", "name of owner", "recorded holder",
                   "holder name", "bhogtidar", "recorded name"],
    "owner_name_local": ["owner_name_local", "owner_vernacular", "owner_vernacular_hi", "owner_local", "local name",
                         "name in local language", "owner name (local)", "marathi name", "holder local"],
    "property_type": ["property_type", "type", "usage type", "occupancy", "tenure", "ownership type"],
    "land_use": ["land_use", "landuse", "use", "use type", "zoning", "land classification", "usage"],
    "recorded_area_sqm": ["recorded_area_sqm", "recorded_area", "legal_area_sqm", "legal area", "area", "area_sqm",
                          "ror area", "deed area", "documented area"],
    "surveyed_area_sqm": ["surveyed_area_sqm", "surveyed_area", "measured area", "actual area", "ground area"],
    "ward": ["ward", "ward_no", "ward number", "prabhag", "segment", "ward code"],
    "village": ["village", "village_name", "gaon", "locality", "town", "place", "mauza"],
    "zone": ["zone", "zone_name", "planning zone", "zone code", "fz", "use zone"],
    "road_ref": ["road_ref", "road", "road name", "street", "marg", "road reference"],
    "utility_ref": ["utility_ref", "utility", "line ref", "pipeline", "power line", "water line"],
}

CANONICAL_FIELD_BY_ALIAS: Dict[str, str] = {}
for _canonical, _aliases in CANONICAL_ALIASES.items():
    for _alias in _aliases:
        CANONICAL_FIELD_BY_ALIAS[_alias] = _canonical


# ---------------------------------------------------------------------------
# Harmonization pipeline definition (order matters)
# ---------------------------------------------------------------------------
PIPELINE_STAGES: List[Dict[str, Any]] = [
    {"key": "ingest", "label": "Ingestion", "group": "Input"},
    {"key": "validate", "label": "Structural & Geometric Validation", "group": "Prepare"},
    {"key": "crs_detect", "label": "CRS Detection", "group": "Prepare"},
    {"key": "crs_normalize", "label": "Coordinate Normalization", "group": "Prepare"},
    {"key": "standardize", "label": "Data Standardization", "group": "Prepare"},
    {"key": "feature_extract", "label": "GeoAI Feature Extraction", "group": "Harmonize"},
    {"key": "spatial_match", "label": "Spatial Matching", "group": "Harmonize"},
    {"key": "geometry_reconcile", "label": "Geometry Reconciliation", "group": "Harmonize"},
    {"key": "attribute_reconcile", "label": "Attribute Reconciliation", "group": "Harmonize"},
    {"key": "topology_validate", "label": "Topology Validation", "group": "Validate"},
    {"key": "conflict_detect", "label": "Conflict Detection", "group": "Validate"},
    {"key": "confidence_score", "label": "Confidence Scoring", "group": "Validate"},
    {"key": "synchronize", "label": "Synchronized Output", "group": "Output"},
]

PIPELINE_STAGE_LABEL = {stage["key"]: stage["label"] for stage in PIPELINE_STAGES}


# ---------------------------------------------------------------------------
# Harmonization / conflict tuning parameters
# ---------------------------------------------------------------------------
DEFAULT_PIPELINE_PARAMS: Dict[str, Any] = {
    "snap_tolerance_m": 0.15,
    "min_sliver_area_sqm": 2.0,
    "eave_buffer_m": 0.40,
    "min_match_iou": 0.55,
    "area_tolerance_pct": 3.5,
    "road_row_buffer_m": 7.0,
    "drainage_buffer_m": 3.0,
    "utility_buffer_m": 2.0,
    "change_shift_threshold_m": 0.5,
    "change_area_threshold_pct": 2.0,
    "target_crs": PROJECT_CRS,
}


# ---------------------------------------------------------------------------
# Export adapter registry - honest capability declaration
# ---------------------------------------------------------------------------
EXPORT_FORMATS: List[Dict[str, Any]] = [
    {"id": "geojson", "label": "GeoJSON (RFC 7946)", "extension": "geojson", "geometry": True, "capability": "native"},
    {"id": "csv", "label": "CSV Attribute Register", "extension": "csv", "geometry": False, "capability": "native"},
    {"id": "geopackage", "label": "OGC GeoPackage", "extension": "gpkg", "geometry": True, "capability": "native"},
    {"id": "shapefile", "label": "ESRI Shapefile (zipped)", "extension": "zip", "geometry": True, "capability": "native"},
    {"id": "parcel_report_pdf", "label": "Parcel Record Report (PDF)", "extension": "pdf", "geometry": False, "capability": "native"},
    {"id": "kml", "label": "KML (Google Earth)", "extension": "kml", "geometry": True, "capability": "adapter-pending"},
    {"id": "dxf", "label": "AutoCAD DXF", "extension": "dxf", "geometry": True, "capability": "adapter-pending"},
    {"id": "geojson_utm", "label": "GeoJSON in project CRS", "extension": "geojson", "geometry": True, "capability": "native"},
]

EXPORT_CAPABILITY_BY_ID = {item["id"]: item for item in EXPORT_FORMATS}


# ---------------------------------------------------------------------------
# Conflict taxonomy
# ---------------------------------------------------------------------------
CONFLICT_TYPES: List[Dict[str, Any]] = [
    {
        "id": "parcel_vs_road_row",
        "label": "Cadastral parcel vs Road Right-of-Way",
        "severity_hint": "high",
    },
    {
        "id": "parcel_vs_drainage",
        "label": "Cadastral parcel vs Stormwater Drainage",
        "severity_hint": "high",
    },
    {
        "id": "parcel_vs_utility",
        "label": "Cadastral parcel vs Utility Corridor",
        "severity_hint": "medium",
    },
    {
        "id": "legacy_vs_survey",
        "label": "Legacy boundary vs Modern survey (GNSS/GT)",
        "severity_hint": "medium",
    },
    {
        "id": "recorded_vs_surveyed_area",
        "label": "Recorded area vs Surveyed area",
        "severity_hint": "medium",
    },
    {
        "id": "building_vs_parcel",
        "label": "Building footprint vs Parcel boundary",
        "severity_hint": "high",
    },
    {
        "id": "duplicate_geometry",
        "label": "Duplicate geometry between sources",
        "severity_hint": "medium",
    },
    {
        "id": "land_use_change",
        "label": "Land-use classification change",
        "severity_hint": "low",
    },
]

CONFLICT_TYPE_BY_ID = {item["id"]: item for item in CONFLICT_TYPES}

CONFLICT_ACTIONS = [
    {"id": "accept_new", "label": "Accept new geometry", "requires_note": True},
    {"id": "retain_legacy", "label": "Retain legacy geometry", "requires_note": True},
    {"id": "merge", "label": "Merge features", "requires_note": True},
    {"id": "manual_review", "label": "Route to manual review", "requires_note": False},
    {"id": "field_verification", "label": "Flag for field / survey verification", "requires_note": False},
    {"id": "dismiss", "label": "Dismiss as false positive", "requires_note": True},
]


# ---------------------------------------------------------------------------
# Source reliability weighting (used by the confidence model)
# ---------------------------------------------------------------------------
SOURCE_RELIABILITY: Dict[str, Dict[str, Any]] = {
    "gnss_cors": {"label": "GNSS / CORS survey", "reliability": 0.98, "positional_weight": 0.35},
    "ground_truthing": {"label": "Ground truthing evidence", "reliability": 0.95, "positional_weight": 0.25},
    "ortho_ori": {"label": "Orthorectified imagery", "reliability": 0.92, "positional_weight": 0.20},
    "building_footprint": {"label": "Building footprint", "reliability": 0.88, "positional_weight": 0.15},
    "drone_imagery": {"label": "Drone imagery", "reliability": 0.85, "positional_weight": 0.10},
    "dsm_dtm": {"label": "Surface model", "reliability": 0.82, "positional_weight": 0.05},
    "municipal_gis": {"label": "Municipal GIS layer", "reliability": 0.86, "positional_weight": 0.20},
    "cadastral_map": {"label": "Legacy cadastral map", "reliability": 0.62, "positional_weight": 0.20},
    "revenue_records": {"label": "Revenue record / RoR", "reliability": 0.75, "positional_weight": 0.00},
    "utility_network": {"label": "Utility network", "reliability": 0.80, "positional_weight": 0.10},
}


def source_reliability(category_id: str) -> float:
    entry = SOURCE_RELIABILITY.get(category_id)
    return float(entry["reliability"]) if entry else 0.70
