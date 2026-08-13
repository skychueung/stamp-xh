"""STAMP Platform — Experimental Validation Schemas (v0.11-P1).

Pydantic models for wet-lab experimental validation runs and measurements.
All schemas enforce scientific-integrity constraints: no fabricated data,
no auto-promotion to EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.project import SchemaBase


# ---------------------------------------------------------------------------
# Enums as Literal strings (following existing codebase convention)
# ---------------------------------------------------------------------------

EXPERIMENT_TYPE_VALUES = [
    "MIC", "MBC", "HEMOLYSIS", "CYTOTOXICITY",
    "SERUM_STABILITY", "PROTEASE_STABILITY", "SALT_STABILITY",
    "BIOFILM", "RESISTANCE_INDUCTION", "OTHER",
]

RUN_STATUS_VALUES = ["PLANNED", "RUNNING", "COMPLETED", "FAILED", "INVALIDATED"]

VALIDATION_STATUS_VALUES = [
    "NOT_EXPERIMENTALLY_VALIDATED",
    "EXPERIMENT_PLANNED",
    "PARTIALLY_VALIDATED",
    "EXPERIMENTALLY_VALIDATED",
    "VALIDATION_FAILED",
]

METRIC_NAME_VALUES = [
    "MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent",
    "HC50_ug_ml", "IC50_ug_ml", "cell_viability_percent",
    "serum_half_life_min", "protease_remaining_percent",
    "biofilm_inhibition_percent",
]

QUALITY_FLAG_VALUES = ["PASS", "WARNING", "FAILED", "NEEDS_REVIEW"]


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class ExperimentalValidationRunBase(SchemaBase):
    """Base fields for an experimental validation run."""

    project_id: str
    candidate_id: str
    experiment_type: str = Field(..., max_length=50)
    organism: Optional[str] = Field(None, max_length=100)
    strain: Optional[str] = Field(None, max_length=100)
    protocol_name: Optional[str] = Field(None, max_length=255)
    protocol_version: Optional[str] = Field(None, max_length=50)
    operator: Optional[str] = Field(None, max_length=100)
    experiment_date: Optional[datetime] = None
    status: str = Field(default="PLANNED", max_length=20)
    notes: Optional[str] = None

    @field_validator("experiment_type")
    @classmethod
    def _validate_experiment_type(cls, v: str) -> str:
        if v not in EXPERIMENT_TYPE_VALUES:
            raise ValueError(f"experiment_type must be one of {EXPERIMENT_TYPE_VALUES}")
        return v

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: str) -> str:
        if v not in RUN_STATUS_VALUES:
            raise ValueError(f"status must be one of {RUN_STATUS_VALUES}")
        return v


class ExperimentalMeasurementBase(SchemaBase):
    """Base fields for an experimental measurement."""

    validation_run_id: str
    candidate_id: str
    metric_name: str = Field(..., max_length=50)
    value: Optional[float] = None
    unit: Optional[str] = Field(None, max_length=20)
    condition_json: dict[str, Any] = Field(default_factory=dict)
    replicate_id: Optional[str] = Field(None, max_length=20)
    raw_data_path: Optional[str] = Field(None, max_length=500)
    quality_flag: str = Field(default="PASS", max_length=20)

    @field_validator("metric_name")
    @classmethod
    def _validate_metric_name(cls, v: str) -> str:
        if v not in METRIC_NAME_VALUES:
            raise ValueError(f"metric_name must be one of {METRIC_NAME_VALUES}")
        return v

    @field_validator("quality_flag")
    @classmethod
    def _validate_quality_flag(cls, v: str) -> str:
        if v not in QUALITY_FLAG_VALUES:
            raise ValueError(f"quality_flag must be one of {QUALITY_FLAG_VALUES}")
        return v

    @field_validator("value")
    @classmethod
    def _validate_value(cls, v: Optional[float], info) -> Optional[float]:
        if v is None:
            return v
        data = info.data
        metric = data.get("metric_name", "")
        if metric in ("MIC_ug_ml", "MBC_ug_ml") and v < 0:
            raise ValueError(f"{metric} must be >= 0")
        if metric in ("hemolysis_percent", "cell_viability_percent", "protease_remaining_percent", "biofilm_inhibition_percent") and not (0 <= v <= 100):
            raise ValueError(f"{metric} must be between 0 and 100")
        return v


# ---------------------------------------------------------------------------
# Create / Update / Response
# ---------------------------------------------------------------------------

class ExperimentalValidationRunCreate(ExperimentalValidationRunBase):
    """Schema for creating a new validation run."""

    pass


class ExperimentalValidationRunUpdate(BaseModel):
    """Schema for updating a validation run (partial)."""

    model_config = ConfigDict(from_attributes=True)

    status: Optional[str] = Field(None, max_length=20)
    validation_status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None
    experiment_date: Optional[datetime] = None
    operator: Optional[str] = Field(None, max_length=100)

    @field_validator("status")
    @classmethod
    def _validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in RUN_STATUS_VALUES:
            raise ValueError(f"status must be one of {RUN_STATUS_VALUES}")
        return v


class ExperimentalValidationRunResponse(ExperimentalValidationRunBase):
    """Schema for returning a validation run."""

    id: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED", max_length=50)
    created_at: datetime
    updated_at: datetime


class ExperimentalMeasurementCreate(ExperimentalMeasurementBase):
    """Schema for creating a new measurement."""

    pass


class ExperimentalMeasurementResponse(ExperimentalMeasurementBase):
    """Schema for returning a measurement."""

    id: str
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Aggregated / Summary schemas
# ---------------------------------------------------------------------------

class ExperimentalValidationSummaryResponse(BaseModel):
    """Summary of all experimental validation data for a candidate."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    overall_validation_status: str
    run_count: int
    completed_run_count: int
    measurements: list[ExperimentalMeasurementResponse]


class CandidateExperimentalPriorityResponse(BaseModel):
    """Candidate priority response including experimental data."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    composite_score: Optional[float] = None
    experimental_priority_score: Optional[float] = None
    priority_status: str
    computational_score_contribution: Optional[float] = None
    structure_support_contribution: Optional[float] = None
    experimental_activity_contribution: Optional[float] = None
    safety_contribution: Optional[float] = None
    validation_status: str
    has_experimental_data: bool


class ProjectExperimentalValidationSummaryResponse(BaseModel):
    """Project-level summary of experimental validation coverage."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    total_candidates: int
    candidates_with_experimental_data: int
    candidates_fully_validated: int
    candidates_failed_validation: int
    candidates_pending: int
    experiment_type_counts: dict[str, int]
    validation_status_counts: dict[str, int]
    measurement_counts: dict[str, int]
    coverage: dict[str, Any]
    top_priority_candidates: list[dict[str, Any]]


class CsvImportError(BaseModel):
    """Single row error from CSV import."""

    row: int
    candidate_id: str
    reason: str


class CsvImportResultResponse(BaseModel):
    """Result of CSV measurement import."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    total_rows: int
    success_count: int
    failed_count: int
    created_run_count: int
    created_measurement_count: int
    errors: list[CsvImportError]


# ---------------------------------------------------------------------------
# v0.11-P4: Candidate prioritization
# ---------------------------------------------------------------------------

class PriorityDecisionCreate(BaseModel):
    """Schema for creating a manual priority decision."""

    decision: str = Field(..., max_length=50)
    decision_reason: str = Field(..., min_length=1)
    reviewer: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = None

    @field_validator("decision")
    @classmethod
    def _validate_decision(cls, v: str) -> str:
        valid = {"SHORTLIST", "HOLD", "REJECT", "NEEDS_REPEAT_EXPERIMENT"}
        if v not in valid:
            raise ValueError(f"decision must be one of {sorted(valid)}")
        return v


class PriorityDecisionResponse(BaseModel):
    """Response after saving a priority decision."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    decision: dict[str, Any]
    composite_score: Optional[float] = None
    validation_status: str


class CandidatePrioritizationItem(BaseModel):
    """Single candidate in the prioritization list."""

    model_config = ConfigDict(from_attributes=True)

    candidate_id: str
    sequence: str
    composite_score: Optional[float] = None
    experimental_priority_score: Optional[float] = None
    priority_status: str
    validation_status: str
    computational_summary: dict[str, Any]
    experimental_summary: dict[str, Any]
    run_count: int
    measurement_count: int
    decision: Optional[dict[str, Any]] = None


class ProjectCandidatePrioritizationResponse(BaseModel):
    """Full project prioritization response."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    summary: dict[str, int]
    candidates: list[CandidatePrioritizationItem]


# ---------------------------------------------------------------------------
# v0.11-P5: Wet-lab validation report export
# ---------------------------------------------------------------------------

class WetlabValidationReportResponse(BaseModel):
    """Response wrapper for wet-lab validation report export (JSON format)."""

    model_config = ConfigDict(from_attributes=True)

    project_id: str
    report_type: str
    generated_at: str
    scientific_boundary: dict[str, bool]
    summary: dict[str, Any]
    candidates: list[dict[str, Any]]
