"""STAMP Platform — Pydantic Schemas for Epitope Scan and Candidate."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.project import SchemaBase


# ---------------------------------------------------------------------------
# Epitope Scan
# ---------------------------------------------------------------------------

class EpitopeScanCreate(SchemaBase):
    project_id: str
    target_protein_id: str
    parameters: Optional[dict] = Field(default_factory=dict)
    algorithm: str = Field(default="heuristic_v1", max_length=100)
    algorithm_version: Optional[str] = Field(None, max_length=50)


class EpitopeScanUpdate(SchemaBase):
    status: Optional[str] = Field(None, max_length=20)
    error_message: Optional[str] = None


class EpitopeScanResponse(SchemaBase):
    id: str
    project_id: str
    target_protein_id: str
    parameters: Optional[dict]
    algorithm: str
    algorithm_version: Optional[str]
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Epitope Candidate
# ---------------------------------------------------------------------------

class EpitopeCandidateCreate(SchemaBase):
    scan_id: str
    start: int
    end: int
    sequence: str = Field(..., max_length=500)
    net_charge: Optional[float] = None
    hydrophobicity: Optional[float] = None
    pi: Optional[float] = None
    cys_count: Optional[int] = None
    surface_exposure_score: Optional[float] = None
    metrics: Optional[dict] = Field(default_factory=dict)
    ranking_score: Optional[float] = None
    filter_status: str = Field(default="PASS", max_length=20)


class EpitopeCandidateUpdate(SchemaBase):
    ranking_score: Optional[float] = None
    filter_status: Optional[str] = Field(None, max_length=20)


class EpitopeCandidateResponse(SchemaBase):
    id: str
    scan_id: str
    start: int
    end: int
    sequence: str
    net_charge: Optional[float]
    hydrophobicity: Optional[float]
    pi: Optional[float]
    cys_count: Optional[int]
    surface_exposure_score: Optional[float]
    metrics: Optional[dict]
    ranking_score: Optional[float]
    filter_status: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# P5-lite P2: Epitope Scan Run schemas
# ---------------------------------------------------------------------------

class EpitopeScanRunRequest(SchemaBase):
    """Request body for POST /api/v1/epitope-scans/run."""
    model_config = ConfigDict(populate_by_name=True)

    project_id: str
    target_protein_id: str
    window_size: int = Field(default=15, ge=5, le=50)
    top_k: int = Field(default=10, ge=1, le=200)
    filters: Optional[dict] = None
    algorithm: str = "heuristic_v1"
    algorithm_version: Optional[str] = "p5_lite_v0.8"


class EpitopeScanCandidateItem(SchemaBase):
    """Response item for a single epitope candidate in scan run response."""
    model_config = ConfigDict(populate_by_name=True)

    candidate_id: str
    start: int
    end: int
    sequence: str
    length: int
    net_charge: Optional[float] = None
    pi: Optional[float] = None
    hydrophobicity: Optional[float] = None
    cys_count: Optional[int] = None
    surface_exposure_score: Optional[float] = None
    ranking_score: Optional[float] = None
    filter_status: str = "PASS"
    recommendation_reason: Optional[str] = None
    risk_notes: Optional[str] = None
    disulfide_risk: Optional[str] = None


class EpitopeScanRunResponse(SchemaBase):
    """Response body for POST /api/v1/epitope-scans/run."""
    model_config = ConfigDict(populate_by_name=True)

    scan_id: str
    project_id: str
    target_protein_id: str
    status: str
    candidate_count: int
    top_candidates: list[EpitopeScanCandidateItem]
    error_message: Optional[str] = None
