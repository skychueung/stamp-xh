"""Batch Jobs Router (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.crud.compute_batches import create_batch, get_batch, list_batches_by_project
from app.crud.jobs import list_jobs_by_project
from app.database import get_db
from app.models.schemas import ApiResponse
from app.services.retry_policy import retry_job

router = APIRouter(prefix="/api/v1/batches", tags=["Batch Jobs"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new compute batch",
)
async def create_batch_endpoint(
    project_id: Annotated[str, Query(...)],
    batch_type: Annotated[str, Query(...)],
    candidate_ids: Annotated[list[str], Query(...)],
    pipeline_stages: Annotated[list[str], Query(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Create a batch of compute jobs for multiple candidates."""
    batch = create_batch(db, project_id, batch_type, candidate_ids, pipeline_stages)
    return ApiResponse.success(data={
        "batch_id": batch.id,
        "project_id": batch.project_id,
        "batch_type": batch.batch_type,
        "status": batch.status,
        "summary": batch.summary_json,
    })


@router.get(
    "/{batch_id}",
    summary="Get batch details",
)
async def get_batch_endpoint(
    batch_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Get batch details including summary."""
    batch = get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")
    # Fetch related jobs
    db.query(list_jobs_by_project).filter_by(batch_id=batch_id).all() if hasattr(list_jobs_by_project, 'filter') else []
    return ApiResponse.success(data={
        "batch_id": batch.id,
        "project_id": batch.project_id,
        "batch_type": batch.batch_type,
        "status": batch.status,
        "candidate_ids": batch.candidate_ids,
        "pipeline_stages": batch.pipeline_stages,
        "summary": batch.summary_json,
        "created_at": batch.created_at.isoformat() if batch.created_at else None,
        "completed_at": batch.completed_at.isoformat() if batch.completed_at else None,
    })


@router.get(
    "",
    summary="List batches for a project",
)
async def list_batches_endpoint(
    project_id: Annotated[str, Query(...)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """List all compute batches for a project."""
    batches = list_batches_by_project(db, project_id, limit=limit)
    return ApiResponse.success(data=[
        {
            "batch_id": b.id,
            "batch_type": b.batch_type,
            "status": b.status,
            "summary": b.summary_json,
            "created_at": b.created_at.isoformat() if b.created_at else None,
        }
        for b in batches
    ])


@router.post(
    "/{batch_id}/retry-failed",
    summary="Retry all failed jobs in a batch",
)
async def retry_failed_in_batch_endpoint(
    batch_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Retry all FAILED jobs within a batch that have retry_count < max_retries."""
    batch = get_batch(db, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Batch not found")

    from app.models.orm import Job
    failed_jobs = db.query(Job).filter(
        Job.batch_id == batch_id,
        Job.status == "FAILED",
        Job.retry_count < Job.max_retries,
    ).all()

    new_job_ids = []
    for job in failed_jobs:
        new_job = retry_job(db, job.id)
        if new_job:
            new_job_ids.append(new_job.id)

    return ApiResponse.success(data={
        "batch_id": batch_id,
        "failed_count": len(failed_jobs),
        "retried_count": len(new_job_ids),
        "new_job_ids": new_job_ids,
    })
