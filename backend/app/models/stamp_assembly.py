"""
STAMP Platform — STAMP Assembly Models (v0.7-P1c)

Request/response schemas for the three-part STAMP assembler.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TargetingPeptideInput(BaseModel):
    """The selected targeting peptide candidate."""

    candidate_id: str = Field(..., examples=["tp_001"])
    sequence: str = Field(..., min_length=1, examples=["EEDDAEEDAEDDAEE"])


class StampAssembleRequest(BaseModel):
    """POST /api/v1/stamp/assemble-v0.7 request body."""

    targeting_peptide: TargetingPeptideInput
    linker: str = Field(default="EAAAK", examples=["EAAAK"])
    amp_name: str = Field(default="P4", examples=["P4"])
    amp_sequence: str = Field(
        default="FSRFLRRVRRYRPKISFNLEPFFKF",
        examples=["FSRFLRRVRRYRPKISFNLEPFFKF"],
    )
    terminal_modification: str = Field(default="-NH2", examples=["-NH2"])


class AmpComponent(BaseModel):
    """AMP component metadata."""

    name: str
    sequence: str
    length: int


class LinkerComponent(BaseModel):
    """Linker component metadata."""

    sequence: str
    length: int


class TargetingDomainComponent(BaseModel):
    """Targeting domain component metadata."""

    name: str
    sequence: str
    length: int


class StampAssembleResponse(BaseModel):
    """Top-level response envelope."""

    code: int = Field(default=200)
    message: str = Field(default="success")
    mode: str = Field(default="REAL_STAMP_ASSEMBLY_V0_7")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    candidate_id: str = Field(..., examples=["stamp_v0_7_001"])
    targeting_domain: TargetingDomainComponent
    linker: LinkerComponent
    amp: AmpComponent
    raw_full_sequence: str
    display_full_sequence: str
    length: int
    net_charge: float
    pI: float
    GRAVY: float
    cys_count: int
    created_at: str = Field(..., examples=["2025-01-15T08:30:00+00:00"])
