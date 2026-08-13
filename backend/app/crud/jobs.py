"""STAMP Platform — CRUD: Job System (v0.9-P6)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import Job, Project
from app.schemas import JobCreate, JobUpdate


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def create_job(db: Session, obj_in: JobCreate) -> Job:
    """Create a job while preserving the project foreign-key invariant."""
    project = db.query(Project).filter(Project.id == obj_in.project_id).first()
    if project is None:
        db.add(
            Project(
                id=obj_in.project_id,
                name=f"System job project {obj_in.project_id}"[:255],
                description="Created for a legacy model-queue submission.",
            )
        )
        db.flush()
    db_obj = Job(
        project_id=obj_in.project_id,
        job_type=obj_in.job_type,
        status="pending",
        progress=0,
        input_json=obj_in.input_json or {},
    )
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------


def get_job(db: Session, job_id: str) -> Optional[Job]:
    """Get a single job by ID."""
    return db.query(Job).filter(Job.id == job_id).first()


def list_jobs_by_project(
    db: Session,
    project_id: str,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> List[Job]:
    """List jobs for a project with optional filters."""
    query = db.query(Job).filter(Job.project_id == project_id)
    if status:
        query = query.filter(Job.status == status)
    if job_type:
        query = query.filter(Job.job_type == job_type)
    return (
        query.order_by(Job.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def count_jobs_by_project(
    db: Session,
    project_id: str,
    status: Optional[str] = None,
    job_type: Optional[str] = None,
) -> int:
    """Count jobs for a project with optional filters."""
    query = db.query(Job).filter(Job.project_id == project_id)
    if status:
        query = query.filter(Job.status == status)
    if job_type:
        query = query.filter(Job.job_type == job_type)
    return query.count()


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def update_job(db: Session, db_obj: Job, obj_in: JobUpdate) -> Job:
    """Update a job record."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def update_job_status(
    db: Session,
    job_id: str,
    status: str,
    progress: Optional[int] = None,
    message: Optional[str] = None,
    error_message: Optional[str] = None,
    output_json: Optional[dict] = None,
) -> Optional[Job]:
    """Atomic status update for a job."""
    db_obj = get_job(db, job_id)
    if db_obj is None:
        return None
    db_obj.status = status
    if progress is not None:
        db_obj.progress = progress
    if message is not None:
        db_obj.message = message
    if error_message is not None:
        db_obj.error_message = error_message
    if output_json is not None:
        db_obj.output_json = output_json
    if status == "running" and db_obj.started_at is None:
        db_obj.started_at = _utc_now()
    if status in ("succeeded", "failed", "cancelled"):
        db_obj.finished_at = _utc_now()
    db.commit()
    db.refresh(db_obj)
    return db_obj


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


def delete_job(db: Session, job_id: str) -> bool:
    """Delete a job by ID. Returns True if deleted."""
    db_obj = get_job(db, job_id)
    if db_obj is None:
        return False
    db.delete(db_obj)
    db.commit()
    return True
