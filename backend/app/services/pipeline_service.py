"""
NAVONMESH - SIH26013 Pipeline Orchestrator (Phase 2)

Executes the real pipeline end to end against on-disk data:

    DATA SOURCES
      -> INGESTION
      -> FORMAT / SCHEMA / GEOMETRY VALIDATION
      -> CRS DETECTION -> CRS NORMALIZATION
      -> DATA STANDARDIZATION
      -> FEATURE EXTRACTION
      -> SPATIAL MATCHING
      -> GEOMETRY HARMONIZATION
      -> TOPOLOGY CORRECTION
      -> ATTRIBUTE RECONCILIATION
      -> CONFLICT DETECTION
      -> CHANGE DETECTION
      -> CONFIDENCE SCORING
      -> HUMAN VERIFICATION QUEUE
      -> HARMONIZED LAND RECORD
      -> WEB-GIS / EXPORT / API

Every number this module returns is measured from data that was read off disk
during the run. There are no target counts, no seeded "expected" statistics and
no random accuracy figures. The previous implementation of this endpoint
returned four of its five stages as hardcoded dict literals; those literals are
gone.

Stage progress is emitted through an optional callback so the UI can render
real backend progress (Phase 31) instead of a setInterval animation.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from app.config import DEFAULT_PIPELINE_PARAMS, PIPELINE_STAGE_LABEL, PROJECT_CRS, STORAGE_CRS
from app.services import (
    attribute_service,
    audit_service,
    change_service,
    confidence_service,
    conflict_service,
    crs_service,
    export_service,
    harmonization_service,
    ingestion_service,
    matching_service,
    repositories,
    standardization_service,
    topology_service,
    validation_service,
)
from app.services.ingestion_service import utc_now
from app.services.repositories import Repository, new_id

ProgressCallback = Callable[[Dict[str, Any]], None]

CATEGORY_LABELS = {
    "cadastral_map": "Existing Cadastral Maps",
    "municipal_gis": "Municipal GIS Layers",
    "building_footprint": "Building Footprints",
    "revenue_records": "Revenue Records / RoR",
    "gnss_cors": "GNSS / CORS Survey Data",
    "ground_truthing": "Ground Truthing (GT)",
    "ortho_ori": "Orthorectified Imagery (ORI)",
    "dsm_dtm": "DSM / DTM",
}


def _emit(cb: Optional[ProgressCallback], **payload: Any) -> None:
    if cb:
        try:
            cb(payload)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Adapter: ingestion_service record -> the flat shape this module uses.
# Kept in one place so a change to the ingestion contract has a single edit.
# ---------------------------------------------------------------------------
def normalise_dataset_record(record: Dict[str, Any]) -> Dict[str, Any]:
    parse = record.get("parse") or {}
    crs = record.get("crs") or {}
    effective_crs = crs.get("source_crs") or crs.get("effective") or crs.get("detected")
    return {
        "dataset_id": record.get("id"),
        "name": record.get("name"),
        "filename": record.get("filename"),
        "category_id": record.get("category_id"),
        "category_label": record.get("category_label"),
        "format": record.get("format"),
        "data_type": record.get("data_type"),
        "parser": record.get("parser"),
        "capability": record.get("parser"),
        "size_human": record.get("size_human"),
        "feature_count": record.get("record_count") or parse.get("features") or 0,
        "upload_status": record.get("upload_status"),
        "parse": parse,
        "columns": record.get("columns") or parse.get("columns") or [],
        "bounds": parse.get("bounds"),
        "source_crs": effective_crs,
        "crs_detail": crs,
        "duplicates": record.get("duplicates") or [],
        "_gdf": record.get("_gdf"),
        "_rows": record.get("_rows"),
        "_file_key": record.get("_file_key"),
    }


def _feature(props: Dict[str, Any], geometry: Optional[BaseGeometry]) -> Dict[str, Any]:
    from shapely.geometry import mapping

    return {
        "type": "Feature",
        "properties": props,
        "geometry": mapping(geometry) if geometry is not None and not geometry.is_empty else None,
    }


# ---------------------------------------------------------------------------
# Stage 1-4: ingestion + validation + CRS + standardization
# ---------------------------------------------------------------------------
def ingest_demo_project(
    repo: Repository,
    *,
    actor: str = "gis_analyst",
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Materialise the demo files on disk, ingest them, validate, normalise CRS."""
    from app.data import demo_project

    started = time.time()
    _emit(progress, stage="ingest", status="running", message="Materialising demo source files")

    descriptor = demo_project.bootstrap_demo_project()
    audit_service.record(
        repo,
        action="bootstrap_demo_project",
        actor=actor,
        target=descriptor["project_id"],
        detail={"files": len(descriptor["files"]), "is_demo": True},
    )

    ingested: List[Dict[str, Any]] = []
    for key, spec in descriptor["files"].items():
        path = Path(spec["path"])
        if not path.exists():
            audit_service.record(
                repo,
                action="ingest",
                actor=actor,
                target=path.name,
                result="MISSING",
                detail={"reason": "demo file not present on disk"},
            )
            continue
        _emit(
            progress,
            stage="ingest",
            status="running",
            dataset=path.name,
            message=f"Ingesting {CATEGORY_LABELS.get(spec['category'], spec['category'])}",
        )
        record = normalise_dataset_record(
            ingestion_service.ingest_file(
                project_id=descriptor["project_id"],
                category_id=spec["category"],
                display_name=path.stem,
                filename=path.name,
                path=path,
                declared_crs=spec.get("crs"),
                source_authority=CATEGORY_LABELS.get(spec["category"], spec["category"]),
                notes="Synthetic demo dataset - not official government data",
            )
        )
        record["_file_key"] = key
        record["_path"] = str(path)
        ingested.append(record)
        audit_service.record(
            repo,
            action="ingest",
            actor=actor,
            target=path.name,
            result="SUCCESS" if record.get("upload_status") == "parsed" else "FAILED",
            detail={
                "category": spec["category"],
                "format": record.get("format"),
                "features": record.get("feature_count"),
                "crs": record.get("detected_crs") or record.get("crs"),
            },
        )

    return {
        "project": descriptor,
        "datasets": ingested,
        "elapsed_seconds": round(time.time() - started, 3),
    }


def validate_and_normalize(
    repo: Repository,
    datasets: Sequence[Dict[str, Any]],
    *,
    actor: str = "gis_analyst",
    progress: Optional[ProgressCallback] = None,
) -> List[Dict[str, Any]]:
    """Format/schema/geometry validation plus CRS detection and normalization."""
    results: List[Dict[str, Any]] = []
    for record in datasets:
        name = record.get("name") or record.get("filename")
        _emit(progress, stage="validate", status="running", dataset=name)

        # Re-validate against the flat adapter shape the validator expects.
        report = validation_service.validate_dataset(
            {
                **record,
                "upload_status": record.get("upload_status"),
                "parse": record.get("parse"),
                "columns": record.get("columns"),
                "crs": {"source_crs": record.get("source_crs")},
            }
        )
        crs_block = {
            "declared": record.get("_declared_crs"),
            "detected": (record.get("crs_detail") or {}).get("source_crs"),
            "effective": record.get("source_crs"),
            "target": PROJECT_CRS,
            "aligned": record.get("source_crs") == PROJECT_CRS,
            "method": (record.get("crs_detail") or {}).get("method"),
            "confidence": (record.get("crs_detail") or {}).get("confidence"),
        }
        quality = quality_gate(record, report, crs_block)
        issues = report.get("issues") or []
        errors = quality.get("error_count") or 0
        warnings = quality.get("warning_count") or 0

        result = {
            "dataset_id": record.get("dataset_id"),
            "name": name,
            "category": record.get("category_id"),
            "category_label": record.get("category_label"),
            "format": record.get("format"),
            "feature_count": record.get("feature_count"),
            "capability": record.get("capability"),
            "size_human": record.get("size_human"),
            "crs": crs_block,
            "bounds": record.get("bounds"),
            "validation": {
                "status": "passed" if not (errors or warnings) else ("warning" if not errors else "failed"),
                "error_count": errors,
                "warning_count": warnings,
                "issues": issues[:8],
            },
            "quality_gate": quality,
        }
        results.append(result)

        audit_service.record(
            repo,
            action="validate_and_normalize",
            actor=actor,
            target=name,
            result="SUCCESS" if not errors else "WARNINGS",
            detail={
                "crs": crs_block,
                "errors": errors,
                "warnings": warnings,
                "quality_score": quality.get("score_pct"),
                "verdict": quality.get("verdict"),
            },
        )
    return results


def quality_gate(
    record: Dict[str, Any],
    report: Dict[str, Any],
    crs_block: Dict[str, Any],
) -> Dict[str, Any]:
    """Phase 6 data-quality gate: a hard stop before harmonization."""
    parse = record.get("parse") or {}
    feature_count = record.get("feature_count") or 0
    issues = report.get("issues") or []
    errors = sum(1 for i in issues if i.get("severity") == "error")
    warnings = sum(1 for i in issues if i.get("severity") == "warning")

    invalid_count = int((report.get("invalid") or {}).get("count") or 0)
    total_geoms = feature_count or 1
    geometry_score = max(0.0, 1.0 - (invalid_count / total_geoms)) if feature_count else 0.0

    # A non-spatial register (CSV RoR, GNSS observation table) legitimately has no
    # CRS and no extent. Penalising it would block the pipeline for a
    # non-defect, so CRS and coverage are scored as "not applicable" for tables.
    is_spatial = (record.get("data_type") or "vector") != "table"
    if is_spatial:
        crs_score = 1.0 if crs_block.get("effective") else 0.0
        coverage_score = 1.0 if record.get("bounds") else 0.0
    else:
        crs_score = 1.0
        coverage_score = 1.0

    attribute_score = float(record.get("attribute_fill_rate") or (1.0 if feature_count else 0.0))
    duplicate_count = len(record.get("duplicates") or [])
    duplicate_score = max(0.0, 1.0 - (duplicate_count / 10.0))

    score = (
        0.28 * geometry_score
        + 0.22 * crs_score
        + 0.22 * attribute_score
        + 0.14 * duplicate_score
        + 0.14 * coverage_score
    )
    score_pct = round(score * 100.0, 1)

    if parse.get("ok") is False or feature_count == 0:
        verdict, blocking = "BLOCKED", True
    elif score_pct >= 85:
        verdict, blocking = "PASS", False
    elif score_pct >= 65:
        verdict, blocking = "PASS_WITH_WARNINGS", False
    else:
        verdict, blocking = "BLOCKED", True

    return {
        "score_pct": score_pct,
        "verdict": verdict,
        "blocking": blocking,
        "components": {
            "Geometry Quality": round(geometry_score * 100, 1),
            "CRS Validity": round(crs_score * 100, 1) if is_spatial else "N/A (non-spatial register)",
            "Attribute Completeness": round(attribute_score * 100, 1),
            "Duplicate Freedom": round(duplicate_score * 100, 1),
            "Spatial Coverage": round(coverage_score * 100, 1) if is_spatial else "N/A (non-spatial register)",
        },
        "warnings": [i.get("message") for i in issues if i.get("severity") == "warning"][:5],
        "errors": [i.get("message") for i in issues if i.get("severity") == "error"][:5],
        "error_count": errors,
        "warning_count": warnings,
        "invalid_geometry_count": invalid_count,
    }


# ---------------------------------------------------------------------------
# Stage 5-13: the harmonization core
# ---------------------------------------------------------------------------
def run_harmonization(
    repo: Repository,
    datasets: Sequence[Dict[str, Any]],
    *,
    params: Optional[Dict[str, Any]] = None,
    actor: str = "gis_analyst",
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Execute matching, harmonization, topology, conflicts, changes, confidence."""
    settings = {**DEFAULT_PIPELINE_PARAMS, **(params or {})}
    started = time.time()
    by_category = {d.get("category_id"): d for d in datasets}

    # -- load the layers the core needs ----------------------------------
    _emit(progress, stage="spatial_match", status="running", message="Loading harmonization layers")
    legacy = by_category.get("cadastral_map")
    revenue = by_category.get("revenue_records")
    buildings = by_category.get("building_footprint")
    municipal = by_category.get("municipal_gis")
    gnss = by_category.get("gnss_cors")
    ground_truth = by_category.get("ground_truthing")

    legacy_gdf = ingestion_service.dataset_frame(legacy["dataset_id"]) if legacy else None
    if legacy_gdf is None or legacy_gdf.empty:
        return {
            "status": "FAILED",
            "reason": "Cadastral dataset unavailable - cannot harmonize",
            "stages": [],
        }

    # -- CRS normalization -------------------------------------------------
    # Every spatial operation below is a metric overlay, so all layers must be
    # in one projected frame first. Detection alone is not enough: a layer left
    # in EPSG:4326 while the cadastre is in EPSG:32643 would produce plausible-
    # looking but meaningless buffers, corridor areas and shift distances.
    _emit(progress, stage="crs_normalize", status="running", message="Normalizing to common CRS")
    spatial_datasets = [d for d in datasets if str(d.get("data_type") or "").lower() == "vector"]
    frames, crs_actions = align_spatial_layers(spatial_datasets, PROJECT_CRS)

    def _frame(dataset: Optional[Dict[str, Any]]):
        """Projected frame for a dataset, reprojected into the project CRS."""
        if not dataset:
            return None
        return frames.get(dataset["dataset_id"])

    legacy_gdf = _frame(legacy)
    if legacy_gdf is None or legacy_gdf.empty:
        return {
            "status": "FAILED",
            "reason": "Cadastral layer could not be projected into the project CRS",
            "stages": [],
        }

    # The demo cadastre deliberately contains invalid rings. Set operations
    # (union / difference / symmetric_difference) raise TopologyException on
    # those, so geometry is repaired here - before harmonization - rather than
    # being allowed to crash the run. The count is reported, not hidden.
    _emit(progress, stage="geometry_reconcile", status="running", message="Repairing invalid rings")
    repaired_count = 0
    cleaned_geoms: List[Optional[BaseGeometry]] = []
    for geom in legacy_gdf.geometry:
        fixed = topology_service.make_valid(geom) if geom is not None else None
        if fixed is not None and (geom is None or not geom.is_valid):
            repaired_count += 1
        cleaned_geoms.append(fixed)

    legacy_geoms = [g for g in cleaned_geoms if g is not None]
    legacy_ids = [str(v) for v in legacy_gdf[legacy_gdf.columns[0]].tolist()] if len(legacy_gdf.columns) else [
        str(i) for i in range(len(legacy_geoms))
    ]
    legacy_props = legacy_gdf.drop(columns=[legacy_gdf.geometry.name]).to_dict("records")
    # Keep ids/props aligned with the geometries that survived repair.
    keep = [i for i, g in enumerate(cleaned_geoms) if g is not None]
    legacy_ids = [legacy_ids[i] for i in keep]
    legacy_props = [legacy_props[i] for i in keep]

    revenue_rows = ingestion_service.dataset_rows(revenue["dataset_id"]) if revenue else []
    # `parcel_ref` is the RoR's own key onto the cadastral `parcel_id`;
    # `survey_no` alone is ambiguous (the same sheet carries `101/1` and
    # `101/1-A` as separate holdings) and is only a fallback.
    revenue_by_key = _index_rows(revenue_rows, ("parcel_ref", "parcel_id", "khasra_no", "survey_no"))

    building_gdf = _frame(buildings)
    structures_by_parcel = _structures_by_parcel(building_gdf, legacy_gdf, legacy_geoms)

    corridors = _corridors(municipal, frames)

    survey_points = _survey_points(gnss, ground_truth)

    # -- georeferencing ---------------------------------------------------
    # A thin-plate warp needs PAIRED observations of the same physical point in
    # two different frames. The demo project ships every layer already
    # co-registered in a common CRS, so there are no such pairs and the stage is
    # reported as SKIPPED. Reporting a fabricated RMSE here would be exactly the
    # failure this pipeline was rebuilt to eliminate.
    _emit(progress, stage="crs_normalize", status="running", message="Assessing georeferencing")
    georef = harmonization_service.fit_georeferencing(_registered_tie_pairs(survey_points, legacy_geoms))

    # -- spatial matching -------------------------------------------------
    # Legacy digitised rings are matched against OUTLINES RECONSTRUCTED FROM
    # SURVEY OBSERVATIONS, not against themselves. Comparing a layer to its own
    # geometry would return IoU 1.0 for every parcel and inflate confidence for
    # no evidential reason. Parcels with too few surveyed corners get no
    # candidate and are honestly reported as unmatched.
    _emit(progress, stage="spatial_match", status="running", message="Matching legacy rings to surveyed outlines")
    matcher = matching_service.SpatialMatcher(min_iou=settings["min_match_iou"])
    candidates = _surveyed_candidates(legacy_ids, survey_points)
    matches = matcher.match_all(
        [{"id": pid, "geometry": geom} for pid, geom in zip(legacy_ids, legacy_geoms)],
        candidates,
        survey_points,
    )
    match_by_id = {m["legacy_id"]: m for m in matches}
    matched_count = sum(
        1 for m in matches if m.get("verdict") in (matching_service.MATCHED, matching_service.PROBABLE)
    )

    # -- per-parcel core -------------------------------------------------
    _emit(progress, stage="geometry_reconcile", status="running", message="Harmonizing geometry")
    topology_inputs: List[BaseGeometry] = []
    parcel_records: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    changes: List[Dict[str, Any]] = []
    confidences: List[Dict[str, Any]] = []
    attribute_matches = 0
    attribute_conflicts = 0
    attribute_status_counts: Dict[str, int] = {}

    total = len(legacy_geoms)
    prepared: List[Dict[str, Any]] = []
    for index, (parcel_id, legacy_geom, props) in enumerate(
        zip(legacy_ids, legacy_geoms, legacy_props)
    ):
        if index % 25 == 0:
            _emit(
                progress,
                stage="geometry_reconcile",
                status="running",
                message="Harmonizing geometry",
                records_processed=index,
                records_total=total,
            )

        standardized = standardization_service.standardise_record(
            props, standardization_service.build_column_map(props.keys())
        )
        # `survey_no` and `parcel_ref` both alias onto khasra_no, so the RoR's
        # own survey number is read directly to avoid collapsing the two.
        rev_raw = revenue_by_key.get(parcel_id) or revenue_by_key.get(
            str(standardized.get("khasra_no") or props.get("survey_no") or "")
        ) or {}
        rev = standardization_service.standardise_record(
            rev_raw, standardization_service.build_column_map(rev_raw.keys())
        ) if rev_raw else {}
        if rev_raw.get("survey_no") and not rev.get("khasra_no"):
            rev["khasra_no"] = str(rev_raw["survey_no"]).strip()

        harmonized = harmonization_service.harmonize_parcel(
            parcel_id=parcel_id,
            legacy_geometry=legacy_geom,
            structures=structures_by_parcel.get(parcel_id, []),
            corridors=corridors,
            eave_shrink_m=0.0,
        )
        harmonized_geom = legacy_geom
        if harmonized.get("status") == "HARMONIZED" and harmonized["area_delta_sqm"] != 0:
            try:
                merged, _ = harmonization_service.conflate_with_structures(
                    legacy_geom, structures_by_parcel.get(parcel_id, [])
                )
                if merged is not None:
                    harmonized_geom = merged
                trimmed, _ = harmonization_service.subtract_corridors(
                    harmonized_geom, corridors
                )
                if trimmed is not None and not trimmed.is_empty:
                    harmonized_geom = trimmed
            except Exception:
                harmonized_geom = legacy_geom
        topology_inputs.append(harmonized_geom)
        prepared.append(
            {
                "parcel_id": parcel_id,
                "legacy_geom": legacy_geom,
                "harmonized_geom": harmonized_geom,
                "harmonized": harmonized,
                "props": props,
                "standardized": standardized,
                "rev": rev,
            }
        )

    # -- topology enforcement over the whole layer -----------------------
    # This is a single whole-layer pass. Running topology detection per parcel
    # was both ~300x slower and structurally blind: overlap, sliver and gap
    # defects are relations BETWEEN parcels, so a single-geometry layer can
    # never report them.
    _emit(progress, stage="topology_validate", status="running", message="Enforcing planar topology")
    topology = topology_service.repair_and_report(
        topology_inputs,
        legacy_ids,
        snap_tolerance_m=settings["snap_tolerance_m"],
        min_sliver_area_sqm=settings["min_sliver_area_sqm"],
    )
    issue_by_id = _issue_counts_by_id(topology)

    for index, item in enumerate(prepared):
        if index % 25 == 0:
            _emit(
                progress,
                stage="topology_validate",
                status="running",
                message="Scoring parcels",
                records_processed=index,
                records_total=total,
            )
        parcel_id = item["parcel_id"]
        legacy_geom = item["legacy_geom"]
        harmonized_geom = item["harmonized_geom"]
        harmonized = item["harmonized"]
        props = item["props"]
        standardized = item["standardized"]
        rev = item["rev"]
        issue_count = issue_by_id.get(parcel_id, 0)

        # -- attribute reconciliation
        # The digitised cadastre carries no owner or area attribute. The
        # MAPPED area of its repaired ring is the figure a RoR area should be
        # compared against.
        #
        # This is deliberately the legacy ring, not the harmonised outline:
        # harmonization subtracts road/drainage corridors and footprints, so its
        # area is the road-usable area and comparing a recorded parcel area
        # against it would report a large false conflict on every parcel.
        try:
            mapped_area = round(float(legacy_geom.area), 2)
        except Exception:
            mapped_area = None
        try:
            harmonized_area = round(float(harmonized_geom.area), 2)
        except Exception:
            harmonized_area = None
        attributes = attribute_service.reconcile_parcel_attributes(
            cadastral={
                **standardized,
                **props,
                "surveyed_area_sqm": props.get("legal_area_sqm") or mapped_area,
            },
            revenue=rev,
            area_tolerance_pct=settings["area_tolerance_pct"],
        )
        # Report the real distribution. Collapsing this to a match/non-match
        # binary hid the fact that the digitised cadastre carries no owner
        # attribute at all, so the owner check is legitimately MISSING for
        # every parcel rather than matching.
        attribute_status_counts[attributes["overall"]] = (
            attribute_status_counts.get(attributes["overall"], 0) + 1
        )
        if attributes["conflicting_fields"]:
            attribute_conflicts += 1
        else:
            attribute_matches += 1

        for field, check in attributes["checks"].items():
            if check["status"] == attribute_service.CONFLICT:
                record = conflict_service.from_attribute_check(parcel_id=parcel_id, check=check)
                if record:
                    record["run_id"] = None
                    conflicts.append(record)

        # -- spatial conflicts
        for corridor in corridors:
            found = conflict_service.detect_linear_encroachment(
                parcel_id=parcel_id,
                parcel_geometry=harmonized_geom,
                line_geometry=corridor["geometry"],
                line_layer=corridor["layer"],
                conflict_type=corridor["conflict_type"],
                buffer_m=corridor["buffer_m"],
                parcel_area_sqm=harmonized_geom.area,
            )
            if found:
                found["run_id"] = None
                conflicts.append(found)

        for structure in structures_by_parcel.get(parcel_id, []):
            relation = conflict_service.detect_building_relation(
                parcel_id=parcel_id,
                parcel_geometry=harmonized_geom,
                building_geometry=structure["geometry"],
                building_id=str(structure.get("id")),
            )
            if relation and relation.get("is_conflict"):
                conflicts.append(
                    {
                        "parcel_id": parcel_id,
                        "conflict_type": "building_vs_parcel",
                        "severity": "MEDIUM",
                        "source_layers": ["Building Footprints"],
                        "status": conflict_service.OPEN,
                        "detail": (
                            f"Building {structure.get('id')} crosses the parcel boundary "
                            f"({relation['building_coverage'] * 100:.0f}% inside)"
                        ),
                        "confidence": 0.8,
                        "run_id": None,
                    }
                )

        # -- boundary divergence (NOT a temporal change)
        # The divergence between the digitised ring and the harmonised outline
        # is a cross-source geometry difference, so it is recorded as a
        # conflict. It is deliberately NOT emitted as a "change": change
        # detection compares two EPOCHS of the same parcel, and this project
        # supplies only one. Recording a difference as temporal change would
        # overstate what the data can support.
        shift = conflict_service.detect_boundary_shift(
            parcel_id=parcel_id,
            legacy_geometry=legacy_geom,
            modern_geometry=harmonized_geom,
            shift_threshold_m=settings["change_shift_threshold_m"],
            area_threshold_pct=settings["change_area_threshold_pct"],
        )
        if shift:
            shift["conflict_type"] = "boundary_divergence"
            shift["severity"] = shift.get("severity") or "MEDIUM"
            shift["source_layers"] = shift.get("source_layers") or [
                "Existing Cadastral Maps",
                "GNSS / CORS Survey Data",
            ]
            shift["status"] = conflict_service.OPEN
            shift["run_id"] = None
            conflicts.append(shift)

        # -- confidence
        owner_check = attributes["checks"]["owner_name"]
        area_check = attributes["checks"]["area"]
        support = _support_for(parcel_id, survey_points, harmonized_geom)
        confidence = confidence_service.evaluate(
            iou=match_by_id.get(parcel_id, {}).get("signals", {}).get("iou"),
            boundary_similarity=match_by_id.get(parcel_id, {}).get("signals", {}).get("boundary_similarity"),
            attribute_score=_attribute_score(owner_check, area_check),
            recorded_area_sqm=rev.get("recorded_area_sqm") or rev.get("legal_area_sqm"),
            surveyed_area_sqm=mapped_area,
            area_tolerance_pct=settings["area_tolerance_pct"],
            topology_issues=issue_count,
            survey_point_distance_m=support.get("distance_m"),
        )
        confidences.append({**confidence, "parcel_id": parcel_id, "run_id": None})

        parcel_records.append(
            {
                "parcel_id": parcel_id,
                "khasra_no": standardized.get("khasra_no") or props.get("survey_no"),
                "owner_name": standardized.get("owner_name") or rev.get("owner_name"),
                "owner_name_local": standardized.get("owner_name_local") or rev.get("owner_name_local"),
                "recorded_area_sqm": rev.get("recorded_area_sqm") or rev.get("legal_area_sqm"),
                # Mapped (digitised) area, compared against the RoR figure.
                "surveyed_area_sqm": mapped_area,
                # Road-usable area after corridor/footprint subtraction. Kept
                # separate because it is a different quantity.
                "harmonized_area_sqm": harmonized_area,
                "land_use": standardized.get("land_use") or rev.get("land_use"),
                "legacy_geometry": legacy_geom,
                "harmonized_geometry": harmonized_geom,
                "harmonization": harmonized,
                "attributes": attributes,
                "match": match_by_id.get(parcel_id, {}),
                "survey_support": support,
                "confidence": confidence,
                "status": _status_for(confidence["route"], issue_count),
                "geometry_status": "VALID" if issue_count == 0 else f"{issue_count} ISSUE(S)",
            }
        )

    _emit(progress, stage="confidence_score", status="running", message="Finalising confidence scores")
    elapsed = round(time.time() - started, 3)

    return {
        "status": "COMPLETED",
        "elapsed_seconds": elapsed,
        "params": settings,
        "georeferencing": georef,
        "crs_normalization": {
            "target_crs": PROJECT_CRS,
            "layers": crs_actions,
            "reprojected": sum(1 for a in crs_actions if a["action"] == "REPROJECTED"),
        },
        "invalid_geometries_repaired": repaired_count,
        "parcels": parcel_records,
        "survey_points": survey_points,
        "topology": topology,
        "conflicts": conflicts,
        "changes": changes,
        "confidences": confidences,
        "matches": matches,
        "attribute_matches": attribute_matches,
        "attribute_conflicts": attribute_conflicts,
        "attribute_status": dict(sorted(attribute_status_counts.items())),
        "spatial_matching": {
            "candidate_source": "GNSS/ground-truth corner reconstruction",
            "candidates": len(candidates),
            "legacy_features": len(legacy_ids),
            "matched": matched_count,
            "unmatched": len(legacy_ids) - matched_count,
            "engine": matcher.describe(),
        },
        "survey_point_count": len(survey_points),
        "corridors": [{"layer": c["layer"], "conflict_type": c["conflict_type"], "buffer_m": c["buffer_m"]} for c in corridors],
    }


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def persist_run(
    repo: Repository,
    result: Dict[str, Any],
    datasets: Sequence[Dict[str, Any]],
    *,
    actor: str = "gis_analyst",
) -> str:
    """Write a completed run, its parcels, conflicts, changes, scores and lineage."""
    run_id = new_id("run")
    run_ref = f"H-{time.strftime('%Y')}-{len(repo.all('harmonization_runs')) + 1:04d}"

    conflicts = result.get("conflicts") or []
    changes = result.get("changes") or []
    confidences = result.get("confidences") or []
    scores = [c["overall"] for c in confidences]

    summary = {
        "datasets": len(datasets),
        "parcels_processed": len(result.get("parcels") or []),
        "topology_before": (result.get("topology") or {}).get("before", {}),
        "topology_after": (result.get("topology") or {}).get("after", {}),
        "attribute_matches": result.get("attribute_matches"),
        "attribute_conflicts": result.get("attribute_conflicts"),
        "conflicts_created": len(conflicts),
        "changes_detected": len(changes),
        "avg_confidence": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "routes": confidence_service.distribution(scores),
        "execution_seconds": result.get("elapsed_seconds"),
        "georeferencing": result.get("georeferencing"),
    }

    repo.put(
        "harmonization_runs",
        {
            "id": run_id,
            "run_ref": run_ref,
            "status": "COMPLETED",
            "started_at": result.get("started_at") or utc_now(),
            "finished_at": utc_now(),
            "summary_json": repositories.json_dumps(summary),
        },
    )

    for record in result.get("parcels") or []:
        parcel_ref = record["parcel_id"]
        confidence = record["confidence"]
        repo.put(
            "parcels",
            {
                # Run-scoped id: a second run must not overwrite the first
                # run's parcel row, or run history becomes unreadable.
                "id": f"parcel::{run_ref}::{parcel_ref}",
                "run_id": run_id,
                "parcel_id": parcel_ref,
                "ulpin": None,
                "status": record["status"],
                "confidence": confidence["overall"],
                "review_state": confidence["route"],
                "khasra_no": record.get("khasra_no"),
                "owner_name": record.get("owner_name"),
                "owner_name_local": record.get("owner_name_local"),
                "recorded_area_sqm": record.get("recorded_area_sqm"),
                "surveyed_area_sqm": record.get("surveyed_area_sqm"),
                "land_use": record.get("land_use"),
                "match_verdict": (record.get("match") or {}).get("verdict"),
                "match_score": (record.get("match") or {}).get("score"),
                "attribute_status": (record.get("attributes") or {}).get("overall"),
                "concerns_json": repositories.json_dumps(confidence.get("concerns") or []),
            },
        )
        audit_service.record_geometry(
            repo,
            parcel_ref=parcel_ref,
            stage="legacy",
            geojson=_to_wgs84_geojson(record["legacy_geometry"]),
            crs=PROJECT_CRS,
            area_sqm=record["harmonization"]["before"]["area_sqm"],
            valid=record["harmonization"]["before"]["valid"],
        )
        audit_service.record_geometry(
            repo,
            parcel_ref=parcel_ref,
            stage="harmonized",
            geojson=_to_wgs84_geojson(record["harmonized_geometry"]),
            crs=PROJECT_CRS,
            area_sqm=record["harmonization"]["after"]["area_sqm"],
            valid=record["harmonization"]["after"]["valid"],
        )
        # Lineage: which layer supplied which field.
        for field, value in (
            ("khasra_no", record["khasra_no"]),
            ("owner_name", record["owner_name"]),
            ("owner_name_local", record["owner_name_local"]),
            ("land_use", record["land_use"]),
        ):
            if value:
                audit_service.record_field_source(
                    repo,
                    parcel_ref=parcel_ref,
                    field=field,
                    value=value,
                    source_layer="Revenue Record (RoR)",
                    run_id=run_id,
                )
        for field in ("recorded_area_sqm", "surveyed_area_sqm"):
            layer = "Revenue Record (RoR)" if field.startswith("recorded") else "Cadastral / Survey Register"
            value = record.get(field)
            if value:
                audit_service.record_field_source(
                    repo,
                    parcel_ref=parcel_ref,
                    field=field,
                    value=value,
                    source_layer=layer,
                    run_id=run_id,
                )
        if record.get("survey_support", {}).get("point_id"):
            audit_service.record_field_source(
                repo,
                parcel_ref=parcel_ref,
                field="survey_support",
                value=record["survey_support"]["point_id"],
                source_layer="GNSS / CORS Survey Data",
                run_id=run_id,
            )
        repo.put(
            "confidence_scores",
            {
                "id": f"conf::{run_ref}::{parcel_ref}",
                "run_id": run_id,
                "parcel_ref": parcel_ref,
                "overall": confidence["overall"],
                "components_json": repositories.json_dumps(confidence["components"]),
                "evidence_json": repositories.json_dumps(
                    {"evidence": confidence["evidence"], "concerns": confidence["concerns"]}
                ),
            },
        )

    for index, conflict in enumerate(conflicts, start=1):
        repo.put(
            "conflicts",
            {
                "id": f"conf-{run_ref}-{index:04d}",
                "run_id": run_id,
                "parcel_ref": conflict.get("parcel_id"),
                "conflict_type": conflict.get("conflict_type"),
                "severity": conflict.get("severity"),
                "status": conflict.get("status", conflict_service.OPEN),
                "confidence": conflict.get("confidence"),
                "source_layers": "; ".join(conflict.get("source_layers") or []),
                "detail": conflict.get("detail"),
                "geometry_json": repositories.json_dumps(
                    conflict.get("geometry") or conflict.get("geometry_difference")
                ),
            },
        )
    for index, change in enumerate(changes, start=1):
        repo.put(
            "changes",
            {
                "id": f"chg-{run_ref}-{index:04d}",
                "run_id": run_id,
                "parcel_ref": change.get("parcel_id"),
                "change_type": change.get("change_type"),
                "confidence": change.get("confidence"),
                "status": "DETECTED",
            },
        )
    for index, observation in enumerate(_all_survey_points_for_run(result), start=1):
        repo.put(
            "survey_points",
            {
                "id": f"sv-{run_ref}-{index:06d}",
                "run_id": run_id,
                "parcel_ref": observation.get("parcel_id"),
                "point_id": observation.get("point_id"),
                "x": observation.get("x"),
                "y": observation.get("y"),
                "lat": observation.get("lat"),
                "lon": observation.get("lon"),
                "accuracy_m": observation.get("accuracy_m"),
                "method": observation.get("method"),
                "base_station": observation.get("base_station"),
                "evidence": observation.get("evidence"),
                "recorded_by": observation.get("recorded_by"),
                "observed_on": observation.get("observed_on"),
            },
        )

    audit_service.record(
        repo,
        action="harmonization_run",
        actor=actor,
        target=run_ref,
        detail=summary,
        run_id=run_id,
    )
    return run_id


def _all_survey_points_for_run(result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every observation ingested by the run, not only the one cited per parcel.

    Keeping only the nearest point per parcel would discard the rest of the
    survey evidence and make the stored evidence unreproducible.
    """
    points: List[Dict[str, Any]] = []
    for point in result.get("survey_points") or []:
        points.append(
            {
                "parcel_id": point.get("parcel_hint") or None,
                "point_id": point.get("point_id"),
                "x": point.get("x"),
                "y": point.get("y"),
                "lat": point.get("lat"),
                "lon": point.get("lon"),
                "accuracy_m": point.get("accuracy_m"),
                "method": point.get("method"),
                "base_station": point.get("base_station"),
                "evidence": point.get("evidence"),
                "recorded_by": point.get("recorded_by"),
                "observed_on": point.get("observed_on"),
            }
        )
    return points


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
_LEGACY_MAP: Dict[str, str] = {}


def _legacy_column_map(props: Dict[str, Any]) -> Dict[str, str]:
    global _LEGACY_MAP
    if not _LEGACY_MAP:
        _LEGACY_MAP = standardization_service.build_column_map(list(props.keys()))
    return _LEGACY_MAP


def align_spatial_layers(
    datasets: Sequence[Dict[str, Any]], target_crs: str = PROJECT_CRS
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """Reproject every vector dataset into ``target_crs``.

    Returns ``(frames_by_dataset_id, actions)``. ``actions`` records what
    actually happened per layer so the run can state it rather than implying
    normalisation that never occurred.
    """
    from app.services import crs_service

    frames: Dict[str, Any] = {}
    actions: List[Dict[str, Any]] = []
    for dataset in datasets:
        dataset_id = dataset.get("dataset_id")
        gdf = ingestion_service.dataset_frame(dataset_id) if dataset_id else None
        if gdf is None:
            continue
        try:
            normalized, report = crs_service.normalize_geodataframe(
                gdf, dataset.get("source_crs") or (gdf.crs and gdf.crs.to_string()), target_crs
            )
        except Exception as exc:
            actions.append(
                {
                    "dataset_id": dataset_id,
                    "name": dataset.get("name"),
                    "action": "FAILED",
                    "detail": str(exc)[:160],
                }
            )
            continue
        frames[dataset_id] = normalized
        actions.append(
            {
                "dataset_id": dataset_id,
                "name": dataset.get("name"),
                "action": "REPROJECTED" if report.get("changed") else "ALIGNED",
                "source_crs": report.get("source_crs"),
                "target_crs": report.get("target_crs") or target_crs,
                "method": report.get("method"),
                "status": report.get("status"),
            }
        )
    return frames, actions


def _issue_counts_by_id(report: Dict[str, Any]) -> Dict[str, int]:
    """Map each feature id to how many topology defects it is implicated in.

    Overlap defects are relations between two parcels, so both members of the
    pair are counted. Missing rings, slivers, disconnected parts and duplicate
    geometry implicate a single feature each.
    """
    counts: Dict[str, int] = {}

    def bump(raw: Any) -> None:
        key = raw.get("id") if isinstance(raw, dict) else raw
        if key is None:
            return
        key = str(key)
        counts[key] = counts.get(key, 0) + 1

    after = report.get("after") or report
    for section_name in ("invalid", "missing", "sliver", "disconnected", "duplicate"):
        section = after.get(section_name) or {}
        for raw in section.get("ids") or section.get("features") or []:
            bump(raw)

    overlap = after.get("overlap") or {}
    for pair in overlap.get("pairs") or []:
        bump(pair.get("a"))
        bump(pair.get("b"))
    for raw in overlap.get("ids") or []:
        bump(raw)

    gap = after.get("gap") or {}
    for raw in gap.get("parts") or []:
        bump(raw)
    return counts


def _index_rows(rows: Sequence[Dict[str, Any]], keys: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value:
                index.setdefault(str(value).strip(), row)
    return index


def _structures_by_parcel(
    building_gdf: Any, legacy_gdf: Any, parcel_geoms: Optional[Sequence[BaseGeometry]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """Assign each building footprint to the parcel that contains most of it."""
    from shapely.strtree import STRtree

    mapping: Dict[str, List[Dict[str, Any]]] = {}
    if building_gdf is None or building_gdf.empty or legacy_gdf is None:
        return mapping

    id_field = legacy_gdf.columns[0]
    all_ids = [str(v) for v in legacy_gdf[id_field].tolist()]
    geoms = list(parcel_geoms) if parcel_geoms is not None else list(legacy_gdf.geometry)

    tree = STRtree(geoms)
    for _, row in building_gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        try:
            hits = tree.query(geom)
        except Exception:
            continue
        for index in hits:
            parcel_geom = geoms[int(index)]
            try:
                if geom.intersects(parcel_geom):
                    mapping.setdefault(all_ids[int(index)], []).append(
                        {"id": str(row.get("building_id") or row.name), "geometry": geom}
                    )
                    break
            except Exception:
                continue
    return mapping


def _corridors(
    municipal: Optional[Dict[str, Any]], frames: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """Statutory exclusion zones from the municipal layer.

    A ``road_row`` feature is a POLYGON that already represents the full
    right-of-way, so it must NOT be buffered again; only linear assets
    (drainage, utility) take the configured buffer. Administrative boundaries
    are not exclusion zones and are ignored.
    """
    if municipal is None:
        return []
    dataset_id = municipal.get("dataset_id") if municipal else None
    gdf = (frames or {}).get(dataset_id)
    if gdf is None and dataset_id:
        gdf = ingestion_service.dataset_frame(dataset_id)
    if gdf is None or gdf.empty:
        return []

    corridors: List[Dict[str, Any]] = []
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        layer_name = str(row.get("layer") or row.get("name") or "").strip()
        lowered = layer_name.lower()

        if layer_name == "road_row" or "road" in lowered or "row" in lowered:
            # Already a polygon footprint of the ROW.
            buffer_m, conflict_type = 0.0, "parcel_vs_road_row"
        elif "drain" in lowered:
            buffer_m, conflict_type = float(row.get("buffer_m") or DEFAULT_PIPELINE_PARAMS["drainage_buffer_m"]), "parcel_vs_drainage"
        elif "util" in lowered or "water" in lowered or "power" in lowered:
            buffer_m, conflict_type = float(row.get("buffer_m") or DEFAULT_PIPELINE_PARAMS["utility_buffer_m"]), "parcel_vs_utility"
        else:
            continue

        corridors.append(
            {
                "layer": layer_name or row.get("name"),
                "authority": row.get("authority"),
                "geometry": geom,
                "buffer_m": buffer_m,
                "conflict_type": conflict_type,
                "geometry_kind": geom.geom_type,
            }
        )
    return corridors


def _survey_points(
    gnss: Optional[Dict[str, Any]], ground_truth: Optional[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Load GNSS and ground-truth observations into the project CRS.

    GNSS rows in the demo project already carry survey-grade eastings and
    northings, so those are used directly instead of being round-tripped through
    geographic coordinates (which would only add transformation error).
    """
    from app.services import crs_service

    points: List[Dict[str, Any]] = []
    for dataset, method in ((gnss, "GNSS/RTK"), (ground_truth, "GROUND_TRUTH")):
        if not dataset:
            continue
        rows = ingestion_service.dataset_rows(dataset["dataset_id"]) or []
        for row in rows:
            lat = row.get("lat") or row.get("latitude")
            lon = row.get("lon") or row.get("longitude") or row.get("long")
            east = row.get("easting_m") or row.get("easting")
            north = row.get("northing_m") or row.get("northing")

            if east is not None and north is not None:
                x, y = float(east), float(north)
            elif lat is not None and lon is not None:
                try:
                    transformed, _ = crs_service.transform_points(
                        [(float(lon), float(lat))], STORAGE_CRS, PROJECT_CRS
                    )
                    x, y = transformed[0]
                except Exception:
                    continue
            else:
                continue

            # Optional legacy-frame coordinates enable a genuine TPS warp.
            legacy_east = row.get("legacy_easting_m") or row.get("legacy_easting")
            legacy_north = row.get("legacy_northing_m") or row.get("legacy_northing")

            points.append(
                {
                    "point_id": str(
                        row.get("obs_id") or row.get("gt_id") or row.get("point_id") or f"{method}-{len(points)}"
                    ),
                    "parcel_hint": str(row.get("parcel_id") or row.get("parcel_ref") or ""),
                    "corner": row.get("corner"),
                    "x": x,
                    "y": y,
                    "lat": float(lat) if lat is not None else None,
                    "lon": float(lon) if lon is not None else None,
                    "accuracy_m": row.get("rms_horizontal_m") or row.get("accuracy_m") or row.get("accuracy"),
                    "method": row.get("method") or method,
                    "base_station": row.get("base_station"),
                    "cors_fixed": row.get("cors_fixed"),
                    "evidence": row.get("evidence") or row.get("condition"),
                    "recorded_by": row.get("recorded_by"),
                    "observed_on": row.get("observed_on"),
                    "legacy_x": float(legacy_east) if legacy_east is not None else None,
                    "legacy_y": float(legacy_north) if legacy_north is not None else None,
                }
            )
    return points


def _support_for(parcel_id: str, points: Sequence[Dict[str, Any]], geometry: BaseGeometry) -> Dict[str, Any]:
    if geometry is None or not points:
        return {"distance_m": None, "point_id": None, "accuracy_m": None}
    import math

    best: Optional[Any] = None
    best_distance = None
    for point in points:
        distance = math.hypot(point["x"] - geometry.centroid.x, point["y"] - geometry.centroid.y)
        if best_distance is None or distance < best_distance:
            best, best_distance = point, distance
    if best is None:
        return {"distance_m": None, "point_id": None, "accuracy_m": None}
    return {
        "distance_m": round(best_distance, 3),
        "point_id": best.get("point_id"),
        "accuracy_m": best.get("accuracy_m"),
        "method": best.get("method"),
    }


def _surveyed_candidate_geometry(
    parcel_ref: str, points: Sequence[Dict[str, Any]]
) -> Optional[BaseGeometry]:
    """Reconstruct a parcel outline from its independently surveyed corners.

    This is the real cross-source counterpart to the digitised legacy ring: the
    GNSS/GT observations are RTK-grade fixes on the same physical monument
    corners, so the outline they imply is an independent measurement rather
    than a copy of the layer being matched. Where fewer than three distinct
    corners were observed, no candidate is produced and the parcel is reported
    as unmatched instead of being scored against itself.
    """
    from shapely.geometry import Polygon

    ordered: Dict[str, Dict[str, Any]] = {}
    for point in points:
        corner = str(point.get("corner") or "").strip().upper()
        if not corner:
            continue
        previous = ordered.get(corner)
        # Prefer the most precise observation available for this corner.
        if previous is None or (point.get("accuracy_m") or 9e9) < (previous.get("accuracy_m") or 9e9):
            ordered[corner] = point

    if len(ordered) < 3:
        return None

    def _order_key(corner: str) -> Tuple[int, float]:
        digits = "".join(ch for ch in corner if ch.isdigit())
        return (int(digits) if digits else 99, corner)

    coords = [(p["x"], p["y"]) for _, p in sorted(ordered.items(), key=lambda kv: _order_key(kv[0]))]
    try:
        candidate = Polygon(coords)
    except Exception:
        return None
    if candidate.is_empty or candidate.area <= 0:
        return None
    repaired = topology_service.make_valid(candidate)
    return repaired if repaired is not None else candidate


def _surveyed_candidates(
    legacy_ids: Sequence[str], points: Sequence[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Build the modern candidate layer from survey evidence, keyed by parcel."""
    by_parcel: Dict[str, List[Dict[str, Any]]] = {}
    for point in points:
        hint = point.get("parcel_hint")
        if hint:
            by_parcel.setdefault(str(hint), []).append(point)

    candidates: List[Dict[str, Any]] = []
    for parcel_ref in legacy_ids:
        geom = _surveyed_candidate_geometry(parcel_ref, by_parcel.get(parcel_ref, []))
        if geom is not None:
            candidates.append({"id": f"survey::{parcel_ref}", "geometry": geom})
    return candidates


def _registered_tie_pairs(
    survey_points: Sequence[Dict[str, Any]], geoms: Sequence[BaseGeometry]
) -> List[Dict[str, Any]]:
    """Collect genuine legacy<->survey tie-point PAIRS for the TPS warp.

    A warp can only be fitted from points whose position is known in BOTH the
    legacy frame and the survey frame. Pairing a survey observation against a
    parcel's representative point is NOT that - it measures parcel size, not
    registration error, and produces a meaningless RMSE.

    Therefore only observations carrying explicit legacy coordinates
    (``legacy_easting_m``/``legacy_northing_m`` or ``legacy_lon``/``legacy_lat``)
    are accepted. The demo project registers every layer in a shared CRS and so
    supplies no such pairs, which correctly yields an empty list and a reported
    SKIPPED stage.
    """
    pairs: List[Dict[str, Any]] = []
    for point in survey_points:
        lx, ly = point.get("legacy_x"), point.get("legacy_y")
        if lx is None or ly is None:
            continue
        pairs.append(
            {
                "point_id": point.get("point_id"),
                "sx": float(lx),
                "sy": float(ly),
                "tx": float(point["x"]),
                "ty": float(point["y"]),
            }
        )
    return pairs


def _attribute_score(owner_check: Dict[str, Any], area_check: Dict[str, Any]) -> Optional[float]:
    scores: List[float] = []
    if owner_check.get("confidence") is not None:
        scores.append(float(owner_check["confidence"]))
    if area_check.get("status") == "MATCH":
        scores.append(1.0)
    elif area_check.get("status") == "CONFLICT" and area_check.get("difference_pct") is not None:
        scores.append(max(0.0, 1.0 - (area_check["difference_pct"] / 14.0)))
    return round(sum(scores) / len(scores), 4) if scores else None


def _status_for(route: str, issue_count: int) -> str:
    if issue_count > 0:
        return "TOPOLOGY_ISSUE"
    if route == confidence_service.AUTO_ACCEPTED:
        return "AUTO_ACCEPTED"
    if route == confidence_service.REVIEW_RECOMMENDED:
        return "REVIEW_RECOMMENDED"
    return "FIELD_VERIFICATION_REQUIRED"


def _to_wgs84_geojson(geometry: BaseGeometry) -> Optional[Dict[str, Any]]:
    """Convert a project-CRS geometry to WGS84 GeoJSON for storage and export.

    A silent ``None`` here used to strip geometry from every stored parcel,
    which made GeoPackage/Shapefile export fail with "no geometry" while the
    rest of the pipeline still reported success.
    """
    if geometry is None or geometry.is_empty:
        return None
    try:
        from shapely.geometry import mapping

        return mapping(export_service._to_wgs84_geometry(geometry))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def run_full_pipeline(
    repo: Repository,
    *,
    params: Optional[Dict[str, Any]] = None,
    actor: str = "gis_analyst",
    progress: Optional[ProgressCallback] = None,
) -> Dict[str, Any]:
    """Ingest -> validate -> normalize -> harmonize -> persist. Returns the run summary."""
    started = utc_now()
    ingestion = ingest_demo_project(repo, actor=actor, progress=progress)
    datasets = ingestion["datasets"]
    if not datasets:
        return {"status": "FAILED", "reason": "No datasets could be ingested", "stages": []}

    _emit(progress, stage="validate", status="running", message="Validating datasets")
    quality = validate_and_normalize(repo, datasets, actor=actor, progress=progress)
    blocking = [q for q in quality if q["quality_gate"]["blocking"]]
    if blocking:
        audit_service.record(
            repo,
            action="quality_gate",
            actor=actor,
            target="project",
            result="BLOCKED",
            detail={"blocked": [b["name"] for b in blocking]},
        )
        return {
            "status": "BLOCKED",
            "reason": "Data quality gate blocked harmonization",
            "blocked_datasets": [b["name"] for b in blocking],
            "quality": quality,
        }

    result = run_harmonization(repo, datasets, params=params, actor=actor, progress=progress)
    if result.get("status") != "COMPLETED":
        return result

    result["started_at"] = started
    run_id = persist_run(repo, result, datasets, actor=actor)

    topology = result.get("topology") or {}
    scores = [c["overall"] for c in result.get("confidences") or []]
    return {
        "status": "COMPLETED",
        "run_id": run_id,
        "started_at": started,
        "finished_at": utc_now(),
        "elapsed_seconds": result.get("elapsed_seconds"),
        "datasets": [
            {
                "dataset_id": d.get("dataset_id"),
                "name": d.get("name") or d.get("display_name"),
                "category": d.get("category_id"),
                "format": d.get("format"),
                "data_type": d.get("data_type"),
                "feature_count": d.get("feature_count"),
                "source_crs": d.get("source_crs"),
                "working_crs": PROJECT_CRS if d.get("data_type") == "VECTOR" else None,
            }
            for d in datasets
        ],
        "crs_normalization": result.get("crs_normalization"),
        "quality": quality,
        "parcels_processed": len(result.get("parcels") or []),
        "topology": {
            "before": topology.get("before"),
            "after": topology.get("after"),
            "by_issue": topology.get("by_issue"),
        },
        "attribute_matches": result.get("attribute_matches"),
        "attribute_conflicts": result.get("attribute_conflicts"),
        "attribute_status": result.get("attribute_status"),
        "spatial_matching": result.get("spatial_matching"),
        "invalid_geometries_repaired": result.get("invalid_geometries_repaired"),
        "conflicts": conflict_service.summarise(result.get("conflicts") or []),
        "changes": change_service.summarise(result.get("changes") or []),
        "confidence": confidence_service.distribution(scores),
        "georeferencing": result.get("georeferencing"),
        "stage_labels": PIPELINE_STAGE_LABEL,
    }
