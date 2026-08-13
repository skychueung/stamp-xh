"""EvoBind2 Compute Router — Job Queue Skeleton (v0.3-p3c-artifacts).

Provides job submit, status query, artifacts listing, download, and cancel endpoints.
All real compute is BLOCKED in this skeleton phase.

This router is registered in main.py and can be gated by
compute_endpoints_enabled().  The dry-run router (evobind2.py) is kept
separate so that dry-run remains available even when compute endpoints
are disabled.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.public_safety import compute_endpoints_enabled
from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas.evobind2 import (
    EvoBind2JobArtifactItem,
    EvoBind2JobArtifactsResponse,
    EvoBind2JobCancelResponse,
    EvoBind2JobResponse,
    EvoBind2JobSubmitRequest,
)
from app.services.evobind2_job_service import (
    cancel_evobind2_job,
    get_evobind2_job,
    get_evobind2_job_artifacts,
    get_evobind2_job_safety_flags,
    resolve_evobind2_artifact_path,
    submit_evobind2_job,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency: compute endpoints must be enabled
# ---------------------------------------------------------------------------


async def _require_compute_enabled() -> None:
    """Raise 403 if compute endpoints are disabled (public demo mode)."""
    if not compute_endpoints_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "EvoBind2 compute endpoints are disabled by the public-demo safety defaults. "
                "Set PUBLIC_DEMO_MODE=false and ENABLE_COMPUTE_ENDPOINTS=true "
                "only in a trusted local deployment."
            ),
        )


router = APIRouter(
    prefix="/api/v1/evobind2",
    tags=["EvoBind2 Compute"],
    dependencies=[Depends(_require_compute_enabled)],
)


# ---------------------------------------------------------------------------
# POST /api/v1/evobind2/jobs
# ---------------------------------------------------------------------------


@router.post(
    "/jobs",
    status_code=status.HTTP_201_CREATED,
    summary="Submit an EvoBind2 job",
    response_model=ApiResponse[EvoBind2JobResponse],
)
async def submit_evobind2_job_endpoint(
    request: Annotated[EvoBind2JobSubmitRequest, ...],
    db: Session = Depends(get_db),
) -> ApiResponse[EvoBind2JobResponse]:
    """Submit a new EvoBind2 predict-only job.

    The job is immediately blocked in this skeleton phase.
    No real model execution, no GPU allocation, and no candidate generation.
    """
    try:
        job = submit_evobind2_job(db, request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    safety_flags = get_evobind2_job_safety_flags(job)

    return ApiResponse.success(
        data=EvoBind2JobResponse(
            job_id=job.id,
            project_id=job.project_id,
            status=job.status,
            job_type=job.job_type,
            model_name=(job.input_json or {}).get("model_name", "model_1_ptm"),
            mode=(job.input_json or {}).get("mode", "predict_only"),
            safety_flags=safety_flags,
            message=job.message,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ),
        message="EvoBind2 job submitted and blocked in skeleton phase",
    )


# ---------------------------------------------------------------------------
# GET /api/v1/evobind2/jobs/{job_id}
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Get an EvoBind2 job by ID",
    response_model=ApiResponse[EvoBind2JobResponse],
)
async def get_evobind2_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[EvoBind2JobResponse]:
    """Retrieve the status and metadata of an EvoBind2 job."""
    job = get_evobind2_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvoBind2 job '{job_id}' not found",
        )

    safety_flags = get_evobind2_job_safety_flags(job)

    return ApiResponse.success(
        data=EvoBind2JobResponse(
            job_id=job.id,
            project_id=job.project_id,
            status=job.status,
            job_type=job.job_type,
            model_name=(job.input_json or {}).get("model_name", "model_1_ptm"),
            mode=(job.input_json or {}).get("mode", "predict_only"),
            safety_flags=safety_flags,
            message=job.message,
            error_message=job.error_message,
            created_at=job.created_at,
            updated_at=job.updated_at,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/evobind2/jobs/{job_id}/artifacts
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}/artifacts",
    status_code=status.HTTP_200_OK,
    summary="List artifacts for an EvoBind2 job",
    response_model=ApiResponse[EvoBind2JobArtifactsResponse],
)
async def get_evobind2_job_artifacts_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[EvoBind2JobArtifactsResponse]:
    """List artifact metadata for a job, verifying existence on disk.

    Only returns metadata for files that actually exist.  Server absolute
    paths are never exposed; each artifact carries an internal relative path
    and a hardened download URL.
    """
    job = get_evobind2_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvoBind2 job '{job_id}' not found",
        )

    artifact_dicts = get_evobind2_job_artifacts(db, job_id)
    artifacts = [
        EvoBind2JobArtifactItem(
            name=a["name"],
            path=a["path"],
            artifact_type=a.get("artifact_type", "other"),
            exists=a["exists"],
            size_bytes=a["size_bytes"],
            download_url=f"/api/v1/evobind2/jobs/{job_id}/artifacts/{a['name']}/download",
        )
        for a in artifact_dicts
    ]

    return ApiResponse.success(
        data=EvoBind2JobArtifactsResponse(
            job_id=job_id,
            status=job.status,
            artifacts=artifacts,
        ),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/evobind2/jobs/{job_id}/artifacts/{artifact_name}/download
# ---------------------------------------------------------------------------


@router.get(
    "/jobs/{job_id}/artifacts/{artifact_name}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a single EvoBind2 artifact",
    response_class=FileResponse,
)
async def download_evobind2_artifact_endpoint(
    job_id: Annotated[str, Path(...)],
    artifact_name: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> FileResponse:
    """Download a single artifact file for a job.

    The artifact name is mapped to a well-known relative path under the job's
    run directory.  Path traversal attempts are rejected, and files outside the
    EvoBind2 artifact root can never be served.
    """
    job = get_evobind2_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvoBind2 job '{job_id}' not found",
        )

    artifact_path = resolve_evobind2_artifact_path(job, artifact_name)
    if artifact_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_name}' not found for job '{job_id}'",
        )

    if not artifact_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_name}' exists in manifest but file is missing on disk",
        )

    return FileResponse(
        path=str(artifact_path),
        filename=artifact_path.name,
        media_type="application/octet-stream",
    )


# ---------------------------------------------------------------------------
# POST /api/v1/evobind2/jobs/{job_id}/cancel
# ---------------------------------------------------------------------------


@router.post(
    "/jobs/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel an EvoBind2 job",
    response_model=ApiResponse[EvoBind2JobCancelResponse],
)
async def cancel_evobind2_job_endpoint(
    job_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[EvoBind2JobCancelResponse]:
    """Cancel a pending, running, or blocked EvoBind2 job.

    Rules:
      - pending / running / blocked -> cancelled
      - cancelled                   -> idempotent
      - succeeded / failed          -> no state change
    """
    job = get_evobind2_job(db, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvoBind2 job '{job_id}' not found",
        )

    previous_status = job.status
    updated = cancel_evobind2_job(db, job_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cancel operation failed",
        )

    return ApiResponse.success(
        data=EvoBind2JobCancelResponse(
            job_id=updated.id,
            previous_status=previous_status,
            status=updated.status,
            message=updated.message or "Job cancelled",
        ),
    )
