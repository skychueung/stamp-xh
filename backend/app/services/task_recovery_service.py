"""Task Recovery Service (v1.5 Wave 3).

Scans for BLOCKED or FAILED jobs and attempts recovery based on error type.

Recovery rules:
- SERVER_UNREACHABLE: retry up to 3 times with exponential backoff
- WRAPPER_NOT_READY: do not retry (requires code change)
- GPU_LOCK_FAILED: retry after GPU lock is released
- ENV_MISSING: retry after environment is fixed

Scientific boundary: never fabricate results on recovery.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import Job
from app.services.production_md_service import submit_production_md_to_server

logger = logging.getLogger("stamp")

MAX_RETRIES = 3
RETRY_BACKOFF_MINUTES = [5, 15, 60]

RECOVERABLE_ERRORS = {
    "SERVER_UNREACHABLE",
    "GPU_LOCK_FAILED",
    "ENV_MISSING",
    "CONDA_ENV_NOT_FOUND",
    "TIMEOUT",
}

NON_RECOVERABLE_ERRORS = {
    "WRAPPER_NOT_READY",
    "INVALID_INPUT",
    "PARSE_ERROR",
    "SCIENTIFIC_BOUNDARY_VIOLATION",
}


def _is_recoverable(error_code: str | None) -> bool:
    if not error_code:
        return True  # Unknown errors are tentatively recoverable
    return error_code in RECOVERABLE_ERRORS


def _next_retry_at(attempt: int) -> datetime:
    minutes = RETRY_BACKOFF_MINUTES[min(attempt, len(RETRY_BACKOFF_MINUTES) - 1)]
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def attempt_job_recovery(db: Session, job: Job) -> dict:
    """Attempt to recover a single BLOCKED or FAILED job.

    Returns:
        Dict with ``status`` (RECOVERED / DEFERRED / GIVEN_UP) and ``detail``.
    """
    if job.status not in ("BLOCKED", "FAILED"):
        return {"status": "SKIPPED", "detail": f"Job status is {job.status}, not recoverable."}

    error_code = None
    error_json = job.error_json or {}
    if isinstance(error_json, dict):
        error_code = error_json.get("error_code")

    if not _is_recoverable(error_code):
        return {
            "status": "GIVEN_UP",
            "detail": f"Error code {error_code} is non-recoverable.",
        }

    retry_count = (job.error_json or {}).get("retry_count", 0) if isinstance(job.error_json, dict) else 0
    if retry_count >= MAX_RETRIES:
        return {
            "status": "GIVEN_UP",
            "detail": f"Max retries ({MAX_RETRIES}) exceeded.",
        }

    if job.job_type == "production_md":
        result = submit_production_md_to_server(db, job)
        if result.get("status") == "SUBMITTED":
            # Update retry count
            new_error_json = dict(error_json) if isinstance(error_json, dict) else {}
            new_error_json["retry_count"] = retry_count + 1
            new_error_json["last_retry_at"] = datetime.now(timezone.utc).isoformat()
            job.error_json = new_error_json
            db.commit()
            return {"status": "RECOVERED", "detail": f"Resubmitted to server (retry {retry_count + 1}/{MAX_RETRIES})."}
        else:
            # Still blocked — schedule next retry
            new_error_json = dict(error_json) if isinstance(error_json, dict) else {}
            new_error_json["retry_count"] = retry_count + 1
            new_error_json["next_retry_at"] = _next_retry_at(retry_count).isoformat()
            job.error_json = new_error_json
            db.commit()
            return {
                "status": "DEFERRED",
                "detail": f"Still blocked. Next retry at {new_error_json['next_retry_at']}.",
            }

    return {"status": "SKIPPED", "detail": f"Recovery not implemented for job type {job.job_type}."}


def scan_and_recover_jobs(db: Session, job_type: Optional[str] = None) -> list[dict]:
    """Scan for recoverable jobs and attempt recovery.

    Args:
        db: Database session.
        job_type: Optional filter by job type (e.g., "production_md").

    Returns:
        List of recovery result dicts.
    """
    query = db.query(Job).filter(Job.status.in_(["BLOCKED", "FAILED"]))
    if job_type:
        query = query.filter(Job.job_type == job_type)

    jobs = query.all()
    results = []
    for job in jobs:
        result = attempt_job_recovery(db, job)
        results.append({
            "job_id": job.id,
            "job_type": job.job_type,
            "status": job.status,
            "recovery_status": result["status"],
            "detail": result["detail"],
        })
    return results
