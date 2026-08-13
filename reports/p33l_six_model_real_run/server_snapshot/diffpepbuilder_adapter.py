"""DiffPepBuilder adapter for P31B.

Read-only probe/dry-run adapter. Uses the dedicated py39 env if
DIFFPEPBUILDER_PYTHON is unset. Real execution is unconditionally blocked.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from app.schemas.model_registry import ModelArtifactsResponse, ModelDryRunPayload, ModelDryRunResult, ModelProbeResult
from app.services.model_adapters.base import BaseModelAdapter
from app.services.model_adapters.p32b_evidence_loader import p32b_evidence_ok
from app.services.target_peptide_model_registry import SCIENTIFIC_BOUNDARY_NOTE

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_DIR = MODEL_ROOT / "source" / "diffpepbuilder"
WEIGHTS_DIR = MODEL_ROOT / "weights" / "diffpepbuilder"
CHECKPOINT_DIR = MODEL_ROOT / "checkpoints" / "diffpepbuilder"
CACHE_DIR = MODEL_ROOT / "cache" / "diffpepbuilder"
ARTIFACT_ROOT = MODEL_ROOT / "artifacts" / "diffpepbuilder"
REPORTS_DIR = Path("/home/xh/kxc/stampup/reports")
GATE_FILE = CHECKPOINT_DIR / ".real_run_enabled"
PYTHON_ENV_VAR = "DIFFPEPBUILDER_PYTHON"
DEFAULT_PYTHON = str(MODEL_ROOT / "envs" / "diffpepbuilder_py39" / "bin" / "python")
REAL_RUN_ENV_VAR = "STAMP_DIFFPEPBUILDER_REAL_RUN_ENABLED"
ENV_PROBE_REPORT = REPORTS_DIR / "diffpepbuilder_p31b_env_probe.json"
FORWARD_PROBE_REPORT = REPORTS_DIR / "diffpepbuilder_p31b_forward_probe.json"
RUNNER_SCRIPT = Path("/mnt/sdb/kxc/stamp_models/scripts/stamp_diffpepbuilder_p31b_smoke_runner.py")
_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class DiffPepBuilderAdapter(BaseModelAdapter):
    """Probe and plan DiffPepBuilder without importing or running the model."""

    @staticmethod
    def _under_model_root(path: Path) -> bool:
        try:
            path.relative_to(MODEL_ROOT)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_true(value: str | None) -> bool:
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}

    def _python_path(self) -> str:
        configured = os.environ.get(PYTHON_ENV_VAR, "").strip()
        if configured:
            return configured
        # Only default to the known env when source/resources are actually present.
        if SOURCE_DIR.is_dir() or WEIGHTS_DIR.is_dir():
            return DEFAULT_PYTHON
        return ""

    def _read_env_probe_report(self) -> dict | None:
        if not ENV_PROBE_REPORT.is_file():
            return None
        try:
            with ENV_PROBE_REPORT.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _read_forward_probe_report(self) -> dict | None:
        if not FORWARD_PROBE_REPORT.is_file():
            return None
        try:
            with FORWARD_PROBE_REPORT.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _environment_summary(self, *, check_python: bool) -> tuple[dict, list[str]]:
        python_path = self._python_path()
        resource_paths = {
            "source_dir": SOURCE_DIR,
            "weights_dir": WEIGHTS_DIR,
            "checkpoint_dir": CHECKPOINT_DIR,
            "cache_dir": CACHE_DIR,
            "artifact_root": ARTIFACT_ROOT,
        }
        blocked_reasons: list[str] = []
        path_guard = {name: self._under_model_root(path) for name, path in resource_paths.items()}
        if not SOURCE_DIR.is_dir():
            blocked_reasons.append("missing_source")
        if not WEIGHTS_DIR.is_dir():
            blocked_reasons.append("missing_weights")
        if not CHECKPOINT_DIR.is_dir():
            blocked_reasons.append("missing_checkpoints")
        if not all(path_guard.values()):
            blocked_reasons.append("model_resource_path_outside_allowed_root")
        if not Path(python_path).is_file():
            blocked_reasons.append("missing_python")

        python_version = None
        python_check_status = "not_run"
        if check_python:
            try:
                completed = subprocess.run(
                    [python_path, "--version"], capture_output=True, check=False, text=True, timeout=10
                )
                python_version = (completed.stdout or completed.stderr).strip() or None
                python_check_status = "ok" if completed.returncode == 0 else "failed"
                if completed.returncode != 0:
                    blocked_reasons.append("python_version_check_failed")
            except (OSError, subprocess.SubprocessError):
                python_check_status = "failed"
                blocked_reasons.append("python_version_check_failed")

        gate_file_exists = GATE_FILE.is_file()
        gate_env_enabled = self._is_true(os.environ.get(REAL_RUN_ENV_VAR))
        env_probe = self._read_env_probe_report()
        summary = {
            "model_root": str(MODEL_ROOT),
            "source_dir": str(SOURCE_DIR), "source_exists": SOURCE_DIR.is_dir(),
            "weights_dir": str(WEIGHTS_DIR), "weights_exists": WEIGHTS_DIR.is_dir(),
            "checkpoint_dir": str(CHECKPOINT_DIR), "checkpoints_exist": CHECKPOINT_DIR.is_dir(),
            "cache_dir": str(CACHE_DIR), "artifact_root": str(ARTIFACT_ROOT),
            "reports_dir": str(REPORTS_DIR), "python_env_var": PYTHON_ENV_VAR,
            "python_path": python_path, "python_configured": Path(python_path).is_file(),
            "python_version_check": python_check_status,
            "python_version": python_version, "path_guard": path_guard,
            "env_probe_report": str(ENV_PROBE_REPORT), "env_probe_ok": env_probe is not None,
            "gate": {
                "gate_file": str(GATE_FILE), "gate_file_exists": gate_file_exists,
                "environment_variable": REAL_RUN_ENV_VAR, "environment_enabled": gate_env_enabled,
                "and_condition_met": gate_file_exists and gate_env_enabled, "phase_enforced_block": True,
            },
        }
        return summary, list(dict.fromkeys(blocked_reasons))

    @staticmethod
    def _top_level_safety() -> dict:
        return {
            "runs_model": False, "generates_candidates": False, "experimental_validation": False,
            "is_scientific_result": False, "computational_prediction_only": True,
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        }

    def probe(self) -> ModelProbeResult:
        p32b = p32b_evidence_ok("diffpepbuilder")
        if p32b["ok"]:
            return ModelProbeResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="controlled_smoke_verified",
                message="DiffPepBuilder P32B controlled smoke verified. Forward probe completed; real execution remains disabled.",
                probe_time=self._now(),
                adapter_id=self.adapter_id,
                safety_flags=self._base_safety_flags(),
                detail={
                    "p32b_evidence": p32b,
                    "gate_observed_only": True,
                    **self._top_level_safety(),
                },
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                available=True,
                actionable=False,
                probe_status="controlled_smoke_verified",
                reason="p32b_controlled_smoke_verified_real_run_disabled",
                stage="P32B_CONTROLLED_SMOKE_OK",
                **self._top_level_safety(),
            )

        environment_summary, blocked_reasons = self._environment_summary(check_python=True)
        env_probe = self._read_env_probe_report()
        env_probe_status = env_probe.get("status") if env_probe else None
        env_probe_ok = env_probe_status == "ENV_CREATED_IMPORT_CHECKPOINT_PROBE_OK"
        forward_probe = self._read_forward_probe_report()
        forward_probe_status = forward_probe.get("status") if forward_probe else None
        forward_probe_ok = forward_probe_status == "SUCCESS"
        runner_exists = RUNNER_SCRIPT.is_file()
        available = not blocked_reasons
        if available and forward_probe_ok and runner_exists:
            stage = "P31B_MINIMAL_SMOKE_RUNNER_OK"
        elif available and forward_probe_ok:
            stage = "P31B_FORWARD_PROBE_OK"
        elif available and env_probe_ok:
            stage = "P31B_ENV_CREATED_IMPORT_CHECKPOINT_PROBE_OK"
        else:
            stage = "P31B_ENV_BLOCKED"
        detail = {"environment_summary": environment_summary, "blocked_reasons": blocked_reasons,
                  "env_probe_status": env_probe_status,
                  "forward_probe_status": forward_probe_status,
                  "forward_probe_report": str(FORWARD_PROBE_REPORT),
                  "runner_script": str(RUNNER_SCRIPT),
                  "runner_script_exists": runner_exists,
                  "p32b_evidence": p32b,
                  "gate_observed_only": True, **self._top_level_safety()}
        return ModelProbeResult(
            model_id=self.model_id, display_name=self.display_name,
            status="BLOCKED" if blocked_reasons else "PROBED",
            message="DiffPepBuilder probe completed; model execution remains disabled.",
            probe_time=self._now(), adapter_id=self.adapter_id, safety_flags=self._base_safety_flags(),
            detail=detail, scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE, available=available,
            actionable=False, probe_status="blocked" if blocked_reasons else "probed",
            reason=blocked_reasons[0] if blocked_reasons else "resources_observed_real_run_disabled",
            stage=stage, **self._top_level_safety(),
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        p32b = p32b_evidence_ok("diffpepbuilder")
        forward_probe = self._read_forward_probe_report()
        forward_probe_ok = forward_probe.get("status") == "SUCCESS" if forward_probe else False
        environment_summary, blocked_reasons = self._environment_summary(check_python=False)
        blocked_reasons = list(dict.fromkeys([*blocked_reasons, "real_run_disabled"]))
        python_path = self._python_path()
        target_pdb_path = payload.target_pdb_path or "<required_target_pdb_path>"
        command_preview = [python_path, str(RUNNER_SCRIPT), "--checkpoint", str(WEIGHTS_DIR / "diffpepbuilder_v1.pth"),
                           "--config", str(SOURCE_DIR / "config" / "base.yaml"),
                           "--gate-file", str(MODEL_ROOT / "artifacts" / "diffpepbuilder" / ".diffpepbuilder_real_run_enabled"),
                           "--output-dir", str(ARTIFACT_ROOT / "<job_id>"),
                           "--num-res", str(payload.peptide_length or 20),
                           "--seed", str(payload.seed if payload.seed is not None else 2024)]
        expected_inputs = {"target_pdb_path": target_pdb_path, "target_chain": payload.target_chain,
                           "peptide_length": payload.peptide_length, "num_candidates": payload.num_candidates,
                           "seed": payload.seed}
        expected_outputs = {"planned_only": True, "candidate_sequences": None, "pdb_files": [],
                            "scientific_metrics": {}}
        artifact_plan = {"artifact_root": str(ARTIFACT_ROOT),
                         "planned_run_dir": str(ARTIFACT_ROOT / "<job_id>"),
                         "directory_created": False, "artifacts_written": False}
        runner_exists = RUNNER_SCRIPT.is_file()
        if p32b["ok"]:
            stage = "P32B_CONTROLLED_SMOKE_OK"
        elif forward_probe_ok and runner_exists:
            stage = "P31B_MINIMAL_SMOKE_RUNNER_OK"
        elif forward_probe_ok:
            stage = "P31B_FORWARD_PROBE_OK"
        else:
            stage = "P31B_ENV_CREATED_IMPORT_CHECKPOINT_PROBE_OK"
        return ModelDryRunResult(
            model_id=self.model_id, display_name=self.display_name, status="BLOCKED",
            message="DiffPepBuilder dry-run plan only; no subprocess or filesystem write was performed.",
            run_id=None, artifacts={}, expected_artifacts={}, expected_inputs=expected_inputs,
            expected_outputs=expected_outputs, artifact_plan=artifact_plan, command_preview=command_preview,
            env_preview={PYTHON_ENV_VAR: python_path}, environment_summary=environment_summary,
            blocked_reasons=blocked_reasons, safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED", scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            available=False, actionable=False, dry_run_status="blocked", reason=blocked_reasons[0],
            stage=stage,
            **{key: value for key, value in self._top_level_safety().items() if key != "validation_status"},
        )

    def submit(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        result = self.dry_run(payload)
        result.message = "DiffPepBuilder submission is unconditionally BLOCKED, regardless of gate state."
        if "submit_unconditionally_blocked_in_p17" not in result.blocked_reasons:
            result.blocked_reasons.append("submit_unconditionally_blocked_in_p17")
        return result

    def list_artifacts(self, job_id: str | None = None) -> ModelArtifactsResponse:
        normalized_job_id = job_id or ""
        if not normalized_job_id or ".." in normalized_job_id or not _SAFE_JOB_ID.fullmatch(normalized_job_id):
            raise ValueError("Invalid DiffPepBuilder job_id")
        return ModelArtifactsResponse(model_id=self.model_id, job_id=normalized_job_id, status="empty", artifacts=[],
                                      validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                                      scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE)
