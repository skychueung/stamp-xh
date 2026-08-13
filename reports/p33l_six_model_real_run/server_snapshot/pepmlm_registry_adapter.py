"""PepMLM Registry Adapter (P30D).

Extends the existing PepMLMAdapter to expose P30B smoke-rerun-verified status
through the model-registry probe endpoint. This adapter does NOT run the model,
does NOT create jobs, and does NOT write artifacts. It only surfaces the
historical P30B smoke rerun evidence as a read-only probe result.

P30B evidence:
  - job_id: ac90e622-492d-4697-a8fa-ce35b2d2bfc5
  - status: succeeded
  - 3 candidates generated on CUDA (RTX 4090)
  - torch 2.4.1+cu118, transformers 4.57.6
  - validation_status: NOT_EXPERIMENTALLY_VALIDATED
  - Reasonix gate: GO_WITH_NOTES
  - real_run gate: CLOSED (final state after P30B)
"""
from __future__ import annotations

from typing import Any

from app.schemas.model_registry import (
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelSafetyFlags,
)
from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter, _real_run_allowed
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
)

# ---------------------------------------------------------------------------
# P30B Smoke Rerun Evidence (frozen, read-only)
# ---------------------------------------------------------------------------

P30B_SMOKE_JOB_ID = "ac90e622-492d-4697-a8fa-ce35b2d2bfc5"
P30B_SMOKE_GATE = "SMOKE_RERUN_GO"
P30B_REASONIX_GATE = "GO_WITH_NOTES"
P30B_CANDIDATE_COUNT = 3
P30B_TORCH_VERSION = "2.4.1+cu118"
P30B_TRANSFORMERS_VERSION = "4.57.6"
P30B_GPU = "NVIDIA GeForce RTX 4090"
P30B_DEVICE = "cuda"
P30B_USES_CUDA = True
P30B_STAGE = "P30B_SMOKE_RERUN_GO"
P30B_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"

P30B_CANDIDATES = [
    "KRTAALLALIAT",
    "KKTKKLLFAIAL",
    "KKTKAAALLLLT",
]


def _smoke_rerun_safety_flags() -> ModelSafetyFlags:
    """Safety flags for the smoke-rerun-verified probe result.

    runs_model=False means the probe itself does NOT run the model.
    It does not deny that P30B historically ran the model.
    """
    flags = build_default_safety_flags()
    flags["generated_candidates"] = False
    flags["generated_structure"] = False
    flags["generated_msa"] = False
    flags["executed_model"] = False
    flags["is_scientific_result"] = False
    flags["computational_prediction_only"] = True
    return ModelSafetyFlags(**flags)


class PepMLMRegistryAdapter(PepMLMAdapter):
    """PepMLM adapter that returns smoke_rerun_verified probe status.

    This adapter wraps the existing PepMLMAdapter and overrides probe() and
    dry_run() to reflect the P30B smoke rerun verification state. The underlying
    PepMLMAdapter's submit() and artifact methods remain unchanged but are
    never invoked by this adapter's probe or dry_run.
    """

    def __init__(self, model_id: str = "pepmlm") -> None:
        super().__init__(model_id)

    def probe(self) -> ModelProbeResult:
        """Return a read-only probe with smoke_rerun_verified status.

        This probe does NOT run the model, does NOT create a job, does NOT
        write artifacts. It only surfaces P30B historical smoke rerun evidence.
        """
        real_run_enabled = _real_run_allowed()
        real_run_status = "blocked" if not real_run_enabled else "open"
        blocked_reason = None if real_run_enabled else "real_run_gate_closed"

        safety = _smoke_rerun_safety_flags()

        detail: dict[str, Any] = {
            "last_smoke_job_id": P30B_SMOKE_JOB_ID,
            "last_smoke_gate": P30B_SMOKE_GATE,
            "last_smoke_reasonix_gate": P30B_REASONIX_GATE,
            "candidate_count": P30B_CANDIDATE_COUNT,
            "candidates": list(P30B_CANDIDATES),
            "uses_cuda": P30B_USES_CUDA,
            "device": P30B_DEVICE,
            "gpu": P30B_GPU,
            "torch_version": P30B_TORCH_VERSION,
            "transformers_version": P30B_TRANSFORMERS_VERSION,
            "real_run_enabled": real_run_enabled,
            "real_run_status": real_run_status,
            "real_run_blocked_reason": blocked_reason,
            "validation_status": P30B_VALIDATION_STATUS,
            "runs_model": False,
            "creates_job": False,
            "generates_candidates": False,
            "generates_pdb": False,
            "experimental_validation": False,
            "is_scientific_result": False,
        }

        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="smoke_rerun_verified",
            message=(
                "PepMLM probe completed without running the model. "
                "P30B smoke rerun verified (job ac90e622, 3 candidates on CUDA RTX 4090). "
                "real_run gate is CLOSED."
            ),
            probe_time=self._now(),
            adapter_id=self.adapter_id,
            safety_flags=safety,
            detail=detail,
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            stage=P30B_STAGE,
            real_run_status=real_run_status,
            real_run_blocked_reason=blocked_reason,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            creates_job=False,
            writes_artifacts=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            validation_status=P30B_VALIDATION_STATUS,
            mode="probe",
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Return a BLOCKED dry-run result.

        dry-run is blocked because real_run gate is closed. This does NOT
        create a job, does NOT write artifacts, does NOT run the model.
        """
        safety = _smoke_rerun_safety_flags()
        blocked_reasons = ["real_run_gate_closed"]

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message=(
                "PepMLM dry-run is BLOCKED: real_run gate is CLOSED. "
                "P30B smoke rerun verified but no new execution is allowed."
            ),
            run_id=None,
            artifacts={},
            command_preview=None,
            env_preview={},
            safety_flags=safety,
            validation_status=P30B_VALIDATION_STATUS,
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            blocked_reasons=blocked_reasons,
            creates_job=False,
            writes_artifacts=False,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            mode="dry_run",
            stage=P30B_STAGE,
            real_run_status="blocked",
            real_run_blocked_reason="real_run_gate_closed",
        )

    def submit(
        self, payload: ModelDryRunPayload, run_id: str | None = None
    ) -> ModelDryRunResult:
        """Submit is unconditionally BLOCKED.

        No job is created, no model is run, no artifacts are written.
        This overrides the parent PepMLMAdapter.submit() which would execute
        the model if the gate were open. In P30D, submit is always blocked
        unless a new authorization stage is explicitly opened.
        """
        safety = _smoke_rerun_safety_flags()
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message=(
                "PepMLM submit is BLOCKED in P30D. "
                "P30B smoke rerun verified but real execution requires a new authorization stage."
            ),
            run_id=None,
            artifacts={},
            command_preview=None,
            env_preview={},
            safety_flags=safety,
            validation_status=P30B_VALIDATION_STATUS,
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            blocked_reasons=["real_run_gate_closed", "p30d_submit_blocked"],
            creates_job=False,
            writes_artifacts=False,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            mode="submit",
            stage=P30B_STAGE,
            real_run_status="blocked",
            real_run_blocked_reason="real_run_gate_closed",
        )
