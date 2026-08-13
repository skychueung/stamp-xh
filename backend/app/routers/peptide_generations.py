"""STAMP Platform — Peptide Generation Router (P5-lite P3).

Routes:
  POST /api/v1/peptide-generations/run     — Run targeting peptide generation + persist
  GET  /api/v1/stamp-generation-runs/{run_id}       — Get generation run by ID
  GET  /api/v1/stamp-generation-runs/{run_id}/candidates — List candidates for run
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import StampException
from app.crud.stamp_candidates import (
    get_stamp_generation_run,
    list_stamp_candidates_by_generation_run,
)
from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas import PeptideGenerationRunRequest, PeptideGenerationRunResponse
from app.services.peptide_generation_persistence import run_peptide_generation_and_persist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/peptide-generations", tags=["Peptide Generations"])
stamp_runs_router = APIRouter(
    prefix="/api/v1/stamp-generation-runs", tags=["STAMP Generation Runs"]
)


# ---------------------------------------------------------------------------
# POST /api/v1/peptide-generations/run
# ---------------------------------------------------------------------------


@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    summary="Run targeting peptide generation and persist results",
    description=(
        "Reads an epitope sequence from the database, runs the rule-based targeting "
        "peptide generator, creates a stamp_generation_runs record, persists all "
        "candidates to stamp_candidates, and returns the run results. "
        "Run status transitions: PENDING -> RUNNING -> COMPLETED/FAILED."
    ),
    response_model=PeptideGenerationRunResponse,
)
async def run_peptide_generation(
    request: Annotated[PeptideGenerationRunRequest, Body(...)],
    db: Session = Depends(get_db),
) -> PeptideGenerationRunResponse:
    """Run targeting peptide generation and persist results to the database."""
    try:
        result = run_peptide_generation_and_persist(db, request)
        return result
    except StampException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


# ---------------------------------------------------------------------------
# GET /api/v1/stamp-generation-runs/{run_id}
# ---------------------------------------------------------------------------


@stamp_runs_router.get(
    "/{run_id}",
    status_code=status.HTTP_200_OK,
    summary="Get generation run by ID",
)
async def get_generation_run(run_id: str, db: Session = Depends(get_db)) -> dict:
    """Retrieve a stamp generation run record by its ID."""
    run = get_stamp_generation_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Generation run '{run_id}' not found")
    return ApiResponse.success(
        data={
            "run_id": run.id,
            "project_id": run.project_id,
            "epitope_id": run.epitope_id,
            "status": run.status,
            "generator_name": run.generator_name,
            "generator_version": run.generator_version,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "error_message": run.error_message,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
    ).model_dump()


# ---------------------------------------------------------------------------
# GET /api/v1/stamp-generation-runs/{run_id}/candidates
# ---------------------------------------------------------------------------


@stamp_runs_router.get(
    "/{run_id}/candidates",
    status_code=status.HTTP_200_OK,
    summary="List candidates for a generation run",
)
async def get_generation_run_candidates(
    run_id: str,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve all stamp candidates associated with a generation run."""
    run = get_stamp_generation_run(db, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Generation run '{run_id}' not found")
    candidates = list_stamp_candidates_by_generation_run(db, run_id, skip=skip, limit=limit)
    return ApiResponse.success(
        data={
            "run_id": run_id,
            "count": len(candidates),
            "candidates": [
                {
                    "id": c.id,
                    "project_id": c.project_id,
                    "epitope_id": c.epitope_id,
                    "generation_run_id": c.generation_run_id,
                    "targeting_peptide_seq": c.targeting_peptide_seq,
                    "linker_seq": c.linker_seq,
                    "full_sequence": c.full_sequence,
                    "composite_score": c.composite_score,
                    "validation_status": c.validation_status,
                    "metrics": c.metrics,
                    "created_at": c.created_at.isoformat() if c.created_at else None,
                }
                for c in candidates
            ],
        }
    ).model_dump()
