"""
STAMP Platform — Targeting Peptide Generation Router

POST /api/v1/targeting-peptide/generate — rule-based targeting peptide design.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Body, status

from app.models.targeting_peptide import TargetingPeptideGenerateRequest
from app.services.targeting_peptide_generator import generate_targeting_peptides

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/targeting-peptide",
    tags=["Targeting Peptide Generation"],
)


@router.post(
    "/generate",
    status_code=status.HTTP_200_OK,
    summary="Generate rule-based targeting peptide candidates",
    description=(
        "Generates up to 20 targeting peptide candidates from a selected epitope "
        "using deterministic biophysical rules (charge complementarity, length 8-15 aa, "
        "Cys=0). No ML models are invoked. All results are marked "
        "NOT_EXPERIMENTALLY_VALIDATED and mode=RULE_BASED_TARGETING_PEPTIDE_GENERATION."
    ),
)
async def generate_targeting_peptide(
    request: Annotated[TargetingPeptideGenerateRequest, Body(...)],
) -> dict:
    result = generate_targeting_peptides(
        source_epitope=request.source_epitope,
        requested_count=20,
    )
    return result
