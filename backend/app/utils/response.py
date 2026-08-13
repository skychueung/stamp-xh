"""
STAMP Platform — Unified Response Utilities

Convenience helpers that wrap raw data into the ``ApiResponse[T]``
envelope so that route handlers stay DRY.
"""

from __future__ import annotations

from typing import TypeVar

from app.models.schemas import ApiResponse, PaginatedResponse

T = TypeVar("T")


def ok(data: T | None = None, message: str = "success") -> ApiResponse[T]:
    """Create a successful ``ApiResponse`` with code 200.

    Args:
        data: Payload to return to the client.
        message: Optional custom message (default: ``"success"``).

    Returns:
        Populated ``ApiResponse[T]``.
    """
    return ApiResponse[T].success(data=data, message=message)


def created(data: T | None = None, message: str = "created") -> ApiResponse[T]:
    """Create a success ``ApiResponse`` with code 201.

    Use this for ``POST`` endpoints that successfully create a resource.
    """
    return ApiResponse[T](code=201, message=message, data=data)


def paginated(
    items: list[T],
    total: int,
    page: int = 1,
    page_size: int = 20,
) -> ApiResponse[PaginatedResponse[T]]:
    """Wrap a paginated list into the unified response envelope.

    Args:
        items: Slice of items for the current page.
        total: Total number of items across all pages.
        page: Current 1-based page number.
        page_size: Number of items per page.

    Returns:
        ``ApiResponse`` containing a ``PaginatedResponse``.
    """
    payload: PaginatedResponse[T] = PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return ApiResponse[PaginatedResponse[T]].success(data=payload.model_dump())
