"""Production MD router.

v1.2-lab-production-fast — P7 Production MD task templates.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm import Job
from app.services.production_md_service import (
    create_production_md_job,
    submit_production_md_to_server,
    VALID_DURATIONS_NS,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/production-md", tags=["Production MD"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ProductionMDCreateRequest(BaseModel):
    project_id: str
    candidate_id: str
    duration_ns: int = Field(..., description="Production run length in nanoseconds")
    topology_path: str = Field(..., description="Path to topology file (.tpr or .top)")
    coordinates_path: str = Field(..., description="Path to coordinate/restart file (.gro or .cpt)")
    previous_md_job_id: Optional[str] = Field(None)
    server_host: Optional[str] = Field(None)
    priority: int = Field(default=0)

    @field_validator("duration_ns")
    @classmethod
    def validate_duration(cls, v: int) -> int:
        if v not in VALID_DURATIONS_NS:
            raise ValueError(f"duration_ns must be one of {sorted(VALID_DURATIONS_NS)}")
        return v


class ProductionMDResponse(BaseModel):
    job_id: str
    status: str
    duration_ns: int
    candidate_id: str
    project_id: str
    created_at: str


class ProductionMDSubmitResponse(BaseModel):
    status: str
    detail: str
    job_id: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/jobs", response_model=ProductionMDResponse, status_code=201)
def create_production_md(
    body: ProductionMDCreateRequest,
    db: Session = Depends(get_db),
):
    """Create a production MD job (PENDING)."""
    try:
        job = create_production_md_job(
            db,
            project_id=body.project_id,
            candidate_id=body.candidate_id,
            duration_ns=body.duration_ns,
            topology_path=body.topology_path,
            coordinates_path=body.coordinates_path,
            previous_md_job_id=body.previous_md_job_id,
            server_host=body.server_host,
            priority=body.priority,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return {
        "job_id": job.id,
        "status": job.status,
        "duration_ns": body.duration_ns,
        "candidate_id": job.candidate_id,
        "project_id": job.project_id,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.post("/jobs/{job_id}/submit", response_model=ProductionMDSubmitResponse)
def submit_production_md(
    job_id: str,
    db: Session = Depends(get_db),
):
    """Submit an existing production MD job to the compute server.

    If the server is unreachable, the job is marked BLOCKED with a retryable error.
    """
    from app.crud.jobs import get_job

    job = get_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.job_type != "production_md":
        raise HTTPException(status_code=422, detail="Job is not a production_md job")

    result = submit_production_md_to_server(db, job)
    return {
        "status": result["status"],
        "detail": result["detail"],
        "job_id": job_id,
    }


@router.get("/durations")
def list_supported_durations():
    """Return supported production MD durations and their step counts."""
    return {
        "durations_ns": sorted(VALID_DURATIONS_NS),
        "details": [
            {"duration_ns": d, "nsteps": d * 500_000, "timestep_ps": 0.002}
            for d in sorted(VALID_DURATIONS_NS)
        ],
    }
