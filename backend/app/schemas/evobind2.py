"""STAMP Platform — EvoBind2 Schemas (v0.3-probe).

Request/response models for EvoBind2 dry-run, job-queue compute, and
environment probe endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.compute_wrappers.evobind2_wrapper import (
    ALLOWED_MODEL_NAMES,
    BLOCKED_MODEL_NAMES,
    DEFAULT_MODEL_NAME,
    validate_fasta_local,
    validate_run_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _default_safety_flags() -> dict[str, bool]:
    return {
        "is_candidate_generation": False,
        "is_scientific_result": False,
        "uses_uniref30": False,
    }


# ---------------------------------------------------------------------------
# Schema base
# ---------------------------------------------------------------------------


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Probe schemas (P2C)
# ---------------------------------------------------------------------------


class EvoBind2ProbeCheck(SchemaBase):
    """A single environment check result from the EvoBind2 probe."""

    name: str = Field(..., description="Machine-readable check identifier.")
    status: str = Field(..., description="PASS | FAIL | DEGRADED.")
    message: str = Field(..., description="Human-readable summary.")
    detail: Optional[str] = Field(default=None, description="Path, version, or extra detail.")
    severity: str = Field(default="INFO", description="INFO | WARNING | ERROR.")


class EvoBind2ProbeResponse(SchemaBase):
    """Response body for GET /api/v1/evobind2/probe.

    This response only contains environment readiness metadata.  It never
    includes candidate peptides, PDB files, or scientific metrics.
    """

    status: str = Field(..., description="AVAILABLE | DEGRADED | UNAVAILABLE.")
    dry_run_status: str = Field(..., description="READY_FOR_DRY_RUN | BLOCKED.")
    real_run_status: str = Field(..., description="Always BLOCKED in this phase.")
    install_status: str = Field(..., description="INSTALL_COMPLETE | INSTALL_INCOMPLETE.")
    checks: List[EvoBind2ProbeCheck] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    resolved_paths: dict[str, Any] = Field(default_factory=dict)
    gpu_devices: List[dict[str, Any]] = Field(default_factory=list)
    safety_flags: dict[str, bool] = Field(default_factory=dict)
    real_run_enabled: bool = Field(default=False)
    executed_model: bool = Field(default=False)
    executed_hhblits_search: bool = Field(default=False)
    generated_msa: bool = Field(default=False)
    generated_candidates: bool = Field(default=False)
    generated_pdb: bool = Field(default=False)
    is_candidate_generation: bool = Field(default=False)
    is_scientific_result: bool = Field(default=False)
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------


class EvoBind2DryRunRequest(SchemaBase):
    """Request body for POST /api/v1/evobind2/dry-run."""

    run_id: str = Field(..., min_length=1, description="Unique run identifier.")
    receptor_fasta: str = Field(..., min_length=1, description="Receptor FASTA content.")
    peptide_length: int = Field(default=10, ge=1, le=50)
    mode: str = Field(default="predict_only")
    peptide_sequence: Optional[str] = Field(default=None)
    model_name: str = Field(default=DEFAULT_MODEL_NAME)
    max_recycles: int = Field(default=1, ge=1, le=10)
    num_iterations: int = Field(default=1, ge=1, le=100)
    use_gpu: bool = Field(default=True)
    selected_gpu: str | int = Field(default="auto")
    msa_mode: str = Field(default="single_sequence")
    receptor_msa_a3m: Optional[str] = Field(default=None)

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, v: str) -> str:
        ok, error = validate_run_id(v)
        if not ok:
            raise ValueError(error)
        return v

    @field_validator("receptor_fasta")
    @classmethod
    def _check_receptor_fasta(cls, v: str) -> str:
        ok, error = validate_fasta_local(v)
        if not ok:
            raise ValueError(error)
        return v

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v != "predict_only":
            raise ValueError("Only 'predict_only' mode is supported in this skeleton.")
        return v

    @field_validator("model_name")
    @classmethod
    def _check_model_name(cls, v: str) -> str:
        if v in BLOCKED_MODEL_NAMES:
            raise ValueError(
                f"{v} parameter exists but current EvoBind2 "
                "mc_design.py/config.py path does not support it."
            )
        if v not in ALLOWED_MODEL_NAMES:
            raise ValueError(
                f"Invalid model name: {v}. Allowed: {ALLOWED_MODEL_NAMES}"
            )
        return v

    @field_validator("peptide_sequence")
    @classmethod
    def _check_peptide_sequence(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        from app.services.compute_wrappers.evobind2_wrapper import AMINO_ACID_PATTERN
        if not AMINO_ACID_PATTERN.match(v):
            raise ValueError("peptide_sequence contains invalid characters")
        if len(v) > 50:
            raise ValueError("peptide_sequence exceeds 50 residues")
        return v

    @model_validator(mode="after")
    def _check_predict_only_contract(self) -> "EvoBind2DryRunRequest":
        """Phase 9A: predict_only requires peptide_sequence == peptide_length."""
        if self.mode == "predict_only":
            seq = self.peptide_sequence
            length = self.peptide_length
            if seq is None or seq == "":
                raise ValueError("peptide_sequence is required for predict_only mode")
            if len(seq) != length:
                raise ValueError(
                    f"peptide_sequence length ({len(seq)}) must equal "
                    f"peptide_length ({length})"
                )
        return self


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------


class EvoBind2DryRunResponse(SchemaBase):
    """Response body for POST /api/v1/evobind2/dry-run."""

    run_id: str
    status: str = Field(default="READY")
    mode: str = Field(default="predict_only")
    model_name: str = Field(default=DEFAULT_MODEL_NAME)
    used_gpu: bool = Field(default=True)
    selected_gpu: Optional[int] = Field(default=None)
    runtime_seconds: Optional[int] = Field(default=None)
    artifacts: dict[str, Optional[str]] = Field(default_factory=dict)
    safety_flags: dict[str, bool] = Field(default_factory=_default_safety_flags)
    command_preview: Optional[list[str]] = Field(default=None)
    env_preview: dict[str, str] = Field(default_factory=dict)
    error_message: Optional[str] = Field(default=None)


# ---------------------------------------------------------------------------
# Job Queue Schemas (v0.2-skeleton)
# ---------------------------------------------------------------------------


class EvoBind2JobSubmitRequest(SchemaBase):
    """Request body for POST /api/v1/evobind2/jobs."""

    project_id: str = Field(..., min_length=1)
    target_sequence: str = Field(..., min_length=1, description="Receptor FASTA or raw sequence.")
    peptide_length: int = Field(default=10, ge=1, le=50)
    peptide_sequence: Optional[str] = Field(default=None)
    mode: str = Field(default="predict_only")
    model_name: str = Field(default=DEFAULT_MODEL_NAME)
    msa_mode: str = Field(default="single_sequence")
    dry_run: bool = Field(default=False)
    max_recycles: int = Field(default=1, ge=1, le=10)
    num_iterations: int = Field(default=1, ge=1, le=100)
    use_gpu: bool = Field(default=True)
    selected_gpu: str | int = Field(default="auto")
    receptor_msa_a3m: Optional[str] = Field(default=None)

    @field_validator("target_sequence")
    @classmethod
    def _check_target_sequence(cls, v: str) -> str:
        ok, error = validate_fasta_local(v)
        if not ok:
            raise ValueError(error)
        return v

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, v: str) -> str:
        if v != "predict_only":
            raise ValueError("Only 'predict_only' mode is supported in this skeleton phase.")
        return v

    @field_validator("model_name")
    @classmethod
    def _check_model_name(cls, v: str) -> str:
        if v in BLOCKED_MODEL_NAMES:
            raise ValueError(
                f"{v} parameter exists but current EvoBind2 "
                "mc_design.py/config.py path does not support it."
            )
        if v not in ALLOWED_MODEL_NAMES:
            raise ValueError(
                f"Invalid model name: {v}. Allowed: {ALLOWED_MODEL_NAMES}"
            )
        return v

    @field_validator("msa_mode")
    @classmethod
    def _check_msa_mode(cls, v: str) -> str:
        allowed = {"single_sequence", "precomputed_a3m"}
        if v not in allowed:
            raise ValueError(
                f"MSA mode '{v}' is not supported. Allowed: {allowed}"
            )
        return v

    @field_validator("peptide_sequence")
    @classmethod
    def _check_peptide_sequence(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return v
        from app.services.compute_wrappers.evobind2_wrapper import AMINO_ACID_PATTERN
        if not AMINO_ACID_PATTERN.match(v):
            raise ValueError("peptide_sequence contains invalid characters")
        if len(v) > 50:
            raise ValueError("peptide_sequence exceeds 50 residues")
        return v

    @model_validator(mode="after")
    def _check_predict_only_contract(self) -> "EvoBind2JobSubmitRequest":
        """Phase 9A: predict_only requires peptide_sequence == peptide_length."""
        if self.mode == "predict_only":
            seq = self.peptide_sequence
            length = self.peptide_length
            if seq is None or seq == "":
                raise ValueError("peptide_sequence is required for predict_only mode")
            if len(seq) != length:
                raise ValueError(
                    f"peptide_sequence length ({len(seq)}) must equal "
                    f"peptide_length ({length})"
                )
        return self


class EvoBind2JobResponse(SchemaBase):
    """Response body for EvoBind2 job endpoints."""

    job_id: str
    project_id: str
    status: str
    job_type: str = Field(default="evobind2_predict")
    model_name: str = Field(default=DEFAULT_MODEL_NAME)
    mode: str = Field(default="predict_only")
    safety_flags: dict[str, bool] = Field(default_factory=_default_safety_flags)
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EvoBind2JobArtifactItem(SchemaBase):
    """Single artifact metadata.

    ``path`` is an internal relative path under the EvoBind2 artifact root;
    the server absolute path is never exposed.  ``download_url`` provides a
    read-only, path-traversal-hardened download endpoint for the artifact.
    """

    name: str
    path: str = Field(..., description="Internal relative path under the artifact root.")
    artifact_type: str = Field(default="other", description="metrics | pdb | log | manifest | input | other")
    exists: bool
    size_bytes: int = Field(default=0)
    download_url: Optional[str] = Field(default=None)


class EvoBind2JobArtifactsResponse(SchemaBase):
    """Response body for GET /api/v1/evobind2/jobs/{job_id}/artifacts."""

    job_id: str
    status: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    safety_note: str = Field(
        default=(
            "These are computational prediction artifacts only. "
            "They are NOT_EXPERIMENTALLY_VALIDATED and must not be interpreted as "
            "experimentally confirmed binding peptides. No Kd, MIC, MM-GBSA, "
            "ipTM, pLDDT, RMSD, or RMSF values are experimental measurements."
        ),
    )
    artifacts: List[EvoBind2JobArtifactItem] = Field(default_factory=list)


class EvoBind2JobCancelResponse(SchemaBase):
    """Response body for POST /api/v1/evobind2/jobs/{job_id}/cancel."""

    job_id: str
    previous_status: str
    status: str
    message: str
