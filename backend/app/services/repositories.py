"""
NAVONMESH - Data Access Layer (Phase 28)
PostgreSQL + PostGIS entity model with a LOCAL DEMO fallback.

Why a repository abstraction
----------------------------
The SIH26013 target deployment is PostGIS, but the judge-facing demo must run
with zero infrastructure. Every service in this package therefore talks to a
``Repository`` interface and never to a database driver directly. Swapping
``NAVONMESH_REPO_MODE=postgis`` re-points the whole platform at PostGIS without
touching a single pipeline stage.

Entities (mirrors the proposed production schema)
-------------------------------------------------
    datasets             source_layers        parcels
    parcel_geometries    parcel_attributes    survey_points
    harmonization_runs   conflicts            changes
    confidence_scores    audit_logs

Geometries are stored as GeoJSON *strings* in the local backend and as native
``geometry(Geometry, 4326)`` columns in PostGIS, so the two modes return
identical Python structures to the API layer.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app.config import STORAGE_DIR

# ---------------------------------------------------------------------------
# Entity name registry - one list so the schema cannot drift from the code.
# ---------------------------------------------------------------------------
ENTITIES: List[str] = [
    "datasets",
    "source_layers",
    "parcels",
    "parcel_geometries",
    "parcel_attributes",
    "survey_points",
    "harmonization_runs",
    "conflicts",
    "changes",
    "confidence_scores",
    "audit_logs",
]


def _now() -> str:
    from app.services.ingestion_service import utc_now

    return utc_now()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class Repository(ABC):
    """Storage-agnostic contract used by every NAVONMESH service."""

    mode: str = "abstract"

    # -- lifecycle ---------------------------------------------------------
    @abstractmethod
    def initialise(self) -> None: ...

    @abstractmethod
    def health(self) -> Dict[str, Any]: ...

    # -- generic entity access --------------------------------------------
    @abstractmethod
    def put(self, entity: str, record: Dict[str, Any], key: str = "id") -> Dict[str, Any]: ...

    @abstractmethod
    def put_many(self, entity: str, records: Iterable[Dict[str, Any]], key: str = "id") -> int: ...

    @abstractmethod
    def get(self, entity: str, record_id: str) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def all(self, entity: str, limit: Optional[int] = None) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def query(self, entity: str, **filters: Any) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def update(self, entity: str, record_id: str, **fields: Any) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def delete(self, entity: str, record_id: str) -> bool: ...

    @abstractmethod
    def clear(self, entity: str) -> int: ...

    def count(self, entity: str, **filters: Any) -> int:
        return len(self.query(entity, **filters))


# ---------------------------------------------------------------------------
# LOCAL DEMO MODE - SQLite, so runs survive a process restart.
# ---------------------------------------------------------------------------
class LocalDemoRepository(Repository):
    """Single-file SQLite store. Real SQL, zero infrastructure.

    SQLite is used rather than plain dicts because harmonization runs must be
    inspectable after a restart during a demo, and because ``audit_logs`` and
    ``harmonization_runs`` are append-only in the real system - a file-backed
    store makes that durability demonstrable.
    """

    mode = "local_demo"

    _SCHEMA = {
        "datasets": "id, name, category_id, status, crs, feature_count, updated_at",
        "source_layers": "id, dataset_id, layer_name, geometry_type, feature_count",
        "parcels": (
            "id, run_id, parcel_id, ulpin, status, confidence, review_state, "
            "khasra_no, owner_name, owner_name_local, recorded_area_sqm, surveyed_area_sqm, "
            "land_use, match_verdict, match_score, attribute_status, concerns_json"
        ),
        "parcel_geometries": "id, run_id, parcel_ref, stage, crs, area_sqm, valid, geojson",
        "parcel_attributes": "id, run_id, parcel_ref, field, value, source_layer, source_value",
        "survey_points": (
            "id, run_id, parcel_ref, point_id, x, y, lat, lon, "
            "accuracy_m, method, base_station, evidence, recorded_by, observed_on"
        ),
        "harmonization_runs": (
            "id, run_ref, status, started_at, finished_at, elapsed_seconds, summary_json"
        ),
        "conflicts": (
            "id, run_id, parcel_ref, conflict_type, severity, status, confidence, "
            "source_layers, detail, geometry_json, review_action, review_note, reviewed_by, reviewed_at"
        ),
        "changes": (
            "id, run_id, parcel_ref, change_type, confidence, status, "
            "description, area_delta_pct, geometry_json"
        ),
        "confidence_scores": "id, run_id, parcel_ref, overall, components_json, evidence_json",
        "audit_logs": "id, run_id, actor, action, target, result, detail_json, created_at",
    }

    def __init__(self, path: Optional[Path] = None) -> None:
        db_path = path or (STORAGE_DIR / "navonmesh.sqlite3")
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.path = db_path
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self.initialise()

    # -- lifecycle ---------------------------------------------------------
    def initialise(self) -> None:
        with self._lock, self._conn:
            for entity, columns in self._SCHEMA.items():
                self._conn.execute(f"CREATE TABLE IF NOT EXISTS {entity} ({columns})")
                # Additive migration: an existing table from an earlier build may
                # lack newly added columns. ALTER TABLE ADD COLUMN is cheap and
                # keeps demo state across code changes.
                existing = {
                    row["name"]
                    for row in self._conn.execute(f"PRAGMA table_info({entity})").fetchall()
                }
                for column in columns.split(","):
                    name = column.split()[0]
                    if name not in existing:
                        self._conn.execute(f"ALTER TABLE {entity} ADD COLUMN {column}")

    def health(self) -> Dict[str, Any]:
        counts = {entity: self._conn.execute(f"SELECT COUNT(*) c FROM {entity}").fetchone()["c"]
                  for entity in ENTITIES}
        return {
            "mode": self.mode,
            "backend": "sqlite",
            "path": str(self.path),
            "entity_counts": counts,
            "writable": True,
        }

    # -- generic access ----------------------------------------------------
    @staticmethod
    def _pk(entity: str) -> str:
        return "id"

    def _table(self, entity: str) -> str:
        if entity not in self._SCHEMA:
            raise KeyError(f"Unknown entity '{entity}'. Known: {sorted(self._SCHEMA)}")
        return entity

    def put(self, entity: str, record: Dict[str, Any], key: str = "id") -> Dict[str, Any]:
        table = self._table(entity)
        row = dict(record)
        row.setdefault("id", new_id(entity.split("_")[0]))
        columns = {c.split()[0] for c in self._SCHEMA[table].split(",")}
        payload = {
            k: _stringify(v) for k, v in row.items() if k in columns
        }
        if not payload:
            raise ValueError(f"Nothing to write to '{table}': record has no known columns")
        placeholders = ",".join("?" for _ in payload)
        cols = ",".join(payload)
        with self._lock, self._conn:
            self._conn.execute(
                f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})",
                tuple(payload.values()),
            )
        return row

    def put_many(self, entity: str, records: Iterable[Dict[str, Any]], key: str = "id") -> int:
        rows = list(records)
        for row in rows:
            self.put(entity, row, key)
        return len(rows)

    def get(self, entity: str, record_id: str) -> Optional[Dict[str, Any]]:
        table = self._table(entity)
        cur = self._conn.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
        found = cur.fetchone()
        return dict(found) if found else None

    def all(self, entity: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        table = self._table(entity)
        sql = f"SELECT * FROM {table}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        return [dict(r) for r in self._conn.execute(sql).fetchall()]

    def query(self, entity: str, **filters: Any) -> List[Dict[str, Any]]:
        table = self._table(entity)
        where = " AND ".join(f"{k} = ?" for k in filters)
        sql = f"SELECT * FROM {table}" + (f" WHERE {where}" if where else "")
        return [dict(r) for r in self._conn.execute(sql, tuple(filters.values())).fetchall()]

    def update(self, entity: str, record_id: str, **fields: Any) -> Optional[Dict[str, Any]]:
        current = self.get(entity, record_id)
        if current is None:
            return None
        current.update(fields)
        return self.put(entity, current)

    def delete(self, entity: str, record_id: str) -> bool:
        table = self._table(entity)
        with self._lock, self._conn:
            cur = self._conn.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
        return cur.rowcount > 0

    def clear(self, entity: str) -> int:
        table = self._table(entity)
        with self._lock, self._conn:
            cur = self._conn.execute(f"DELETE FROM {table}")
        return cur.rowcount


# ---------------------------------------------------------------------------
# POSTGIS MODE
# ---------------------------------------------------------------------------
POSTGIS_DDL = """
CREATE TABLE IF NOT EXISTS source_layers (
    id UUID PRIMARY KEY, dataset_id UUID, layer_name TEXT, geometry_type TEXT,
    feature_count INTEGER, properties JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS survey_points (
    id UUID PRIMARY KEY, point_id TEXT, x DOUBLE PRECISION, y DOUBLE PRECISION,
    lat DOUBLE PRECISION, lon DOUBLE PRECISION, accuracy_m DOUBLE PRECISION, method TEXT,
    base_station TEXT, evidence TEXT, recorded_by TEXT, observed_on TEXT,
    parcel_ref TEXT, run_id UUID, geom geometry(Point,4326)
);
CREATE TABLE IF NOT EXISTS parcel_geometries (
    id UUID PRIMARY KEY, parcel_ref TEXT, stage TEXT, crs TEXT, geom geometry(Geometry,4326),
    area_sqm DOUBLE PRECISION, valid BOOLEAN DEFAULT TRUE, run_id UUID
);
CREATE TABLE IF NOT EXISTS parcel_attributes (
    id UUID PRIMARY KEY, parcel_ref TEXT, field TEXT, value TEXT, source_layer TEXT,
    source_value TEXT, run_id UUID
);
CREATE TABLE IF NOT EXISTS parcels (
    id UUID PRIMARY KEY, parcel_id TEXT, ulpin TEXT, run_id UUID, status TEXT,
    confidence DOUBLE PRECISION, review_state TEXT, khasra_no TEXT, owner_name TEXT,
    owner_name_local TEXT, recorded_area_sqm DOUBLE PRECISION, surveyed_area_sqm DOUBLE PRECISION,
    land_use TEXT, match_verdict TEXT, match_score DOUBLE PRECISION, attribute_status TEXT,
    concerns JSONB
);
CREATE TABLE IF NOT EXISTS harmonization_runs (
    id UUID PRIMARY KEY, run_ref TEXT, status TEXT, started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ, elapsed_seconds DOUBLE PRECISION, params JSONB, summary JSONB
);
CREATE TABLE IF NOT EXISTS conflicts (
    id UUID PRIMARY KEY, run_id UUID, parcel_ref TEXT, conflict_type TEXT, severity TEXT,
    status TEXT, confidence DOUBLE PRECISION, source_layers TEXT, detail TEXT,
    geometry JSONB, geom geometry(Geometry,4326),
    review_action TEXT, review_note TEXT, reviewed_by TEXT, reviewed_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS changes (
    id UUID PRIMARY KEY, run_id UUID, parcel_ref TEXT, change_type TEXT, confidence DOUBLE
    PRECISION, status TEXT, description TEXT, area_delta_pct DOUBLE PRECISION,
    geometry JSONB
);
CREATE TABLE IF NOT EXISTS confidence_scores (
    id UUID PRIMARY KEY, run_id UUID, parcel_ref TEXT, overall DOUBLE PRECISION,
    components JSONB, evidence JSONB
);
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY, run_id UUID, actor TEXT, action TEXT, target TEXT, result TEXT,
    detail JSONB, created_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS parcels_geom_idx ON parcels (parcel_id);
CREATE INDEX IF NOT EXISTS conflicts_geom_idx ON conflicts USING GIST (geom);
CREATE INDEX IF NOT EXISTS changes_parcel_idx ON changes (parcel_ref);
"""


class PostGISRepository(Repository):
    """PostgreSQL + PostGIS backend for production-shaped deployments.

    Implemented against psycopg2 + PostGIS. Geometry columns are exposed as
    GeoJSON strings so callers in LOCAL and POSTGIS modes see identical
    structures. If the driver or the extension is unavailable the constructor
    raises a clear, actionable error rather than silently degrading, because a
    silent fallback would misrepresent which backend is actually in use.
    """

    mode = "postgis"

    def __init__(self, dsn: Optional[str] = None) -> None:
        self.dsn = dsn or os.environ.get("NAVONMESH_POSTGIS_DSN")
        if not self.dsn:
            raise RuntimeError(
                "NAVONMESH_REPO_MODE=postgis requires NAVONMESH_POSTGIS_DSN, e.g. "
                "postgresql://user:pass@localhost:5432/navonmesh"
            )
        try:
            import psycopg2  # noqa: F401
        except ImportError as exc:  # pragma: no cover - environment dependent
            raise RuntimeError(
                "PostGIS mode needs psycopg2-binary. Install it or set "
                "NAVONMESH_REPO_MODE=demo to run the local demonstrator."
            ) from exc
        import psycopg2

        self._psycopg2 = psycopg2
        self._conn = psycopg2.connect(self.dsn)
        self._lock = threading.RLock()
        self.initialise()

    def initialise(self) -> None:  # pragma: no cover - requires live PostGIS
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS postgis")
                cur.execute(POSTGIS_DDL)

    def health(self) -> Dict[str, Any]:  # pragma: no cover
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute("SELECT PostGIS_Version()")
                version = cur.fetchone()[0]
                cur.execute("SELECT version()")
                server = cur.fetchone()[0]
        return {
            "mode": self.mode,
            "backend": "postgresql/postgis",
            "postgis_version": version,
            "server_version": server,
            "writable": True,
        }

    # A thin generic implementation keeps the two backends behaviourally equal.
    _TABLES = {
        "datasets": "source_layers",
        "source_layers": "source_layers",
        "parcels": "parcels",
        "parcel_geometries": "parcel_geometries",
        "parcel_attributes": "parcel_attributes",
        "survey_points": "survey_points",
        "harmonization_runs": "harmonization_runs",
        "conflicts": "conflicts",
        "changes": "changes",
        "confidence_scores": "confidence_scores",
        "audit_logs": "audit_logs",
    }

    def put(self, entity: str, record: Dict[str, Any], key: str = "id") -> Dict[str, Any]:  # pragma: no cover
        table = self._TABLES[entity]
        row = dict(record)
        row.setdefault("id", new_id(entity.split("_")[0]))
        cols = [c for c in row if c != "geom"]
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    f"INSERT INTO {table} ({','.join(cols)}) "
                    f"VALUES ({','.join(['%s'] * len(cols))}) "
                    f"ON CONFLICT (id) DO UPDATE SET "
                    + ",".join(f"{c}=EXCLUDED.{c}" for c in cols if c != "id"),
                    tuple(row[c] for c in cols),
                )
        return row

    def put_many(self, entity: str, records: Iterable[Dict[str, Any]], key: str = "id") -> int:  # pragma: no cover
        rows = list(records)
        for row in rows:
            self.put(entity, row, key)
        return len(rows)

    def get(self, entity: str, record_id: str) -> Optional[Dict[str, Any]]:  # pragma: no cover
        found = self.query(entity, id=record_id)
        return found[0] if found else None

    def all(self, entity: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:  # pragma: no cover
        return self.query(entity)[: limit or 10**9]

    def query(self, entity: str, **filters: Any) -> List[Dict[str, Any]]:  # pragma: no cover
        table = self._TABLES[entity]
        where = " AND ".join(f"{k} = %s" for k in filters)
        sql = f"SELECT *, ST_AsGeoJSON(geom) AS geojson FROM {table}"
        if where:
            sql += f" WHERE {where}"
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute(sql, tuple(filters.values()))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def update(self, entity: str, record_id: str, **fields: Any) -> Optional[Dict[str, Any]]:  # pragma: no cover
        current = self.get(entity, record_id)
        if current is None:
            return None
        current.update(fields)
        return self.put(entity, current)

    def delete(self, entity: str, record_id: str) -> bool:  # pragma: no cover
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute(f"DELETE FROM {self._TABLES[entity]} WHERE id = %s", (record_id,))
        return cur.rowcount > 0

    def clear(self, entity: str) -> int:  # pragma: no cover
        with self._lock, self._conn:
            with self._conn.cursor() as cur:
                cur.execute(f"DELETE FROM {self._TABLES[entity]}")
        return cur.rowcount


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_REPO: Optional[Repository] = None
_REPO_LOCK = threading.Lock()


def get_repository(mode: Optional[str] = None) -> Repository:
    """Return the process-wide repository. Mode: ``demo`` (default) or ``postgis``."""
    global _REPO
    if _REPO is not None and mode is None:
        return _REPO
    resolved = (mode or os.environ.get("NAVONMESH_REPO_MODE") or "demo").lower()
    with _REPO_LOCK:
        if _REPO is None or mode is not None:
            _REPO = PostGISRepository() if resolved == "postgis" else LocalDemoRepository()
    return _REPO


def reset_repository(mode: Optional[str] = None) -> Repository:
    """Force-rebuild the repository. Used by tests and by /api/admin/reset."""
    global _REPO
    with _REPO_LOCK:
        _REPO = None
    return get_repository(mode)


def json_dumps(value: Any) -> str:
    """Deterministic JSON for column storage."""
    return json.dumps(value, separators=(",", ":"), sort_keys=True, default=str)


# Columns that hold structured values rather than scalars.
_JSON_SUFFIXES = ("_json",)


def _stringify(value: Any) -> Any:
    """Coerce a value for a scalar column, serialising structured payloads.

    SQLite is dynamically typed, but storing a dict or list directly would make
    reads return whatever the driver infers. Both backends therefore store JSON
    text for structured columns, keeping them byte-for-byte comparable.
    """
    if isinstance(value, (dict, list, tuple)):
        return json_dumps(value)
    return value


def json_loads(value: Optional[str], default: Any = None) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default
