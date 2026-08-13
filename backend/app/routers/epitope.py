"""
STAMP Platform — Epitope Scanning Router

POST /api/v1/epitope/scan — runs the 15 aa sliding window biophysics scanner.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, status

from app.models.epitope import EpitopeScanRequest
from app.services.biophys import validate_sequence
from app.services.epitope_scanner import scan_epitopes

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/epitope", tags=["Epitope Scanning"])


@router.post(
    "/scan",
    status_code=status.HTTP_200_OK,
    summary="Run 15 aa sliding window epitope scan",
    description=(
        "Scans the target protein sequence with a 15 aa sliding window (step=1), "
        "computes biophysical properties (GRAVY, net_charge, pI, Cys count, "
        "disulfide risk) for each window, ranks candidates, and returns the "
        "top-k epitope candidates. All results are marked "
        "NOT_EXPERIMENTALLY_VALIDATED and mode=REAL_BIOPHYSICS_SLIDING_WINDOW."
    ),
)
async def scan_epitope(
    request: Annotated[EpitopeScanRequest, Body(...)],
) -> dict:
    validated_seq = validate_sequence(request.sequence)
    result = scan_epitopes(
        sequence=validated_seq,
        target_name=request.target_name,
        species=request.species,
        window_size=request.window_size,
        top_k=request.top_k,
        filters=request.filters,
    )
    return result
