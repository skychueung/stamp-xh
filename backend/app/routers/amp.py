"""
STAMP Platform — AMP Library Router

Endpoints for browsing the antimicrobial peptide (AMP) library and
accessing the AMP structure manifest.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status

from app.core.exceptions import AmpNotFoundError
from app.data.loader import get_amp_structure_manifest, get_priority_amp_library
from app.models.schemas import (
    AmpListItem,
    AmpRecord,
    ApiResponse,
    PaginatedResponse,
)
from app.services.amp_selector import get_amp_by_name, list_amp_records
from app.utils.response import ok, paginated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/amp", tags=["AMP Library"])


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


@router.get(
    "/library",
    response_model=ApiResponse[PaginatedResponse[AmpListItem]],
    status_code=status.HTTP_200_OK,
    summary="List AMP library records",
    description="Browse the priority AMP library with pagination.  "
                "Records include P4, P15, and other screened peptides.",
)
async def list_amp_library(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ApiResponse[PaginatedResponse[AmpListItem]]:
    """List AMP library records.

    Args:
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Paginated list of trimmed AMP items.
    """
    raw = get_priority_amp_library()
    items_raw, total = _paginate(raw, page, page_size)

    items = [
        AmpListItem(
            amp_name=r["ampName"],
            clean_sequence=r["cleanSequence"],
            priority=r.get("priority", "medium"),
            role=r.get("role", "killing_domain"),
        )
        for r in items_raw
    ]

    return paginated(items=items, total=total, page=page, page_size=page_size)


@router.get(
    "/library/{amp_name}",
    response_model=ApiResponse[AmpRecord],
    status_code=status.HTTP_200_OK,
    summary="Get a single AMP record",
    description="Retrieve full details for a specific AMP by canonical name.",
)
async def get_amp(
    amp_name: Annotated[str, Path(description="AMP name, e.g. P4")],
) -> ApiResponse[AmpRecord]:
    """Get a single AMP record.

    Args:
        amp_name: Canonical AMP identifier.

    Returns:
        Full ``AmpRecord``.

    Raises:
        AmpNotFoundError: If the AMP is not in the library.
    """
    raw = get_priority_amp_library()
    amp = get_amp_by_name(raw, amp_name)
    return ok(data=amp)


@router.get(
    "/structures",
    response_model=ApiResponse[PaginatedResponse[dict]],
    status_code=status.HTTP_200_OK,
    summary="List AMP structure manifest",
    description="Retrieve the structure availability manifest for AMPs.",
)
async def list_amp_structures(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
) -> ApiResponse[PaginatedResponse[dict]]:
    """List AMP structure manifest entries.

    Args:
        page: 1-based page number.
        page_size: Items per page.

    Returns:
        Paginated list of structure manifest records.
    """
    raw = get_amp_structure_manifest()
    items, total = _paginate(raw, page, page_size)
    return paginated(items=items, total=total, page=page, page_size=page_size)
