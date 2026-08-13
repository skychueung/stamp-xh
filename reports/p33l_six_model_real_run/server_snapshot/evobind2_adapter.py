"""EvoBind2 adapter for the unified Model Registry.

This adapter delegates to the existing EvoBind2 wrapper, job service, and
probe functions.  Real execution remains blocked unless the real-run gate is
explicitly opened.
"""

from __future__ import annotations

from typing import Any

from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelSafetyFlags,
)
from app.services.compute_wrappers.evobind2_wrapper import (
    DEFAULT_MODEL_NAME,
    EVOBIND2_REAL_RUN_ENABLED,
    EvoBind2Input,
    dry_run_plan,
    probe,
)
from app.services.evobind2_job_service import (
    EVOBIND2_ARTIFACT_ROOT,
    get_evobind2_job,
    get_evobind2_job_artifacts,
)
from app.services.model_adapters.base import BaseModelAdapter
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
)


def _normalize_target_sequence(sequence: str) -> str:
    """Ensure target sequence is in FASTA format for downstream validation.

    The model registry accepts raw amino-acid strings; the EvoBind2 wrapper
    requires a FASTA header.  If the input already has a header, return it
    unchanged.
    """
    if sequence.startswith(">"):
        return sequence
    return f">target\n{sequence}"


class EvoBind2Adapter(BaseModelAdapter):
    """Standardized adapter wrapping the existing EvoBind2 runtime skeleton."""

    def __init__(self, model_id: str = "evobind2") -> None:
        super().__init__(model_id)

    def _base_safety_flags(self) -> ModelSafetyFlags:
        flags = build_default_safety_flags()
        flags["generated_structure"] = False
        flags["generated_candidates"] = False
        flags["generated_msa"] = False
        flags["executed_model"] = False
        flags["is_scientific_result"] = False
        flags["computational_prediction_only"] = True
        return ModelSafetyFlags(**flags)

    def probe(self) -> ModelProbeResult:
        """Delegate to the existing EvoBind2 read-only probe."""
        result = probe()
        status = str(result.get("status", "UNAVAILABLE"))
        message = str(
            result.get("message", "EvoBind2 probe completed without running the model")
        )
        safety = self._base_safety_flags()
        safety.executed_model = False
        safety.generated_structure = False

        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=status,
            message=message,
            probe_time=self._now(),
            adapter_id=self.adapter_id,
            safety_flags=safety,
            detail={
                "dry_run_status": result.get("dry_run_status"),
                "real_run_status": result.get("real_run_status"),
                "install_status": result.get("install_status"),
                "checks": result.get("checks", []),
                "warnings": result.get("warnings", []),
                "errors": result.get("errors", []),
                "gpu_devices": result.get("gpu_devices", []),
                "real_run_enabled": result.get("real_run_enabled", False),
                "resolved_paths": result.get("resolved_paths", {}),
                "legacy_fallback_warning": any(
                    str(item).startswith("legacy_fallback_warning:")
                    for item in result.get("warnings", [])
                ),
                "runs_model": False,
                "generates_candidates": False,
                "experimental_validation": False,
                "is_scientific_result": False,
                "computational_prediction_only": True,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            },
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Delegate to the existing EvoBind2 dry-run planner."""
        run_id = f"evobind2_dryrun_{self._now().replace(':', '_').replace('+', '_')}"
        inp = EvoBind2Input(
            run_id=run_id,
            receptor_fasta=_normalize_target_sequence(payload.target_sequence),
            peptide_length=payload.peptide_length,
            mode="predict_only",
            peptide_sequence=payload.peptide_sequence,
            model_name=payload.model_name or DEFAULT_MODEL_NAME,
            max_recycles=payload.max_recycles,
            num_iterations=payload.num_iterations,
            use_gpu=True,
            selected_gpu="auto",
            msa_mode="single_sequence",
        )
        plan = dry_run_plan(inp)

        safety = self._base_safety_flags()
        safety.is_scientific_result = False
        safety.executed_model = False

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=plan.status,
            message="EvoBind2 dry-run planned without executing the model.",
            run_id=run_id,
            artifacts={},
            expected_inputs={
                "target_sequence": "provided_in_request",
                "peptide_length": payload.peptide_length,
                "model_name": payload.model_name or DEFAULT_MODEL_NAME,
            },
            expected_outputs=plan.artifacts,
            command_preview=plan.command_preview,
            env_preview=plan.env_preview,
            environment_summary={
                "path_only_preview": True,
                "subprocess_runner_invoked": False,
                "directory_created": False,
                "artifacts_written": False,
                "runs_model": False,
                "generates_candidates": False,
                "experimental_validation": False,
                "is_scientific_result": False,
                "computational_prediction_only": True,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            },
            blocked_reasons=["real_run_gate_blocked"],
            safety_flags=safety,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Block real submission unless the real-run gate is open."""
        if not EVOBIND2_REAL_RUN_ENABLED:
            safety = self._base_safety_flags()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message="EvoBind2 real execution is disabled (real_run_enabled=false).",
                run_id=None,
                artifacts={},
                command_preview=None,
                env_preview={},
                safety_flags=safety,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            )
        # Gate-open path is intentionally left unimplemented in P4A.
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message="EvoBind2 real submission gate is open but P4A adapter intentionally blocks submit.",
            run_id=None,
            artifacts={},
            command_preview=None,
            env_preview={},
            safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def get_status(self, job_id: str) -> dict[str, Any]:
        """Return job status via the existing EvoBind2 job service."""
        from app.database import SessionLocal

        with SessionLocal() as db:
            job = get_evobind2_job(db, job_id)
            if job is None:
                return {
                    "model_id": self.model_id,
                    "job_id": job_id,
                    "status": "not_found",
                    "message": f"EvoBind2 job '{job_id}' not found.",
                    "safety_flags": self._base_safety_flags().model_dump(),
                }
            return {
                "model_id": self.model_id,
                "job_id": job_id,
                "status": job.status,
                "message": job.message,
                "safety_flags": self._base_safety_flags().model_dump(),
            }

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """List artifacts via the existing EvoBind2 job service."""
        from app.database import SessionLocal

        with SessionLocal() as db:
            job = get_evobind2_job(db, job_id)
            if job is None:
                return ModelArtifactsResponse(
                    model_id=self.model_id,
                    job_id=job_id,
                    status="not_found",
                    artifacts=[],
                    validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                    scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                )

            artifact_dicts = get_evobind2_job_artifacts(db, job_id)
            artifacts = [
                {
                    "name": a["name"],
                    "path": a["path"],
                    "artifact_type": a.get("artifact_type", "other"),
                    "exists": a["exists"],
                    "size_bytes": a["size_bytes"],
                    "download_url": f"/api/v1/models/{self.model_id}/jobs/{job_id}/artifacts/{a['name']}/download",
                }
                for a in artifact_dicts
            ]
            return ModelArtifactsResponse(
                model_id=self.model_id,
                job_id=job_id,
                status=job.status,
                artifacts=artifacts,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            )
