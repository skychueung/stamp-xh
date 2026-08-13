"""PepHAR real runner skeleton — P31C.

Provides gate-check, path validation, command preview, and manifest schema
for future PepHAR real execution. Default gate is CLOSED; no subprocess,
no model inference, no affinity score generation occurs without explicit
authorization.

All outputs are marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_ROOT = MODEL_ROOT / "source" / "pephar" / "extracted_p25_install_probe" / "PepHAR-main"
DEFAULT_DENSITY_CONFIG = SOURCE_ROOT / "configs" / "density_v4_x5o2.yml"
DEFAULT_PREDICTION_CONFIG = SOURCE_ROOT / "configs" / "prediction_d2_x2o1.yml"
DENSITY_CHECKPOINT = (
    MODEL_ROOT
    / "checkpoints"
    / "pephar"
    / "p25_install_probe"
    / "PepHAR_ICLR2025_SHARE"
    / "ckpts"
    / "density_v4_x5o2_2024_09_08__11_25_36"
    / "checkpoints"
    / "1400.pt"
)
PREDICTION_CHECKPOINT = (
    MODEL_ROOT
    / "checkpoints"
    / "pephar"
    / "p25_install_probe"
    / "PepHAR_ICLR2025_SHARE"
    / "ckpts"
    / "prediction_d2_x2o1_2024_09_08__11_21_33"
    / "checkpoints"
    / "2400.pt"
)
RUNTIME_ENV = MODEL_ROOT / "envs" / "pephar_py310_pypi_candidate"
ENV_PYTHON = RUNTIME_ENV / "bin" / "python"
GATE_FILE = MODEL_ROOT / "reports" / "pephar" / ".pephar_real_run_enabled"

DEV_ROOT = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev")
DATA_DEV = DEV_ROOT / "data_dev"
ARTIFACTS_BASE = DATA_DEV / "artifacts" / "pephar"
LOGS_BASE = DEV_ROOT / "logs_dev" / "pephar"

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
_ALLOWED_SOURCE_ROOTS: tuple[Path, ...] = (MODEL_ROOT / "source" / "pephar",)
_ALLOWED_CHECKPOINT_ROOTS: tuple[Path, ...] = (MODEL_ROOT / "checkpoints" / "pephar",)

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class PepHARRunnerBlocked(Exception):
    """Raised when a PepHAR runner operation is blocked by gate or policy."""


class PepHARRunner:
    """PepHAR runner with default-closed real-run gate."""

    def __init__(
        self,
        job_id: str | None = None,
        out_root: str | Path | None = None,
        model_variant: str = "prediction",
        checkpoint_path: str | Path | None = None,
        config_path: str | Path | None = None,
        device: str = "cpu",
        env_python: str | None = None,
    ):
        self.job_id = self._validate_job_id(job_id or self._generate_job_id())
        self.out_root = self._validate_out_root(out_root or ARTIFACTS_BASE / self.job_id)
        self.model_variant = self._validate_variant(model_variant)
        self.checkpoint_path = self._validate_checkpoint_path(
            checkpoint_path or (PREDICTION_CHECKPOINT if self.model_variant == "prediction" else DENSITY_CHECKPOINT)
        )
        self.config_path = self._validate_source_path(
            config_path or (DEFAULT_PREDICTION_CONFIG if self.model_variant == "prediction" else DEFAULT_DENSITY_CONFIG)
        )
        self.device = device
        self.env_python = Path(env_python or ENV_PYTHON)
        self.artifact_dir = self.out_root
        self.log_path = LOGS_BASE / f"{self.job_id}.log"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _generate_job_id() -> str:
        return f"pephar_{uuid.uuid4().hex[:16]}"

    @classmethod
    def _validate_job_id(cls, job_id: str) -> str:
        job_id = str(job_id).strip()
        if not _SAFE_JOB_ID.match(job_id):
            raise PepHARRunnerBlocked(f"invalid job_id: {job_id}")
        return job_id

    @staticmethod
    def _validate_variant(variant: str) -> str:
        v = str(variant).strip().lower()
        if v not in {"prediction", "density"}:
            raise PepHARRunnerBlocked(f"invalid model_variant: {variant}; must be prediction or density")
        return v

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
            raise PepHARRunnerBlocked(f"forbidden out_root: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_OUT_ROOTS):
            raise PepHARRunnerBlocked(f"out_root not under allowed base: {p}")
        return p

    @classmethod
    def _validate_source_path(cls, src_path: str | Path) -> Path:
        p = Path(src_path).resolve()
        if cls._is_forbidden(p):
            raise PepHARRunnerBlocked(f"forbidden source path: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_SOURCE_ROOTS):
            raise PepHARRunnerBlocked(f"source path not under allowed base: {p}")
        return p

    @classmethod
    def _validate_checkpoint_path(cls, ckpt_path: str | Path) -> Path:
        p = Path(ckpt_path).resolve()
        if cls._is_forbidden(p):
            raise PepHARRunnerBlocked(f"forbidden checkpoint path: {p}")
        if not any(p == allowed or p.is_relative_to(allowed) for allowed in _ALLOWED_CHECKPOINT_ROOTS):
            raise PepHARRunnerBlocked(f"checkpoint path not under allowed base: {p}")
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
            raise PepHARRunnerBlocked("real-run gate is open; this skeleton does not support execution")

    def build_command(self, complex_pdb: str | Path) -> list[str]:
        """Construct the PepHAR inference command preview (no execution)."""
        self.ensure_gate_closed()
        complex_pdb_path = Path(complex_pdb)
        if self._is_forbidden(complex_pdb_path):
            raise PepHARRunnerBlocked(f"forbidden complex_pdb path: {complex_pdb_path}")
        # Placeholder command; real entrypoint TBD during smoke run authorization.
        return [
            str(self.env_python),
            "-m",
            "sample",
            "--config",
            str(self.config_path),
            "--param_path",
            str(self.checkpoint_path),
            "--input_pdb",
            str(complex_pdb_path),
            "--output",
            str(self.out_root),
            "--device",
            self.device,
            "--model_variant",
            self.model_variant,
        ]

    def run(self, complex_pdb: str | Path) -> dict[str, Any]:
        """Always blocked in P31C skeleton."""
        self.ensure_gate_closed()
        raise PepHARRunnerBlocked("PepHAR real run is blocked in P31C skeleton")

    def build_manifest_post(self, complex_pdb: str | Path) -> dict[str, Any]:
        return {
            "model_id": "pephar",
            "job_id": self.job_id,
            "stage": STAGE,
            "command_preview": self.build_command(complex_pdb),
            "checkpoint_used": str(self.checkpoint_path),
            "config_used": str(self.config_path),
            "env_python": str(self.env_python),
            "out_root": str(self.out_root),
            "device": self.device,
            "model_variant": self.model_variant,
            "validation_status": VALIDATION_STATUS,
            "disclaimer": DISCLAIMER,
            "computational_prediction_only": True,
            "experimental_validation": False,
            "runs_model": False,
            "generates_affinity_score": False,
            "creates_job": False,
            "writes_artifacts": False,
            "subprocess_spawned": False,
            "timestamp": self._now(),
        }

    def build_failure(self, reason: str, complex_pdb: str | Path | None = None) -> dict[str, Any]:
        return {
            "model_id": "pephar",
            "job_id": self.job_id,
            "stage": STAGE,
            "status": "BLOCKED",
            "blocked_reason": reason,
            "command_preview": self.build_command(complex_pdb) if complex_pdb else None,
            "validation_status": VALIDATION_STATUS,
            "disclaimer": DISCLAIMER,
            "computational_prediction_only": True,
            "experimental_validation": False,
            "runs_model": False,
            "generates_affinity_score": False,
            "creates_job": False,
            "writes_artifacts": False,
            "subprocess_spawned": False,
            "timestamp": self._now(),
        }
