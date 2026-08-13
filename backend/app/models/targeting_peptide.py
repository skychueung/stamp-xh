"""
STAMP Platform — Targeting Peptide Generation Models

Request/response schemas for the rule-based targeting peptide generator.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.models.epitope import VALID_AA, FilterStatus


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class SourceEpitope(BaseModel):
    """The selected epitope candidate used as the design template."""

    candidate_id: str = Field(..., examples=["epi_1_15"])
    sequence: str = Field(..., min_length=1, examples=["MKKTAIAIAIVAAGV"])
    start: int = Field(..., ge=1, examples=[1])
    end: int = Field(..., ge=1, examples=[15])
    target_name: str = Field(default="Unknown", examples=["Pseudomonas OprF"])
    species: str = Field(default="Unknown", examples=["Pseudomonas aeruginosa"])

    @field_validator("sequence")
    @classmethod
    def _validate_sequence(cls, v: str) -> str:
        seq = v.upper().strip()
        if not seq:
            raise ValueError("sequence must not be empty")
        invalid = [c for c in seq if c not in VALID_AA]
        if invalid:
            unique = sorted(set(invalid))
            raise ValueError(
                f"Sequence contains illegal characters: {', '.join(unique)}. "
                f"Only standard amino acids are allowed."
            )
        return seq


class TargetingPeptideGenerateRequest(BaseModel):
    """POST /api/v1/targeting-peptide/generate request body."""

    source_epitope: SourceEpitope


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class TargetingPeptideCandidate(BaseModel):
    """A single rule-based targeting peptide candidate."""

    candidate_id: str = Field(..., examples=["tp_001"])
    source_epitope_id: str = Field(..., examples=["epi_1_15"])
    sequence: str = Field(..., min_length=1, examples=["EEDDAEEDAEDDAEE"])
    length: int = Field(..., ge=8, le=15, examples=[12])
    net_charge: float = Field(..., examples=[-3.5])
    pI: float = Field(..., examples=[4.2])
    GRAVY: float = Field(..., examples=[-0.8])
    cys_count: int = Field(..., ge=0, examples=[0])
    complementarity_note: str = Field(
        default="",
        examples=["Designed for charge complementarity against +2.4 epitope"],
    )
    filter_status: FilterStatus = Field(default=FilterStatus.PASS)
    ranking_score: float = Field(..., ge=0.0, le=1.0, examples=[0.85])
    validation_status: str = Field(
        default="NOT_EXPERIMENTALLY_VALIDATED",
        examples=["NOT_EXPERIMENTALLY_VALIDATED"],
    )
    mode: str = Field(
        default="RULE_BASED_TARGETING_PEPTIDE_GENERATION",
        examples=["RULE_BASED_TARGETING_PEPTIDE_GENERATION"],
    )


class TargetingPeptideInputSummary(BaseModel):
    """Summary of the input epitope used for generation."""

    source_epitope_id: str
    source_sequence: str
    source_length: int
    source_net_charge: float
    source_target_name: str
    source_species: str
    requested_count: int


class TargetingPeptideGenerateResponse(BaseModel):
    """Top-level response envelope (mirrors epitope scan shape)."""

    code: int = Field(default=200)
    message: str = Field(default="success")
    mode: str = Field(default="RULE_BASED_TARGETING_PEPTIDE_GENERATION")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    input_summary: TargetingPeptideInputSummary
    candidates: list[TargetingPeptideCandidate]
