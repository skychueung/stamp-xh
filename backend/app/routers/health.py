"""
STAMP Platform — Health Check Router (v1.2-lab-production-fast)

Provides liveness/readiness endpoints plus DB, storage, and queue checks
for server deployment monitoring.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter, status
from sqlalchemy import text

from app.core.config import settings
from app.database import SessionLocal
from app.models.schemas import ApiResponse
from app.services.resource_probe import probe_resources
from app.utils.response import ok

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Health / liveness check",
)
async def health_check() -> ApiResponse[dict]:
    """Basic liveness check."""
    return ok(
        data={
            "status": "healthy",
            "service": "stamp-backend",
            "version": settings.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        message="STAMP backend is healthy",
    )


@router.get(
    "/health/db",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Database health check",
)
async def health_db() -> ApiResponse[dict]:
    """Verify SQLite database connectivity."""
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return ok(
            data={"status": "healthy", "database": "sqlite", "reachable": True},
            message="Database is reachable",
        )
    except Exception as exc:
        return ok(
            data={"status": "unhealthy", "database": "sqlite", "reachable": False, "error": str(exc)},
            message=f"Database check failed: {exc}",
        )


@router.get(
    "/health/storage",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Storage health check",
)
async def health_storage() -> ApiResponse[dict]:
    """Verify critical storage directories exist and are writable."""
    dirs = ["data/uploads", "data/jobs", "data/results", "data/archive"]
    checks = {}
    all_ok = True
    for d in dirs:
        path = os.path.abspath(d)
        exists = os.path.isdir(path)
        writable = os.access(path, os.W_OK) if exists else False
        checks[d] = {"exists": exists, "writable": writable}
        if not (exists and writable):
            all_ok = False
    return ok(
        data={"status": "healthy" if all_ok else "degraded", "checks": checks},
        message="Storage is healthy" if all_ok else "Some storage paths missing or not writable",
    )


@router.get(
    "/health/queue",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Job queue health check",
)
async def health_queue() -> ApiResponse[dict]:
    """Check job queue status by counting jobs in each state."""
    try:
        from app.crud.jobs import list_jobs_by_project
        from app.database import SessionLocal

        db = SessionLocal()
        # Simple count query across all jobs
        from sqlalchemy import func
        from app.models.orm import Job

        counts = {
            "pending": db.query(Job).filter(Job.status == "PENDING").count(),
            "running": db.query(Job).filter(Job.status == "RUNNING").count(),
            "succeeded": db.query(Job).filter(Job.status == "SUCCEEDED").count(),
            "failed": db.query(Job).filter(Job.status == "FAILED").count(),
            "blocked": db.query(Job).filter(Job.status == "BLOCKED").count(),
        }
        db.close()
        total = sum(counts.values())
        return ok(
            data={"status": "healthy", "total_jobs": total, "breakdown": counts},
            message=f"Queue healthy — {total} jobs tracked",
        )
    except Exception as exc:
        return ok(
            data={"status": "unhealthy", "error": str(exc)},
            message=f"Queue check failed: {exc}",
        )


@router.get(
    "/health/resources",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Server resource status (GPU/CPU/RAM/Disk)",
)
async def health_resources() -> ApiResponse[dict]:
    """Return GPU/CPU/RAM/Disk status plus GPU lock state.

    If resources are insufficient, ``data.status`` is ``"blocked"``
    and ``data.blocked_reasons`` lists why.
    """
    data = probe_resources()
    status_str = data.get("status", "unknown")
    message = (
        "Resources healthy"
        if status_str == "healthy"
        else f"Resources blocked: {', '.join(data.get('blocked_reasons') or [])}"
    )
    return ok(data=data, message=message)
