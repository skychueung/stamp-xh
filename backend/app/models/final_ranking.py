"""
STAMP Platform — Final Ranking Models (v0.7-P1e)

Request/response schemas for the heuristic final-ranking endpoint.
All fields are limited to biophysical properties actually computed in v0.7.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FinalRankingCandidateInput(BaseModel):
    """A single STAMP candidate fed into the ranking engine."""

    candidate_id: str = Field(..., examples=["STAMP_V07_20250115_083000_A1B2C3"])
    full_sequence: str = Field(..., examples=["EEDDAEEDAEDDAEEEAAAKFSRFLRRVRRYRPKISFNLEPFFKF"])
    targeting_peptide: str = Field(..., examples=["EEDDAEEDAEDDAEE"])
    linker: str = Field(default="EAAAK", examples=["EAAAK"])
    amp: str = Field(..., examples=["FSRFLRRVRRYRPKISFNLEPFFKF"])
    length: int = Field(..., ge=1, examples=[45])
    net_charge: float = Field(..., examples=[5.2])
    pI: float = Field(..., examples=[8.1])
    GRAVY: float = Field(..., examples=[-0.35])
    cys_count: int = Field(..., ge=0, examples=[0])
    mode: str = Field(default="REAL_STAMP_ASSEMBLY_V0_7", examples=["REAL_STAMP_ASSEMBLY_V0_7"])
    created_at: str | None = Field(default=None, examples=["2025-01-15T08:30:00+00:00"])


class FinalRankingCandidateOutput(BaseModel):
    """A ranked candidate with its composite heuristic score."""

    candidate_id: str
    full_sequence: str
    targeting_peptide: str
    linker: str
    amp: str
    length: int
    net_charge: float
    pI: float
    GRAVY: float
    cys_count: int
    composite_score: float = Field(..., description="Heuristic composite score (0-1).")
    mode: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    created_at: str | None = None


class FinalRankingComputeRequest(BaseModel):
    """POST /api/v1/final-ranking/compute request body."""

    candidates: list[FinalRankingCandidateInput] = Field(
        ...,
        min_length=1,
        description="List of STAMP candidates to rank.",
    )


class FinalRankingComputeResponse(BaseModel):
    """Top-level response envelope."""

    code: int = Field(default=200)
    message: str = Field(default="success")
    mode: str = Field(default="HEURISTIC_FINAL_RANKING_V0_7")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    total_candidates: int
    ranked_candidates: list[FinalRankingCandidateOutput]
    ranking_methodology: dict = Field(
        default_factory=dict,
        description="Human-readable description of the heuristic weights used.",
    )
