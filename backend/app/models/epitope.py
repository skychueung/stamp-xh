"""
STAMP Platform — Epitope Scanning Models

Request/response schemas for the 15 aa sliding-window epitope scanner.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

VALID_AA: set[str] = set("ACDEFGHIKLMNPQRSTVWY")


class FilterStatus(str, Enum):
    PASS = "Pass"
    WARNING = "Warning"
    FAIL = "Fail"


class DisulfideRisk(str, Enum):
    NONE = "none"
    SINGLE_CYS = "single_cys"
    POTENTIAL_DISULFIDE = "potential_disulfide"


class HydrophobicityClass(str, Enum):
    HYDROPHILIC = "hydrophilic"
    NEUTRAL = "neutral"
    HYDROPHOBIC = "hydrophobic"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class EpitopeScanFilters(BaseModel):
    min_charge: float = Field(default=-4.0)
    max_charge: float = Field(default=6.0)
    min_pI: float = Field(default=4.0)
    max_pI: float = Field(default=11.0)
    max_gravy: float = Field(default=1.0)
    max_cys: int = Field(default=1, ge=0)


class EpitopeScanRequest(BaseModel):
    target_name: str = Field(default="Unknown", examples=["Pseudomonas OprF"])
    species: str = Field(default="Unknown", examples=["Pseudomonas aeruginosa"])
    sequence: str = Field(
        ...,
        min_length=1,
        examples=["MKKTAIAIAIVAAGVATVQAATAEQVNTLKGNVAAGAANLNETTSGVQNYTQFDFNLDKES"],
    )
    window_size: int = Field(default=15, ge=3, le=50)
    top_k: int = Field(default=20, ge=1, le=200)
    filters: EpitopeScanFilters = Field(default_factory=EpitopeScanFilters)

    @field_validator("sequence")
    @classmethod
    def validate_sequence(cls, v: str) -> str:
        seq = v.upper().strip()
        if not seq:
            raise ValueError("sequence must not be empty")
        invalid = [c for c in seq if c not in VALID_AA]
        if invalid:
            unique = sorted(set(invalid))
            raise ValueError(
                f"Sequence contains illegal characters: {', '.join(unique)}. "
                f"Only standard amino acids are allowed: {''.join(sorted(VALID_AA))}"
            )
        return seq


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class EpitopeCandidate(BaseModel):
    candidate_id: str
    start: int
    end: int
    sequence: str
    length: int
    net_charge: float
    pI: float
    GRAVY: float
    cys_count: int
    disulfide_risk: str
    hydrophobicity_class: str
    filter_status: FilterStatus
    ranking_score: float
    risk_notes: str | None = None
    recommendation_reason: str | None = None


class InputSummary(BaseModel):
    target_name: str
    species: str
    sequence_length: int
    window_size: int
    total_windows: int


class FilteringSummary(BaseModel):
    total_windows: int
    passed: int
    warning: int
    failed: int
    returned: int


class EpitopeScanResponse(BaseModel):
    code: int = 200
    message: str = "Epitope scan completed"
    mode: str = "REAL_BIOPHYSICS_SLIDING_WINDOW"
    validation_status: str = "NOT_EXPERIMENTALLY_VALIDATED"
    input_summary: InputSummary
    filtering_summary: FilteringSummary
    candidates: list[EpitopeCandidate]
