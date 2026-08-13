"""STAMP Platform — Schemas for Targeted Peptide Design Center (P2/P3)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import ConfigDict, Field, field_validator

from app.schemas.project import SchemaBase

STANDARD_AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


def _normalize_fasta_target_sequence(value: str) -> str:
    """Normalize a target protein sequence, stripping FASTA headers and whitespace."""
    if value is None:
        raise ValueError("target_sequence is required")

    lines: list[str] = []
    for raw_line in str(value).splitlines():
        line = raw_line.strip()
        if not line or line.startswith(">"):
            continue
        lines.append(line)

    sequence = "".join(lines).replace(" ", "").replace("	", "").upper()
    if not sequence:
        raise ValueError("target_sequence is required after removing FASTA header")

    illegal = sorted({aa for aa in sequence if aa not in STANDARD_AMINO_ACIDS})
    if illegal:
        raise ValueError(
            "target_sequence contains non-standard amino acids: " + "".join(illegal)
        )

    if len(sequence) < 5:
        raise ValueError("target_sequence must be at least 5 amino acids long")

    return sequence


class TargetPeptideDesignModelInfo(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    model_id: str
    display_name: str
    category: str
    input_type: str
    status: str
    stage: str
    description: str
    requires_structure: bool
    requires_gpu: bool
    notes: str


class TargetPeptideDesignModelsResponse(SchemaBase):
    models: list[TargetPeptideDesignModelInfo]
    scientific_boundary: str


class TargetPeptideDesignModelProbeResult(SchemaBase):
    probe_time: datetime
    model_id: str
    display_name: str
    status: str
    message: str
    backend_env_status: str
    pepmlm_env_status: str
    pepmlm_env_python: Optional[str] = None
    pepmlm_env_check_script: str
    recommended_runtime_env: str
    dependency_status: dict[str, Any]
    cuda_status: dict[str, Any]
    path_status: dict[str, Any]
    config_status: dict[str, Any]
    scientific_boundary: str
    next_action: str


class TargetPeptideDesignModelProbesResponse(SchemaBase):
    probe_time: datetime
    probes: list[TargetPeptideDesignModelProbeResult]
    scientific_boundary: str
    summary: dict[str, Any]


class TargetPeptideDesignJobCreate(SchemaBase):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    target_name: str = Field(..., max_length=255)
    target_sequence: str = Field(...)
    model_id: str = Field(..., max_length=100)
    peptide_length: int = Field(..., ge=5, le=80)
    num_candidates: int = Field(..., ge=1, le=500)
    notes: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("target_sequence", mode="before")
    @classmethod
    def _normalize_target_sequence(cls, value: str) -> str:
        return _normalize_fasta_target_sequence(value)


class TargetPeptideDesignJobResponse(SchemaBase):
    job_id: str
    target_name: str
    target_sequence: str
    model_id: str
    peptide_length: int
    num_candidates: int
    status: str
    message: str
    artifact_dir: str
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime
    scientific_boundary: str


class TargetPeptideDesignCandidateItem(SchemaBase):
    sequence: str
    length: int
    source_model: str
    status: str
    notes: Optional[str] = None


class TargetPeptideDesignCandidatesResponse(SchemaBase):
    job_id: str
    candidates: list[TargetPeptideDesignCandidateItem]
    note: str
    scientific_boundary: str
