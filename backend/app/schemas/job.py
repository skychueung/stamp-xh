"""STAMP Platform — Pydantic Schemas for Job System (v0.9-P6)."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Job CRUD Schemas
# ---------------------------------------------------------------------------

class JobCreate(SchemaBase):
    project_id: str
    job_type: str = Field(..., max_length=100)
    input_json: Optional[dict] = Field(default_factory=dict)


class JobUpdate(SchemaBase):
    status: Optional[str] = Field(None, max_length=20)
    progress: Optional[int] = Field(None, ge=0, le=100)
    message: Optional[str] = None
    error_message: Optional[str] = None
    output_json: Optional[dict] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class JobResponse(SchemaBase):
    id: str
    project_id: str
    job_type: str
    status: str
    progress: Optional[int]
    message: Optional[str]
    error_message: Optional[str]
    input_json: Optional[dict]
    output_json: Optional[dict]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    updated_at: datetime


# ---------------------------------------------------------------------------
# Job List Response
# ---------------------------------------------------------------------------

class JobListResponse(SchemaBase):
    project_id: str
    total_count: int
    jobs: List[JobResponse]


# ---------------------------------------------------------------------------
# Job Run / Cancel Request/Response
# ---------------------------------------------------------------------------

class JobRunMockRequest(SchemaBase):
    """Request body for POST /api/v1/jobs/{job_id}/run-mock."""

    sleep_seconds: float = Field(default=0.5, ge=0, le=10)
    should_fail: bool = Field(default=False)
    fail_message: Optional[str] = Field(default="Mock failure for testing.")


class JobRunMockResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/run-mock."""

    job_id: str
    status: str
    message: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")


class JobCancelResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/cancel."""

    job_id: str
    previous_status: str
    status: str
    message: str


class JobStartResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/start."""

    job_id: str
    status: str
    progress: int
    message: str


class JobRetryResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/retry."""

    original_job_id: str
    new_job_id: str
    status: str
    message: str


class BepiPred3PersistResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/persist-bepipred3-results."""

    job_id: str
    scan_id: str
    candidate_count: int
    created_candidate_ids: list[str]
    status: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    prediction_status: str = Field(default="COMPUTATIONAL_PREDICTION_ONLY")
    skipped_count: int = Field(default=0)


class StructurePredictionPersistResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/persist-structure-prediction-results."""

    job_id: str
    candidate_id: str
    status: str = Field(default="COMPLETED")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    prediction_status: str = Field(default="COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY")
    mean_plddt: Optional[float] = None
    ptm: Optional[float] = None
    iptm: Optional[float] = None
    metrics_are_real: bool = Field(default=True)


class InterfaceQualityPersistResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/persist-interface-quality-results."""

    job_id: str
    candidate_id: str
    status: str = Field(default="COMPLETED")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    prediction_status: str = Field(default="COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY")
    pdockq: float
    interface_contact_count: Optional[int] = None
    interface_residue_plddt_mean: Optional[float] = None
    metrics_are_real: bool = Field(default=True)


class EnergyQualityPersistResponse(SchemaBase):
    """Response for POST /api/v1/jobs/{job_id}/persist-energy-quality-results."""

    job_id: str
    candidate_id: str
    status: str = Field(default="COMPLETED")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    prediction_status: str = Field(default="COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY")
    interaction_energy_kcal_mol: float
    energy_terms: Optional[dict] = None
    quality_flags: Optional[dict] = None
    metrics_are_real: bool = Field(default=True)


# ---------------------------------------------------------------------------
# Job Failure Diagnosis
# ---------------------------------------------------------------------------

class JobFailureDiagnosis(SchemaBase):
    """Structured failure diagnosis for a job."""

    job_id: str
    job_type: str
    status: str
    error_category: str = Field(..., description="One of: tool_missing, input_missing, invalid_parameter, command_failed, artifact_missing, permission_denied, storage_unwritable, gpu_locked, external_api_failed, unknown")
    cause: str = Field(..., description="Human-readable root cause")
    suggestions: List[str] = Field(default_factory=list, description="Actionable fix suggestions")
    related_logs: List[str] = Field(default_factory=list, description="Likely log file paths")
    related_artifacts: List[dict] = Field(default_factory=list, description="Likely artifact file paths")
    raw_error_message: Optional[str] = None
    raw_error_json: Optional[dict] = None
