"""STAMP Platform — CRUD: epitopes (scans + candidates)."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import EpitopeCandidate, EpitopeScan
from app.schemas import (
    EpitopeCandidateCreate,
    EpitopeCandidateUpdate,
    EpitopeScanCreate,
    EpitopeScanUpdate,
)


# --- Epitope Scans ---


def create_epitope_scan(db: Session, obj_in: EpitopeScanCreate) -> EpitopeScan:
    db_obj = EpitopeScan(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_epitope_scan(db: Session, scan_id: str) -> Optional[EpitopeScan]:
    return db.query(EpitopeScan).filter(EpitopeScan.id == scan_id).first()


def update_epitope_scan(
    db: Session, obj: EpitopeScan, obj_in: EpitopeScanUpdate
) -> EpitopeScan:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


# --- Epitope Candidates ---


def create_epitope_candidate(
    db: Session, obj_in: EpitopeCandidateCreate
) -> EpitopeCandidate:
    db_obj = EpitopeCandidate(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def create_epitope_candidates_bulk(
    db: Session, objs_in: List[EpitopeCandidateCreate]
) -> List[EpitopeCandidate]:
    db_objs = [EpitopeCandidate(**o.model_dump()) for o in objs_in]
    db.add_all(db_objs)
    db.commit()
    for o in db_objs:
        db.refresh(o)
    return db_objs


def get_epitope_candidate(db: Session, candidate_id: str) -> Optional[EpitopeCandidate]:
    return db.query(EpitopeCandidate).filter(EpitopeCandidate.id == candidate_id).first()


def list_epitope_candidates_by_scan(
    db: Session, scan_id: str, *, skip: int = 0, limit: int = 500
) -> List[EpitopeCandidate]:
    return (
        db.query(EpitopeCandidate)
        .filter(EpitopeCandidate.scan_id == scan_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_epitope_candidate(
    db: Session, obj: EpitopeCandidate, obj_in: EpitopeCandidateUpdate
) -> EpitopeCandidate:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


# --- Epitope Scan Status Management (P5-lite P2) ---


def mark_epitope_scan_running(db: Session, scan_id: str) -> Optional[EpitopeScan]:
    """Mark scan as RUNNING and set started_at."""
    from datetime import datetime, timezone
    scan = db.query(EpitopeScan).filter(EpitopeScan.id == scan_id).first()
    if not scan:
        return None
    scan.status = "RUNNING"
    scan.started_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan)
    return scan


def mark_epitope_scan_completed(db: Session, scan_id: str) -> Optional[EpitopeScan]:
    """Mark scan as COMPLETED and set finished_at."""
    from datetime import datetime, timezone
    scan = db.query(EpitopeScan).filter(EpitopeScan.id == scan_id).first()
    if not scan:
        return None
    scan.status = "COMPLETED"
    scan.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan)
    return scan


def mark_epitope_scan_failed(
    db: Session, scan_id: str, error_message: str
) -> Optional[EpitopeScan]:
    """Mark scan as FAILED, set finished_at and error_message."""
    from datetime import datetime, timezone
    scan = db.query(EpitopeScan).filter(EpitopeScan.id == scan_id).first()
    if not scan:
        return None
    scan.status = "FAILED"
    scan.finished_at = datetime.now(timezone.utc)
    scan.error_message = error_message
    db.commit()
    db.refresh(scan)
    return scan


def update_epitope_scan_status(
    db: Session, scan_id: str, status: str, error_message: Optional[str] = None
) -> Optional[EpitopeScan]:
    """Generic status update with optional error message.

    Automatically manages started_at for RUNNING and finished_at for
    COMPLETED/FAILED.
    """
    from datetime import datetime, timezone
    scan = db.query(EpitopeScan).filter(EpitopeScan.id == scan_id).first()
    if not scan:
        return None
    scan.status = status
    now = datetime.now(timezone.utc)
    if status == "RUNNING":
        scan.started_at = now
    elif status in ("COMPLETED", "FAILED"):
        scan.finished_at = now
    if error_message is not None:
        scan.error_message = error_message
    db.commit()
    db.refresh(scan)
    return scan
