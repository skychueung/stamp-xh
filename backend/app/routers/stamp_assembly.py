"""
STAMP Platform — STAMP Assembly Router (v0.7-P1c)

POST /api/v1/stamp/assemble-v0.7 — three-part STAMP assembly.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, status

from app.models.stamp_assembly import StampAssembleRequest
from app.services.stamp_assembler import assemble_stamp

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/stamp", tags=["STAMP Assembly"])


@router.post(
    "/assemble-v0.7",
    status_code=status.HTTP_200_OK,
    summary="Assemble a STAMP candidate from targeting peptide + linker + AMP",
    description=(
        "Takes a selected targeting peptide and assembles it with a linker "
        "(default EAAAK) and an AMP killing domain (default P4) into a full "
        "STAMP candidate. Computes biophysical properties for the full sequence. "
        "All results are marked NOT_EXPERIMENTALLY_VALIDATED."
    ),
)
async def assemble_stamp_endpoint(
    request: Annotated[StampAssembleRequest, Body(...)],
) -> dict:
    result = assemble_stamp(request)
    return result
