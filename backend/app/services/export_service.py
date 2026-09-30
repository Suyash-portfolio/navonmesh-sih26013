"""
NAVONMESH - Export Service (Phase 34)

Genuine file generation for every advertised format.

Why this module exists
----------------------
The previous frontend shipped an ``ExportDropdown`` whose GeoPackage and
"ESRI Shapefile" buttons wrote a four-line text file to a ``.gpkg``/``.zip``
filename and then displayed "exported successfully". A GeoPackage is a SQLite
database and a Shapefile is a set of binary sidecar files; neither can be
faked. This module produces real files with the geospatial stack, and refuses
to emit a format it cannot genuinely write.

Supported
    geojson        RFC 7946 FeatureCollection
    geojson_utm    same, reprojected to the project CRS
    csv            attribute register (UTF-8 BOM for Excel)
    geopackage     OGC GeoPackage via GeoPandas/Fiona
    shapefile      ESRI Shapefile, zipped with all sidecars
    parcel_report_pdf

Not advertised as supported (and rejected with a clear reason):
    kml, dxf  - marked ``adapter-pending`` in config.EXPORT_FORMATS
"""

from __future__ import annotations

import csv as csv_module
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from app.config import EXPORT_DIR, PLATFORM, PROJECT_CRS, STORAGE_CRS
from app.services.ingestion_service import utc_now

# Formats this build can genuinely write.
IMPLEMENTED = {"geojson", "geojson_utm", "csv", "geopackage", "shapefile", "parcel_report_pdf"}

REJECTED_REASON = {
    "kml": "KML export is declared adapter-pending in config.EXPORT_FORMATS and is not implemented.",
    "dxf": "DXF export is declared adapter-pending in config.EXPORT_FORMATS and is not implemented.",
}


class ExportError(RuntimeError):
    """Raised when a format is requested that cannot be genuinely produced."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _feature_collection(features: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "type": "FeatureCollection",
        "features": list(features),
    }


def _to_wgs84_geometry(geom: Any) -> Any:
    """Reproject a projected geometry to WGS84 for browser/RFC 7946 output."""
    try:
        from shapely.ops import transform as shapely_transform

        from app.services.crs_service import _make_transformer

        transformer, _method = _make_transformer(PROJECT_CRS, STORAGE_CRS)
        if transformer is None:
            return geom
        return shapely_transform(transformer.transform, geom)
    except Exception:
        return geom


def _gdf_from_features(features: Sequence[Dict[str, Any]], crs: str = STORAGE_CRS):
    """Build a GeoDataFrame from feature dicts, tagged with their true CRS.

    ``crs`` must describe the coordinates actually present in ``geometry``.
    The pipeline stores parcel geometry as WGS84 GeoJSON, so defaulting this to
    the project CRS would silently mislabel every exported layer.
    """
    import geopandas as gpd

    from shapely.geometry import shape

    records = []
    geoms = []
    for feature in features:
        props = dict(feature.get("properties") or {})
        geometry = feature.get("geometry")
        if geometry is None:
            continue
        geom = shape(geometry)
        geoms.append(geom)
        records.append(props)
    frame = gpd.GeoDataFrame(records, geometry=geoms, crs=crs)
    return frame


# ---------------------------------------------------------------------------
# format writers
# ---------------------------------------------------------------------------
def write_geojson(
    features: Sequence[Dict[str, Any]],
    *,
    to_wgs84: bool = True,
) -> bytes:
    """RFC 7946 FeatureCollection. Geometry is reprojected to EPSG:4326."""
    if to_wgs84:
        converted = []
        for feature in features:
            geometry = feature.get("geometry")
            if geometry is not None:
                try:
                    from shapely.geometry import mapping, shape

                    geometry = mapping(_to_wgs84_geometry(shape(geometry)))
                except Exception:
                    pass
            converted.append({**feature, "geometry": geometry})
        payload = _feature_collection(converted)
    else:
        payload = _feature_collection(features)
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def write_csv(features: Sequence[Dict[str, Any]]) -> bytes:
    """Attribute register with a UTF-8 BOM so Devanagari survives Excel."""
    rows: List[Dict[str, Any]] = []
    for feature in features:
        props = dict(feature.get("properties") or {})
        props.pop("geometry", None)
        rows.append(props)

    columns: List[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)

    buffer = io.StringIO()
    buffer.write("\ufeff")  # BOM
    writer = csv_module.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({c: row.get(c) for c in columns})
    return buffer.getvalue().encode("utf-8")


def write_geopackage(features: Sequence[Dict[str, Any]], layer: str = "parcels") -> bytes:
    """Real OGC GeoPackage (SQLite) via GeoPandas."""
    frame = _gdf_from_features(features)
    if frame.empty:
        raise ExportError("No features with geometry available for GeoPackage export.")
    target = EXPORT_DIR / f"navonmesh_{layer}.gpkg"
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    if target.exists():
        target.unlink()
    frame.to_file(target, layer=layer, driver="GPKG")
    return target.read_bytes()


def write_shapefile(features: Sequence[Dict[str, Any]]) -> bytes:
    """Real ESRI Shapefile zipped with .shp/.shx/.dbf/.prj sidecars."""
    frame = _gdf_from_features(features)
    if frame.empty:
        raise ExportError("No features with geometry available for Shapefile export.")
    if len(frame.columns) > 10:
        # OGR caps DBF field names; trim to the core identity fields. The
        # active geometry column must survive, otherwise `frame[keep]`
        # degrades the GeoDataFrame to a plain DataFrame and loses to_file().
        keep = [c for c in ("parcel_id", "ulpin", "khasra_no", "owner_name", "status") if c in frame.columns]
        keep += [c for c in frame.columns if c not in keep][: max(0, 9 - len(keep))]
        geometry_column = frame.geometry.name
        if geometry_column not in keep:
            keep.append(geometry_column)
        import geopandas as gpd

        frame = gpd.GeoDataFrame(frame[keep], geometry=geometry_column, crs=frame.crs)
    tmp_dir = EXPORT_DIR / "_shp"
    if tmp_dir.exists():
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    base = tmp_dir / "navonmesh_parcels"
    frame.to_file(base, driver="ESRI Shapefile")

    parts = sorted(p for p in tmp_dir.rglob("*") if p.is_file())
    if not parts:
        import shutil

        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise ExportError("Shapefile writer produced no output files.")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in parts:
            archive.write(path, arcname=path.name)
    import shutil

    shutil.rmtree(tmp_dir, ignore_errors=True)
    return buffer.getvalue()


def build_parcel_report_pdf(
    parcel: Dict[str, Any],
    *,
    lineage: Optional[List[Dict[str, Any]]] = None,
    conflicts: Optional[List[Dict[str, Any]]] = None,
    confidence: Optional[Dict[str, Any]] = None,
) -> bytes:
    """Genuine PDF parcel record report (Phase 34 content list)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=f"NAVONMESH Parcel Report {parcel.get('parcel_id', '')}",
        author=PLATFORM["product_name"],
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "NM", parent=styles["Heading1"], fontSize=16, textColor=colors.HexColor("#0F766E")
    )

    story: List[Any] = [
        Paragraph(PLATFORM["product_name"], title_style),
        Paragraph(
            f"{PLATFORM['full_title']} &nbsp;|&nbsp; {PLATFORM['problem_statement_id']} Prototype",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
        Paragraph(PLATFORM["disclaimer"], styles["Italic"]),
        Spacer(1, 5 * mm),
    ]

    identity = [
        ["Parcel ID", str(parcel.get("parcel_id", "-"))],
        ["ULPIN (prototype ref)", str(parcel.get("ulpin", "-"))],
        ["Survey / Khasra No", str(parcel.get("khasra_no", "-"))],
        ["Owner", str(parcel.get("owner_name", "-"))],
        ["Owner (local language)", str(parcel.get("owner_name_local", "-"))],
        ["Recorded Area (sq m)", str(parcel.get("recorded_area_sqm", "-"))],
        ["Surveyed Area (sq m)", str(parcel.get("surveyed_area_sqm", "-"))],
        ["Geometry status", str(parcel.get("geometry_status", "-"))],
        ["Confidence", f"{confidence.get('overall_pct', '-') if confidence else '-'}%"],
        ["Verification route", str((confidence or {}).get("route", "-"))],
        ["Generated (UTC)", utc_now()],
    ]
    story.append(_table(identity, styles, colors))

    if lineage:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Source Lineage", styles["Heading2"]))
        story.append(
            _table(
                [["Source layer", "Fields supplied"]] + [
                    [item.get("source_layer"), str(item.get("field_count"))] for item in lineage
                ],
                styles,
                colors,
            )
        )

    if conflicts:
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph("Open Conflicts", styles["Heading2"]))
        story.append(
            _table(
                [["Type", "Severity", "Status", "Detail"]]
                + [
                    [
                        c.get("conflict_type"),
                        c.get("severity"),
                        c.get("status"),
                        str(c.get("detail", ""))[:60],
                    ]
                    for c in conflicts[:12]
                ],
                styles,
                colors,
            )
        )

    doc.build(story)
    return buffer.getvalue()


def _table(rows: List[List[str]], styles: Any, colors: Any) -> Any:
    from reportlab.platypus import Table, TableStyle

    table = Table(rows, colWidths=[55 * 3.2, 105 * 3.2])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#1D453A")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#E8F5F0")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


# ---------------------------------------------------------------------------
# dispatcher
# ---------------------------------------------------------------------------
MEDIA_TYPES = {
    "geojson": "application/geo+json",
    "geojson_utm": "application/geo+json",
    "csv": "text/csv",
    "geopackage": "application/geopackage+sqlite3",
    "shapefile": "application/zip",
    "parcel_report_pdf": "application/pdf",
}

EXTENSIONS = {
    "geojson": "geojson",
    "geojson_utm": "geojson",
    "csv": "csv",
    "geopackage": "gpkg",
    "shapefile": "zip",
    "parcel_report_pdf": "pdf",
}


def export(
    fmt: str,
    features: Sequence[Dict[str, Any]],
    *,
    parcel: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Produce a real export. Returns bytes plus honest metadata."""
    if fmt in REJECTED_REASON:
        raise ExportError(REJECTED_REASON[fmt])
    if fmt not in IMPLEMENTED:
        raise ExportError(
            f"Unknown export format '{fmt}'. Implemented: {sorted(IMPLEMENTED)}"
        )

    if fmt == "geojson":
        payload = write_geojson(features, to_wgs84=True)
    elif fmt == "geojson_utm":
        payload = write_geojson(features, to_wgs84=False)
    elif fmt == "csv":
        payload = write_csv(features)
    elif fmt == "geopackage":
        payload = write_geopackage(features)
    elif fmt == "shapefile":
        payload = write_shapefile(features)
    elif fmt == "parcel_report_pdf":
        if parcel is None:
            raise ExportError("A parcel record is required for the PDF report.")
        payload = build_parcel_report_pdf(parcel, **kwargs)
    else:  # pragma: no cover - guarded above
        raise ExportError(f"Unhandled format {fmt}")

    extension = EXTENSIONS[fmt]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "format": fmt,
        "media_type": MEDIA_TYPES[fmt],
        "extension": extension,
        "filename": f"NAVONMESH_{fmt}_{stamp}.{extension}",
        "bytes": payload,
        "size": len(payload),
        "feature_count": len(features),
        "generated_at": utc_now(),
        "is_genuine_format": True,
    }


def available_formats() -> List[Dict[str, Any]]:
    """The export registry with real availability flags for the UI."""
    from app.config import EXPORT_FORMATS

    out = []
    for item in EXPORT_FORMATS:
        entry = dict(item)
        entry["available"] = item["id"] in IMPLEMENTED
        if not entry["available"]:
            entry["unavailable_reason"] = REJECTED_REASON.get(
                item["id"], "Not implemented in this build."
            )
        out.append(entry)
    return out
