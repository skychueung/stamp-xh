"""PepHAR adapter — P31C.

Read-only adapter for PepHAR model registry. Performs existence checks on
source, checkpoints, safe-load evidence, and candidate env. Real execution is
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
SOURCE_DIR = MODEL_ROOT / "source" / "pephar" / "extracted_p25_install_probe" / "PepHAR-main"
CHECKPOINT_ROOT = (
    MODEL_ROOT
    / "checkpoints"
    / "pephar"
    / "p25_install_probe"
    / "PepHAR_ICLR2025_SHARE"
    / "ckpts"
)
SAFELOAD_REPORT = Path("/home/xh/kxc/stampup/reports/pepflow_pephar_p31c_import_rerun_after_patch.json")
FORWARD_PROBE_REPORT = Path("/mnt/sdb/kxc/stamp_models/reports/pephar_p31c_forward_probe.json")
RUNNER_SCRIPT = Path("/mnt/sdb/kxc/stamp_models/scripts/stamp_pephar_p31c_smoke_runner.py")
ENV_PYTHON = MODEL_ROOT / "envs" / "pephar_py310" / "bin" / "python"
ARTIFACT_ROOT = MODEL_ROOT / "artifacts" / "pephar"
PYTHON_ENV_VAR = "PEPHAR_PYTHON"


class PepHARAdapter(BaseModelAdapter):
    """Read-only PepHAR adapter: probe/dry-run only; submit always blocked."""

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
        density_checkpoint = (
            CHECKPOINT_ROOT
            / "density_v4_x5o2_2024_09_08__11_25_36"
            / "checkpoints"
            / "1400.pt"
        )
        prediction_checkpoint = (
            CHECKPOINT_ROOT
            / "prediction_d2_x2o1_2024_09_08__11_21_33"
            / "checkpoints"
            / "2400.pt"
        )
        density_exists = density_checkpoint.is_file()
        prediction_exists = prediction_checkpoint.is_file()
        safeload = self._read_safeload()
        forward_probe = self._read_forward_probe_report()
        runner_exists = RUNNER_SCRIPT.is_file()
        env_python_path = os.environ.get(PYTHON_ENV_VAR, "").strip() or str(ENV_PYTHON)
        env_python_exists = Path(env_python_path).is_file()

        blocked_reasons: list[str] = []
        if not source_exists:
            blocked_reasons.append("missing_source")
        if not density_exists:
            blocked_reasons.append("missing_density_checkpoint")
        if not prediction_exists:
            blocked_reasons.append("missing_prediction_checkpoint")
        if not safeload:
            blocked_reasons.append("missing_safeload_report")
        if not env_python_exists:
            blocked_reasons.append("missing_env_python")

        detail = {
            "source_exists": source_exists,
            "density_checkpoint_exists": density_exists,
            "prediction_checkpoint_exists": prediction_exists,
            "safeload_report_exists": safeload is not None,
            "env_python_path": env_python_path,
            "env_python_exists": env_python_exists,
            "path_guard": {
                "source_under_model_root": self._under_model_root(SOURCE_DIR),
                "checkpoint_under_model_root": self._under_model_root(CHECKPOINT_ROOT),
                "env_under_model_root": self._under_model_root(ENV_PYTHON),
                "artifact_root_under_model_root": self._under_model_root(ARTIFACT_ROOT),
            },
            "runs_model": False,
            "generates_affinity_score": False,
            "generates_density": False,
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
        density_p32b = p32b_evidence_ok("pephar_density")
        prediction_p32b = p32b_evidence_ok("pephar_prediction")
        p32b_ok = density_p32b["ok"] and prediction_p32b["ok"]
        if p32b_ok:
            return ModelProbeResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="controlled_smoke_verified",
                message="PepHAR P32B controlled smoke verified. Density and prediction variants completed; real execution remains disabled.",
                probe_time=self._now(),
                adapter_id=self.adapter_id,
                safety_flags=self._base_safety_flags(),
                detail={
                    "p32b_density_evidence": density_p32b,
                    "p32b_prediction_evidence": prediction_p32b,
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
            message="PepHAR probe completed. Candidate env ready; real execution remains disabled.",
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
        density_p32b = p32b_evidence_ok("pephar_density")
        prediction_p32b = p32b_evidence_ok("pephar_prediction")
        p32b_ok = density_p32b["ok"] and prediction_p32b["ok"]
        forward_probe = self._read_forward_probe_report()
        forward_probe_ok = forward_probe.get("status") == "SUCCESS" if forward_probe else False
        runner_exists = RUNNER_SCRIPT.is_file()
        detail, _blocked = self._probe_checks()
        blocked_reasons = ["pephar_real_run_not_implemented"]
        if _blocked:
            blocked_reasons = list(dict.fromkeys([*_blocked, *blocked_reasons]))

        env_python_path = os.environ.get(PYTHON_ENV_VAR, "").strip() or str(ENV_PYTHON)
        complex_pdb_path = payload.target_pdb_path or "<required_complex_pdb_path>"
        model_variant = getattr(payload, "model_variant", "prediction")

        checkpoint = (
            CHECKPOINT_ROOT
            / ("prediction_d2_x2o1_2024_09_08__11_21_33" if model_variant == "prediction" else "density_v4_x5o2_2024_09_08__11_25_36")
            / "checkpoints"
            / ("2400.pt" if model_variant == "prediction" else "1400.pt")
        )
        config = SOURCE_DIR / "configs" / ("prediction_d2_x2o1.yml" if model_variant == "prediction" else "density_v4_x5o2.yml")

        command_preview = [
            env_python_path,
            str(RUNNER_SCRIPT),
            "--model-variant",
            model_variant,
            "--checkpoint",
            str(checkpoint),
            "--config",
            str(config),
            "--gate-file",
            str(MODEL_ROOT / "artifacts" / "pephar" / ".pephar_real_run_enabled"),
            "--output-dir",
            str(ARTIFACT_ROOT / "<job_id>"),
            "--seed",
            str(payload.seed if payload.seed is not None else 2024),
        ]

        expected_inputs = {
            "complex_pdb_path": complex_pdb_path,
            "model_variant": model_variant,
            "device": "cpu",
        }
        expected_outputs = {
            "planned_only": True,
            "affinity_score": None,
            "scientific_metrics": {},
        }

        if p32b_ok:
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
            message="PepHAR dry-run plan only; no job, artifact, or subprocess was created.",
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
            reason="pephar_real_run_not_implemented",
            stage=stage,
            runs_model=False,
            generates_candidates=False,
            generates_pdb=False,
            experimental_validation=False,
            is_scientific_result=False,
            computational_prediction_only=True,
            mode="dry_run",
            would_use_checkpoint=str(checkpoint),
            would_use_env=str(ENV_PYTHON),
            creates_job=False,
            writes_artifacts=False,
            runs_subprocess=False,
        )
