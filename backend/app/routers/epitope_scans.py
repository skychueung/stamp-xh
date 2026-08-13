"""STAMP Platform -- Epitope Scan Management Router (P5-lite P2).

Routes:
  POST /api/v1/epitope-scans/run     -- Run scan + persist (NEW)
  POST /api/v1/epitope-scans         -- Create scan record only (legacy)
  GET  /api/v1/epitope-scans/{id}    -- Get scan by ID
  GET  /api/v1/epitope-scans/{id}/candidates -- List candidates for scan
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import StampException
from app.crud.epitopes import (
    create_epitope_scan,
    get_epitope_scan,
    list_epitope_candidates_by_scan,
)
from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas import (
    EpitopeScanCreate,
    EpitopeScanRunRequest,
    EpitopeScanRunResponse,
)
from app.services.epitope_scan_persistence import run_epitope_scan_and_persist

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/epitope-scans", tags=["Epitope Scans"])


@router.post(
    "/run",
    status_code=status.HTTP_200_OK,
    summary="Run epitope scan and persist results",
    description=(
        "Runs a real biophysical sliding-window scan against a target protein "
        "stored in the database. Creates an epitope_scans record, executes the scan, "
        "persists all candidate epitopes to epitope_candidates, and returns "
        "the scan results. Scan status transitions: PENDING -> RUNNING -> COMPLETED/FAILED."
    ),
    response_model=EpitopeScanRunResponse,
)
async def run_epitope_scan(
    request: Annotated[EpitopeScanRunRequest, Body(...)],
    db: Session = Depends(get_db),
) -> EpitopeScanRunResponse:
    """Run a real epitope scan and persist results to the database."""
    try:
        result = run_epitope_scan_and_persist(db, request)
        return result
    except StampException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a scan record only (lightweight)",
    description="Creates an epitope_scans record without running the actual scan.",
)
async def create_scan_only(
    scan_in: Annotated[EpitopeScanCreate, Body(...)],
    db: Session = Depends(get_db),
) -> dict:
    """Create a scan record (status=PENDING) without running the scan."""
    scan = create_epitope_scan(db, scan_in)
    return ApiResponse.success(
        data={"scan_id": scan.id, "status": scan.status}
    ).model_dump()


@router.get(
    "/{scan_id}",
    status_code=status.HTTP_200_OK,
    summary="Get scan by ID",
)
async def get_scan(scan_id: str, db: Session = Depends(get_db)) -> dict:
    """Retrieve an epitope scan record by its ID."""
    scan = get_epitope_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_id}' not found")
    return ApiResponse.success(
        data={
            "scan_id": scan.id,
            "project_id": scan.project_id,
            "target_protein_id": scan.target_protein_id,
            "status": scan.status,
            "algorithm": scan.algorithm,
            "algorithm_version": scan.algorithm_version,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "finished_at": scan.finished_at.isoformat() if scan.finished_at else None,
            "error_message": scan.error_message,
            "created_at": scan.created_at.isoformat() if scan.created_at else None,
        }
    ).model_dump()


@router.get(
    "/{scan_id}/candidates",
    status_code=status.HTTP_200_OK,
    summary="List candidates for a scan",
)
async def get_scan_candidates(
    scan_id: str,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve all epitope candidates associated with a scan."""
    scan = get_epitope_scan(db, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail=f"Scan '{scan_id}' not found")
    candidates = list_epitope_candidates_by_scan(db, scan_id, skip=skip, limit=limit)
    return ApiResponse.success(
        data={
            "scan_id": scan_id,
            "count": len(candidates),
            "candidates": [
                {
                    "id": c.id,
                    "start": c.start,
                    "end": c.end,
                    "sequence": c.sequence,
                    "net_charge": c.net_charge,
                    "hydrophobicity": c.hydrophobicity,
                    "pi": c.pi,
                    "cys_count": c.cys_count,
                    "surface_exposure_score": c.surface_exposure_score,
                    "ranking_score": c.ranking_score,
                    "filter_status": c.filter_status,
                    "metrics": c.metrics,
                }
                for c in candidates
            ],
        }
    ).model_dump()
