"""
NAVONMESH - FastAPI Backend Server
Navonmesh - Intelligent Multi-Source Geospatial Harmonization Platform
SIH26013 Prototype (Smart Automation) - MoRD / DoLR problem statement

Every value in this module is derived from a real service computation or from
the repository. Nothing is hardcoded, simulated or randomised. The system is a
decision-support prototype and confers no legal title or official status.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import CANONICAL_PARCEL_SCHEMA, PIPELINE_STAGE_LABEL
from app.services import (
    audit_service,
    confidence_service,
    conflict_service,
    export_service,
    ingestion_service,
    pipeline_service,
    repositories,
)
from app.services.export_service import ExportError

app = FastAPI(
    title="NAVONMESH - Intelligent Multi-Source Geospatial Harmonization Platform",
    description=(
        "Navonmesh prototype for intelligent integration and harmonization of "
        "urban land records. SIH26013. All reported values are computed from "
        "the loaded data. Output is decision support only and confers no legal "
        "title, ownership or official record status."
    ),
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    # A local prototype, not an internet-facing service. Narrowed from "*" so
    # the API is not trivially callable from any origin.
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type"],
)


def repo() -> repositories.Repository:
    return repositories.get_repository()


def _latest_run_id() -> Optional[str]:
    runs = repo().all("harmonization_runs")
    if not runs:
        return None
    ordered = sorted(runs, key=lambda r: str(r.get("finished_at") or ""))
    return ordered[-1].get("id")


def _require_run(run_id: Optional[str] = None) -> str:
    resolved = run_id or _latest_run_id()
    if not resolved:
        raise HTTPException(
            status_code=409,
            detail="No harmonization run yet. POST /api/harmonization/runs first.",
        )
    return resolved


@app.get("/")
def root() -> Dict[str, Any]:
    health = repo().health()
    datasets = ingestion_service.list_datasets()
    runs = repo().all("harmonization_runs")
    return {
        "system": "NAVONMESH - Intelligent Multi-Source Geospatial Harmonization Platform",
        "status": "online",
        "program": "SIH26013 Prototype (Smart Automation)",
        "problem_owner": "Ministry of Rural Development (MoRD) / DoLR",
        "storage_mode": health.get("mode"),
        "datasets_loaded": len(datasets),
        "runs_recorded": len(runs),
        "disclaimer": (
            "Prototype decision-support output. No record confers legal title, "
            "ownership or official status. Demo data is synthetic."
        ),
    }


@app.get("/api/health")
def health() -> Dict[str, Any]:
    return repo().health()


# ---------------------------------------------------------------------------
# Source data
# ---------------------------------------------------------------------------
@app.get("/api/datasets")
def list_datasets() -> Dict[str, Any]:
    datasets = ingestion_service.list_datasets()
    return {"count": len(datasets), "datasets": datasets}


@app.get("/api/datasets/coverage")
def dataset_coverage() -> Dict[str, Any]:
    return ingestion_service.coverage_report()


@app.get("/api/source-categories")
def source_categories() -> Dict[str, Any]:
    return {"categories": ingestion_service.SOURCE_CATEGORIES}


@app.get("/api/schema/canonical")
def canonical_schema() -> Dict[str, Any]:
    return {"fields": CANONICAL_PARCEL_SCHEMA, "stage_labels": PIPELINE_STAGE_LABEL}


@app.post("/api/demo/load")
def load_demo() -> Dict[str, Any]:
    """Materialise and ingest the synthetic demo project."""
    result = pipeline_service.ingest_demo_project(repo())
    return {
        "status": "LOADED",
        "is_demo": True,
        "notice": result.get("project", {}).get("dataset_notice"),
        "project": result.get("project"),
        "dataset_count": len(result.get("datasets") or []),
        "datasets": [
            {
                "dataset_id": d.get("dataset_id"),
                "name": d.get("name"),
                "category_id": d.get("category_id"),
                "format": d.get("format"),
                "data_type": d.get("data_type"),
                "feature_count": d.get("feature_count"),
                "source_crs": d.get("source_crs"),
            }
            for d in result.get("datasets") or []
        ],
    }


# ---------------------------------------------------------------------------
# Harmonization runs
# ---------------------------------------------------------------------------
class RunRequest(BaseModel):
    params: Optional[Dict[str, Any]] = Field(default=None)
    actor: str = "gis_analyst"


@app.post("/api/harmonization/runs")
def start_run(request: RunRequest) -> Dict[str, Any]:
    """Execute the real pipeline over every loaded dataset and persist results."""
    datasets = ingestion_service.list_datasets()
    if not datasets:
        raise HTTPException(
            status_code=409, detail="No datasets loaded. POST /api/demo/load first."
        )
    result = pipeline_service.run_full_pipeline(
        repo(), params=request.params, actor=request.actor
    )
    if result.get("status") != "COMPLETED":
        raise HTTPException(
            status_code=422, detail=result.get("reason") or "Harmonization failed"
        )
    return result


@app.get("/api/harmonization/runs")
def list_runs() -> Dict[str, Any]:
    runs = repo().all("harmonization_runs")
    ordered = sorted(runs, key=lambda r: str(r.get("finished_at") or ""), reverse=True)
    decorated = []
    for run in ordered:
        summary = repositories.json_loads(run.get("summary_json"), {}) or {}
        decorated.append(
            {
                "id": run.get("id"),
                "run_ref": run.get("run_ref"),
                "status": run.get("status"),
                "started_at": run.get("started_at"),
                "finished_at": run.get("finished_at"),
                "elapsed_seconds": run.get("elapsed_seconds"),
                "parcels_processed": summary.get("parcels_processed"),
                "conflicts_created": summary.get("conflicts_created"),
                "avg_confidence": summary.get("avg_confidence"),
            }
        )
    return {"count": len(decorated), "runs": decorated}


@app.get("/api/harmonization/runs/{run_id}")
def get_run(run_id: str) -> Dict[str, Any]:
    record = repo().get("harmonization_runs", run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    return {**record, "summary": repositories.json_loads(record.get("summary_json"), {})}


@app.get("/api/harmonization/runs/{run_id}/quality")
def run_quality(run_id: str) -> Dict[str, Any]:
    record = repo().get("harmonization_runs", run_id)
    if not record:
        raise HTTPException(status_code=404, detail="Run not found")
    summary = repositories.json_loads(record.get("summary_json"), {}) or {}
    return {
        "run_id": run_id,
        "quality": summary.get("quality"),
        "topology_before": summary.get("topology_before"),
        "topology_after": summary.get("topology_after"),
        "crs_normalization": summary.get("crs_normalization"),
        "spatial_matching": summary.get("spatial_matching"),
        "georeferencing": summary.get("georeferencing"),
    }



# ---------------------------------------------------------------------------
# Parcels
# ---------------------------------------------------------------------------
@app.get("/api/parcels")
def list_parcels(
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    review_state: Optional[str] = None,
    search: Optional[str] = None,
    min_confidence: Optional[float] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    resolved = _require_run(run_id)
    rows = repo().query("parcels", run_id=resolved)
    rows.sort(key=lambda r: r.get("confidence") or 0.0, reverse=True)
    if status:
        rows = [r for r in rows if str(r.get("status") or "").upper() == status.upper()]
    if review_state:
        rows = [r for r in rows if str(r.get("review_state") or "").upper() == review_state.upper()]
    if min_confidence is not None:
        rows = [r for r in rows if (r.get("confidence") or 0) >= min_confidence]
    if search:
        needle = search.strip().lower()
        rows = [
            r
            for r in rows
            if needle in str(r.get("parcel_id") or "").lower()
            or needle in str(r.get("khasra_no") or "").lower()
            or needle in str(r.get("owner_name") or "").lower()
        ]
    total = len(rows)
    return {
        "run_id": resolved,
        "total": total,
        "count": len(rows[offset : offset + limit]),
        "offset": offset,
        "parcels": [
            {
                "id": r.get("id"),
                "parcel_id": r.get("parcel_id"),
                "khasra_no": r.get("khasra_no"),
                "owner_name": r.get("owner_name"),
                "owner_name_local": r.get("owner_name_local"),
                "land_use": r.get("land_use"),
                "recorded_area_sqm": r.get("recorded_area_sqm"),
                "surveyed_area_sqm": r.get("surveyed_area_sqm"),
                "harmonized_area_sqm": r.get("harmonized_area_sqm"),
                "confidence": r.get("confidence"),
                "status": r.get("status"),
                "review_state": r.get("review_state"),
                "match_verdict": r.get("match_verdict"),
                "attribute_status": r.get("attribute_status"),
            }
            for r in rows[offset : offset + limit]
        ],
    }


@app.get("/api/parcels/dossier")
def parcel_dossier(parcel_ref: str, run_id: Optional[str] = None) -> Dict[str, Any]:
    """Full dossier: attributes, both geometries, conflicts, lineage and score.

    ``parcel_ref`` is a query parameter rather than a path segment because
    cadastral identifiers contain "/" (e.g. "MH-PUN-101/1"), which would
    otherwise be parsed as a route separator.
    """
    resolved = _require_run(run_id)
    rows = [
        r for r in repo().query("parcels", run_id=resolved)
        if r.get("parcel_id") == parcel_ref
    ]
    if not rows:
        raise HTTPException(status_code=404, detail="Parcel not found in this run")
    parcel = rows[0]

    geometries = [
        {
            "stage": g.get("stage"),
            "crs": g.get("crs"),
            "area_sqm": g.get("area_sqm"),
            "valid": g.get("valid"),
            "geojson": repositories.json_loads(g.get("geojson")),
        }
        for g in repo().query("parcel_geometries", parcel_ref=parcel_ref)
    ]
    attributes = [
        {
            "field": a.get("field"),
            "value": a.get("value"),
            "source_layer": a.get("source_layer"),
            "source_value": a.get("source_value"),
        }
        for a in repo().query("parcel_attributes", parcel_ref=parcel_ref)
    ]
    conflicts = repo().query("conflicts", run_id=resolved, parcel_ref=parcel_ref)
    changes = repo().query("changes", run_id=resolved, parcel_ref=parcel_ref)
    scores = repo().query("confidence_scores", run_id=resolved, parcel_ref=parcel_ref)
    points = repo().query("survey_points", parcel_ref=parcel_ref)[:50]

    return {
        "run_id": resolved,
        "parcel": parcel,
        "geometries": geometries,
        "attribute_lineage": attributes,
        "conflicts": conflicts,
        "changes": changes,
        "confidence": {
            "overall": scores[0].get("overall") if scores else None,
            "components": repositories.json_loads(scores[0].get("components_json"), {}) if scores else {},
            "evidence": repositories.json_loads(scores[0].get("evidence_json"), {}) if scores else {},
        },
        "survey_points": points,
        "audit": audit_service.dossier_lineage(repo(), parcel_ref),
    }


# ---------------------------------------------------------------------------
# Conflicts, changes, review
# ---------------------------------------------------------------------------
@app.get("/api/conflicts")
def list_conflicts(
    run_id: Optional[str] = None,
    conflict_type: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
) -> Dict[str, Any]:
    resolved = _require_run(run_id)
    rows = repo().query("conflicts", run_id=resolved)
    if conflict_type:
        rows = [r for r in rows if r.get("conflict_type") == conflict_type]
    if severity:
        rows = [r for r in rows if str(r.get("severity") or "").upper() == severity.upper()]
    if status:
        rows = [r for r in rows if str(r.get("status") or "").upper() == status.upper()]
    return {
        "run_id": resolved,
        "total": len(rows),
        "summary": conflict_service.summarise(rows),
        "conflicts": rows[offset : offset + limit],
    }


@app.get("/api/changes")
def list_changes(run_id: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    resolved = _require_run(run_id)
    rows = repo().query("changes", run_id=resolved)
    return {
        "run_id": resolved,
        "total": len(rows),
        "note": (
            "Temporal change detection compares two epochs of the same parcel. "
            "The demo project supplies a single epoch, so this list is normally "
            "empty; cross-source geometry differences are reported as "
            "conflicts, not as changes."
        ),
        "changes": rows[:limit],
    }


class ReviewRequest(BaseModel):
    parcel_ref: str
    conflict_id: Optional[str] = None
    action: str
    note: Optional[str] = None
    actor: str = "reviewer"


@app.post("/api/review")
def submit_review(request: ReviewRequest) -> Dict[str, Any]:
    """Record a human verification decision. This is what makes scores advisory."""
    allowed = {"VERIFIED", "REJECTED", "NEEDS_INFO", "ESCALATED"}
    if request.action not in allowed:
        raise HTTPException(
            status_code=400, detail=f"action must be one of {sorted(allowed)}"
        )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).isoformat()
    store = repo()
    if request.conflict_id:
        record = store.get("conflicts", request.conflict_id)
        if not record:
            raise HTTPException(status_code=404, detail="Conflict not found")
        store.put(
            "conflicts",
            {
                **record,
                "status": request.action,
                "review_action": request.action,
                "review_note": request.note,
                "reviewed_by": request.actor,
                "reviewed_at": now,
            },
        )
    else:
        rows = store.query("parcels", parcel_id=request.parcel_ref)
        if not rows:
            raise HTTPException(status_code=404, detail="Parcel not found")
        store.put(
            "parcels",
            {**rows[0], "review_state": request.action, "status": "REVIEWED"},
        )
    audit_service.record(
        store,
        action="review_decision",
        actor=request.actor,
        target=request.conflict_id or request.parcel_ref,
        detail={"action": request.action, "note": request.note},
    )
    return {"status": "RECORDED", "action": request.action, "at": now}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@app.get("/api/audit/log")
def audit_log(limit: int = 200) -> Dict[str, Any]:
    rows = repo().all("audit_logs")
    ordered = sorted(rows, key=lambda r: str(r.get("created_at") or ""), reverse=True)
    return {"count": len(ordered), "logs": ordered[:limit]}


@app.get("/api/audit/parcel")
def parcel_lineage(parcel_ref: str) -> Dict[str, Any]:
    return {"parcel_ref": parcel_ref, **audit_service.dossier_lineage(repo(), parcel_ref)}


@app.get("/api/audit/capabilities")
def audit_capabilities() -> Dict[str, Any]:
    return {
        "roles": audit_service.ROLES,
        "note": (
            "Confidence scores are advisory. Only these roles may record a human "
            "verification decision, and every decision is written to the audit log."
        ),
    }


# ---------------------------------------------------------------------------
# Analytics and export
# ---------------------------------------------------------------------------
@app.get("/api/analytics")
def analytics(run_id: Optional[str] = None) -> Dict[str, Any]:
    resolved = _require_run(run_id)
    run = repo().get("harmonization_runs", resolved) or {}
    summary = repositories.json_loads(run.get("summary_json"), {}) or {}
    conflicts = repo().query("conflicts", run_id=resolved)
    parcels = repo().query("parcels", run_id=resolved)
    scores = [p.get("confidence") or 0.0 for p in parcels]
    return {
        "run_id": resolved,
        "run_ref": run.get("run_ref"),
        "parcels_processed": len(parcels),
        "confidence": confidence_service.distribution(scores),
        "conflicts": conflict_service.summarise(conflicts),
        "attribute_status": summary.get("attribute_status"),
        "spatial_matching": summary.get("spatial_matching"),
        "topology": {
            "before": summary.get("topology_before"),
            "after": summary.get("topology_after"),
        },
        "elapsed_seconds": run.get("elapsed_seconds"),
    }


class ExportRequest(BaseModel):
    run_id: Optional[str] = None
    parcel_ids: Optional[list] = None
    include_conflicts: bool = True
    actor: str = "gis_analyst"


@app.post("/api/export/report.pdf")
def export_pdf(request: ExportRequest) -> Response:
    """Per-parcel verification dossier as a real PDF."""
    resolved = _require_run(request.run_id)
    rows = repo().query("parcels", run_id=resolved)
    if request.parcel_ids:
        wanted = set(request.parcel_ids)
        rows = [r for r in rows if r.get("parcel_id") in wanted]
    if not rows:
        raise HTTPException(status_code=404, detail="Nothing to export")

    lineage = audit_service.dossier_lineage(repo(), rows[0].get("parcel_id"))
    scores = repo().query(
        "confidence_scores", run_id=resolved, parcel_ref=rows[0].get("parcel_id")
    )
    blob = export_service.build_parcel_report_pdf(
        rows[0],
        lineage=lineage.get("field_lineage"),
        conflicts=(
            repo().query("conflicts", run_id=resolved, parcel_ref=rows[0].get("parcel_id"))
            if request.include_conflicts
            else None
        ),
        confidence=(
            {
                "overall": scores[0].get("overall"),
                "components": repositories.json_loads(scores[0].get("components_json"), {}),
                "evidence": repositories.json_loads(scores[0].get("evidence_json"), {}),
            }
            if scores
            else None
        ),
    )
    filename = f"navonmesh_{rows[0].get('parcel_id').replace('/', '-')}_dossier.pdf"
    return Response(
        content=blob,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )



@app.get("/api/export/formats")
def export_formats() -> Dict[str, Any]:
    """Formats that are genuinely implemented, and their real capability state."""
    return {
        "formats": export_service.available_formats(),
        "note": (
            "Formats marked unavailable are refused with 501 rather than "
            "silently emitting a renamed text file."
        ),
    }


def _export_feature(row: Dict[str, Any]) -> Dict[str, Any]:
    """Combine a parcel row with its harmonised geometry for export."""
    geom_row = None
    for candidate in repo().query(
        "parcel_geometries", parcel_ref=row.get("parcel_id"), stage="harmonized"
    ):
        geom_row = candidate
        break
    geometry = repositories.json_loads(geom_row.get("geojson")) if geom_row else None
    return {
        "properties": {k: v for k, v in row.items() if k != "id"},
        "geometry": geometry,
    }



@app.post("/api/export/{fmt}")
def export(fmt: str, request: ExportRequest) -> Response:
    """Produce a real file in the requested format. Unsupported formats 501."""
    resolved = _require_run(request.run_id)
    rows = repo().query("parcels", run_id=resolved)
    if request.parcel_ids:
        wanted = set(request.parcel_ids)
        rows = [r for r in rows if r.get("parcel_id") in wanted]
    if not rows:
        raise HTTPException(status_code=404, detail="Nothing to export")

    features = [_export_feature(r) for r in rows]
    payloads = {
        "geojson": (lambda f: export_service.write_geojson(f), "application/geo+json", "geojson"),
        "csv": (lambda f: export_service.write_csv(f), "text/csv", "csv"),
        "geopackage": (
            lambda f: export_service.write_geopackage(f, layer="navonmesh_parcels"),
            "application/geopackage+sqlite3",
            "gpkg",
        ),
        "shapefile": (lambda f: export_service.write_shapefile(f), "application/zip", "zip"),
    }
    if fmt not in payloads:
        raise HTTPException(
            status_code=501,
            detail=f"Format '{fmt}' is not implemented. Available: {sorted(payloads)}",
        )
    builder, media_type, extension = payloads[fmt]
    try:
        blob = builder(features)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except ExportError as exc:
        raise HTTPException(status_code=501, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Export failed: {exc}")

    audit_service.record(
        repo(),
        action="export",
        actor=request.actor,
        target=fmt,
        detail={"records": len(rows), "run_id": resolved},
    )
    filename = f"navonmesh_{run_ref_of(repo(), resolved)}_{extension}"
    return Response(
        content=blob,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def run_ref_of(repository: repositories.Repository, run_id: str) -> str:
    record = repository.get("harmonization_runs", run_id) or {}
    return str(record.get("run_ref") or "run")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)