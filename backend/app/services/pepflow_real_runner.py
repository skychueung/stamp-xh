"""PepFlow real runner skeleton — P31C.

Provides gate-check, path validation, command preview, and manifest schema
for future PepFlow real execution. Default gate is CLOSED; no subprocess,
no model inference, no PDB generation occurs without explicit authorization.

All outputs are marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_ROOT = MODEL_ROOT / "source" / "pepflow" / "extracted_p25_install_probe" / "PepFlowww-main"
INFERENCE_ENTRY = SOURCE_ROOT / "models_con" / "inference.py"
DEFAULT_CONFIG = SOURCE_ROOT / "configs" / "learn_angle.yaml"
CHECKPOINT_ROOT = MODEL_ROOT / "checkpoints" / "pepflow" / "p25_install_probe" / "PepFlow2024_share"
DEFAULT_CHECKPOINT = CHECKPOINT_ROOT / "model1.pt"
RUNTIME_ENV = MODEL_ROOT / "envs" / "pepflow_py310_pypi_candidate"
ENV_PYTHON = RUNTIME_ENV / "bin" / "python"
GATE_FILE = MODEL_ROOT / "reports" / "pepflow" / ".pepflow_real_run_enabled"

DEV_ROOT = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev")
DATA_DEV = DEV_ROOT / "data_dev"
ARTIFACTS_BASE = DATA_DEV / "artifacts" / "pepflow"
LOGS_BASE = DEV_ROOT / "logs_dev" / "pepflow"

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
DISCLAIMER = "computational prediction only; not experimentally validated"
STAGE = "P31C_RUNNER_SKELETON_ONLY"

FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "/tmp",
    "/root",
    "/home/xh/stamp",
    "/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform",
    "/home/xh/kxc/靶向肽/backups",
)

_ALLOWED_OUT_ROOTS: tuple[Path, ...] = (ARTIFACTS_BASE,)
_ALLOWED_SOURCE_ROOTS: tuple[Path, ...] = (MODEL_ROOT / "source" / "pepflow",)
_ALLOWED_CHECKPOINT_ROOTS: tuple[Path, ...] = (MODEL_ROOT / "checkpoints" / "pepflow",)

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class PepFlowRunnerBlocked(Exception):
    """Raised when a PepFlow runner operation is blocked by gate or policy."""


class PepFlowRunner:
    """PepFlow runner with default-closed real-run gate."""

    def __init__(
        self,
        job_id: str | None = None,
        out_root: str | Path | None = None,
        checkpoint_path: str | Path | None = None,
        config_path: str | Path | None = None,
        device: str = "cpu",
        num_samples: int = 1,
        num_steps: int = 200,
        env_python: str | None = None,
    ):
        self.job_id = self._validate_job_id(job_id or self._generate_job_id())
        self.out_root = self._validate_out_root(out_root or ARTIFACTS_BASE / self.job_id)
        self.checkpoint_path = self._validate_checkpoint_path(
            checkpoint_path or DEFAULT_CHECKPOINT
        )
        self.config_path = self._validate_source_path(config_path or DEFAULT_CONFIG)
        self.device = device
        self.num_samples = max(1, int(num_samples))
        self.num_steps = max(1, int(num_steps))
        self.env_python = Path(env_python or ENV_PYTHON)
        self.artifact_dir = self.out_root
        self.log_path = LOGS_BASE / f"{self.job_id}.log"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _generate_job_id() -> str:
        return f"pepflow_{uuid.uuid4().hex[:16]}"

    @classmethod
    def _validate_job_id(cls, job_id: str) -> str:
        job_id = str(job_id).strip()
        if not _SAFE_JOB_ID.match(job_id):
            raise PepFlowRunnerBlocked(f"invalid job_id: {job_id}")
        return job_id

    @staticmethod
    def _is_forbidden(path: Path) -> bool:
        resolved = path.resolve()
        for prefix in FORBIDDEN_PREFIXES:
            try:
                resolved.relative_to(Path(prefix).resolve())
                return True
            except ValueError:
                continue
        return False

    @classmethod
    def _validate_out_root(cls, out_root: str | Path) -> Path:
        p = Path(out_root).resolve()
        if cls._is_forbidden(p):
            raise PepFlowRunnerBlocked(f"forbidden out_root: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_OUT_ROOTS):
            raise PepFlowRunnerBlocked(f"out_root not under allowed base: {p}")
        return p

    @classmethod
    def _validate_source_path(cls, src_path: str | Path) -> Path:
        p = Path(src_path).resolve()
        if cls._is_forbidden(p):
            raise PepFlowRunnerBlocked(f"forbidden source path: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_SOURCE_ROOTS):
            raise PepFlowRunnerBlocked(f"source path not under allowed base: {p}")
        return p

    @classmethod
    def _validate_checkpoint_path(cls, ckpt_path: str | Path) -> Path:
        p = Path(ckpt_path).resolve()
        if cls._is_forbidden(p):
            raise PepFlowRunnerBlocked(f"forbidden checkpoint path: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_CHECKPOINT_ROOTS):
            raise PepFlowRunnerBlocked(f"checkpoint path not under allowed base: {p}")
        return p

    @staticmethod
    def gate_open() -> bool:
        """Return True only if the real-run gate file exists and is non-empty."""
        if not GATE_FILE.is_file():
            return False
        try:
            return GATE_FILE.read_text(encoding="utf-8").strip().lower() in {"1", "true", "yes", "on"}
        except OSError:
            return False

    @classmethod
    def ensure_gate_closed(cls) -> None:
        """No-op safety helper to document that gate must be explicitly opened."""
        if cls.gate_open():
            raise PepFlowRunnerBlocked("real-run gate is open; this skeleton does not support execution")

    def build_command(self, receptor_pdb: str | Path) -> list[str]:
        """Construct the PepFlow inference command preview (no execution)."""
        self.ensure_gate_closed()
        receptor_pdb_path = Path(receptor_pdb)
        if self._is_forbidden(receptor_pdb_path):
            raise PepFlowRunnerBlocked(f"forbidden receptor_pdb path: {receptor_pdb_path}")
        return [
            str(self.env_python),
            str(INFERENCE_ENTRY),
            "--config",
            str(self.config_path),
            "--ckpt",
            str(self.checkpoint_path),
            "--receptor",
            str(receptor_pdb_path),
            "--output",
            str(self.out_root),
            "--num_samples",
            str(self.num_samples),
            "--num_steps",
            str(self.num_steps),
            "--device",
            self.device,
        ]

    def run(self, receptor_pdb: str | Path) -> dict[str, Any]:
        """Always blocked in P31C skeleton."""
        self.ensure_gate_closed()
        raise PepFlowRunnerBlocked("PepFlow real run is blocked in P31C skeleton")

    def build_manifest_post(self, receptor_pdb: str | Path) -> dict[str, Any]:
        return {
            "model_id": "pepflow",
            "job_id": self.job_id,
            "stage": STAGE,
            "command_preview": self.build_command(receptor_pdb),
            "checkpoint_used": str(self.checkpoint_path),
            "config_used": str(self.config_path),
            "env_python": str(self.env_python),
            "out_root": str(self.out_root),
            "device": self.device,
            "num_samples": self.num_samples,
            "num_steps": self.num_steps,
            "validation_status": VALIDATION_STATUS,
            "disclaimer": DISCLAIMER,
            "computational_prediction_only": True,
            "experimental_validation": False,
            "runs_model": False,
            "generates_candidates": False,
            "creates_job": False,
            "writes_artifacts": False,
            "subprocess_spawned": False,
            "timestamp": self._now(),
        }

    def build_failure(self, reason: str, receptor_pdb: str | Path | None = None) -> dict[str, Any]:
        return {
            "model_id": "pepflow",
            "job_id": self.job_id,
            "stage": STAGE,
            "status": "BLOCKED",
            "blocked_reason": reason,
            "command_preview": self.build_command(receptor_pdb) if receptor_pdb else None,
            "validation_status": VALIDATION_STATUS,
            "disclaimer": DISCLAIMER,
            "computational_prediction_only": True,
            "experimental_validation": False,
            "runs_model": False,
            "generates_candidates": False,
            "creates_job": False,
            "writes_artifacts": False,
            "subprocess_spawned": False,
            "timestamp": self._now(),
        }
