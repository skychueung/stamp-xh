"""PepFlow adapter — P31C.

Read-only adapter for PepFlow model registry. Performs existence checks on
source, checkpoint, safe-load evidence, and candidate env. Real execution is
unconditionally blocked in this skeleton.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.schemas.model_registry import (
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
)
from app.services.model_adapters.base import BaseModelAdapter
from app.services.model_adapters.p32b_evidence_loader import p32b_evidence_ok
from app.services.target_peptide_model_registry import SCIENTIFIC_BOUNDARY_NOTE

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_DIR = MODEL_ROOT / "source" / "pepflow" / "extracted_p25_install_probe" / "PepFlowww-main"
CHECKPOINT_DIR = MODEL_ROOT / "checkpoints" / "pepflow" / "p25_install_probe" / "PepFlow2024_share"
SAFELOAD_REPORT = Path("/home/xh/kxc/stampup/reports/pepflow_pephar_p31c_import_rerun_after_patch.json")
FORWARD_PROBE_REPORT = Path("/mnt/sdb/kxc/stamp_models/reports/pepflow_p31c_forward_probe.json")
RUNNER_SCRIPT = Path("/mnt/sdb/kxc/stamp_models/scripts/stamp_pepflow_p31c_smoke_runner.py")
ENV_PYTHON = MODEL_ROOT / "envs" / "pepflow_py310" / "bin" / "python"
ARTIFACT_ROOT = MODEL_ROOT / "artifacts" / "pepflow"
PYTHON_ENV_VAR = "PEPFLOW_PYTHON"


class PepFlowAdapter(BaseModelAdapter):
    """Read-only PepFlow adapter: probe/dry-run only; submit always blocked."""

    @staticmethod
    def _under_model_root(path: Path) -> bool:
        try:
            path.relative_to(MODEL_ROOT)
            return True
        except ValueError:
            return False

    def _read_safeload(self) -> dict[str, Any] | None:
        if not SAFELOAD_REPORT.is_file():
            return None
        try:
            with SAFELOAD_REPORT.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _read_forward_probe_report(self) -> dict[str, Any] | None:
        if not FORWARD_PROBE_REPORT.is_file():
            return None
        try:
            with FORWARD_PROBE_REPORT.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _probe_checks(self) -> tuple[dict[str, Any], list[str]]:
        source_exists = SOURCE_DIR.is_dir()
        checkpoint1_exists = (CHECKPOINT_DIR / "model1.pt").is_file()
        checkpoint2_exists = (CHECKPOINT_DIR / "model2.pt").is_file()
        safeload = self._read_safeload()
        forward_probe = self._read_forward_probe_report()
        env_python_path = os.environ.get(PYTHON_ENV_VAR, "").strip() or str(ENV_PYTHON)
        env_python_exists = Path(env_python_path).is_file()
        runner_exists = RUNNER_SCRIPT.is_file()

        blocked_reasons: list[str] = []
        if not source_exists:
            blocked_reasons.append("missing_source")
        if not (checkpoint1_exists or checkpoint2_exists):
            blocked_reasons.append("missing_checkpoint")
        if not safeload:
            blocked_reasons.append("missing_safeload_report")
        if not env_python_exists:
            blocked_reasons.append("missing_env_python")

        detail = {
            "source_exists": source_exists,
            "checkpoint1_exists": checkpoint1_exists,
            "checkpoint2_exists": checkpoint2_exists,
            "safeload_report_exists": safeload is not None,
            "env_python_path": env_python_path,
            "env_python_exists": env_python_exists,
            "path_guard": {
                "source_under_model_root": self._under_model_root(SOURCE_DIR),
                "checkpoint_under_model_root": self._under_model_root(CHECKPOINT_DIR),
                "env_under_model_root": self._under_model_root(ENV_PYTHON),
                "artifact_root_under_model_root": self._under_model_root(ARTIFACT_ROOT),
            },
            "runs_model": False,
            "generates_candidates": False,
            "generates_pdb": False,
            "experimental_validation": False,
            "is_scientific_result": False,
            "computational_prediction_only": True,
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "forward_probe_status": forward_probe.get("status") if forward_probe else None,
            "runner_script": str(RUNNER_SCRIPT),
            "runner_script_exists": runner_exists,
            "blocked_reasons": blocked_reasons,
            "real_run_status": "blocked",
            "real_run_blocked_reason": "p31c_source_import_passed_runner_pending",
        }
        return detail, list(dict.fromkeys(blocked_reasons))

    def probe(self) -> ModelProbeResult:
        p32b = p32b_evidence_ok("pepflow")
        if p32b["ok"]:
            return ModelProbeResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="controlled_smoke_verified",
                message="PepFlow P32B controlled smoke verified. 3-step dummy sample completed; real execution remains disabled.",
                probe_time=self._now(),
                adapter_id=self.adapter_id,
                safety_flags=self._base_safety_flags(),
                detail={
                    "p32b_evidence": p32b,
                    "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                    "real_run_status": "blocked",
                    "real_run_blocked_reason": "REAL_RUN_GATE_CLOSED",
                },
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
                available=True,
                actionable=False,
                probe_status="controlled_smoke_verified",
                reason="p32b_controlled_smoke_verified_real_run_disabled",
                stage="P32B_CONTROLLED_SMOKE_OK",
                runs_model=False,
                generates_candidates=False,
                generates_pdb=False,
                experimental_validation=False,
                is_scientific_result=False,
                computational_prediction_only=True,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                real_run_status="blocked",
                real_run_blocked_reason="REAL_RUN_GATE_CLOSED",
            )

        detail, blocked_reasons = self._probe_checks()
        forward_probe = self._read_forward_probe_report()
        forward_probe_ok = forward_probe.get("status") == "SUCCESS" if forward_probe else False
        runner_exists = RUNNER_SCRIPT.is_file()
        available = not blocked_reasons
        status = "available_for_probe" if available else "blocked"
        reason = blocked_reasons[0] if blocked_reasons else "p31c_source_import_passed_runner_pending"
        if available and forward_probe_ok and runner_exists:
            stage = "P31C_MINIMAL_SMOKE_RUNNER_OK"
        elif available and forward_probe_ok:
            stage = "P31C_FORWARD_PROBE_OK"
        else:
            stage = "P31C_SOURCE_IMPORT_PASSED_RUNNER_PENDING"

        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=status,
            message="PepFlow probe completed. Candidate env ready; real execution remains disabled.",
            probe_time=self._now(),
            adapter_id=self.adapter_id,
            safety_flags=self._base_safety_flags(),
            detail=detail,
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            available=available,
            actionable=False,
            probe_status=status,
            reason=reason,
            stage=stage,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            real_run_status="blocked",
            real_run_blocked_reason="p31c_source_import_passed_runner_pending",
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        p32b = p32b_evidence_ok("pepflow")
        forward_probe = self._read_forward_probe_report()
        forward_probe_ok = forward_probe.get("status") == "SUCCESS" if forward_probe else False
        runner_exists = RUNNER_SCRIPT.is_file()
        detail, _blocked = self._probe_checks()
        blocked_reasons = ["pepflow_real_run_not_implemented"]
        if _blocked:
            blocked_reasons = list(dict.fromkeys([*_blocked, *blocked_reasons]))

        env_python_path = os.environ.get(PYTHON_ENV_VAR, "").strip() or str(ENV_PYTHON)
        receptor_pdb_path = payload.target_pdb_path or "<required_receptor_pdb_path>"

        command_preview = [
            env_python_path,
            str(RUNNER_SCRIPT),
            "--checkpoint",
            str(CHECKPOINT_DIR / "model1.pt"),
            "--config",
            str(SOURCE_DIR / "configs" / "learn_angle.yaml"),
            "--gate-file",
            str(MODEL_ROOT / "artifacts" / "pepflow" / ".pepflow_real_run_enabled"),
            "--output-dir",
            str(ARTIFACT_ROOT / "<job_id>"),
            "--num-steps",
            "10",
            "--seed",
            str(payload.seed if payload.seed is not None else 2024),
            "--device",
            "cpu",
        ]

        expected_inputs = {
            "receptor_pdb_path": receptor_pdb_path,
            "num_samples": getattr(payload, "num_candidates", 1),
            "device": "cpu",
        }
        expected_outputs = {
            "planned_only": True,
            "generated_structures": None,
            "sequences": None,
            "scientific_metrics": {},
        }

        if p32b["ok"]:
            stage = "P32B_CONTROLLED_SMOKE_OK"
        elif forward_probe_ok and runner_exists:
            stage = "P31C_MINIMAL_SMOKE_RUNNER_OK"
        elif forward_probe_ok:
            stage = "P31C_FORWARD_PROBE_OK"
        else:
            stage = "P31C_SOURCE_IMPORT_PASSED_RUNNER_PENDING"

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="BLOCKED",
            message="PepFlow dry-run plan only; no job, artifact, or subprocess was created.",
            run_id=None,
            artifacts={},
            expected_artifacts={},
            expected_inputs=expected_inputs,
            expected_outputs=expected_outputs,
            command_preview=command_preview,
            env_preview={PYTHON_ENV_VAR: env_python_path},
            environment_summary=detail,
            blocked_reasons=blocked_reasons,
            safety_flags=self._base_safety_flags(),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            available=False,
            actionable=False,
            dry_run_status="blocked",
            reason="pepflow_real_run_not_implemented",
            stage=stage,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            mode="dry_run",
            would_use_checkpoint=str(CHECKPOINT_DIR / "model1.pt"),
            would_use_env=str(ENV_PYTHON),
            creates_job=False,
            writes_artifacts=False,
            runs_subprocess=False,
        )
