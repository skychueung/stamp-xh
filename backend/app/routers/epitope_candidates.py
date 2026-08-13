"""STAMP Platform — Epitope Candidate Router (P5-lite P2 patch).

Routes:
  GET /api/v1/epitope-candidates/{candidate_id}  -- Get single epitope candidate
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud.epitopes import get_epitope_candidate
from app.database import get_db
from app.models.schemas import ApiResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/epitope-candidates", tags=["Epitope Candidates"])


@router.get(
    "/{candidate_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a single epitope candidate by ID",
    description="Retrieve an epitope candidate record by its ID. No experimental data is fabricated.",
)
async def get_epitope_candidate_by_id(
    candidate_id: Annotated[str, ...],
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve a single epitope candidate by ID."""
    candidate = get_epitope_candidate(db, candidate_id)
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Epitope candidate '{candidate_id}' not found",
        )
    return ApiResponse.success(
        data={
            "id": candidate.id,
            "scan_id": candidate.scan_id,
            "start": candidate.start,
            "end": candidate.end,
            "sequence": candidate.sequence,
            "net_charge": candidate.net_charge,
            "hydrophobicity": candidate.hydrophobicity,
            "pi": candidate.pi,
            "cys_count": candidate.cys_count,
            "surface_exposure_score": candidate.surface_exposure_score,
            "ranking_score": candidate.ranking_score,
            "filter_status": candidate.filter_status,
            "metrics": candidate.metrics,
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
            "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
        }
    ).model_dump()
