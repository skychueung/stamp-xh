"""STAMP Platform — CRUD: stamp_candidates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import StampCandidate, StampGenerationRun
from app.schemas import (
    StampCandidateCreate,
    StampCandidateUpdate,
    StampGenerationRunCreate,
    StampGenerationRunUpdate,
)


# --- STAMP Generation Runs ---


def create_stamp_generation_run(
    db: Session, obj_in: StampGenerationRunCreate
) -> StampGenerationRun:
    db_obj = StampGenerationRun(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_stamp_generation_run(db: Session, run_id: str) -> Optional[StampGenerationRun]:
    return db.query(StampGenerationRun).filter(StampGenerationRun.id == run_id).first()


def update_stamp_generation_run(
    db: Session, obj: StampGenerationRun, obj_in: StampGenerationRunUpdate
) -> StampGenerationRun:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


# --- STAMP Generation Run Status Management (P5-lite P3) ---


def update_stamp_generation_run_status(
    db: Session, run_id: str, status: str, error_message: Optional[str] = None
) -> Optional[StampGenerationRun]:
    """Generic status update with optional error message.

    Automatically manages started_at for RUNNING and finished_at for
    COMPLETED/FAILED.
    """
    run = db.query(StampGenerationRun).filter(StampGenerationRun.id == run_id).first()
    if not run:
        return None
    run.status = status
    now = datetime.now(timezone.utc)
    if status == "RUNNING":
        run.started_at = now
    elif status in ("COMPLETED", "FAILED"):
        run.finished_at = now
    if error_message is not None:
        run.error_message = error_message
    db.commit()
    db.refresh(run)
    return run


def mark_stamp_generation_run_running(db: Session, run_id: str) -> Optional[StampGenerationRun]:
    """Mark generation run as RUNNING and set started_at."""
    run = db.query(StampGenerationRun).filter(StampGenerationRun.id == run_id).first()
    if not run:
        return None
    run.status = "RUNNING"
    run.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def mark_stamp_generation_run_completed(db: Session, run_id: str) -> Optional[StampGenerationRun]:
    """Mark generation run as COMPLETED and set finished_at."""
    run = db.query(StampGenerationRun).filter(StampGenerationRun.id == run_id).first()
    if not run:
        return None
    run.status = "COMPLETED"
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def mark_stamp_generation_run_failed(
    db: Session, run_id: str, error_message: str
) -> Optional[StampGenerationRun]:
    """Mark generation run as FAILED, set finished_at and error_message."""
    run = db.query(StampGenerationRun).filter(StampGenerationRun.id == run_id).first()
    if not run:
        return None
    run.status = "FAILED"
    run.finished_at = datetime.now(timezone.utc)
    run.error_message = error_message
    db.commit()
    db.refresh(run)
    return run


# --- STAMP Candidates ---


def create_stamp_candidate(
    db: Session, obj_in: StampCandidateCreate
) -> StampCandidate:
    db_obj = StampCandidate(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def create_stamp_candidates_bulk(
    db: Session, objs_in: List[StampCandidateCreate]
) -> List[StampCandidate]:
    """Bulk create stamp candidates."""
    db_objs = [StampCandidate(**o.model_dump()) for o in objs_in]
    db.add_all(db_objs)
    db.commit()
    for o in db_objs:
        db.refresh(o)
    return db_objs


def get_stamp_candidate(db: Session, candidate_id: str) -> Optional[StampCandidate]:
    return db.query(StampCandidate).filter(StampCandidate.id == candidate_id).first()


def list_stamp_candidates_by_project(
    db: Session, project_id: str, *, skip: int = 0, limit: int = 100
) -> List[StampCandidate]:
    return (
        db.query(StampCandidate)
        .filter(StampCandidate.project_id == project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def list_stamp_candidates_by_generation_run(
    db: Session, generation_run_id: str, *, skip: int = 0, limit: int = 500
) -> List[StampCandidate]:
    """List stamp candidates by generation run ID."""
    return (
        db.query(StampCandidate)
        .filter(StampCandidate.generation_run_id == generation_run_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_stamp_candidate(
    db: Session, obj: StampCandidate, obj_in: StampCandidateUpdate
) -> StampCandidate:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def update_stamp_candidates_bulk(
    db: Session,
    updates: List[tuple[StampCandidate, StampCandidateUpdate]],
) -> List[StampCandidate]:
    """Bulk update stamp candidates.

    Args:
        db: SQLAlchemy session.
        updates: List of (candidate_obj, update_obj) tuples.

    Returns:
        List of updated StampCandidate objects.
    """
    updated = []
    for obj, obj_in in updates:
        update_data = obj_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(obj, field, value)
        updated.append(obj)
    if updated:
        db.commit()
        for obj in updated:
            db.refresh(obj)
    return updated
