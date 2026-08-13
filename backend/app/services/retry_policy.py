"""Retry policy engine for compute jobs (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.crud.jobs import get_job, update_job_status
from app.models.orm import Job
from app.services.audit_log_service import log_job_retry


RETRYABLE_ERRORS = {
    "ENV_MISSING",
    "COMPUTE_TIMEOUT",
    "DISK_FULL",
    "SERVER_UNREACHABLE",
    "UNKNOWN_ERROR",
}

NON_RETRYABLE_ERRORS = {
    "INPUT_INVALID",
    "CONVERGENCE_FAILED",
}


def should_retry(job: Job) -> bool:
    """Determine if a failed job should be retried."""
    if job.status != "FAILED":
        return False
    if job.retry_count >= job.max_retries:
        return False
    error_code = (job.error_json or {}).get("error_code", "UNKNOWN_ERROR")
    return error_code in RETRYABLE_ERRORS


def retry_job(db: Session, job_id: str, submitted_by: Optional[str] = None) -> Optional[Job]:
    """Clone a failed job as a new PENDING job and increment retry count on original."""
    original = get_job(db, job_id)
    if original is None:
        return None
    if not should_retry(original):
        return None

    # Create new job with same payload
    from app.crud.jobs import create_job
    from app.schemas import JobCreate

    new_job = create_job(
        db,
        JobCreate(
            project_id=original.project_id,
            job_type=original.job_type,
            input_json=original.input_json,
        ),
    )
    # Copy v1.2 fields
    new_job.candidate_id = original.candidate_id
    new_job.batch_id = original.batch_id
    new_job.server_host = original.server_host
    new_job.priority = original.priority
    new_job.max_retries = original.max_retries
    new_job.retry_count = 0
    db.commit()
    db.refresh(new_job)

    # Mark original as retried
    original.retry_count = (original.retry_count or 0) + 1
    db.commit()
    db.refresh(original)

    log_job_retry(db, original_id=original.id, new_id=new_job.id, submitted_by=submitted_by)
    return new_job
