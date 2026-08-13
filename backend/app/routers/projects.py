"""
STAMP Platform — Minimal Projects API (P5-lite)

Provides basic CRUD endpoints for the projects table.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.projects import create_project, delete_project, get_project, list_projects
from app.schemas import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ---------------------------------------------------------------------------
# POST /api/v1/projects
# ---------------------------------------------------------------------------

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_new_project(
    project_in: ProjectCreate,
    db: Session = Depends(get_db),
):
    """Create a new STAMP project."""
    return create_project(db, project_in)


# ---------------------------------------------------------------------------
# GET /api/v1/projects
# ---------------------------------------------------------------------------

@router.get("", response_model=List[ProjectResponse])
def read_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all projects with pagination."""
    return list_projects(db, skip=skip, limit=limit)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.get("/{project_id}", response_model=ProjectResponse)
def read_project(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Get a single project by UUID."""
    project = get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return project


# ---------------------------------------------------------------------------
# PATCH /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project_endpoint(
    project_id: str,
    project_in: ProjectUpdate,
    db: Session = Depends(get_db),
):
    """Partially update a project."""
    from app.crud.projects import update_project

    project = get_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return update_project(db, project, project_in)


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{project_id}
# ---------------------------------------------------------------------------

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_endpoint(
    project_id: str,
    db: Session = Depends(get_db),
):
    """Delete a project (cascades to children)."""
    project = delete_project(db, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found.",
        )
    return None
