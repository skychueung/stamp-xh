"""Base interface for model adapters in the unified Model Registry.

All adapters must inherit from BaseModelAdapter and return safety flags on
every operation.  Base and placeholder adapters never execute real models.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelSafetyFlags,
)
from app.services.target_peptide_model_registry import (
    MODEL_STATUS_DISABLED,
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
    get_model,
)


class BaseModelAdapter(ABC):
    """Common contract for every model adapter registered in P4A."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        model = get_model(model_id)
        if model is None:
            raise ValueError(f"Unknown model_id '{model_id}'")
        self.model_entry = model
        self.display_name = str(model.get("display_name", model_id))
        self.adapter_id = str(model.get("adapter_id", f"{model_id}_placeholder"))

    @property
    def supports_probe(self) -> bool:
        return bool(self.model_entry.get("supports_probe", False))

    @property
    def supports_dry_run(self) -> bool:
        return bool(self.model_entry.get("supports_dry_run", False))

    @property
    def supports_real_run(self) -> bool:
        return bool(self.model_entry.get("supports_real_run", False))

    @property
    def supports_structure_output(self) -> bool:
        return bool(self.model_entry.get("supports_structure_output", False))

    @property
    def supports_sequence_output(self) -> bool:
        return bool(self.model_entry.get("supports_sequence_output", False))

    @property
    def supports_ranking(self) -> bool:
        return bool(self.model_entry.get("supports_ranking", False))

    def get_capabilities(self) -> dict[str, Any]:
        """Return capability metadata for the model."""
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "adapter_id": self.adapter_id,
            "supports_probe": self.supports_probe,
            "supports_dry_run": self.supports_dry_run,
            "supports_real_run": self.supports_real_run,
            "supports_structure_output": self.supports_structure_output,
            "supports_sequence_output": self.supports_sequence_output,
            "supports_ranking": self.supports_ranking,
            "output_artifact_types": list(self.model_entry.get("output_artifact_types", [])),
            "status": str(self.model_entry.get("status", MODEL_STATUS_DISABLED)),
            "real_run_enabled": bool(self.model_entry.get("real_run_enabled", False)),
        }

    def _base_safety_flags(self) -> ModelSafetyFlags:
        return ModelSafetyFlags(**build_default_safety_flags())

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    @abstractmethod
    def probe(self) -> ModelProbeResult:
        """Return environment readiness metadata without running the model."""

    @abstractmethod
    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Plan a run without executing it."""

    def submit(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Submit a real run (blocked by default)."""
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message="Real execution is disabled in this phase.",
            safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit_dev_smoke(
        self,
        job: dict[str, Any],
        job_dir: Path,
        seed: int | None = None,
    ) -> None:
        """Dev-only minimal real-run smoke (P33U-D23 additive contract method).

        Default: not supported. Overridden by adapters that carry a hardened
        dev-smoke runner (DiffPepBuilderAdapter, PepHARAdapter) to delegate to
        SmokeRunnerAdapter with full provenance. The default registry
        ``submit()`` remains BLOCKED (read-only P31B / P31C / P30D); this is a
        separate opt-in contract for the Run Console's dev-smoke path, invoked
        via ``app.services.p33u.dev_smoke_dispatch.dispatch_dev_smoke``. Mutates
        the job dict in place; never returns a ModelDryRunResult.

        Forbidden: never writes dev-smoke as Top4 / primary, never claims
        experimental validation, never invokes PPFlow.
        """
        job["status"] = "blocked"
        job["failure_reason"] = (
            f"submit_dev_smoke not supported on adapter '{self.adapter_id}' "
            f"(model_id={self.model_id}); dev-smoke dispatch unavailable"
        )

    def cancel(self, job_id: str) -> dict[str, Any]:
        """Cancel a job if it exists.  Default is no-op for placeholders."""
        return {
            "model_id": self.model_id,
            "job_id": job_id,
            "status": "disabled",
            "message": "This model adapter does not support job cancellation in P4A.",
            "safety_flags": self._base_safety_flags().model_dump(),
        }

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Return status for a job.  Default is disabled for placeholders."""
        return {
            "model_id": self.model_id,
            "job_id": job_id,
            "status": "disabled",
            "message": "This model adapter does not support job status queries in P4A.",
            "safety_flags": self._base_safety_flags().model_dump(),
        }

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """List artifacts for a job.  Default is empty for placeholders."""
        return ModelArtifactsResponse(
            model_id=self.model_id,
            job_id=job_id,
            status="disabled",
            artifacts=[],
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def normalize_result(self, job_id: str) -> dict[str, Any]:
        """Normalize job result metadata.  Default is disabled for placeholders."""
        return {
            "model_id": self.model_id,
            "job_id": job_id,
            "status": "disabled",
            "message": "This model adapter does not support result normalization in P4A.",
            "safety_flags": self._base_safety_flags().model_dump(),
        }
