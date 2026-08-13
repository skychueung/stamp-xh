"""Placeholder adapter for models that are not connected or planned in P4A."""

from __future__ import annotations

from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
)
from app.services.model_adapters.base import BaseModelAdapter
from app.services.target_peptide_model_registry import (
    MODEL_STATUS_DISABLED,
    MODEL_STATUS_PENDING_REGISTRY,
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
    get_model,
)


class PlaceholderAdapter(BaseModelAdapter):
    """Adapter for models in parked / pending_registry / disabled / planned states.

    This adapter never runs a model, never generates candidates, and always
    returns safety flags marking the result as a non-scientific placeholder.
    The returned status mirrors the registry status so the UI can show
    parked / pending_registry without claiming the model is disabled.
    """

    def _is_pending_registry(self) -> bool:
        """Return True when the registered model is in pending_registry state."""
        model = get_model(self.model_id)
        if model is None:
            return False
        return str(model.get("status", "")) == MODEL_STATUS_PENDING_REGISTRY

    def _pending_registry_reason(self) -> str:
        """Return the machine-readable reason from registry or a default."""
        return str(
            self.model_entry.get("status_reason", "pending_registry_skeleton_not_yet_implemented")
        )

    def _pending_registry_probe_detail(self) -> dict:
        return {
            "available": False,
            "actionable": False,
            "probe_status": "blocked",
            "reason": self._pending_registry_reason(),
            "stage": "P1_SKELETON",
            "runs_model": False,
            "generates_candidates": False,
            "experimental_validation": False,
        }

    def probe(self) -> ModelProbeResult:
        """Return a read-only probe result without touching any runtime."""
        if self._is_pending_registry():
            detail = self._pending_registry_probe_detail()
            return ModelProbeResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status=MODEL_STATUS_PENDING_REGISTRY,
                message="Adapter skeleton registered. Real model execution is not enabled in this stage.",
                probe_time=self._now(),
                adapter_id=self.adapter_id,
                safety_flags=self._base_safety_flags(),
                detail=detail,
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                available=detail["available"],
                actionable=detail["actionable"],
                probe_status=detail["probe_status"],
                reason=detail["reason"],
                stage=detail["stage"],
                runs_model=detail["runs_model"],
                generates_candidates=detail["generates_candidates"],
                experimental_validation=detail["experimental_validation"],
            )

        model = get_model(self.model_id)
        status = str(model.get("status", MODEL_STATUS_DISABLED)) if model else MODEL_STATUS_DISABLED
        reason = (
            f"{self.display_name} is registered with status '{status}'. "
            "No probe, no runtime check, and no model execution are performed."
        )
        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=status,
            message=reason,
            probe_time=self._now(),
            adapter_id=self.adapter_id,
            safety_flags=self._base_safety_flags(),
            detail={"placeholder": True, "status": status},
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Return a dry-run result without planning any execution."""
        if self._is_pending_registry():
            reason = self._pending_registry_reason()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message="Adapter skeleton registered. Real model execution is not enabled in this stage.",
                run_id=None,
                artifacts={},
                expected_artifacts={},
                command_preview=None,
                env_preview={},
                environment_summary={},
                blocked_reasons=[reason],
                safety_flags=self._base_safety_flags(),
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                available=False,
                actionable=False,
                dry_run_status="blocked",
                reason=reason,
                stage="P1_SKELETON",
                runs_model=False,
                generates_candidates=False,
                experimental_validation=False,
            )

        model = get_model(self.model_id)
        status = str(model.get("status", MODEL_STATUS_DISABLED)) if model else MODEL_STATUS_DISABLED
        reason = (
            f"{self.display_name} is registered with status '{status}'. "
            "Dry-run is not available and no command is generated."
        )
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=status.upper(),
            message=reason,
            run_id=None,
            artifacts={},
            expected_artifacts={},
            command_preview=None,
            env_preview={},
            environment_summary={},
            blocked_reasons=[],
            safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Always block real submission for placeholder models."""
        model_status = self.model_entry.get("status", MODEL_STATUS_DISABLED)
        if self._is_pending_registry():
            reason = self._pending_registry_reason()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message=(
                    f"{self.display_name} is registered with status '{model_status}' "
                    "and cannot accept submissions. Adapter skeleton only; real execution is disabled."
                ),
                run_id=None,
                artifacts={},
                expected_artifacts={},
                command_preview=None,
                env_preview={},
                environment_summary={},
                blocked_reasons=[reason],
                safety_flags=self._base_safety_flags(),
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                available=False,
                actionable=False,
                dry_run_status="blocked",
                reason=reason,
                stage="P1_SKELETON",
                runs_model=False,
                generates_candidates=False,
                experimental_validation=False,
            )

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message=(
                f"{self.display_name} is registered with status '{model_status}' "
                "and cannot accept submissions. Select a pending_probe or available model to probe / dry-run."
            ),
            run_id=None,
            artifacts={},
            expected_artifacts={},
            command_preview=None,
            env_preview={},
            environment_summary={},
            blocked_reasons=[],
            safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """Return an empty artifact list with a clear disabled message."""
        return ModelArtifactsResponse(
            model_id=self.model_id,
            job_id=job_id,
            status="disabled",
            artifacts=[],
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )
