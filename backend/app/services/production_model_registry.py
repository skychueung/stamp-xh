"""Truthful runtime registry for the five production pipeline models."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


MODEL_IDS = ("pepmlm", "pepprclip", "evobind2", "pephar", "pepflow")
VALID_STATES = {
    "registered", "installed", "checkpoint_missing", "dependency_missing",
    "ready", "busy", "degraded", "offline",
}


class ModelAdapter(Protocol):
    model_id: str

    def probe(self) -> dict[str, Any]: ...
    def validate_input(self, payload: dict[str, Any]) -> list[str]: ...
    def estimate_resources(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def run(self, payload: dict[str, Any]) -> dict[str, Any]: ...
    def submit(self, db: Any, payload: dict[str, Any], **kwargs: Any) -> Any: ...
    def status(self, db: Any, job_id: str) -> dict[str, Any]: ...
    def cancel(self, db: Any, job_id: str) -> dict[str, Any]: ...
    def collect_artifacts(self, db: Any, job_id: str) -> list[dict[str, Any]]: ...
    def normalize_result(self, raw: dict[str, Any]) -> dict[str, Any]: ...


@dataclass(frozen=True)
class RuntimeSpec:
    model_id: str
    version: str
    root_env: str
    python_env: str
    checkpoint_env: str
    default_root: str
    default_python: str
    default_checkpoint: str
    install_hint: str


SPECS = {
    "pepmlm": RuntimeSpec("pepmlm", "ChatterjeeLab/PepMLM-650M", "STAMP_PEPMLM_ROOT", "STAMP_PEPMLM_PYTHON", "STAMP_PEPMLM_CHECKPOINT", "/home/xh/kxc/stampup/models_dev/pepmlm", "/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python", "/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M/model.safetensors", "Set STAMP_PEPMLM_ROOT/PYTHON/CHECKPOINT after installing PepMLM."),
    "pepprclip": RuntimeSpec("pepprclip", "canonical-miniclip-4-22-23", "STAMP_PEPPRCLIP_ROOT", "STAMP_PEPPRCLIP_PYTHON", "STAMP_PEPPRCLIP_CHECKPOINT", "/home/xh/kxc/stampup/models_dev/pepprclip", "/home/xh/kxc/stampup/models_dev/pepprclip/envs/pepprclip/bin/python", "/home/xh/kxc/stampup/models_dev/pepprclip/weights/canonical_miniclip_4-22-23.ckpt", "Install the licensed PepPrCLIP weight archive and set STAMP_PEPPRCLIP_* paths."),
    "evobind2": RuntimeSpec("evobind2", "EvoBind2-model_1", "STAMP_EVOBIND2_ROOT", "STAMP_EVOBIND2_PYTHON", "STAMP_EVOBIND2_CHECKPOINT", "/home/xh/kxc/stampup/models_dev/evobind2/source/EvoBind", "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/envs/evobind/bin/python", "/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/cache/af2_params/params_model_1.npz", "Set EvoBind2 source, environment and AlphaFold parameter paths."),
    "pephar": RuntimeSpec("pephar", "ICLR-2025", "STAMP_PEPHAR_ROOT", "STAMP_PEPHAR_PYTHON", "STAMP_PEPHAR_CHECKPOINT", "/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main", "/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python", "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36/checkpoints/1400.pt", "Set PepHAR source, Python and density checkpoint paths; the prediction checkpoint is supplied to its runner command."),
    "pepflow": RuntimeSpec("pepflow", "ICML-2024-model2", "STAMP_PEPFLOW_ROOT", "STAMP_PEPFLOW_PYTHON", "STAMP_PEPFLOW_CHECKPOINT", "/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main", "/mnt/sdb/kxc/stamp_models/envs/pepflow_py310/bin/python", "/mnt/sdb/kxc/stamp_models/checkpoints/pepflow/p25_install_probe/PepFlow2024_share/model2.pt", "Set PepFlow source, Python and model2 checkpoint paths."),
}


def _resolve(env_name: str, default: str) -> Path:
    value = os.environ.get(env_name, default)
    path = Path(value).expanduser()
    model_base = Path(os.environ.get("STAMP_MODEL_HOME", ".")).expanduser()
    return path if path.is_absolute() else model_base / path


class ConfiguredModelAdapter:
    def __init__(self, spec: RuntimeSpec) -> None:
        self.spec = spec
        self.model_id = spec.model_id

    def probe(self) -> dict[str, Any]:
        root = _resolve(self.spec.root_env, self.spec.default_root)
        python = _resolve(self.spec.python_env, self.spec.default_python)
        checkpoint = _resolve(self.spec.checkpoint_env, self.spec.default_checkpoint)
        missing: list[str] = []
        state = "registered"
        if not root.exists():
            missing.append("runtime_root")
        else:
            state = "installed"
        if not python.is_file():
            missing.append("python_environment")
            state = "dependency_missing"
        elif not checkpoint.is_file():
            missing.append("checkpoint")
            state = "checkpoint_missing"
        elif root.exists():
            state = "ready"
        busy_file = root / ".busy"
        if state == "ready" and busy_file.exists():
            state = "busy"
        checkpoint_sha256 = None
        if checkpoint.is_file():
            digest = hashlib.sha256()
            with checkpoint.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            checkpoint_sha256 = digest.hexdigest()
        assert state in VALID_STATES
        return {
            "model_id": self.model_id,
            "model_version": self.spec.version,
            "state": state,
            "missing": missing,
            "checkpoint_sha256": checkpoint_sha256,
            "install_hint": self.spec.install_hint if missing else None,
            "configured": {
                "root": bool(os.environ.get(self.spec.root_env)),
                "python": bool(os.environ.get(self.spec.python_env)),
                "checkpoint": bool(os.environ.get(self.spec.checkpoint_env)),
            },
        }

    def validate_input(self, payload: dict[str, Any]) -> list[str]:
        sequence = str(payload.get("target_sequence", "")).strip().upper()
        errors = []
        if not (10 <= len(sequence) <= 5000):
            errors.append("target_sequence length must be 10..5000")
        if set(sequence) - set("ACDEFGHIKLMNPQRSTVWY"):
            errors.append("target_sequence contains unsupported residues")
        return errors

    def estimate_resources(self, payload: dict[str, Any]) -> dict[str, Any]:
        length = len(str(payload.get("target_sequence", "")))
        return {"gpu_count": 1, "estimated_vram_gb": 8 + min(16, length / 250), "input_length": length}

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Compatibility entrypoint reporting that durable submission is required."""
        errors = self.validate_input(payload)
        probe = self.probe()
        if errors:
            return {"status": "invalid_input", "errors": errors, "model_id": self.model_id}
        if probe["state"] != "ready":
            return {"status": "blocked", "model_id": self.model_id, "probe": probe}
        return {
            "status": "submit_required",
            "model_id": self.model_id,
            "resources": self.estimate_resources(payload),
            "submit_endpoint": f"/api/v1/models/{self.model_id}/jobs",
        }

    def submit(self, db: Any, payload: dict[str, Any], **kwargs: Any) -> Any:
        from app.services.unified_model_runtime import submit_model_job
        return submit_model_job(db, self.model_id, payload, **kwargs)

    def status(self, db: Any, job_id: str) -> dict[str, Any]:
        from app.models.orm import Job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None or job.job_type != f"model_generate:{self.model_id}":
            raise KeyError(job_id)
        return {"job_id": job.id, "model_id": self.model_id, "status": job.status,
                "progress": job.progress, "result": job.output_json, "error": job.error_json}

    def cancel(self, db: Any, job_id: str) -> dict[str, Any]:
        from app.models.orm import Job
        from app.services.unified_model_runtime import cancel_model_job
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None or job.job_type != f"model_generate:{self.model_id}":
            raise KeyError(job_id)
        cancel_model_job(db, job)
        return self.status(db, job_id)

    def collect_artifacts(self, db: Any, job_id: str) -> list[dict[str, Any]]:
        from app.models.orm import Job
        from app.services.unified_model_runtime import list_job_artifacts
        job = db.query(Job).filter(Job.id == job_id).first()
        if job is None or job.job_type != f"model_generate:{self.model_id}":
            raise KeyError(job_id)
        return list_job_artifacts(job)

    def normalize_result(self, raw: dict[str, Any]) -> dict[str, Any]:
        return {"model_id": self.model_id, "model_version": self.spec.version, "result": raw}


class ProductionModelRegistry:
    def __init__(self) -> None:
        self._adapters = {model_id: ConfiguredModelAdapter(SPECS[model_id]) for model_id in MODEL_IDS}

    def get(self, model_id: str) -> ConfiguredModelAdapter:
        return self._adapters[model_id.lower()]

    def probe_all(self) -> list[dict[str, Any]]:
        return [self._adapters[model_id].probe() for model_id in MODEL_IDS]


production_registry = ProductionModelRegistry()
