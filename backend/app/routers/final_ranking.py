"""
STAMP Platform — Final Ranking Router (v0.7-P1e)

POST /api/v1/final-ranking/compute — heuristic composite ranking.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, status

from app.models.final_ranking import FinalRankingComputeRequest
from app.services.final_ranking import compute_final_ranking

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/final-ranking", tags=["Final Ranking"])


@router.post(
    "/compute",
    status_code=status.HTTP_200_OK,
    summary="Compute heuristic composite ranking for STAMP candidates",
    description=(
        "Accepts a list of STAMP candidates (sequence-derived properties only) "
        "and returns them ranked by a heuristic composite score. "
        "No ML predictions, no structural metrics, no experimental data. "
        "All results are marked NOT_EXPERIMENTALLY_VALIDATED."
    ),
)
async def final_ranking_compute_endpoint(
    request: Annotated[FinalRankingComputeRequest, Body(...)],
) -> dict:
    result = compute_final_ranking([c.model_dump() for c in request.candidates])
    return result
