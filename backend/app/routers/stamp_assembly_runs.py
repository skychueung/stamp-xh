"""STAMP Platform — STAMP Assembly Run Router (P5-lite P4).

POST /api/v1/stamp-assembly/run — Assemble and rank STAMP candidates.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import StampException
from app.database import get_db
from app.schemas import StampAssemblyRunRequest, StampAssemblyRunResponse
from app.services.stamp_assembly_persistence import run_stamp_assembly_and_persist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stamp-assembly", tags=["STAMP Assembly"])


@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    summary="Run STAMP assembly and final ranking for a generation run",
    description=(
        "Reads all stamp candidates from a generation run, assembles each with "
        "the provided linker and killing peptide, computes heuristic composite scores, "
        "and updates the database. Supports force reprocessing."
    ),
    response_model=StampAssemblyRunResponse,
)
async def run_stamp_assembly(
    request: Annotated[StampAssemblyRunRequest, Body(...)],
    db: Session = Depends(get_db),
) -> StampAssemblyRunResponse:
    """Run STAMP assembly and final ranking."""
    try:
        result = run_stamp_assembly_and_persist(db, request)
        return result
    except StampException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        logger.exception("STAMP assembly run failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"STAMP assembly failed: {type(exc).__name__}: {str(exc)}",
        ) from exc
