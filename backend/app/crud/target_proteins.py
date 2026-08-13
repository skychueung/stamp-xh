"""STAMP Platform — CRUD: target_proteins."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import TargetProtein
from app.schemas import TargetProteinCreate, TargetProteinUpdate


def create_target_protein(
    db: Session, obj_in: TargetProteinCreate
) -> TargetProtein:
    db_obj = TargetProtein(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_target_protein(db: Session, tp_id: str) -> Optional[TargetProtein]:
    return db.query(TargetProtein).filter(TargetProtein.id == tp_id).first()


def list_target_proteins_by_project(
    db: Session, project_id: str, *, skip: int = 0, limit: int = 100
) -> List[TargetProtein]:
    return (
        db.query(TargetProtein)
        .filter(TargetProtein.project_id == project_id)
        .offset(skip)
        .limit(limit)
        .all()
    )


def update_target_protein(
    db: Session, obj: TargetProtein, obj_in: TargetProteinUpdate
) -> TargetProtein:
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj
