"""
STAMP Platform — Minimal Projects API (P5-lite)

Provides basic CRUD endpoints for the projects table.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.projects import create_project, delete_project, get_project, list_projects
from app.schemas import ProjectCreate, ProjectResponse, ProjectUpdate
from app.core.limiter import limiter
from app.core.security import require_active, validate_csrf
from app.models.user import User

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _owned_project(db: Session, project_id: str, user: User):
    project = get_project(db, project_id)
    if project is None or (user.role != "admin" and project.owner_id != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _csrf(request: Request) -> None:
    validate_csrf(request)


# ---------------------------------------------------------------------------
# POST /api/v1/projects
# ---------------------------------------------------------------------------

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_new_project(
    request: Request,
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Create a new STAMP project."""
    return create_project(db, project_in, owner_id=user.id)


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    """List all projects with pagination."""
    return list_projects(db, skip=skip, limit=limit, owner_id=None if user.role == "admin" else user.id)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    """Get a single project by UUID."""
    return _owned_project(db, project_id, user)


# ---------------------------------------------------------------------------
# PATCH /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.patch("/{project_id}", response_model=ProjectResponse)
@limiter.limit("20/minute")
def update_project_endpoint(
    request: Request,
    project_id: str,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Partially update a project."""
    from app.crud.projects import update_project

    project = _owned_project(db, project_id, user)
    return update_project(db, project, project_in)


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
def delete_project_endpoint(
    request: Request,
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Delete a project (cascades to children)."""
    _owned_project(db, project_id, user)
    delete_project(db, project_id)
    return None
