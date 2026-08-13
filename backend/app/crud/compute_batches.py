"""CRUD for ComputeBatch (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import ComputeBatch


def create_batch(db: Session, project_id: str, batch_type: str, candidate_ids: list[str],
                 pipeline_stages: list[str]) -> ComputeBatch:
    batch = ComputeBatch(
        project_id=project_id,
        batch_type=batch_type,
        candidate_ids=candidate_ids,
        pipeline_stages=pipeline_stages,
        status="PENDING",
        summary_json={"total": len(candidate_ids), "succeeded": 0, "failed": 0, "running": 0},
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def get_batch(db: Session, batch_id: str) -> Optional[ComputeBatch]:
    return db.query(ComputeBatch).filter(ComputeBatch.id == batch_id).first()


def list_batches_by_project(db: Session, project_id: str, limit: int = 100) -> list[ComputeBatch]:
    return db.query(ComputeBatch).filter(ComputeBatch.project_id == project_id).order_by(
        ComputeBatch.created_at.desc()
    ).limit(limit).all()


def update_batch_status(db: Session, batch_id: str, status: str, summary_json: Optional[dict] = None) -> Optional[ComputeBatch]:
    batch = get_batch(db, batch_id)
    if batch is None:
        return None
    batch.status = status
    if summary_json is not None:
        batch.summary_json = summary_json
    db.commit()
    db.refresh(batch)
    return batch
