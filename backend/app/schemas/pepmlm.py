"""STAMP Platform — Pydantic Schemas for PepMLM Job (v0.10-P3a)."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class SchemaBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PepMLMJobInput(SchemaBase):
    """Input schema for pepmlm_generation jobs."""

    project_id: str
    epitope_id: Optional[str] = None
    epitope_sequence: Optional[str] = Field(None, max_length=1000)
    sidecar_url: str = Field(default="http://127.0.0.1:5011", max_length=500)
    top_k: int = Field(default=10, ge=1, le=100)
    linker_seq: str = Field(default="GGGGS", max_length=100)
    parameters: Optional[dict] = Field(default_factory=dict)


class PepMLMPersistResponse(SchemaBase):
    """Response for POST /jobs/{job_id}/persist-pepmlm-results."""

    job_id: str
    generation_run_id: str
    candidate_count: int
    created_candidate_ids: list[str]
    status: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    generation_status: str = Field(default="COMPUTATIONAL_GENERATION_STUB_ONLY")
    real_model_loaded: bool = Field(default=False)
