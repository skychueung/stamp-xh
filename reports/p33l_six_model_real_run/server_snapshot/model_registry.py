"""Schemas for the unified Model Registry and Adapter Interface (P4A).

All scientific outputs carry validation_status=NOT_EXPERIMENTALLY_VALIDATED
and safety_flags marking them as computational predictions only.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import ConfigDict, Field

from app.schemas.project import SchemaBase


class ModelSafetyFlags(SchemaBase):
    """Safety flags attached to every model adapter operation."""

    executed_model: bool = Field(default=False)
    generated_candidates: bool = Field(default=False)
    generated_structure: bool = Field(default=False)
    generated_msa: bool = Field(default=False)
    is_scientific_result: bool = Field(default=False)
    runs_model: bool = Field(default=False)
    generates_candidates: bool = Field(default=False)
    experimental_validation: bool = Field(default=False)
    computational_prediction_only: bool = Field(default=True)
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")


class ModelRegistryEntry(SchemaBase):
    """Standardized model metadata in the unified registry."""

    model_config = ConfigDict(from_attributes=True)

    model_id: str
    display_name: str
    category: str
    status: str = Field(
        ...,
        description=(
            "available | not_connected | planned | disabled | probed | "
            "parked | pending_probe | pending_registry"
        ),
    )
    status_reason: Optional[str] = Field(
        default=None,
        description="Short machine-readable reason for the current status (e.g. parked_due_to_cert_or_weight_access_issue).",
    )
    description: str
    supports_probe: bool = Field(default=False)
    supports_dry_run: bool = Field(default=False)
    supports_real_run: bool = Field(default=False)
    supports_structure_output: bool = Field(default=False)
    supports_sequence_output: bool = Field(default=False)
    supports_ranking: bool = Field(default=False)
    output_artifact_types: list[str] = Field(default_factory=list)
    adapter_id: str
    safety_note: str = Field(default="Computational prediction only; NOT_EXPERIMENTALLY_VALIDATED.")
    validation_policy: str = Field(
        default=(
            "All outputs are computational predictions. "
            "They are NOT_EXPERIMENTALLY_VALIDATED and must not be interpreted as "
            "experimentally confirmed binding peptides, Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF."
        )
    )
    real_run_enabled: bool = Field(default=False)
    stage: str = Field(default="P4A")
    notes: Optional[str] = None
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    # P32A display-only readiness fields (do not overwrite canonical stage)
    readiness_gate: Optional[str] = Field(default=None)
    readiness_level: Optional[str] = Field(default=None)
    execution_locked: bool = Field(default=True)
    blocker_code: Optional[str] = Field(default=None)
    next_authorization: Optional[str] = Field(default=None)
    last_verified_at: Optional[str] = Field(default=None)
    evidence_ref: Optional[str] = Field(default=None)
    # P33K product-group UI governance fields
    product_group: str = Field(
        default="unknown",
        description="available_six | reserved_placeholder | excluded",
    )
    ui_selectable: bool = Field(default=False)
    ui_execution_state: str = Field(
        default="unknown",
        description="probe_dry_run_available | locked_placeholder | excluded",
    )
    activation_requirements: str = Field(default="explicit authorization required")
    delivery_status: str = Field(default="unknown")


class ModelsListResponse(SchemaBase):
    """Response for GET /api/v1/models."""

    models: list[ModelRegistryEntry]
    scientific_boundary: str


class ModelRegistryStatusEntry(SchemaBase):
    """Compact status entry for the 8-model track dashboard."""

    model_id: str
    display_name: str
    status: str
    status_reason: Optional[str] = None
    stage: str
    supports_probe: bool = Field(default=False)
    supports_dry_run: bool = Field(default=False)
    supports_real_run: bool = Field(default=False)
    notes: Optional[str] = None
    # P33K product-group UI governance fields
    product_group: str = Field(
        default="unknown",
        description="available_six | reserved_placeholder | excluded",
    )
    ui_selectable: bool = Field(default=False)
    ui_execution_state: str = Field(
        default="unknown",
        description="probe_dry_run_available | locked_placeholder | excluded",
    )
    activation_requirements: str = Field(default="explicit authorization required")
    delivery_status: str = Field(default="unknown")


class ModelRegistryStatusResponse(SchemaBase):
    """Response for GET /api/v1/model-registry/status."""

    models: list[ModelRegistryStatusEntry]
    parked_models: list[str] = Field(default_factory=list)
    pending_probe_models: list[str] = Field(default_factory=list)
    pending_registry_models: list[str] = Field(default_factory=list)
    scientific_boundary: str
    count_total: int
    count_parked: int
    count_pending_probe: int
    count_pending_registry: int


class ModelDetailResponse(SchemaBase):
    """Response for GET /api/v1/models/{model_id}."""

    model: ModelRegistryEntry
    safety_flags: ModelSafetyFlags
    scientific_boundary: str


class ModelProbeResult(SchemaBase):
    """Response for GET /api/v1/models/{model_id}/probe."""

    model_id: str
    display_name: str
    status: str
    message: str
    probe_time: str
    adapter_id: str
    safety_flags: ModelSafetyFlags
    detail: dict[str, Any] = Field(default_factory=dict)
    scientific_boundary: str
    # P1 skeleton blocked fields (optional, populated for pending_registry adapters)
    available: Optional[bool] = Field(default=None)
    actionable: Optional[bool] = Field(default=None)
    probe_status: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    stage: Optional[str] = Field(default=None)
    runs_model: Optional[bool] = Field(default=None)
    generates_candidates: Optional[bool] = Field(default=None)
    experimental_validation: Optional[bool] = Field(default=None)
    is_scientific_result: Optional[bool] = Field(default=None)
    computational_prediction_only: Optional[bool] = Field(default=None)

    real_run_status: Optional[str] = Field(default=None)
    real_run_blocked_reason: Optional[str] = Field(default=None)
    generates_pdb: Optional[bool] = Field(default=None)
    creates_job: Optional[bool] = Field(default=None)
    writes_artifacts: Optional[bool] = Field(default=None)
    runs_subprocess: Optional[bool] = Field(default=None)
    would_use_checkpoint: Optional[str] = Field(default=None)
    would_use_env: Optional[str] = Field(default=None)
    mode: Optional[str] = Field(default=None)
    validation_status: Optional[str] = Field(default=None)


class ModelDryRunPayload(SchemaBase):
    """Request body for POST /api/v1/models/{model_id}/dry-run."""

    target_sequence: Optional[str] = Field(default=None, min_length=1)
    peptide_length: int = Field(default=10, ge=1, le=100)
    peptide_sequence: Optional[str] = Field(default=None)
    model_name: str = Field(default="model_1_ptm")
    max_recycles: int = Field(default=1, ge=1, le=10)
    num_iterations: int = Field(default=1, ge=1, le=100)
    dry_run: bool = Field(default=True)
    # PepMLM / PepPrCLIP / PepGLAD specific optional fields
    num_candidates: int = Field(default=5, ge=1, le=100)
    max_length: int = Field(default=10, ge=1, le=200)
    top_k: int = Field(default=3, ge=1, le=100)
    device: str = Field(default="auto")
    seed: Optional[int] = Field(default=None, ge=0)
    candidate_peptides: Optional[str | list[str]] = Field(default=None)
    # PepGLAD structure-conditioned inputs
    target_pdb_path: Optional[str] = Field(default=None)
    target_chain: str = Field(default="A", min_length=1, max_length=8)
    pocket_residues: Optional[list[str]] = Field(default=None)


class ModelDryRunResult(SchemaBase):
    """Response for POST /api/v1/models/{model_id}/dry-run."""

    model_id: str
    display_name: str
    status: str
    message: str
    run_id: Optional[str] = None
    artifacts: dict[str, Optional[str]] = Field(default_factory=dict)
    expected_artifacts: dict[str, Optional[str]] = Field(default_factory=dict)
    expected_inputs: dict[str, Any] = Field(default_factory=dict)
    expected_outputs: dict[str, Any] = Field(default_factory=dict)
    artifact_plan: dict[str, Any] = Field(default_factory=dict)
    command_preview: Optional[list[str]] = None
    env_preview: dict[str, str] = Field(default_factory=dict)
    environment_summary: dict[str, Any] = Field(default_factory=dict)
    blocked_reasons: list[str] = Field(default_factory=list)
    safety_flags: ModelSafetyFlags
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    scientific_boundary: str
    # P1 skeleton blocked fields (optional, populated for pending_registry adapters)
    available: Optional[bool] = Field(default=None)
    actionable: Optional[bool] = Field(default=None)
    dry_run_status: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    stage: Optional[str] = Field(default=None)
    runs_model: Optional[bool] = Field(default=None)
    generates_candidates: Optional[bool] = Field(default=None)
    experimental_validation: Optional[bool] = Field(default=None)
    is_scientific_result: Optional[bool] = Field(default=None)
    computational_prediction_only: Optional[bool] = Field(default=None)

    real_run_status: Optional[str] = Field(default=None)
    real_run_blocked_reason: Optional[str] = Field(default=None)
    generates_pdb: Optional[bool] = Field(default=None)
    creates_job: Optional[bool] = Field(default=None)
    writes_artifacts: Optional[bool] = Field(default=None)
    runs_subprocess: Optional[bool] = Field(default=None)
    would_use_checkpoint: Optional[str] = Field(default=None)
    would_use_env: Optional[str] = Field(default=None)
    mode: Optional[str] = Field(default=None)



class TargetDesignWorkflowPayload(SchemaBase):
    """Request body for POST /api/v1/workflows/target-design/dry-run."""

    target_sequence: str = Field(..., min_length=1)
    generator_model: str = Field(default="pepmlm")
    ranker_model: str = Field(default="pepprclip")
    structure_model: str = Field(default="evobind2")
    num_candidates: int = Field(default=3, ge=1, le=100)
    peptide_length: int = Field(default=12, ge=1, le=200)
    top_k: int = Field(default=3, ge=1, le=100)
    dry_run: bool = Field(default=True)


class WorkflowStep(SchemaBase):
    """Single step in a target-design workflow dry-run plan."""

    step_id: str
    name: str
    model_id: str
    status: str
    message: str
    blocked_reason: Optional[str] = Field(default=None)
    command_preview: Optional[list[str]] = Field(default=None)
    env_preview: dict[str, str] = Field(default_factory=dict)
    artifacts: dict[str, Optional[str]] = Field(default_factory=dict)
    expected_artifacts: dict[str, Optional[str]] = Field(default_factory=dict)


class WorkflowArtifactReference(SchemaBase):
    """Existing or planned artifact in the target-design workflow lineage."""

    label: str
    model_id: str
    job_id: Optional[str] = None
    artifact_name: str
    artifact_path: Optional[str] = None
    status: str
    reason: Optional[str] = None
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    download_url: Optional[str] = None


class TargetDesignWorkflowResult(SchemaBase):
    """Response for POST /api/v1/workflows/target-design/dry-run."""

    workflow_id: str
    workflow_type: str = Field(default="target-design")
    status: str
    message: str
    steps: list[WorkflowStep]
    expected_artifacts: dict[str, Optional[str]] = Field(default_factory=dict)
    safety_flags: ModelSafetyFlags
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    scientific_boundary: str
    # P1 skeleton blocked fields (optional, populated for pending_registry adapters)
    available: Optional[bool] = Field(default=None)
    actionable: Optional[bool] = Field(default=None)
    dry_run_status: Optional[str] = Field(default=None)
    reason: Optional[str] = Field(default=None)
    stage: Optional[str] = Field(default=None)
    runs_model: Optional[bool] = Field(default=None)
    generates_candidates: Optional[bool] = Field(default=None)
    experimental_validation: Optional[bool] = Field(default=None)
    blocked_reasons: list[str] = Field(default_factory=list)
    prior_artifacts_referenced: dict[str, Optional[str]] = Field(default_factory=dict)
    artifact_references: list[WorkflowArtifactReference] = Field(default_factory=list)


class ModelArtifactItem(SchemaBase):
    """Single artifact metadata returned by the unified model API."""

    name: str
    path: str = Field(..., description="Internal relative path under the artifact root.")
    artifact_type: str = Field(default="other")
    exists: bool
    size_bytes: int = Field(default=0)
    download_url: Optional[str] = None


class ModelArtifactsResponse(SchemaBase):
    """Response for GET /api/v1/models/{model_id}/jobs/{job_id}/artifacts."""

    model_id: str
    job_id: str
    status: str
    validation_status: str = Field(default="NOT_EXPERIMENTALLY_VALIDATED")
    safety_note: str = Field(
        default=(
            "These are computational prediction artifacts only. "
            "They are NOT_EXPERIMENTALLY_VALIDATED and must not be interpreted as "
            "experimentally confirmed binding peptides."
        )
    )
    artifacts: list[ModelArtifactItem] = Field(default_factory=list)
