"""CRUD for BatchComputation and BatchComputationItem (v1.4-batch-computation)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import BatchComputation, BatchComputationItem


def create_batch_computation(
    db: Session,
    *,
    project_id: str,
    name: str,
    job_type: str,
    input_json: dict,
    artifact_dir: str,
    created_by: Optional[str] = None,
) -> BatchComputation:
    batch = BatchComputation(
        project_id=project_id,
        name=name,
        job_type=job_type,
        input_json=input_json,
        artifact_dir=artifact_dir,
        created_by=created_by,
        status="PENDING",
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch_computation(db: Session, batch_id: str) -> Optional[BatchComputation]:
    return db.query(BatchComputation).filter(BatchComputation.id == batch_id).first()


def list_batch_computations(
    db: Session,
    project_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[BatchComputation], int]:
    query = db.query(BatchComputation)
    if project_id:
        query = query.filter(BatchComputation.project_id == project_id)
    if status:
        query = query.filter(BatchComputation.status == status)
    total = query.count()
    results = query.order_by(BatchComputation.created_at.desc()).offset(offset).limit(limit).all()
    return results, total


def update_batch_computation_status(
    db: Session,
    batch: BatchComputation,
    status: str,
    summary_json: Optional[dict] = None,
) -> BatchComputation:
    batch.status = status
    if status == "RUNNING" and batch.started_at is None:
        batch.started_at = datetime.now(timezone.utc)
    if status in ("SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"):
        batch.finished_at = datetime.now(timezone.utc)
    if summary_json is not None:
        batch.summary_json = summary_json
    db.commit()
    db.refresh(batch)
    return batch


def cancel_batch_computation(db: Session, batch: BatchComputation) -> BatchComputation:
    batch.status = "CANCELLED"
    batch.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(batch)
    # Also cancel pending items
    items = db.query(BatchComputationItem).filter(
        BatchComputationItem.batch_id == batch.id,
        BatchComputationItem.status.in_(["PENDING", "RUNNING"]),
    ).all()
    for item in items:
        item.status = "CANCELLED"
        item.finished_at = datetime.now(timezone.utc)
    db.commit()
    return batch


# ---------------------------------------------------------------------------
# Item CRUD
# ---------------------------------------------------------------------------

def create_batch_item(
    db: Session,
    *,
    batch_id: str,
    project_id: str,
    candidate_id: Optional[str],
    job_type: str,
    input_json: dict,
    artifact_dir: str,
) -> BatchComputationItem:
    item = BatchComputationItem(
        batch_id=batch_id,
        project_id=project_id,
        candidate_id=candidate_id,
        job_type=job_type,
        input_json=input_json,
        artifact_dir=artifact_dir,
        status="PENDING",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_batch_item(db: Session, item_id: str) -> Optional[BatchComputationItem]:
    return db.query(BatchComputationItem).filter(BatchComputationItem.id == item_id).first()


def list_batch_items(db: Session, batch_id: str) -> list[BatchComputationItem]:
    return (
        db.query(BatchComputationItem)
        .filter(BatchComputationItem.batch_id == batch_id)
        .order_by(BatchComputationItem.created_at.asc())
        .all()
    )


def update_batch_item_status(
    db: Session,
    item: BatchComputationItem,
    status: str,
    output_json: Optional[dict] = None,
    error_message: Optional[str] = None,
) -> BatchComputationItem:
    item.status = status
    if status == "RUNNING" and item.started_at is None:
        item.started_at = datetime.now(timezone.utc)
    if status in ("SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED"):
        item.finished_at = datetime.now(timezone.utc)
    if output_json is not None:
        item.output_json = output_json
    if error_message is not None:
        item.error_message = error_message
    db.commit()
    db.refresh(item)
    return item
