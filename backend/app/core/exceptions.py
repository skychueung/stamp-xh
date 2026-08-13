"""
STAMP Platform — Custom Business Exceptions

Defines a hierarchy of domain-specific exceptions together with a
FastAPI-compatible exception handler that normalises every error into
the ``ApiResponse`` envelope.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.models.schemas import ApiResponse


# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class StampException(Exception):
    """Base class for all STAMP domain exceptions.

    Attributes:
        status_code: HTTP status code to return.
        detail: Human-readable error message.
        error_code: Machine-readable error identifier.
    """

    def __init__(
        self,
        status_code: int,
        detail: str,
        error_code: str = "STAMP_ERROR",
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        super().__init__(detail)


class CandidateNotFoundError(StampException):
    """Raised when a requested PepMLM or STAMP candidate does not exist."""

    def __init__(self, candidate_id: str) -> None:
        super().__init__(
            status_code=404,
            detail=f"Candidate '{candidate_id}' not found.",
            error_code="CANDIDATE_NOT_FOUND",
        )


class AmpNotFoundError(StampException):
    """Raised when a requested AMP name is not present in the library."""

    def __init__(self, amp_name: str) -> None:
        super().__init__(
            status_code=404,
            detail=f"AMP '{amp_name}' not found in the library.",
            error_code="AMP_NOT_FOUND",
        )


class AmpLibraryEmptyError(StampException):
    """Raised when the AMP library contains no usable records."""

    def __init__(self) -> None:
        super().__init__(
            status_code=500,
            detail="AMP library is empty — cannot select a killing domain.",
            error_code="AMP_LIBRARY_EMPTY",
        )


class InvalidSequenceError(StampException):
    """Raised when a peptide sequence fails validation rules."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=400,
            detail=f"Sequence validation failed: {reason}",
            error_code="INVALID_SEQUENCE",
        )


class DataLoadError(StampException):
    """Raised when a required JSON data file cannot be read or parsed."""

    def __init__(self, filepath: str, reason: str) -> None:
        super().__init__(
            status_code=500,
            detail=f"Failed to load data from '{filepath}': {reason}",
            error_code="DATA_LOAD_ERROR",
        )


class BuildError(StampException):
    """Raised when STAMP assembly cannot be completed for any reason."""

    def __init__(self, reason: str) -> None:
        super().__init__(
            status_code=422,
            detail=f"STAMP build failed: {reason}",
            error_code="BUILD_ERROR",
        )


# ---------------------------------------------------------------------------
# FastAPI exception handler
# ---------------------------------------------------------------------------


async def stamp_exception_handler(
    _request: Request,
    exc: StampException,
) -> JSONResponse:
    """Convert any ``StampException`` into a JSONResponse with the unified
    ``ApiResponse`` envelope.

    Args:
        _request: The incoming HTTP request (unused).
        exc: The raised STAMP exception.

    Returns:
        A ``JSONResponse`` with *status_code* matching the exception.
    """
    body = ApiResponse[None].error(
        code=exc.status_code,
        message=exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(),
    )


async def generic_exception_handler(
    _request: Request,
    exc: Exception,
) -> JSONResponse:
    """Fallback handler for unhandled exceptions.

    In production (``debug=False``) the original traceback is *not*
    leaked to the client.
    """
    body = ApiResponse[None].error(
        code=500,
        message="Internal server error. Please contact the administrator.",
    )
    return JSONResponse(
        status_code=500,
        content=body.model_dump(),
    )
