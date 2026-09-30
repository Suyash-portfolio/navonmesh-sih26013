"""
Dataset ingestion service (SIH26013 - Stage 1: UPLOAD / INGEST).

Responsibilities
----------------
* Materialise datasets on disk and register them in the project repository.
* Parse each source with the *real* reader for its format. Formats without a
  bundled reader are registered honestly as ``adapter-ready`` or
  ``demo-parser`` - they are never presented as fully processed.
* Capture per-dataset source metadata: name, data type, format, CRS, record
  counts, extent, band statistics, upload / validation / processing status.
* Detect the CRS through :mod:`app.services.crs_service`.

Format capability matrix
------------------------
Native   : GeoJSON, GeoPackage, Shapefile, CSV, GeoTIFF/COG, LAS (header)
Adapters : GML, DXF, RINEX, KML, XLSX, ZIP packages
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.config import (
    SOURCE_CATEGORIES,
    SOURCE_CATEGORY_BY_ID,
    UPLOAD_DIR,
    CANONICAL_FIELD_BY_ALIAS,
    CANONICAL_PARCEL_SCHEMA,
)
from app.services import crs_service

try:
    import geopandas as gpd
    GEOF_AVAILABLE = True
except Exception:  # pragma: no cover
    gpd = None  # type: ignore
    GEOF_AVAILABLE = False

try:
    import rasterio
    RASTERIO_AVAILABLE = True
except Exception:  # pragma: no cover
    rasterio = None  # type: ignore
    RASTERIO_AVAILABLE = False


FORMAT_CAPABILITY: Dict[str, str] = {
    ".geojson": "native",
    ".json": "native",
    ".gpkg": "native",
    ".shp": "native",
    ".csv": "native",
    ".tsv": "native",
    ".tif": "native",
    ".tiff": "native",
    ".las": "native-header",
    ".laz": "adapter-ready",
    ".gml": "adapter-ready",
    ".dxf": "adapter-ready",
    ".kml": "adapter-ready",
    ".xlsx": "adapter-ready",
    ".zip": "adapter-ready",
    ".rnx": "adapter-ready",
    ".pdf": "adapter-ready",
}

FORMAT_MIME: Dict[str, str] = {
    ".geojson": "application/geo+json",
    ".json": "application/json",
    ".gpkg": "application/geopackage+sqlite3",
    ".shp": "application/octet-stream",
    ".csv": "text/csv",
    ".tsv": "text/tab-separated-values",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".las": "application/octet-stream",
    ".laz": "application/octet-stream",
}

GEOMETRY_KIND_BY_EXTENSION: Dict[str, str] = {
    ".geojson": "vector",
    ".json": "vector",
    ".gpkg": "vector",
    ".shp": "vector",
    ".csv": "table",
    ".tsv": "table",
    ".tif": "raster",
    ".tiff": "raster",
    ".las": "point",
    ".laz": "point",
    ".gml": "vector",
    ".dxf": "vector",
    ".kml": "vector",
    ".xlsx": "table",
    ".zip": "package",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def detect_extension(filename: str) -> str:
    return Path(filename).suffix.lower()


# ---------------------------------------------------------------------------
# Field role inference (used by the standardization service)
# ---------------------------------------------------------------------------
def normalise_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(name).strip().lower()).strip()


def infer_field_roles(columns: List[str]) -> Dict[str, str]:
    """Map raw column names onto canonical land-record fields."""
    mapping: Dict[str, str] = {}
    for column in columns:
        key = normalise_key(column)
        canonical = CANONICAL_FIELD_BY_ALIAS.get(key)
        if canonical is None:
            for alias, target in CANONICAL_FIELD_BY_ALIAS.items():
                if alias and (key == alias or key.startswith(alias + " ") or key.endswith(" " + alias)):
                    canonical = target
                    break
        if canonical and canonical not in mapping:
            mapping[column] = canonical
    return mapping


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------
def read_vector(path: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    if not GEOF_AVAILABLE:
        return None, {"ok": False, "error": "GeoPandas is not installed in this environment."}
    try:
        gdf = gpd.read_file(path)
    except Exception as exc:
        return None, {"ok": False, "error": f"Vector parse failed: {exc.__class__.__name__}: {exc}"}
    meta = {
        "ok": True,
        "features": int(len(gdf)),
        "columns": [str(c) for c in gdf.columns],
        "geometry_types": sorted({str(t) for t in gdf.geom_type.unique()}) if len(gdf) else [],
        "crs": gdf.crs.to_string() if gdf.crs is not None else None,
        "bounds": [float(v) for v in gdf.total_bounds] if len(gdf) else None,
        "valid_count": int(gdf.geometry.is_valid.sum()) if len(gdf) else 0,
        "null_geometry_count": int(gdf.geometry.isna().sum()) if len(gdf) else 0,
    }
    return gdf, meta


def read_raster(path: Path) -> Tuple[Optional[Any], Dict[str, Any]]:
    if not RASTERIO_AVAILABLE:
        return None, {"ok": False, "error": "Rasterio is not installed in this environment."}
    try:
        with rasterio.open(path) as dataset:
            stats = []
            for band in range(1, min(dataset.count, 3) + 1):
                array = dataset.read(band, masked=True)
                valid = array.compressed()
                if valid.size == 0:
                    continue
                stats.append(
                    {
                        "band": band,
                        "description": dataset.descriptions[band - 1],
                        "dtype": str(array.dtype),
                        "min": round(float(valid.min()), 4),
                        "max": round(float(valid.max()), 4),
                        "mean": round(float(valid.mean()), 4),
                    }
                )
            res = abs(dataset.res[0])
            meta = {
                "ok": True,
                "features": int(dataset.width * dataset.height),
                "width": int(dataset.width),
                "height": int(dataset.height),
                "bands": int(dataset.count),
                "crs": dataset.crs.to_string() if dataset.crs else None,
                "bounds": [float(v) for v in dataset.bounds],
                "resolution_m": round(res, 4),
                "gsd_cm": round(res * 100.0, 2),
                "band_statistics": stats,
                "driver": dataset.driver,
            }
            return dataset, meta
    except Exception as exc:
        return None, {"ok": False, "error": f"Raster parse failed: {exc.__class__.__name__}: {exc}"}


def read_table(path: Path) -> Tuple[Optional[List[Dict[str, Any]]], Dict[str, Any]]:
    try:
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, delimiter=delimiter)
            columns = reader.fieldnames or []
            rows = [dict(row) for row in reader]
    except UnicodeDecodeError:
        return None, {"ok": False, "error": "File is not UTF-8 text; a binary reader adapter is required."}
    except Exception as exc:
        return None, {"ok": False, "error": f"Tabular parse failed: {exc.__class__.__name__}: {exc}"}

    roles = infer_field_roles(columns)
    numeric = 0
    for row in rows[:50]:
        for value in row.values():
            try:
                float(value)
                numeric += 1
            except (TypeError, ValueError):
                continue
    return rows, {
        "ok": True,
        "features": len(rows),
        "columns": columns,
        "inferred_field_roles": roles,
        "unmapped_columns": [c for c in columns if c not in roles],
        "numeric_cell_ratio": round(numeric / max(1, len(rows[:50]) * max(1, len(columns))), 3),
        "delimiter": "," if delimiter == "," else "\\t",
    }


def read_las_header(path: Path) -> Tuple[None, Dict[str, Any]]:
    """Read the LAS/LAZ public header block only - no point decoding."""
    try:
        with open(path, "rb") as handle:
            header = handle.read(375)
    except Exception as exc:
        return None, {"ok": False, "error": f"Could not open file: {exc}"}
    if len(header) < 227:
        return None, {"ok": False, "error": "File is too short to contain a LAS/LAZ header."}
    signature = header[0:4]
    if signature not in (b"LASF",):
        return None, {"ok": False, "error": "Missing LASF signature - not a LAS/LAZ file."}
    version = f"{header[24]}.{header[25]}"
    point_format = header[104] & 0x3F
    return None, {
        "ok": True,
        "partial": True,
        "las_version": version,
        "point_format": int(point_format),
        "point_count_header": int.from_bytes(header[107:111], "little"),
        "scale_x": round(int.from_bytes(header[131:139], "little", signed=True), 8),
        "offset_x": round(int.from_bytes(header[139:147], "little", signed=True), 8),
        "features": int.from_bytes(header[107:111], "little"),
        "columns": ["x", "y", "z", "intensity", "return_number", "classification"],
        "note": "Header parsed only. Point decoding requires a LAS adapter (PDAL/laspy).",
    }


READER_FOR_EXTENSION = {
    ".geojson": read_vector,
    ".json": read_vector,
    ".gpkg": read_vector,
    ".shp": read_vector,
    ".csv": read_table,
    ".tsv": read_table,
    ".tif": read_raster,
    ".tiff": read_raster,
    ".las": read_las_header,
}


# ---------------------------------------------------------------------------
# Dataset registry
# ---------------------------------------------------------------------------
class DatasetRegistry:
    """In-memory dataset registry backed by the project repository."""

    def __init__(self) -> None:
        self._datasets: Dict[str, Dict[str, Any]] = {}
        self._order: List[str] = []

    # -- CRUD ---------------------------------------------------------------
    def register(self, record: Dict[str, Any]) -> Dict[str, Any]:
        dataset_id = record.get("id") or f"DS-{uuid.uuid4().hex[:10].upper()}"
        record["id"] = dataset_id
        record.setdefault("uploaded_at", utc_now())
        record.setdefault("upload_status", "uploaded")
        record.setdefault("validation_status", "pending")
        record.setdefault("processing_status", "pending")
        record.setdefault("record_count", None)
        if dataset_id not in self._datasets:
            self._order.append(dataset_id)
        self._datasets[dataset_id] = record
        return record

    def get(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        return self._datasets.get(dataset_id)

    def require(self, dataset_id: str) -> Dict[str, Any]:
        record = self._datasets.get(dataset_id)
        if record is None:
            raise KeyError(f"Dataset '{dataset_id}' is not registered.")
        return record

    def update(self, dataset_id: str, **fields: Any) -> Dict[str, Any]:
        record = self.require(dataset_id)
        record.update(fields)
        return record

    def list_all(self) -> List[Dict[str, Any]]:
        return [self._datasets[key] for key in self._order if key in self._datasets]

    def remove(self, dataset_id: str) -> bool:
        if dataset_id in self._datasets:
            del self._datasets[dataset_id]
            self._order = [k for k in self._order if k != dataset_id]
            return True
        return False

    def clear(self) -> None:
        self._datasets.clear()
        self._order.clear()

    def __len__(self) -> int:
        return len(self._datasets)


REGISTRY = DatasetRegistry()


# ---------------------------------------------------------------------------
# Ingestion
# ---------------------------------------------------------------------------
def _summary(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compact dataset record for API responses (drops in-memory objects)."""
    return {
        key: value
        for key, value in record.items()
        if not key.startswith("_") and key not in {"gdf", "rows", "dataset_handle"}
    }


def ingest_file(
    *,
    project_id: str,
    category_id: str,
    display_name: str,
    filename: str,
    content: Optional[bytes] = None,
    path: Optional[Path] = None,
    declared_crs: Optional[str] = None,
    source_authority: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest a single dataset file.

    ``content`` (uploaded bytes) and ``path`` (already-materialised demo file)
    are both supported.
    """
    category = SOURCE_CATEGORY_BY_ID.get(category_id)
    if category is None:
        raise ValueError(f"Unknown source category '{category_id}'.")

    extension = detect_extension(filename)
    resolved_path: Optional[Path] = None

    if content is not None:
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        resolved_path = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{Path(filename).name}"
        resolved_path.write_bytes(content)
    elif path is not None:
        resolved_path = Path(path)
        if not resolved_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {resolved_path}")
    else:
        raise ValueError("Either 'content' or 'path' must be supplied.")

    assert resolved_path is not None
    size_bytes = resolved_path.stat().st_size
    reader = READER_FOR_EXTENSION.get(extension)
    capability = FORMAT_CAPABILITY.get(extension, "adapter-ready")

    record: Dict[str, Any] = {
        "project_id": project_id,
        "name": display_name,
        "filename": Path(filename).name,
        "path": str(resolved_path),
        "extension": extension,
        "format": (category["default_format"] if extension in (".geojson", ".json") else extension.lstrip(".").upper()),
        "category_id": category_id,
        "category_label": category["label"],
        "data_type": category["geometry"],
        "geometry_kind": GEOMETRY_KIND_BY_EXTENSION.get(extension, "unknown"),
        "mime_type": FORMAT_MIME.get(extension, "application/octet-stream"),
        "size_bytes": size_bytes,
        "size_human": _human_size(size_bytes),
        "source_authority": source_authority or "Demo dataset (synthetic)",
        "notes": notes,
        "parser": capability,
        "parser_label": _parser_label(capability),
        "upload_status": "uploaded",
        "validation_status": "pending",
        "processing_status": "pending",
        "record_count": None,
    }

    # --- Parse -------------------------------------------------------------
    if reader is not None:
        parsed, meta = reader(resolved_path)
        record["parse"] = meta
        record["record_count"] = meta.get("features")
        record["columns"] = meta.get("columns")
        record["geometry_types"] = meta.get("geometry_types")
        record["parse_error"] = None if meta.get("ok") else meta.get("error")
        record["upload_status"] = "parsed" if meta.get("ok") else "parse_failed"
        if reader is read_vector:
            record["_gdf"] = parsed
        elif reader is read_table:
            record["_rows"] = parsed
    else:
        record["parse"] = {
            "ok": False,
            "partial": True,
            "features": None,
            "columns": None,
            "error": (
                f"No binary reader is bundled for '{extension}'. The file has been stored and "
                f"registered; a format adapter is required before it can contribute geometry."
            ),
        }
        record["parse_error"] = record["parse"]["error"]
        record["upload_status"] = "stored_adapter_pending"

    # --- CRS detection -----------------------------------------------------
    gdf = record.pop("_gdf", None)
    rows = record.pop("_rows", None)
    crs_report = _detect_for_record(record, gdf, rows, declared_crs)
    record["crs"] = crs_report
    record["source_crs"] = crs_report.get("source_crs")
    record["processing_status"] = "crs_pending" if crs_report.get("source_crs") else "crs_blocked"

    record["_gdf"] = gdf
    record["_rows"] = rows
    return REGISTRY.register(record)


def _detect_for_record(
    record: Dict[str, Any],
    gdf: Optional[Any],
    rows: Optional[List[Dict[str, Any]]],
    declared_crs: Optional[str],
) -> Dict[str, Any]:
    vectors = [gdf] if gdf is not None else None
    if gdf is not None:
        return crs_service.detect_crs(declared_crs=declared_crs, vectors=[gdf])

    if rows:
        lon_key = next((c for c in (rows[0].keys()) if normalise_key(c) in ("lon", "lng", "longitude", "long", "x")), None)
        lat_key = next((c for c in (rows[0].keys()) if normalise_key(c) in ("lat", "latitude", "y")), None)
        if lon_key and lat_key:
            coords = []
            for row in rows[:200]:
                try:
                    coords.append((float(row[lon_key]), float(row[lat_key])))
                except (TypeError, ValueError):
                    continue
            if coords:
                report = crs_service.detect_crs(declared_crs=declared_crs, coordinates=coords)
                report["coordinate_columns"] = {"x": lon_key, "y": lat_key}
                return report
        # Purely attribute table - spatial join must use the identifier.
        return {
            "status": "not_applicable",
            "source_crs": None,
            "method": "non-spatial attribute table",
            "confidence": 1.0,
            "description": (
                "This dataset is a non-spatial attribute table. It is joined to geometry through "
                "the shared survey / parcel identifier during attribute reconciliation."
            ),
            "is_geographic": None,
            "unit": None,
            "warnings": [],
        }

    if record.get("geometry_kind") == "raster":
        return crs_service.detect_crs(declared_crs=declared_crs)

    return crs_service.detect_crs(declared_crs=declared_crs)


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} GB"


def _parser_label(capability: str) -> str:
    return {
        "native": "Native server-side parser",
        "native-header": "Header-only parser",
        "adapter-ready": "Adapter ready - not parsed",
    }.get(capability, "Unknown")


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------
def list_datasets(project_id: Optional[str] = None, category_id: Optional[str] = None) -> List[Dict[str, Any]]:
    records = REGISTRY.list_all()
    if project_id:
        records = [r for r in records if r.get("project_id") == project_id]
    if category_id:
        records = [r for r in records if r.get("category_id") == category_id]
    return [_summary(r) for r in records]


def get_dataset(dataset_id: str) -> Dict[str, Any]:
    try:
        return _summary(REGISTRY.require(dataset_id))
    except KeyError as exc:
        raise LookupError(str(exc)) from exc


def dataset_frame(dataset_id: str):
    """Return the parsed GeoDataFrame for a dataset (or ``None``)."""
    return REGISTRY.require(dataset_id).get("_gdf")


def dataset_rows(dataset_id: str) -> Optional[List[Dict[str, Any]]]:
    return REGISTRY.require(dataset_id).get("_rows")


def coverage_report(project_id: Optional[str] = None) -> Dict[str, Any]:
    """Report which of the ten SIH26013 source categories are populated."""
    records = REGISTRY.list_all()
    if project_id:
        records = [r for r in records if r.get("project_id") == project_id]
    populated = {r["category_id"] for r in records}
    categories = []
    for category in SOURCE_CATEGORIES:
        entry = dict(category)
        entry["datasets"] = [r["id"] for r in records if r["category_id"] == category["id"]]
        entry["populated"] = entry["datasets"] != []
        entry["record_count"] = sum(
            r.get("record_count") or 0 for r in records if r["category_id"] == category["id"]
        )
        categories.append(entry)
    return {
        "categories": categories,
        "populated_count": len(populated),
        "total_categories": len(SOURCE_CATEGORIES),
        "canonical_schema": CANONICAL_PARCEL_SCHEMA,
    }


def upload_spec() -> Dict[str, Any]:
    """Return the upload contract used by the ingestion UI."""
    return {
        "categories": SOURCE_CATEGORIES,
        "max_bytes": 512 * 1024 * 1024,
        "crs_options": crs_service.crs_options(),
        "crs_optional_hint": (
            "Leave the CRS empty when the file carries one. If a dataset has no CRS the platform "
            "will not silently assume one - select it explicitly so normalization can proceed."
        ),
        "formats": [
            {"extension": ext, "capability": cap, "mime": FORMAT_MIME.get(ext, "application/octet-stream")}
            for ext, cap in sorted(FORMAT_CAPABILITY.items())
        ],
    }


def store_bytes(filename: str, payload: io.BytesIO | bytes) -> Path:
    """Persist an uploaded payload on disk (used by the API layer)."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    path = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{Path(filename).name}"
    if isinstance(payload, bytes):
        path.write_bytes(payload)
    else:
        path.write_bytes(payload.getvalue())
    return path


def geojson_bounds_lonlat(gdf) -> Optional[List[List[float]]]:
    if gdf is None or len(gdf) == 0:
        return None
    return json.loads(gpd.GeoSeries([gdf.union_all()]).to_crs("EPSG:4326").to_json())["coordinates"][0]
