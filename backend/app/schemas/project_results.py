"""STAMP Platform — Pydantic Schemas for Project-Level Result Queries (P5-lite P5)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional


from app.schemas.project import SchemaBase


# ---------------------------------------------------------------------------
# Reusable lightweight schemas
# ---------------------------------------------------------------------------


class TargetProteinLite(SchemaBase):
    """Lightweight target protein view for project results."""

    id: str
    name: str
    sequence: str
    length: int
    organism: Optional[str]
    source_type: str
    created_at: datetime


class EpitopeScanLite(SchemaBase):
    """Lightweight epitope scan view for project results."""

    id: str
    target_protein_id: str
    algorithm: str
    algorithm_version: Optional[str]
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    created_at: datetime


class EpitopeCandidateLite(SchemaBase):
    """Lightweight epitope candidate view for project results."""

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
    ranking_score: Optional[float]
    filter_status: str
    created_at: datetime


class GenerationRunLite(SchemaBase):
    """Lightweight generation run view for project results."""

    id: str
    project_id: str
    epitope_id: Optional[str]
    generator_name: str
    generator_version: Optional[str]
    status: str
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    error_message: Optional[str]
    parameters: Optional[dict]
    created_at: datetime


class StampCandidateLite(SchemaBase):
    """Lightweight stamp candidate view for project results."""

    id: str
    project_id: str
    epitope_id: Optional[str]
    generation_run_id: Optional[str]
    targeting_peptide_seq: str
    linker_seq: str
    full_sequence: str
    composite_score: Optional[float]
    validation_status: str
    created_at: datetime
    updated_at: datetime


class StampCandidateDetail(SchemaBase):
    """Full stamp candidate detail view."""

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
# Project summary
# ---------------------------------------------------------------------------


class ProjectSummaryResponse(SchemaBase):
    """Project overview statistics."""

    project_id: str
    project_name: str
    target_protein_count: int
    epitope_scan_count: int
    epitope_candidate_count: int
    generation_run_count: int
    stamp_candidate_count: int
    assembled_candidate_count: int
    ranked_candidate_count: int
    latest_updated_at: Optional[datetime]


# ---------------------------------------------------------------------------
# Pipeline results
# ---------------------------------------------------------------------------


class ProjectPipelineResultsResponse(SchemaBase):
    """Full pipeline results for a project."""

    project_id: str
    project_name: str
    target_proteins: List[TargetProteinLite]
    epitope_scans: List[EpitopeScanLite]
    epitope_candidates: List[EpitopeCandidateLite]
    generation_runs: List[GenerationRunLite]
    stamp_candidates: List[StampCandidateDetail]


# ---------------------------------------------------------------------------
# STAMP results
# ---------------------------------------------------------------------------


class ProjectStampResultsResponse(SchemaBase):
    """Assembled and ranked STAMP candidates for a project."""

    project_id: str
    project_name: str
    total_count: int
    returned_count: int
    candidates: List[StampCandidateDetail]


# ---------------------------------------------------------------------------
# Generation runs list
# ---------------------------------------------------------------------------


class GenerationRunListResponse(SchemaBase):
    """List of generation runs for a project."""

    project_id: str
    project_name: str
    total_count: int
    generation_runs: List[GenerationRunLite]
