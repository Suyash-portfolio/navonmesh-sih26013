"""
NAVONMESH - Audit & Lineage Service (Phases 18 and 25)

Government-style auditability and per-parcel data lineage.

Two distinct concerns live here because they share the same storage and the
same guarantee - that every derived value can be traced back to the operation
and the source that produced it:

* ``audit``   append-only log of every operation (who/what/when/result).
* ``lineage`` per-parcel record of which source layer supplied which field.

Nothing in this module ever mutates a parcel. It only observes.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.services import repositories
from app.services.repositories import Repository, new_id

# ---------------------------------------------------------------------------
# Roles (Phase 24) - used for attribution and for role-aware UI.
# ---------------------------------------------------------------------------
ROLES: List[Dict[str, str]] = [
    {
        "id": "gis_analyst",
        "label": "GIS Analyst",
        "capabilities": [
            "ingest", "validate", "run_harmonization", "inspect_geometry", "export",
        ],
    },
    {
        "id": "surveyor",
        "label": "Surveyor",
        "capabilities": ["ground_truth", "gnss_points", "field_verification"],
    },
    {
        "id": "revenue_officer",
        "label": "Revenue Officer",
        "capabilities": ["ror_attributes", "owner_records", "attribute_conflicts"],
    },
    {
        "id": "ulb_administrator",
        "label": "ULB Administrator",
        "capabilities": ["municipal_layers", "road_row", "drainage", "utilities"],
    },
    {
        "id": "reviewer",
        "label": "Reviewer",
        "capabilities": ["review_conflicts", "approve", "reject", "resolve"],
    },
]


def role_label(role_id: str) -> str:
    for role in ROLES:
        if role["id"] == role_id:
            return role["label"]
    return role_id


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------
def record(
    repo: Repository,
    *,
    action: str,
    actor: str = "system",
    target: str = "",
    result: str = "SUCCESS",
    run_id: Optional[str] = None,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Append one audit entry. Returns the stored record."""
    from app.services.ingestion_service import utc_now

    entry = {
        "id": new_id("aud"),
        "run_id": run_id,
        "actor": actor,
        "action": action,
        "target": target,
        "result": result,
        "detail_json": repositories.json_dumps(detail or {}),
        "created_at": utc_now(),
    }
    return repo.put("audit_logs", entry)


def list_audit(
    repo: Repository,
    *,
    run_id: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """Newest first. ``detail`` is returned as a real object, not a JSON string."""
    rows = repo.query("audit_logs", run_id=run_id) if run_id else repo.all("audit_logs")
    rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
    out: List[Dict[str, Any]] = []
    for row in rows[:limit]:
        out.append(
            {
                "id": row.get("id"),
                "run_id": row.get("run_id"),
                "time": row.get("created_at"),
                "actor": row.get("actor"),
                "actor_label": role_label(row.get("actor") or "system"),
                "action": row.get("action"),
                "target": row.get("target"),
                "result": row.get("result"),
                "detail": repositories.json_loads(row.get("detail_json"), {}),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Lineage (Phase 18)
# ---------------------------------------------------------------------------
def record_field_source(
    repo: Repository,
    *,
    parcel_ref: str,
    field: str,
    value: Any,
    source_layer: str,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Store one field-level provenance record (which layer supplied which field)."""
    return repo.put(
        "parcel_attributes",
        {
            "id": new_id("attr"),
            "parcel_ref": parcel_ref,
            "field": field,
            "value": "" if value is None else str(value),
            "source_layer": source_layer,
        },
    )


def parcel_lineage(repo: Repository, parcel_ref: str) -> List[Dict[str, Any]]:
    """All field-level provenance for one parcel, grouped by source layer."""
    rows = repo.query("parcel_attributes", parcel_ref=parcel_ref)
    by_layer: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_layer.setdefault(row.get("source_layer") or "unknown", []).append(
            {"field": row.get("field"), "value": row.get("value")}
        )
    return [
        {
            "source_layer": layer,
            "field_count": len(fields),
            "fields": sorted(fields, key=lambda f: f["field"] or ""),
        }
        for layer, fields in sorted(by_layer.items())
    ]


def geometry_lineage(repo: Repository, parcel_ref: str) -> List[Dict[str, Any]]:
    """Every stored geometry stage for a parcel (legacy / modern / harmonized)."""
    rows = repo.query("parcel_geometries", parcel_ref=parcel_ref)
    return [
        {
            "stage": r.get("stage"),
            "crs": r.get("crs"),
            "area_sqm": r.get("area_sqm"),
            "valid": bool(r.get("valid")),
            "geojson": repositories.json_loads(r.get("geojson")),
        }
        for r in rows
    ]


def record_geometry(
    repo: Repository,
    *,
    parcel_ref: str,
    stage: str,
    geojson: Optional[Dict[str, Any]],
    crs: str,
    area_sqm: Optional[float] = None,
    valid: bool = True,
) -> Dict[str, Any]:
    return repo.put(
        "parcel_geometries",
        {
            "id": new_id("geom"),
            "parcel_ref": parcel_ref,
            "stage": stage,
            "crs": crs,
            "area_sqm": area_sqm,
            "valid": bool(valid),
            "geojson": repositories.json_dumps(geojson) if geojson else None,
        },
    )


def dossier_lineage(repo: Repository, parcel_ref: str) -> Dict[str, Any]:
    """The complete 'Derived from' block shown in the parcel dossier."""
    layers = parcel_lineage(repo, parcel_ref)
    return {
        "parcel_id": parcel_ref,
        "source_layers": layers,
        "source_layer_count": len(layers),
        "geometry_stages": [g["stage"] for g in geometry_lineage(repo, parcel_ref)],
    }
