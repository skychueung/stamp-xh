"""STAMP Platform — Pydantic Schemas for STAMP Generation Run and Candidate."""

from datetime import datetime
from typing import List, Optional

from pydantic import Field

from app.schemas.project import SchemaBase


# ---------------------------------------------------------------------------
# STAMP Generation Run
# ---------------------------------------------------------------------------

class StampGenerationRunCreate(SchemaBase):
    project_id: str
    epitope_id: Optional[str] = None
    parameters: Optional[dict] = Field(default_factory=dict)
    generator_name: str = Field(default="manual", max_length=100)
    generator_version: Optional[str] = Field(None, max_length=50)


class StampGenerationRunUpdate(SchemaBase):
    status: Optional[str] = Field(None, max_length=20)
    error_message: Optional[str] = None


class StampGenerationRunResponse(SchemaBase):
    id: str
    project_id: str
    epitope_id: Optional[str]
    parameters: Optional[dict]
    generator_name: str
    generator_version: Optional[str]
    status: str
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# STAMP Candidate
# ---------------------------------------------------------------------------

class StampCandidateCreate(SchemaBase):
    project_id: str
    epitope_id: Optional[str] = None
    generation_run_id: Optional[str] = None
    targeting_peptide_seq: str = Field(..., max_length=500)
    linker_seq: str = Field(..., max_length=100)
    full_sequence: str
    composite_score: Optional[float] = None
    validation_status: Optional[str] = Field(
        default="NOT_EXPERIMENTALLY_VALIDATED", max_length=50
    )
    metrics: Optional[dict] = Field(default_factory=dict)


class StampCandidateUpdate(SchemaBase):
    full_sequence: Optional[str] = None
    linker_seq: Optional[str] = Field(None, max_length=100)
    composite_score: Optional[float] = None
    validation_status: Optional[str] = Field(None, max_length=50)
    metrics: Optional[dict] = None


class StampCandidateResponse(SchemaBase):
    id: str
    project_id: str
    epitope_id: Optional[str]
    generation_run_id: Optional[str]
    targeting_peptide_seq: str
    linker_seq: str
    full_sequence: str
    composite_score: Optional[float]
    validation_status: str
    metrics: Optional[dict]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Peptide Generation Run (P5-lite P3)
# ---------------------------------------------------------------------------

class PeptideGenerationRunRequest(SchemaBase):
    """Request body for POST /api/v1/peptide-generations/run."""

    project_id: str
    epitope_id: str
    generator_name: str = Field(default="heuristic_targeting_peptide_v1", max_length=100)
    generator_version: Optional[str] = Field(default="p5_lite_v0.8", max_length=50)
    top_k: int = Field(default=10, ge=1, le=100)
    linker_seq: str = Field(default="GGGGS", max_length=100)
    parameters: Optional[dict] = Field(default_factory=dict)


class PeptideGenerationRunResponse(SchemaBase):
    """Response body for POST /api/v1/peptide-generations/run."""

    generation_run_id: str
    project_id: str
    epitope_id: str
    status: str
    candidate_count: int
    top_candidates: List[StampCandidateResponse]
    error_message: Optional[str] = None


# ---------------------------------------------------------------------------
# STAMP Assembly Run (P5-lite P4)
# ---------------------------------------------------------------------------

class StampAssemblyRunRequest(SchemaBase):
    """Request body for POST /api/v1/stamp-assembly/run."""

    project_id: str
    generation_run_id: str
    linker_seq: str = Field(default="GGGGS", max_length=100, min_length=1)
    killing_peptide_seq: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    parameters: Optional[dict] = Field(default_factory=dict)
    force: bool = False


class StampAssemblyFailedCandidate(SchemaBase):
    """A candidate that failed during assembly/ranking."""

    candidate_id: str
    error_message: str


class StampAssemblyRankedCandidate(SchemaBase):
    """A successfully assembled and ranked candidate."""

    rank: int
    candidate_id: str
    targeting_peptide_seq: str
    full_sequence: str
    composite_score: Optional[float]
    validation_status: str


class StampAssemblyRunResponse(SchemaBase):
    """Response body for POST /api/v1/stamp-assembly/run."""

    project_id: str
    generation_run_id: str
    status: str
    processed_count: int
    skipped_count: int
    failed_count: int
    ranked_candidates: List[StampAssemblyRankedCandidate]
    failed_candidates: List[StampAssemblyFailedCandidate]
    error_message: Optional[str] = None
