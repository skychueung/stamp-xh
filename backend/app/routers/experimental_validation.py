"""STAMP Platform — Experimental Validation Router (v0.11-P1).

REST endpoints for wet-lab validation runs, measurements, and candidate priority.
"""

from __future__ import annotations

import io
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, Response, UploadFile, status
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas.experimental_validation import (
    CandidateExperimentalPriorityResponse,
    CandidatePrioritizationItem,
    CsvImportError,
    CsvImportResultResponse,
    ExperimentalMeasurementCreate,
    ExperimentalMeasurementResponse,
    ExperimentalValidationRunCreate,
    ExperimentalValidationRunResponse,
    ExperimentalValidationRunUpdate,
    ExperimentalValidationSummaryResponse,
    PriorityDecisionCreate,
    PriorityDecisionResponse,
    ProjectCandidatePrioritizationResponse,
    ProjectExperimentalValidationSummaryResponse,
    WetlabValidationReportResponse,
)
from app.services.candidate_prioritization_service import (
    build_project_candidate_prioritization,
    save_candidate_priority_decision,
)
from app.services.wetlab_report_export import (
    build_wetlab_validation_report_data,
    render_wetlab_report_csv,
    render_wetlab_report_markdown,
    render_wetlab_report_pdf,
    render_wetlab_report_xlsx,
    validate_wetlab_report_integrity,
)
from app.services.experimental_validation_service import (
    add_experimental_measurement,
    compute_candidate_priority,
    create_experimental_validation_run,
    get_project_experimental_validation_summary,
    import_measurements_csv,
    update_run_status,
)

router = APIRouter(prefix="/api/v1/experimental-validation", tags=["experimental-validation"])


# ---------------------------------------------------------------------------
# Validation Runs
# ---------------------------------------------------------------------------

@router.post(
    "/runs",
    response_model=ApiResponse[ExperimentalValidationRunResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create an experimental validation run",
)
def create_run(
    payload: ExperimentalValidationRunCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Create a new experimental validation run for a candidate.

    Defaults to status=PLANNED and validation_status=EXPERIMENT_PLANNED.
    """
    run = create_experimental_validation_run(db, payload)
    return ApiResponse.success(
        data=ExperimentalValidationRunResponse.model_validate(run),
        message="Validation run created",
    ).model_dump()


@router.get(
    "/runs/{run_id}",
    response_model=ApiResponse[ExperimentalValidationRunResponse],
    summary="Get a validation run",
)
def get_run(
    run_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Get a validation run by ID."""
    from app.crud.experimental_validation import get_validation_run

    run = get_validation_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")
    return ApiResponse.success(
        data=ExperimentalValidationRunResponse.model_validate(run)
    ).model_dump()


@router.patch(
    "/runs/{run_id}/status",
    response_model=ApiResponse[ExperimentalValidationRunResponse],
    summary="Update run execution status",
)
def patch_run_status(
    run_id: Annotated[str, Path(...)],
    status_value: Annotated[str, Query(..., alias="status")],
    notes: Optional[str] = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    """Update the execution status of a validation run (e.g., COMPLETED, FAILED).

    Triggers re-evaluation of the candidate's validation_status.
    """
    run = update_run_status(db, run_id, status_value, notes)
    return ApiResponse.success(
        data=ExperimentalValidationRunResponse.model_validate(run),
        message="Run status updated",
    ).model_dump()


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

@router.post(
    "/runs/{run_id}/measurements",
    response_model=ApiResponse[ExperimentalMeasurementResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Add a measurement to a run",
)
def create_measurement(
    run_id: Annotated[str, Path(...)],
    payload: ExperimentalMeasurementCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Add an experimental measurement to a validation run.

    Triggers re-evaluation of the candidate's validation_status.
    """
    measurement = add_experimental_measurement(db, run_id, payload)
    return ApiResponse.success(
        data=ExperimentalMeasurementResponse.model_validate(measurement),
        message="Measurement added",
    ).model_dump()


@router.get(
    "/runs/{run_id}/measurements",
    response_model=ApiResponse[list[ExperimentalMeasurementResponse]],
    summary="List measurements for a run",
)
def list_measurements(
    run_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """List all measurements for a validation run."""
    from app.crud.experimental_validation import (
        get_validation_run,
        list_measurements_by_run,
    )

    run = get_validation_run(db, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found")

    measurements = list_measurements_by_run(db, run_id)
    return ApiResponse.success(
        data=[ExperimentalMeasurementResponse.model_validate(m) for m in measurements]
    ).model_dump()


# ---------------------------------------------------------------------------
# Candidate-level
# ---------------------------------------------------------------------------

@router.get(
    "/candidates/{candidate_id}/validation",
    response_model=ApiResponse[ExperimentalValidationSummaryResponse],
    summary="Get candidate experimental validation summary",
)
def get_candidate_validation(
    candidate_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Get experimental validation summary for a candidate."""
    from app.crud.experimental_validation import (
        list_measurements_by_candidate,
        list_validation_runs_by_candidate,
        summarize_candidate_experimental_validation,
    )

    summary = summarize_candidate_experimental_validation(db, candidate_id)
    measurements = list_measurements_by_candidate(db, candidate_id)

    return ApiResponse.success(
        data=ExperimentalValidationSummaryResponse(
            candidate_id=candidate_id,
            overall_validation_status=summary["overall_validation_status"],
            run_count=summary["run_count"],
            completed_run_count=summary["completed_run_count"],
            measurements=[
                ExperimentalMeasurementResponse.model_validate(m)
                for m in measurements
            ],
        )
    ).model_dump()


@router.get(
    "/candidates/{candidate_id}/priority",
    response_model=ApiResponse[CandidateExperimentalPriorityResponse],
    summary="Get candidate experimental priority score",
)
def get_candidate_priority(
    candidate_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Compute experimental priority score for a candidate."""
    try:
        result = compute_candidate_priority(db, candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse.success(data=result).model_dump()


# ---------------------------------------------------------------------------
# Project-level
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/summary",
    response_model=ApiResponse[ProjectExperimentalValidationSummaryResponse],
    summary="Get project experimental validation summary",
)
def get_project_summary(
    project_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Get project-level experimental validation summary."""
    from app.crud.projects import get_project

    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    summary = get_project_experimental_validation_summary(db, project_id)
    return ApiResponse.success(
        data=ProjectExperimentalValidationSummaryResponse(**summary)
    ).model_dump()


@router.post(
    "/projects/{project_id}/import-measurements-csv",
    response_model=ApiResponse[CsvImportResultResponse],
    summary="Import measurements from CSV",
)
async def import_csv_measurements(
    project_id: Annotated[str, Path(...)],
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Import experimental measurements from a CSV file.

    CSV columns: candidate_id,experiment_type,organism,strain,protocol_name,
    experiment_date,metric_name,value,unit,replicate_id,quality_flag,
    condition_json,notes
    """
    from app.crud.projects import get_project

    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    content = await file.read()
    result = import_measurements_csv(db, project_id, content)
    return ApiResponse.success(
        data=CsvImportResultResponse(**result)
    ).model_dump()



# ---------------------------------------------------------------------------
# v0.11-P4: Candidate Prioritization
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/candidate-prioritization",
    response_model=ApiResponse[ProjectCandidatePrioritizationResponse],
    summary="Get project candidate prioritization",
)
def get_project_candidate_prioritization(
    project_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Get full prioritization data for all candidates in a project.

    Combines computational metrics, experimental measurements, and manual
    review decisions into a decision-support view.
    """
    from app.crud.projects import get_project

    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result = build_project_candidate_prioritization(db, project_id)
    return ApiResponse.success(
        data=ProjectCandidatePrioritizationResponse(**result)
    ).model_dump()


@router.post(
    "/candidates/{candidate_id}/priority-decision",
    response_model=ApiResponse[PriorityDecisionResponse],
    summary="Save a manual priority decision",
)
def save_priority_decision(
    candidate_id: Annotated[str, Path(...)],
    payload: PriorityDecisionCreate,
    db: Session = Depends(get_db),
) -> dict:
    """Save a manual review decision for a candidate.

    Does NOT modify composite_score or validation_status.
    Decision is stored in candidate.metrics['priority_decision'].
    """
    try:
        result = save_candidate_priority_decision(db, candidate_id, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return ApiResponse.success(
        data=PriorityDecisionResponse(**result)
    ).model_dump()


# ---------------------------------------------------------------------------
# v0.11-P5: Wet-lab Validation Report Export
# ---------------------------------------------------------------------------

@router.get(
    "/projects/{project_id}/wetlab-validation-report",
    summary="Export wet-lab validation report",
)
def get_wetlab_validation_report(
    project_id: Annotated[str, Path(...)],
    format: Annotated[str, Query(...)] = "json",
    top_k: Annotated[int, Query(..., ge=1, le=1000)] = 50,
    db: Session = Depends(get_db),
):
    """Export a project-level wet-lab validation report.

    Formats: json, markdown/md, csv, xlsx, pdf.
    """
    from app.crud.projects import get_project

    project = get_project(db, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    fmt = format.lower()
    if fmt == "md":
        fmt = "markdown"
    valid_formats = {"json", "markdown", "csv", "xlsx", "pdf"}
    if fmt not in valid_formats:
        raise HTTPException(
            status_code=400,
            detail=f"format must be one of {sorted(valid_formats)}",
        )

    report_data = build_wetlab_validation_report_data(db, project_id, top_k=top_k)

    # Run integrity checks
    integrity_errors = validate_wetlab_report_integrity(report_data)
    if integrity_errors:
        raise HTTPException(
            status_code=500,
            detail=f"Report integrity check failed: {integrity_errors[0]}",
        )

    if fmt == "json":
        return ApiResponse.success(
            data=WetlabValidationReportResponse(**report_data)
        ).model_dump()

    if fmt == "markdown":
        markdown = render_wetlab_report_markdown(report_data)
        return PlainTextResponse(
            content=markdown,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="wetlab_validation_report_{project_id}.md"'},
        )

    if fmt == "csv":
        csv_content = render_wetlab_report_csv(report_data)
        return PlainTextResponse(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="wetlab_validation_report_{project_id}.csv"'},
        )

    if fmt == "xlsx":
        xlsx_bytes = render_wetlab_report_xlsx(report_data)
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="wetlab_validation_report_{project_id}.xlsx"'},
        )

    if fmt == "pdf":
        pdf_bytes = render_wetlab_report_pdf(report_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="wetlab_validation_report_{project_id}.pdf"'},
        )

    # Fallback (should never reach here due to validation above)
    raise HTTPException(status_code=400, detail="Unsupported format")
