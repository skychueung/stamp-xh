"""STAMP Platform — Job System Router (v0.9-P6).

Background job lifecycle endpoints.
All mock outputs are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.crud.jobs import (
    count_jobs_by_project,
    create_job,
    get_job,
    list_jobs_by_project,
)
from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas import (
    BepiPred3PersistResponse,
    EnergyQualityPersistResponse,
    InterfaceQualityPersistResponse,
    JobCancelResponse,
    JobCreate,
    JobFailureDiagnosis,
    JobListResponse,
    JobResponse,
    JobRetryResponse,
    JobRunMockRequest,
    JobRunMockResponse,
    JobStartResponse,
    StructurePredictionPersistResponse,
)
from app.schemas.pepmlm import PepMLMPersistResponse
from app.services.job_service import cancel_job, retry_job, run_mock_job, run_real_job, start_job_async

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


# ---------------------------------------------------------------------------
# POST /api/v1/jobs
# ---------------------------------------------------------------------------


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new background job",
    response_model=ApiResponse[JobResponse],
)
async def create_job_endpoint(
    request: Annotated[JobCreate, ...],
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """Create a new background computation job."""
    job = create_job(db, request)
    return ApiResponse.success(data=JobResponse.model_validate(job))


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a job by ID",
    response_model=ApiResponse[JobResponse],
)
async def get_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """Retrieve a single job by its ID."""
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return ApiResponse.success(data=JobResponse.model_validate(job))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/jobs
# ---------------------------------------------------------------------------


@router.get(
    "/by-project/{project_id}",
    status_code=status.HTTP_200_OK,
    summary="List jobs for a project",
    response_model=ApiResponse[JobListResponse],
)
async def list_jobs_by_project_endpoint(
    project_id: Annotated[str, Path(...)],
    status_filter: Optional[str] = Query(default=None, alias="status"),
    job_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ApiResponse[JobListResponse]:
    """List all background jobs for a given project."""
    jobs = list_jobs_by_project(
        db,
        project_id=project_id,
        status=status_filter,
        job_type=job_type,
        limit=limit,
        offset=offset,
    )
    total = count_jobs_by_project(
        db, project_id=project_id, status=status_filter, job_type=job_type
    )
    return ApiResponse.success(
        data=JobListResponse(
            project_id=project_id,
            total_count=total,
            jobs=[JobResponse.model_validate(j) for j in jobs],
        )
    )


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/run-mock
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/run-mock",
    status_code=status.HTTP_200_OK,
    summary="Run a mock job execution (for testing)",
    response_model=ApiResponse[JobRunMockResponse],
)
async def run_mock_job_endpoint(
    job_id: Annotated[str, Path(...)],
    request: Annotated[JobRunMockRequest, ...],
    db: Session = Depends(get_db),
) -> ApiResponse[JobRunMockResponse]:
    """Execute a mock run of the job for testing the lifecycle.

    This does NOT run any real ML model or structural prediction.
    Output is explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    updated = run_mock_job(
        db,
        job_id=job_id,
        sleep_seconds=request.sleep_seconds,
        should_fail=request.should_fail,
        fail_message=request.fail_message or "Mock failure for testing.",
    )
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mock run failed unexpectedly",
        )

    return ApiResponse.success(
        data=JobRunMockResponse(
            job_id=updated.id,
            status=updated.status,
            message=updated.message or "Mock run completed",
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
        )
    )


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/start
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a real job execution asynchronously",
    response_model=ApiResponse[JobStartResponse],
)
async def start_job_endpoint(
    job_id: Annotated[str, Path(...)],
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> ApiResponse[JobStartResponse]:
    """Enqueue a real job for asynchronous background execution.

    Returns immediately with status=running (or current terminal status).
    The actual BepiPred3/sidecar work runs in a background thread.
    Poll GET /api/v1/jobs/{job_id} to track progress.

    Rules:
      - pending  → accepted, background task enqueued
      - running  → accepted, no duplicate start
      - succeeded → accepted, return as-is
      - failed / cancelled → accepted, return as-is (no auto-restart)
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    updated = start_job_async(db, job_id=job_id, background_tasks=background_tasks)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start job asynchronously",
        )

    return ApiResponse.success(
        data=JobStartResponse(
            job_id=updated.id,
            status=updated.status,
            progress=updated.progress or 0,
            message=updated.message or "Job accepted",
        )
    )


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/run
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/run",
    status_code=status.HTTP_200_OK,
    summary="Run a real P5-lite job execution (synchronous)",
    response_model=ApiResponse[JobResponse],
)
async def run_real_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[JobResponse]:
    """Execute a real P5-lite workflow job SYNCHRONOUSLY.

    This blocks the HTTP request until the job completes.
    For long-running jobs (e.g. BepiPred3 CPU inference), use
    POST /api/v1/jobs/{job_id}/start instead.

    Dispatches to the appropriate persistence service based on job_type.
    Output is explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    # Terminal-state guard: cannot re-run failed/cancelled jobs
    if job.status in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' is in terminal state '{job.status}' and cannot be re-run",
        )

    # Idempotent: already succeeded → return as-is
    if job.status == "succeeded":
        return ApiResponse.success(data=JobResponse.model_validate(job))

    updated = run_real_job(db, job_id=job_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Real run failed unexpectedly",
        )

    return ApiResponse.success(data=JobResponse.model_validate(updated))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel a pending or running job",
    response_model=ApiResponse[JobCancelResponse],
)
async def cancel_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[JobCancelResponse]:
    """Cancel a job.

    Rules:
      - pending / running → cancelled
      - cancelled         → idempotent, return as-is
      - succeeded         → 400 Bad Request (cannot cancel succeeded job)
      - failed            → 400 Bad Request (cannot cancel failed job)
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    if job.status == "succeeded":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' has already succeeded and cannot be cancelled",
        )

    if job.status == "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' has already failed; use retry instead",
        )

    previous_status = job.status
    updated = cancel_job(db, job_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cancel operation failed",
        )

    return ApiResponse.success(
        data=JobCancelResponse(
            job_id=updated.id,
            previous_status=previous_status,
            status=updated.status,
            message=updated.message or "Job cancelled",
        )
    )


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/retry
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/retry",
    status_code=status.HTTP_201_CREATED,
    summary="Retry a failed or cancelled job",
    response_model=ApiResponse[JobRetryResponse],
)
async def retry_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[JobRetryResponse]:
    """Create a new pending job by copying a failed or cancelled job.

    The original job is preserved for audit history.
    """
    job = get_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    if job.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job '{job_id}' is {job.status} and cannot be retried",
        )

    new_job = retry_job(db, job_id=job_id)
    if new_job is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Retry operation failed",
        )

    return ApiResponse.success(
        data=JobRetryResponse(
            original_job_id=job.id,
            new_job_id=new_job.id,
            status=new_job.status,
            message="Retry job created",
        )
    )


# ---------------------------------------------------------------------------
# GET /api/v1/jobs/{job_id}/diagnosis
# ---------------------------------------------------------------------------


@router.get(
    "/{job_id}/diagnosis",
    status_code=status.HTTP_200_OK,
    summary="Get failure diagnosis for a job",
    response_model=ApiResponse[JobFailureDiagnosis],
)
async def get_job_diagnosis_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[JobFailureDiagnosis]:
    """Return a structured failure diagnosis for a job.

    Works for any job status, but is most useful for failed, blocked,
    or cancelled jobs. Parses error_message and error_json to infer
    the root cause and suggests actionable fixes.
    """
    from app.services.failure_diagnosis_service import diagnose_job_by_id

    diagnosis = diagnose_job_by_id(db, job_id)
    if diagnosis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )
    return ApiResponse.success(data=JobFailureDiagnosis.model_validate(diagnosis))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/persist-bepipred3-results
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/persist-bepipred3-results",
    status_code=status.HTTP_200_OK,
    summary="Persist BepiPred3 job results to epitope candidates",
    response_model=ApiResponse[BepiPred3PersistResponse],
)
async def persist_bepipred3_results_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[BepiPred3PersistResponse]:
    """Persist a succeeded bepipred3_scan job into epitope_scans + epitope_candidates.

    Creates one epitope_scan record and zero or more epitope_candidate records
    from the job's output_json. Empty ranked peptide lists are handled gracefully
    (scan created, no candidates, candidate_count = 0).

    All results remain NOT_EXPERIMENTALLY_VALIDATED.
    """
    from app.services.bepipred3_persistence import persist_bepipred3_results

    try:
        result = persist_bepipred3_results(db, job_id)
    except ValueError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ApiResponse.success(data=BepiPred3PersistResponse.model_validate(result))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/persist-pepmlm-results
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/persist-pepmlm-results",
    status_code=status.HTTP_200_OK,
    summary="Persist PepMLM job results to stamp generation runs and candidates",
    response_model=ApiResponse[PepMLMPersistResponse],
)
async def persist_pepmlm_results_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[PepMLMPersistResponse]:
    """Persist a succeeded pepmlm_generation job into stamp_generation_runs + stamp_candidates.

    Creates one stamp_generation_runs record and zero or more stamp_candidates
    from the job's output_json. All results remain NOT_EXPERIMENTALLY_VALIDATED.
    """
    from app.services.pepmlm_persistence import persist_pepmlm_results

    try:
        result = persist_pepmlm_results(db, job_id)
    except ValueError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ApiResponse.success(data=PepMLMPersistResponse.model_validate(result))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/persist-structure-prediction-results
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/persist-structure-prediction-results",
    status_code=status.HTTP_200_OK,
    summary="Persist structure prediction job results to stamp candidate metrics",
    response_model=ApiResponse[StructurePredictionPersistResponse],
)
async def persist_structure_prediction_results_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[StructurePredictionPersistResponse]:
    """Persist a succeeded structure_prediction job into stamp_candidate.metrics.

    Writes structure_prediction metrics (pLDDT, pTM, PAE, etc.) to
    stamp_candidate.metrics['structure_prediction'] without overwriting
    other metric keys. All results remain NOT_EXPERIMENTALLY_VALIDATED.
    """
    from app.services.structure_prediction_persistence import (
        persist_structure_prediction_to_candidate,
    )

    try:
        result = persist_structure_prediction_to_candidate(db, job_id)
    except ValueError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ApiResponse.success(data=StructurePredictionPersistResponse.model_validate(result))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/persist-interface-quality-results
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/persist-interface-quality-results",
    status_code=status.HTTP_200_OK,
    summary="Persist interface quality (pDockQ) results to stamp candidate metrics",
    response_model=ApiResponse[InterfaceQualityPersistResponse],
)
async def persist_interface_quality_results_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[InterfaceQualityPersistResponse]:
    """Persist a succeeded complex_structure_prediction job's interface quality to candidate metrics.

    Runs P6i interface parser + P6j pDockQ calculator and writes the result to
    stamp_candidate.metrics['interface_quality'] without overwriting other keys.
    """
    from app.services.interface_quality_persistence import (
        persist_interface_quality_to_candidate,
    )

    try:
        result = persist_interface_quality_to_candidate(db, job_id)
    except ValueError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ApiResponse.success(data=InterfaceQualityPersistResponse.model_validate(result))


# ---------------------------------------------------------------------------
# POST /api/v1/jobs/{job_id}/persist-energy-quality-results
# ---------------------------------------------------------------------------


@router.post(
    "/{job_id}/persist-energy-quality-results",
    status_code=status.HTTP_200_OK,
    summary="Persist energy quality (FoldX interaction energy) results to stamp candidate metrics",
    response_model=ApiResponse[EnergyQualityPersistResponse],
)
async def persist_energy_quality_results_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[EnergyQualityPersistResponse]:
    """Persist a succeeded job's FoldX energy quality to candidate metrics.

    Runs P6m FoldX output parser and writes the result to
    stamp_candidate.metrics['energy_quality'] without overwriting other keys.
    """
    from app.services.energy_quality_persistence import (
        EnergyQualityError,
        persist_energy_quality_to_candidate,
    )

    try:
        result = persist_energy_quality_to_candidate(db, job_id)
    except EnergyQualityError as exc:
        error_msg = str(exc).lower()
        if "not found" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return ApiResponse.success(data=EnergyQualityPersistResponse.model_validate(result))
