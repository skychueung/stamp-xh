"""
STAMP Platform — PepMLM Candidate Router

Endpoints for listing and retrieving PepMLM-generated targeting
peptide candidates.  Supports pagination and ``filter_status`` filtering.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.core.exceptions import CandidateNotFoundError
from app.data.loader import get_pepmlm_candidates
from app.models.schemas import (
    ApiResponse,
    FilterStatus,
    PaginatedResponse,
    PepMLMCandidate,
    PepMLMCandidateListItem,
)
from app.utils.response import ok, paginated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/pepmlm", tags=["PepMLM Candidates"])


def _paginate(
    items: list[Any],
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    """Slice *items* for the requested page.

    Returns:
        Tuple of (sliced items, total count).
    """
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


@router.get(
    "/candidates",
    response_model=ApiResponse[PaginatedResponse[PepMLMCandidateListItem]],
    status_code=status.HTTP_200_OK,
    summary="List PepMLM targeting peptide candidates",
    description="Retrieve all PepMLM-generated candidates with optional "
                "pagination and ``filter_status`` filtering.",
)
async def list_pepmlm_candidates(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    filter_status: Annotated[FilterStatus | None, Query()] = None,
) -> ApiResponse[PaginatedResponse[PepMLMCandidateListItem]]:
    """List PepMLM candidates.

    Args:
        page: 1-based page number.
        page_size: Items per page (max 200).
        filter_status: Optional status filter (Pass / Fail / Warning).

    Returns:
        Paginated list of trimmed candidate items.
    """
    raw = get_pepmlm_candidates()

    # Apply filter if requested
    if filter_status is not None:
        raw = [r for r in raw if r.get("filter_status") == filter_status.value]

    items_raw, total = _paginate(raw, page, page_size)

    items = [
        PepMLMCandidateListItem(
            candidate_id=r["candidate_id"],
            target_name=r["target_name"],
            peptide_length=r["peptide_length"],
            generated_peptide=r["generated_peptide"],
            ppl_score=r["ppl_score"],
            filter_status=FilterStatus(r.get("filter_status", "Pass")),
        )
        for r in items_raw
    ]

    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/candidates/{candidate_id}",
    response_model=ApiResponse[PepMLMCandidate],
    status_code=status.HTTP_200_OK,
    summary="Get a single PepMLM candidate",
    description="Retrieve full details for a specific PepMLM candidate by ID.",
)
async def get_pepmlm_candidate(
    candidate_id: Annotated[str, Path(description="PepMLM candidate ID, e.g. OPRF_0001")],
) -> ApiResponse[PepMLMCandidate]:
    """Get a single PepMLM candidate.

    Args:
        candidate_id: Unique candidate identifier.

    Returns:
        Full ``PepMLMCandidate`` record.

    Raises:
        CandidateNotFoundError: If the ID does not exist.
    """
    raw_list = get_pepmlm_candidates()
    for raw in raw_list:
        if str(raw.get("candidate_id", "")).strip() == candidate_id.strip():
            candidate = PepMLMCandidate.model_validate(raw)
            return ok(data=candidate)
    raise CandidateNotFoundError(candidate_id)
