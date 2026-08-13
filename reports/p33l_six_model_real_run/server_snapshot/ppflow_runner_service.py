"""PPFlow runner service skeleton — P29F.

This module provides the service layer that wraps ``ppflow_real_runner``.
It exposes a clean interface for the adapter / API to:

* Check the real-run gate.
* Plan a run (construct paths, command, manifest — without executing).
* Return a BLOCKED result with manifest/failure schemas.

P29F does **not** execute PPFlow, does not import PPFlow source, does not
``torch.load``, does not generate candidates or PDB, does not create real
job/artifact directories, and does not open the real-run gate.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.ppflow_real_runner import (
    STAGE,
    VALIDATION_STATUS,
    DISCLAIMER,
    check_gate,
    plan_run,
    generate_job_id,
    job_dir_path,
    artifact_dir_path,
    log_file_path,
    build_command,
    build_manifest_post,
    build_failure,
    validate_out_root,
    validate_source_path,
    validate_checkpoint_path,
    PPFlowRunnerBlocked,
    GATE_FILE,
    SOURCE_ROOT,
    CODESIGN_PP,
    DEFAULT_CHECKPOINT,
    ENV_PYTHON,
    JOBS_BASE,
    ARTIFACTS_BASE,
    LOGS_BASE,
    FORBIDDEN_PREFIXES,
)

# Re-export constants for external consumers
__all__ = [
    "PPFlowRunnerService",
    "check_gate",
    "plan_run",
    "generate_job_id",
    "build_command",
    "build_manifest_post",
    "build_failure",
    "STAGE",
    "VALIDATION_STATUS",
    "DISCLAIMER",
    "GATE_FILE",
]


class PPFlowRunnerService:
    """Service-layer wrapper around the PPFlow real runner skeleton.

    All methods are **non-executing**: they plan, validate, and return
    BLOCKED results.  No subprocess is spawned, no directory is created,
    no gate is opened.
    """

    def __init__(
        self,
        *,
        gate_file: Path | None = None,
        jobs_base: Path | None = None,
        artifacts_base: Path | None = None,
        logs_base: Path | None = None,
    ) -> None:
        self.gate_file = gate_file or GATE_FILE
        self.jobs_base = jobs_base or JOBS_BASE
        self.artifacts_base = artifacts_base or ARTIFACTS_BASE
        self.logs_base = logs_base or LOGS_BASE

    # -- gate ---------------------------------------------------------------

    def check_gate(self) -> dict[str, Any]:
        """Check whether the real-run gate is open (always closed in P29F)."""
        return check_gate(self.gate_file)

    # -- path planning ------------------------------------------------------

    def plan_paths(self, job_id: str | None = None) -> dict[str, Any]:
        """Return planned job/artifact/log paths without creating them."""
        jid = job_id or generate_job_id()
        return {
            "job_id": jid,
            "job_dir": str(job_dir_path(jid, base=self.jobs_base)),
            "artifact_dir": str(artifact_dir_path(jid, base=self.artifacts_base)),
            "log_file": str(log_file_path(jid, base=self.logs_base)),
            "paths_created": False,
            "stage": STAGE,
        }

    # -- command preview ----------------------------------------------------

    def command_preview(
        self,
        *,
        job_id: str | None = None,
        config_path: Path | str | None = None,
        checkpoint: Path | str | None = None,
        device: str = "cpu",
        batch_size: int = 1,
        tag: str = "smoke",
        seed: int | None = None,
        index: int = 0,
    ) -> dict[str, Any]:
        """Return a CLI command preview without executing it.

        If path validation fails, the returned dict includes ``path_errors``
        and ``command_preview`` is an empty list.
        """
        jid = job_id or generate_job_id()
        a_dir = artifact_dir_path(jid, base=self.artifacts_base)

        try:
            cmd = build_command(
                env_python=ENV_PYTHON,
                source_root=SOURCE_ROOT,
                codesign_pp=CODESIGN_PP,
                config_path=config_path,
                checkpoint=checkpoint or DEFAULT_CHECKPOINT,
                out_root=a_dir,
                tag=tag,
                seed=seed,
                device=device,
                batch_size=batch_size,
                index=index,
            )
            errors: list[str] = []
        except PPFlowRunnerBlocked as exc:
            cmd = []
            errors = [str(exc)]

        return {
            "job_id": jid,
            "command_preview": cmd,
            "path_errors": errors,
            "stage": STAGE,
            "executed": False,
            "subprocess_called": False,
        }

    # -- full plan ----------------------------------------------------------

    def plan_run(
        self,
        *,
        job_id: str | None = None,
        config_path: Path | str | None = None,
        checkpoint: Path | str | None = None,
        device: str = "cpu",
        batch_size: int = 1,
        tag: str = "smoke",
        seed: int | None = None,
        index: int = 0,
    ) -> dict[str, Any]:
        """Plan a full PPFlow run.

        Delegates to ``ppflow_real_runner.plan_run``.  Always returns
        ``status="blocked"`` in P29F.
        """
        jid = job_id or generate_job_id()
        return plan_run(
            job_id=jid,
            config_path=config_path,
            checkpoint=checkpoint,
            device=device,
            batch_size=batch_size,
            tag=tag,
            seed=seed,
            index=index,
            jobs_base=self.jobs_base,
            artifacts_base=self.artifacts_base,
            logs_base=self.logs_base,
        )

    # -- schemas ------------------------------------------------------------

    def build_manifest_post(
        self,
        job_id: str,
        status: str = "planned",
        artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Build a manifest_post schema dict."""
        return build_manifest_post(
            job_id=job_id,
            status=status,
            artifacts=artifacts,
        )

    def build_failure(
        self,
        job_id: str,
        error_type: str = "gate_closed",
        message: str = "",
    ) -> dict[str, Any]:
        """Build a failure schema dict."""
        return build_failure(
            job_id=job_id,
            error_type=error_type,
            message=message,
        )

    # -- status summary -----------------------------------------------------

    def status_summary(self) -> dict[str, Any]:
        """Return a summary of the runner's current (P29F skeleton) state."""
        gate = self.check_gate()
        return {
            "model_id": "ppflow",
            "stage": STAGE,
            "runner_skeleton_implemented": True,
            "real_runner_implemented": False,
            "real_run_enabled": False,
            "executes_codesign_ppf": False,
            "imports_ppflow_source": False,
            "uses_torch_load": False,
            "runs_model": False,
            "generates_candidates": False,
            "generates_pdb": False,
            "validation_status": VALIDATION_STATUS,
            "disclaimer": DISCLAIMER,
            "gate": gate,
            "submit_enabled": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
