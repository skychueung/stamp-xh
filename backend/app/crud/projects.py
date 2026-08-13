"""STAMP Platform — CRUD: projects."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import Project
from app.schemas import ProjectCreate, ProjectUpdate


def create_project(db: Session, obj_in: ProjectCreate) -> Project:
    """Create a new project."""
    db_obj = Project(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_project(db: Session, project_id: str) -> Optional[Project]:
    """Get a single project by UUID."""
    return db.query(Project).filter(Project.id == project_id).first()


def list_projects(db: Session, *, skip: int = 0, limit: int = 100) -> List[Project]:
    """List projects with pagination."""
    return db.query(Project).offset(skip).limit(limit).all()


def update_project(
    db: Session, project: Project, obj_in: ProjectUpdate
) -> Project:
    """Patch a project (partial update)."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return project


def delete_project(db: Session, project_id: str) -> Optional[Project]:
    """Delete a project (cascades to children via ORM)."""
    obj = get_project(db, project_id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj
