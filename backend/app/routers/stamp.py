"""
STAMP Platform — STAMP Candidate Router

Core endpoints for building and querying STAMP hybrid peptide candidates.
The ``POST /build`` endpoint is the heart of the platform: it assembles
TP + EAAAK + AMP into a complete STAMP molecule.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Body, Path, Query, status

from app.core.exceptions import CandidateNotFoundError
from app.data.loader import (
    get_pepmlm_candidates,
    get_priority_amp_library,
    get_stamp_hybrid_candidates,
    get_stamp_template_library,
)
from app.models.schemas import (
    ApiResponse,
    PaginatedResponse,
    StampBuildRequest,
    StampCandidate,
    StampListItem,
    ValidationStatus,
)
from app.services.stamp_builder import build_stamp
from app.utils.response import created, ok, paginated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stamp", tags=["STAMP Candidates"])


def _paginate(
    items: list[Any],
    page: int,
    page_size: int,
) -> tuple[list[Any], int]:
    """Slice items for pagination."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return items[start:end], total


# ---------------------------------------------------------------------------
# POST /api/v1/stamp/build  (CORE ENDPOINT)
# ---------------------------------------------------------------------------

@router.post(
    "/build",
    response_model=ApiResponse[StampCandidate],
    status_code=status.HTTP_200_OK,
    summary="Build a STAMP candidate",
    description=(
        "Assemble a STAMP molecule from a PepMLM targeting peptide "
        "and an AMP killing domain.  The linker is fixed to EAAAK.  "
        "If ``amp_name`` is omitted, P4 is used by default.  "
        "No mock experimental data is ever fabricated."
    ),
)
async def build_stamp_candidate(
    request: Annotated[StampBuildRequest, Body(...)],
) -> ApiResponse[StampCandidate]:
    """Build a single STAMP candidate.

    Args:
        request: Build request containing PepMLM candidate ID
                 and optional AMP name override.

    Returns:
        Fully assembled ``StampCandidate`` with code 201.
    """
    stamp = build_stamp(
        candidate_id=request.candidate_id,
        amp_library=get_priority_amp_library(),
        pepmlm_candidates=get_pepmlm_candidates(),
        preferred_amp_name=request.amp_name,
    )
    return ok(data=stamp, message="STAMP candidate built successfully")


# ---------------------------------------------------------------------------
# GET /api/v1/stamp/templates
# ---------------------------------------------------------------------------

@router.get(
    "/templates",
    response_model=ApiResponse[PaginatedResponse[dict]],
    status_code=status.HTTP_200_OK,
    summary="List STAMP templates",
    description="Retrieve available STAMP template configurations.",
)
async def list_stamp_templates(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ApiResponse[PaginatedResponse[dict]]:
    """List STAMP template records.

    Args:
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Paginated list of template records.
    """
    raw = get_stamp_template_library()
    items, total = _paginate(raw, page, page_size)
    return paginated(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# GET /api/v1/stamp/hybrid-candidates
# ---------------------------------------------------------------------------

@router.get(
    "/hybrid-candidates",
    response_model=ApiResponse[PaginatedResponse[dict]],
    status_code=status.HTTP_200_OK,
    summary="List hybrid candidates",
    description="Retrieve pre-existing STAMP hybrid candidates (reference data).",
)
async def list_hybrid_candidates(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ApiResponse[PaginatedResponse[dict]]:
    """List hybrid candidate records.

    Args:
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Paginated list of hybrid candidate records.
    """
    raw = get_stamp_hybrid_candidates()
    items, total = _paginate(raw, page, page_size)
    return paginated(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# GET /api/v1/stamp/candidates/{candidate_id}
# ---------------------------------------------------------------------------

@router.get(
    "/candidates/{candidate_id}",
    response_model=ApiResponse[StampCandidate],
    status_code=status.HTTP_200_OK,
    summary="Get a STAMP candidate",
    description="Look up a previously built STAMP candidate by its generated ID.",
)
async def get_stamp_candidate(
    candidate_id: Annotated[
        str,
        Path(description="STAMP candidate ID, e.g. stamp_oprf_0001"),
    ],
) -> ApiResponse[StampCandidate]:
    """Get a STAMP candidate by ID.

    In the current v0.6d implementation candidates are built on-the-fly
    and not persisted.  This endpoint rebuilds the candidate if the
    corresponding PepMLM record exists.

    Args:
        candidate_id: STAMP candidate identifier.

    Returns:
        ``StampCandidate`` if found.

    Raises:
        CandidateNotFoundError: If the underlying PepMLM record is absent.
    """
    # v0.6d: rebuild on-the-fly since we don't persist yet.
    # Extract the PepMLM ID from stamp ID: "stamp_oprf_0001" -> "OPRF_0001"
    if candidate_id.lower().startswith("stamp_"):
        pepmlm_id = candidate_id[6:].upper()
    else:
        pepmlm_id = candidate_id.upper()

    stamp = build_stamp(
        candidate_id=pepmlm_id,
        amp_library=get_priority_amp_library(),
        pepmlm_candidates=get_pepmlm_candidates(),
    )
    return ok(data=stamp)


# ---------------------------------------------------------------------------
# GET /api/v1/stamp/demo-one
# ---------------------------------------------------------------------------


@router.get(
    "/demo-one",
    response_model=ApiResponse[StampCandidate],
    status_code=status.HTTP_200_OK,
    summary="Build a single default STAMP candidate",
    description=(
        "Assemble a STAMP molecule using the top-ranked PepMLM candidate "
        "(lowest PPL), the default AMP (P4), and the fixed EAAAK linker. "
        "Returns a complete StampCandidate with no mock experimental data."
    ),
)
async def demo_one_stamp() -> ApiResponse[StampCandidate]:
    """Build a single default STAMP candidate (demo).

    Uses the PepMLM candidate with the lowest PPL score as the targeting
    domain, P4 as the killing domain, and EAAAK as the rigid linker.

    Returns:
        Fully assembled ``StampCandidate`` with code 200.
    """
    candidates = get_pepmlm_candidates()
    if not candidates:
        from app.core.exceptions import CandidateNotFoundError
        raise CandidateNotFoundError("No PepMLM candidates available")

    # Select candidate with lowest PPL score
    top1 = min(candidates, key=lambda c: c.get("ppl_score", float("inf")))
    top1_id = top1.get("candidate_id", "")

    stamp = build_stamp(
        candidate_id=top1_id,
        amp_library=get_priority_amp_library(),
        pepmlm_candidates=candidates,
        preferred_amp_name=None,  # defaults to P4
    )
    return ok(data=stamp, message="Single STAMP demo candidate assembled")
