"""STAMP Platform — BepiPred3 Sidecar Schemas (v0.10-P1a).

Pydantic models for BepiPred3 HTTP sidecar job input/output.
All predictions are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Job Input
# ---------------------------------------------------------------------------


class BepiPred3JobInput(SchemaBase):
    """Input payload for a bepipred3_scan job.

    Either ``sequence`` or ``target_protein_id`` must be provided.
    If ``target_protein_id`` is given and ``sequence`` is absent,
    the service layer will look up the sequence from the database.
    """

    project_id: str
    target_protein_id: Optional[str] = Field(default=None)
    sequence: Optional[str] = Field(default=None, min_length=10, max_length=5000)
    sidecar_url: str = Field(default="http://127.0.0.1:5001/api/predict", max_length=500)
    parameters: Optional[dict] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Job Output
# ---------------------------------------------------------------------------


class BepiPred3JobOutput(SchemaBase):
    """Summary output written to Job.output_json after a bepipred3_scan run."""

    job_type: str = Field(default="bepipred3_scan")
    mode: str = Field(default="BEPIPRED3_HTTP_SIDECAR")
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    prediction_status: str = Field(default="COMPUTATIONAL_PREDICTION_ONLY")
    target_protein_id: Optional[str] = None
    candidate_count: int = Field(default=0, ge=0)
    raw_result_summary: dict = Field(default_factory=dict)
    sidecar_url: str = Field(default="http://127.0.0.1:5001/api/predict")


# ---------------------------------------------------------------------------
# Sidecar Request / Response helpers
# ---------------------------------------------------------------------------


class BepiPred3SidecarRequest(SchemaBase):
    """Payload sent TO the BepiPred3 sidecar HTTP endpoint."""

    sequence: str = Field(..., min_length=10, max_length=5000)
    parameters: Optional[dict] = Field(default_factory=dict)


class BepiPred3SidecarResponse(SchemaBase):
    """Expected payload returned FROM the BepiPred3 sidecar."""

    model_config = ConfigDict(extra="allow")

    status: str = Field(default="success")
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    message: Optional[str] = None
