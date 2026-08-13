"""RFpeptides adapter — P33 Claude Lane.

Self-contained staging adapter for RFdiffusion/rfd_macro (macrocycle peptide
design). Provides probe / dry-run / submit. Real execution is unconditionally
blocked; submit always returns blocked. Designed to be merged into the shared
adapter registry by Kimi Primary as a pending patch.

All filesystem paths are allow-listed under MODEL_ROOT. No model is imported,
loaded, or executed by this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.target_peptide_model_registry import get_model

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_DIR = MODEL_ROOT / "source" / "rfpeptides" / "rfd_macro"
WEIGHTS_DIR = MODEL_ROOT / "weights" / "rfpeptides"
CHECKPOINT_DIR = MODEL_ROOT / "checkpoints" / "rfpeptides"
CACHE_DIR = MODEL_ROOT / "cache" / "rfpeptides"
ARTIFACT_ROOT = MODEL_ROOT / "artifacts" / "rfpeptides"
REPORTS_DIR = Path("/home/xh/kxc/stampup/reports")
STAGING_DIR = Path("/home/xh/kxc/stampup/staging/p33_claude_rfpeptides")

BASE_CKPT = WEIGHTS_DIR / "Base_ckpt.pt"
BASE_CKPT_SHA256 = "0fcf7d7c32b4848030aca3a051e6768de194616f96ba6c38186351a33bfc6eca"
BASE_CKPT_SIZE = 483616107

ENV_PYTHON = MODEL_ROOT / "envs" / "rfpeptides_py310" / "bin" / "python"
PYTHON_ENV_VAR = "RFPEPTIDES_PYTHON"
RUNNER_SCRIPT = STAGING_DIR / "stamp_rfpeptides_smoke_runner_hardened.py"
GATE_FILE = ARTIFACT_ROOT / ".rfpeptides_real_run_enabled"
REAL_RUN_ENV_VAR = "STAMP_RFPEPTIDES_REAL_RUN_ENABLED"

IMPORT_CHECK_REPORT = REPORTS_DIR / "CLAUDE_CODE_STAMP_P33_RFPEPTIDES_IMPORT_CHECK.json"

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

SCIENTIFIC_BOUNDARY_NOTE = (
    "All outputs are computational predictions only and NOT_EXPERIMENTALLY_VALIDATED. "
    "Do not interpret generated sequences or structures as binding, stability, or efficacy evidence."
)


@dataclass
class SafetyFlags:
    runs_model: bool = False
    generates_candidates: bool = False
    generates_pdb: bool = False
    experimental_validation: bool = False
    is_scientific_result: bool = False
    computational_prediction_only: bool = True
    validation_status: str = "NOT_EXPERIMENTALLY_VALIDATED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "runs_model": self.runs_model,
            "generates_candidates": self.generates_candidates,
            "generates_pdb": self.generates_pdb,
            "experimental_validation": self.experimental_validation,
            "is_scientific_result": self.is_scientific_result,
            "computational_prediction_only": self.computational_prediction_only,
            "validation_status": self.validation_status,
        }


@dataclass
class ProbeResult:
    model_id: str = "rfpeptides"
    display_name: str = "RFpeptides"
    status: str = "blocked"
    message: str = ""
    probe_time: str = ""
    adapter_id: str = "rfpeptides"
    safety_flags: dict = field(default_factory=lambda: SafetyFlags().as_dict())
    detail: dict = field(default_factory=dict)
    scientific_boundary: str = SCIENTIFIC_BOUNDARY_NOTE
    available: bool = False
    actionable: bool = False
    probe_status: str = "blocked"
    reason: str = ""
    stage: str = "RFDIFFUSION_BASE_CKPT_UPLOADED_SHA256_OK"

    def __post_init__(self) -> None:
        if not self.probe_time:
            self.probe_time = datetime.now(timezone.utc).isoformat()


@dataclass
class DryRunResult:
    model_id: str = "rfpeptides"
    display_name: str = "RFpeptides"
    status: str = "BLOCKED"
    message: str = ""
    run_id: str | None = None
    artifacts: dict = field(default_factory=dict)
    expected_artifacts: dict = field(default_factory=dict)
    expected_inputs: dict = field(default_factory=dict)
    expected_outputs: dict = field(default_factory=dict)
    command_preview: list[str] = field(default_factory=list)
    env_preview: dict = field(default_factory=dict)
    environment_summary: dict = field(default_factory=dict)
    artifact_plan: dict = field(default_factory=dict)
    blocked_reasons: list[str] = field(default_factory=list)
    safety_flags: dict = field(default_factory=lambda: SafetyFlags().as_dict())
    validation_status: str = "NOT_EXPERIMENTALLY_VALIDATED"
    scientific_boundary: str = SCIENTIFIC_BOUNDARY_NOTE
    available: bool = False
    actionable: bool = False
    dry_run_status: str = "blocked"
    reason: str = ""
    stage: str = "RFDIFFUSION_BASE_CKPT_UPLOADED_SHA256_OK"


class RFpeptidesAdapter:
    """Read-only staging adapter for RFpeptides."""

    def __init__(self, model_id: str = "rfpeptides") -> None:
        self.model_id = model_id
        # Expose the registry model_entry so the unified model detail endpoint
        # can return metadata without touching any model execution path.
        self.model_entry = get_model(model_id)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

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

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _python_path(self) -> str:
        configured = os.environ.get(PYTHON_ENV_VAR, "").strip()
        if configured:
            return configured
        return str(ENV_PYTHON)

    def _read_import_check_report(self) -> dict | None:
        if not IMPORT_CHECK_REPORT.is_file():
            return None
        try:
            with IMPORT_CHECK_REPORT.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
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

        base_ckpt_ok = False
        base_ckpt_sha = None
        if BASE_CKPT.is_file():
            size = BASE_CKPT.stat().st_size
            if size != BASE_CKPT_SIZE:
                blocked_reasons.append("base_ckpt_size_mismatch")
            else:
                try:
                    base_ckpt_sha = self._sha256_file(BASE_CKPT)
                    if base_ckpt_sha.lower() != BASE_CKPT_SHA256.lower():
                        blocked_reasons.append("base_ckpt_sha256_mismatch")
                    else:
                        base_ckpt_ok = True
                except OSError:
                    blocked_reasons.append("base_ckpt_sha_read_failed")
        else:
            blocked_reasons.append("missing_base_ckpt")

        python_version = None
        python_check_status = "not_run"
        if check_python:
            if Path(python_path).is_file():
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
            else:
                python_check_status = "missing"
                blocked_reasons.append("missing_env_python")

        gate_file_exists = GATE_FILE.is_file()
        gate_env_enabled = self._is_true(os.environ.get(REAL_RUN_ENV_VAR))
        import_check = self._read_import_check_report()

        summary = {
            "model_root": str(MODEL_ROOT),
            **{k: str(v) for k, v in resource_paths.items()},
            "source_exists": SOURCE_DIR.is_dir(),
            "weights_exists": WEIGHTS_DIR.is_dir(),
            "checkpoints_exist": CHECKPOINT_DIR.is_dir(),
            "path_guard": path_guard,
            "base_ckpt": {
                "path": str(BASE_CKPT),
                "exists": BASE_CKPT.is_file(),
                "size": BASE_CKPT.stat().st_size if BASE_CKPT.is_file() else None,
                "expected_size": BASE_CKPT_SIZE,
                "sha256": base_ckpt_sha,
                "expected_sha256": BASE_CKPT_SHA256,
                "sha_ok": base_ckpt_ok,
            },
            "python_env_var": PYTHON_ENV_VAR,
            "python_path": python_path,
            "python_configured": Path(python_path).is_file(),
            "python_version_check": python_check_status,
            "python_version": python_version,
            "import_check_report": str(IMPORT_CHECK_REPORT),
            "import_check_exists": import_check is not None,
            "runner_script": str(RUNNER_SCRIPT),
            "runner_script_exists": RUNNER_SCRIPT.is_file(),
            "gate": {
                "gate_file": str(GATE_FILE),
                "gate_file_exists": gate_file_exists,
                "environment_variable": REAL_RUN_ENV_VAR,
                "environment_enabled": gate_env_enabled,
                "and_condition_met": gate_file_exists and gate_env_enabled,
                "phase_enforced_block": True,
            },
        }
        return summary, list(dict.fromkeys(blocked_reasons))

    def _resolve_stage(self, summary: dict, blocked_reasons: list[str]) -> str:
        import_check = self._read_import_check_report()
        import_ok = import_check is not None and import_check.get("status") == "OK"
        runner_exists = summary.get("runner_script_exists", False)
        python_exists = summary.get("python_configured", False)
        base_ok = summary.get("base_ckpt", {}).get("sha_ok", False)

        if blocked_reasons:
            return "RFDIFFUSION_BASE_CKPT_UPLOADED_SHA256_OK"
        if import_ok and runner_exists:
            return "RFPEPTIDES_RUNNER_STAGED"
        if import_ok:
            return "RFPEPTIDES_IMPORT_ONLY_OK"
        if python_exists and base_ok:
            return "RFPEPTIDES_ENV_CREATED_IMPORT_PENDING"
        return "RFDIFFUSION_BASE_CKPT_UPLOADED_SHA256_OK"

    def probe(self, payload: dict | None = None) -> ProbeResult:
        summary, blocked_reasons = self._environment_summary(check_python=True)
        stage = self._resolve_stage(summary, blocked_reasons)
        available = not blocked_reasons
        status = "available_for_probe" if available else "blocked"
        reason = blocked_reasons[0] if blocked_reasons else "base_ckpt_and_source_ready_env_pending"

        detail = {
            "environment_summary": summary,
            "blocked_reasons": blocked_reasons,
            **SafetyFlags().as_dict(),
        }

        return ProbeResult(
            status=status,
            message="RFpeptides probe completed. Base_ckpt SHA verified; real execution remains disabled.",
            detail=detail,
            available=available,
            actionable=False,
            probe_status=status,
            reason=reason,
            stage=stage,
        )

    def _payload_dict(self, payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}
        if hasattr(payload, "model_dump"):
            return payload.model_dump(mode="json")
        if hasattr(payload, "__dict__"):
            return payload.__dict__
        return dict(payload)

    def dry_run(self, payload: dict | None = None) -> DryRunResult:
        p = self._payload_dict(payload)
        summary, blocked_reasons = self._environment_summary(check_python=False)
        stage = self._resolve_stage(summary, blocked_reasons)
        blocked_reasons = list(dict.fromkeys([*blocked_reasons, "real_run_disabled"]))
        python_path = self._python_path()

        job_id = p.get("job_id") or "<job_id>"
        contig = p.get("contig") or "[5-10]"
        num_designs = int(p.get("num_designs", 1))
        num_steps = int(p.get("num_steps", 5))
        seed = int(p.get("seed", 2024)) if p.get("seed") is not None else 2024
        cyclic = bool(p.get("cyclic", True))
        device = str(p.get("device", "cpu")).lower()

        output_dir = ARTIFACT_ROOT / job_id
        command_preview = [
            python_path,
            str(RUNNER_SCRIPT),
            "--checkpoint", str(BASE_CKPT),
            "--config-name", "base",
            "--config-path", str(SOURCE_DIR / "config" / "inference"),
            "--output-dir", str(output_dir),
            "--gate-file", str(GATE_FILE),
            "--contig", contig,
            "--num-designs", str(num_designs),
            "--num-steps", str(num_steps),
            "--seed", str(seed),
            "--cyclic", str(cyclic),
            "--device", device,
            "--max-wall-seconds", "300",
            "--output-quota-bytes", "10485760",
        ]

        expected_inputs = {
            "contig": contig,
            "num_designs": num_designs,
            "num_steps": num_steps,
            "seed": seed,
            "cyclic": cyclic,
            "device": device,
            "checkpoint_sha256": BASE_CKPT_SHA256,
        }
        expected_outputs = {
            "planned_only": True,
            "candidate_sequences": None,
            "pdb_files": None,
            "scientific_metrics": {},
        }
        artifact_plan = {
            "artifact_root": str(ARTIFACT_ROOT),
            "planned_run_dir": str(output_dir),
            "directory_created": False,
            "artifacts_written": False,
        }

        return DryRunResult(
            message="RFpeptides dry-run plan only; no subprocess or filesystem write was performed.",
            command_preview=command_preview,
            env_preview={PYTHON_ENV_VAR: python_path},
            environment_summary=summary,
            blocked_reasons=blocked_reasons,
            expected_inputs=expected_inputs,
            expected_outputs=expected_outputs,
            artifact_plan=artifact_plan,
            available=False,
            actionable=False,
            dry_run_status="blocked",
            reason=blocked_reasons[0],
            stage=stage,
        )

    def submit(self, payload: dict | None = None) -> DryRunResult:
        result = self.dry_run(payload)
        result.message = "RFpeptides submission is unconditionally BLOCKED, regardless of gate state."
        if "submit_unconditionally_blocked_in_p33" not in result.blocked_reasons:
            result.blocked_reasons.append("submit_unconditionally_blocked_in_p33")
        return result


    def list_artifacts(self, job_id: str) -> Any:
        """Return an empty artifact listing for P33."""
        from app.schemas.model_registry import ModelArtifactsResponse
        return ModelArtifactsResponse(
            model_id=getattr(self, "model_id", "rfpeptides"),
            job_id=job_id,
            status="empty",
            artifacts=[],
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )


def main() -> None:
    adapter = RFpeptidesAdapter()
    print("=== PROBE ===")
    print(json.dumps(adapter.probe().__dict__, indent=2, default=str))
    print("=== DRY RUN ===")
    print(json.dumps(adapter.dry_run({"contig": "[5-10]", "num_steps": 5}).__dict__, indent=2, default=str))
    print("=== SUBMIT ===")
    print(json.dumps(adapter.submit({"contig": "[5-10]", "num_steps": 5}).__dict__, indent=2, default=str))


if __name__ == "__main__":
    main()
