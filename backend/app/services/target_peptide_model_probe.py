"""Model probe utilities for the Targeted Peptide Design Center."""

from __future__ import annotations

import importlib
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import settings
from app.schemas.target_peptide_design import (
    TargetPeptideDesignModelProbeResult,
    TargetPeptideDesignModelProbesResponse,
)
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    get_target_peptide_model,
    list_target_peptide_models,
)

DEV_PROJECT_ROOT = Path(__file__).resolve().parents[3]
PEPMLM_ENV_SCRIPT = DEV_PROJECT_ROOT / "scripts/ops/stampup_pepmlm_env.sh"
PEPMLM_ENV_CHECK_SCRIPT = DEV_PROJECT_ROOT / "scripts/ops/stampup_pepmlm_env_check.sh"
PEPMLM_ENV_CHECK_TIMEOUT_SECONDS = 300

PROBE_NOTE = "Current phase only performs environment probes; no model download or inference was run."
PEPMLM_CONFIG_REQUIRED_MESSAGE = (
    "PepMLM is registered but not configured yet; set PEPMLM_MODEL_PATH or PEPMLM_HF_MODEL_ID before real inference."
)
PEPMLM_OFFLINE_ONLY_MESSAGE = (
    "PepMLM is in offline-only mode and no local model artifacts are available; no download or inference was attempted."
)
PEPMLM_GPU_NOT_AVAILABLE_MESSAGE = (
    "PepMLM isolated environment probe passed, but CUDA is not available, so no real inference was attempted."
)
PEPMLM_AVAILABLE_MESSAGE = (
    "PepMLM isolated environment probe passed; no real inference was attempted in P6."
)
PLANNED_MESSAGE = "Model remains planned; no runtime integration or probe execution was performed."


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utcnow().isoformat()


def get_target_peptide_design_root() -> Path:
    return Path(settings.stamp_data_dir).expanduser().resolve() / "target_peptide_design"


def get_target_peptide_design_probe_root() -> Path:
    return get_target_peptide_design_root() / "probes"


def _safe_import_module(module_name: str) -> dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
        return {
            "available": True,
            "version": getattr(module, "__version__", None),
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - import failures are environment dependent
        return {
            "available": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _writable_dir_status(path: Path) -> dict[str, Any]:
    path = path.expanduser()
    status: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "writable": False,
        "error": None,
    }
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / f".write_probe_{uuid4().hex}.tmp"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink(missing_ok=True)
        status["writable"] = True
    except Exception as exc:  # pragma: no cover - depends on filesystem permissions
        status["error"] = f"{type(exc).__name__}: {exc}"
    return status


def _collect_backend_dependency_status() -> dict[str, Any]:
    python_version = sys.version.split()[0]
    pip_executable = shutil.which("pip3") or shutil.which("pip")
    return {
        "python_executable": sys.executable,
        "python_version": python_version,
        "pip_executable": pip_executable,
        "torch": _safe_import_module("torch"),
        "transformers": _safe_import_module("transformers"),
        "huggingface_hub": _safe_import_module("huggingface_hub"),
    }


def _collect_backend_cuda_status(dependency_status: dict[str, Any]) -> dict[str, Any]:
    torch_status = dependency_status["torch"]
    if not torch_status.get("available"):
        return {
            "available": False,
            "device_count": 0,
            "devices": [],
            "torch_cuda_version": None,
            "current_device": None,
            "error": torch_status.get("error"),
        }

    try:
        import torch

        available = bool(torch.cuda.is_available())
        device_count = int(torch.cuda.device_count()) if available else 0
        devices: list[dict[str, Any]] = []
        if available:
            for index in range(device_count):
                devices.append(
                    {
                        "index": index,
                        "name": torch.cuda.get_device_name(index),
                    }
                )
        current_device = int(torch.cuda.current_device()) if available and device_count > 0 else None
        return {
            "available": available,
            "device_count": device_count,
            "devices": devices,
            "torch_cuda_version": getattr(torch.version, "cuda", None),
            "current_device": current_device,
            "error": None,
        }
    except Exception as exc:  # pragma: no cover - GPU availability varies by host
        return {
            "available": False,
            "device_count": 0,
            "devices": [],
            "torch_cuda_version": None,
            "current_device": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _collect_path_status() -> dict[str, Any]:
    models_dir = Path(settings.target_peptide_models_dir).expanduser().resolve()
    design_root = get_target_peptide_design_root()
    probe_root = get_target_peptide_design_probe_root()
    return {
        "target_peptide_models_dir": _writable_dir_status(models_dir),
        "target_peptide_design_root": _writable_dir_status(design_root),
        "probe_root": _writable_dir_status(probe_root),
    }


def _collect_config_status() -> dict[str, Any]:
    model_path = settings.pepmlm_model_path.strip() if settings.pepmlm_model_path else None
    hf_model_id = settings.pepmlm_hf_model_id.strip() if settings.pepmlm_hf_model_id else None
    model_path_obj = Path(model_path).expanduser().resolve() if model_path else None
    model_path_exists = model_path_obj.exists() if model_path_obj else False
    model_path_is_dir = model_path_obj.is_dir() if model_path_obj else False
    model_path_empty = False
    if model_path_obj and model_path_exists and model_path_is_dir:
        try:
            model_path_empty = not any(model_path_obj.iterdir())
        except Exception:
            model_path_empty = True

    return {
        "pepmlm_model_path_configured": bool(model_path),
        "pepmlm_model_path": str(model_path_obj) if model_path_obj else None,
        "pepmlm_model_path_exists": model_path_exists,
        "pepmlm_model_path_is_dir": model_path_is_dir,
        "pepmlm_model_path_empty": model_path_empty,
        "pepmlm_hf_model_id_configured": bool(hf_model_id),
        "pepmlm_hf_model_id": hf_model_id,
        "pepmlm_device": settings.pepmlm_device,
        "pepmlm_allow_download": settings.pepmlm_allow_download,
        "pepmlm_offline_only": settings.pepmlm_offline_only,
        "target_peptide_models_dir": str(Path(settings.target_peptide_models_dir).expanduser().resolve()),
    }


def _collect_backend_environment_context() -> dict[str, Any]:
    dependency_status = _collect_backend_dependency_status()
    cuda_status = _collect_backend_cuda_status(dependency_status)
    path_status = _collect_path_status()
    config_status = _collect_config_status()
    return {
        "dependency_status": dependency_status,
        "cuda_status": cuda_status,
        "path_status": path_status,
        "config_status": config_status,
    }


def _collect_backend_env_status(context: dict[str, Any]) -> str:
    dependency_status = context["dependency_status"]
    cuda_status = context["cuda_status"]
    path_status = context["path_status"]
    config_status = context["config_status"]

    if not dependency_status["torch"]["available"] or not dependency_status["transformers"]["available"] or not dependency_status["huggingface_hub"]["available"]:
        return "DEPENDENCY_MISSING"

    models_dir_writable = bool(path_status["target_peptide_models_dir"]["writable"])
    data_dir_writable = bool(path_status["target_peptide_design_root"]["writable"])
    probe_dir_writable = bool(path_status["probe_root"]["writable"])
    if not models_dir_writable or not data_dir_writable or not probe_dir_writable:
        return "MODEL_NOT_AVAILABLE"

    model_path_configured = bool(config_status["pepmlm_model_path_configured"])
    hf_model_id_configured = bool(config_status["pepmlm_hf_model_id_configured"])
    model_path_exists = bool(config_status["pepmlm_model_path_exists"])
    model_path_is_dir = bool(config_status["pepmlm_model_path_is_dir"])
    model_path_empty = bool(config_status["pepmlm_model_path_empty"])
    offline_only = bool(config_status["pepmlm_offline_only"])
    allow_download = bool(config_status["pepmlm_allow_download"])

    if not model_path_configured and not hf_model_id_configured:
        return "CONFIG_REQUIRED"

    local_artifacts_available = model_path_exists and model_path_is_dir and not model_path_empty
    if local_artifacts_available:
        if not cuda_status["available"]:
            return "GPU_NOT_AVAILABLE"
        return "AVAILABLE"

    if model_path_configured and not model_path_exists:
        if offline_only or not allow_download:
            return "OFFLINE_ONLY"
        return "MODEL_NOT_AVAILABLE"

    if model_path_configured and model_path_is_dir and model_path_empty:
        if offline_only or not allow_download:
            return "OFFLINE_ONLY"
        return "MODEL_NOT_AVAILABLE"

    if hf_model_id_configured:
        if offline_only or not allow_download:
            return "OFFLINE_ONLY"
        return "MODEL_NOT_AVAILABLE"

    return "CONFIG_REQUIRED"


def _collect_pepmlm_env_probe() -> dict[str, Any]:
    fallback = {
        "probe_time": _iso_now(),
        "status": "DEPENDENCY_MISSING",
        "message": "PepMLM isolated environment probe is unavailable; falling back to backend dependency status.",
        "backend_env_status": "DEPENDENCY_MISSING",
        "pepmlm_env_status": "DEPENDENCY_MISSING",
        "pepmlm_env_python": None,
        "pepmlm_env_check_script": str(PEPMLM_ENV_CHECK_SCRIPT),
        "recommended_runtime_env": str(PEPMLM_ENV_SCRIPT),
        "python_version": sys.version.split()[0],
        "dependency_status": {
            "torch": _safe_import_module("torch"),
            "transformers": _safe_import_module("transformers"),
            "huggingface_hub": _safe_import_module("huggingface_hub"),
        },
        "cuda_status": _collect_backend_cuda_status(_collect_backend_dependency_status()),
        "path_status": _collect_path_status(),
        "config_status": _collect_config_status(),
        "writeability": {
            "models_dev": False,
            "data_dev_target_peptide_design": False,
        },
        "model_artifacts": {
            "exists": False,
            "is_dir": False,
            "empty": None,
        },
        "source_artifacts": {
            "exists": False,
            "is_dir": False,
            "git_commit": None,
        },
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
        "next_action": "Install missing isolated-runtime dependencies first.",
    }

    if not PEPMLM_ENV_CHECK_SCRIPT.exists():
        fallback["message"] = f"PepMLM env check script is missing: {PEPMLM_ENV_CHECK_SCRIPT}"
        return fallback

    try:
        result = subprocess.run(
            ["bash", str(PEPMLM_ENV_CHECK_SCRIPT)],
            cwd=str(DEV_PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=PEPMLM_ENV_CHECK_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - depends on local runtime
        fallback["message"] = f"PepMLM env check failed to execute: {type(exc).__name__}: {exc}"
        return fallback

    stdout = result.stdout or ""
    stderr = result.stderr or ""
    json_path: Path | None = None
    for line in reversed(stdout.splitlines()):
        match = re.match(r"^RESULT_JSON=(.+)$", line.strip())
        if match:
            json_path = Path(match.group(1)).expanduser()
            break

    if result.returncode != 0 or json_path is None or not json_path.exists():
        fallback["message"] = (
            f"PepMLM env check returned {result.returncode}; using backend dependency status."
            if result.returncode != 0
            else "PepMLM env check did not produce a JSON report; using backend dependency status."
        )
        if stderr:
            fallback["message"] += f" stderr={stderr.strip()}"
        return fallback

    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - unexpected file contents
        fallback["message"] = f"PepMLM env check JSON parse failed: {type(exc).__name__}: {exc}"
        return fallback

    payload["backend_env_status"] = _collect_backend_env_status(_collect_backend_environment_context())
    payload.setdefault("pepmlm_env_status", payload.get("status", "DEPENDENCY_MISSING"))
    payload.setdefault("pepmlm_env_check_script", str(PEPMLM_ENV_CHECK_SCRIPT))
    payload.setdefault("recommended_runtime_env", str(PEPMLM_ENV_SCRIPT))
    payload.setdefault("scientific_boundary", SCIENTIFIC_BOUNDARY_NOTE)
    payload.setdefault("next_action", "PepMLM isolated runtime probe completed; keep inference gated by later workflow approval.")
    return payload


def _build_pepmlm_message(status: str, pepmlm_env_payload: dict[str, Any] | None = None) -> str:
    if pepmlm_env_payload and pepmlm_env_payload.get("message"):
        return str(pepmlm_env_payload["message"])
    if status == "AVAILABLE":
        return PEPMLM_AVAILABLE_MESSAGE
    if status == "GPU_NOT_AVAILABLE":
        return PEPMLM_GPU_NOT_AVAILABLE_MESSAGE
    if status == "OFFLINE_ONLY":
        return PEPMLM_OFFLINE_ONLY_MESSAGE
    if status == "DEPENDENCY_MISSING":
        return "Required Python dependencies are missing from the isolated runtime environment."
    if status == "MODEL_NOT_AVAILABLE":
        return "PepMLM model artifacts are not available locally."
    return PEPMLM_CONFIG_REQUIRED_MESSAGE


def _build_next_action(status: str, model_id: str) -> str:
    if model_id != "PepMLM":
        return "Keep the model on the roadmap until an integration runner is added."
    if status == "AVAILABLE":
        return (
            "PepMLM isolated runtime is ready; keep inference gated by later workflow approval. "
            "Do not run real inference in P6."
        )
    if status == "GPU_NOT_AVAILABLE":
        return "Provision a GPU-backed runtime before attempting real PepMLM inference."
    if status == "OFFLINE_ONLY":
        return "Either stage local artifacts into models_dev or switch to a later controlled download phase."
    if status == "DEPENDENCY_MISSING":
        return "Install the missing Python dependencies in the isolated runtime and re-run the probe."
    if status == "MODEL_NOT_AVAILABLE":
        return "Stage model artifacts into the stampup models_dev directory before attempting integration."
    return "Configure PEPMLM_MODEL_PATH or PEPMLM_HF_MODEL_ID, then re-run the probe."


def _build_model_probe_result(
    model_id: str,
    context: dict[str, Any],
    probe_time: datetime,
    pepmlm_env_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    model = get_target_peptide_model(model_id)
    if model is None:
        raise ValueError(f"Unknown model_id '{model_id}'")

    backend_env_status = _collect_backend_env_status(context)
    if model_id == "PepMLM":
        pepmlm_env_status = str((pepmlm_env_payload or {}).get("pepmlm_env_status") or (pepmlm_env_payload or {}).get("status") or backend_env_status)
        status = pepmlm_env_status
        message = _build_pepmlm_message(status, pepmlm_env_payload)
        next_action = str((pepmlm_env_payload or {}).get("next_action") or _build_next_action(status, model_id))
    else:
        status = str(model["status"])
        message = PLANNED_MESSAGE
        next_action = _build_next_action(status, model_id)
        pepmlm_env_status = str((pepmlm_env_payload or {}).get("pepmlm_env_status") or backend_env_status)

    payload = {
        "probe_time": probe_time,
        "model_id": model["model_id"],
        "display_name": model["display_name"],
        "status": status,
        "message": message,
        "backend_env_status": backend_env_status,
        "pepmlm_env_status": pepmlm_env_status,
        "pepmlm_env_python": (pepmlm_env_payload or {}).get("pepmlm_env_python"),
        "pepmlm_env_check_script": (pepmlm_env_payload or {}).get("pepmlm_env_check_script", str(PEPMLM_ENV_CHECK_SCRIPT)),
        "recommended_runtime_env": (pepmlm_env_payload or {}).get("recommended_runtime_env", str(PEPMLM_ENV_SCRIPT)),
        "dependency_status": context["dependency_status"],
        "cuda_status": context["cuda_status"],
        "path_status": context["path_status"],
        "config_status": context["config_status"],
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
        "next_action": next_action,
    }
    if pepmlm_env_payload and model_id == "PepMLM":
        payload["pepmlm_env_status_detail"] = pepmlm_env_payload
    return payload


def _persist_probe_payload(filename_prefix: str, payload: dict[str, Any], probe_time: datetime) -> Path:
    probe_root = get_target_peptide_design_probe_root()
    probe_root.mkdir(parents=True, exist_ok=True)
    timestamp = probe_time.strftime("%Y%m%d_%H%M%S")
    path = probe_root / f"{filename_prefix}_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _summarize_probes(probes: list[dict[str, Any]], probe_time: datetime, pepmlm_env_payload: dict[str, Any] | None) -> dict[str, Any]:
    counts = Counter(str(item["status"]) for item in probes)
    pepmlm_probe = next((item for item in probes if item["model_id"] == "PepMLM"), None)
    path_status = probes[0]["path_status"] if probes else _collect_backend_environment_context()["path_status"]
    config_status = probes[0]["config_status"] if probes else _collect_config_status()
    return {
        "probe_time": probe_time.isoformat(),
        "total_models": len(probes),
        "available_models": counts.get("AVAILABLE", 0),
        "config_required_models": counts.get("CONFIG_REQUIRED", 0),
        "dependency_missing_models": counts.get("DEPENDENCY_MISSING", 0),
        "gpu_not_available_models": counts.get("GPU_NOT_AVAILABLE", 0),
        "model_not_available_models": counts.get("MODEL_NOT_AVAILABLE", 0),
        "offline_only_models": counts.get("OFFLINE_ONLY", 0),
        "planned_models": counts.get("PLANNED", 0),
        "pepmlm_status": pepmlm_probe["status"] if pepmlm_probe else "PLANNED",
        "pepmlm_env_status": pepmlm_env_payload.get("pepmlm_env_status") if pepmlm_env_payload else None,
        "pepmlm_next_action": pepmlm_probe["next_action"] if pepmlm_probe else "PepMLM probe not available.",
        "pepmlm_env_python": pepmlm_env_payload.get("pepmlm_env_python") if pepmlm_env_payload else None,
        "pepmlm_env_check_script": str(PEPMLM_ENV_CHECK_SCRIPT),
        "recommended_runtime_env": str(PEPMLM_ENV_SCRIPT),
        "probe_dir": str(get_target_peptide_design_probe_root()),
        "models_dir": str(Path(settings.target_peptide_models_dir).expanduser().resolve()),
        "models_dir_writable": path_status["target_peptide_models_dir"]["writable"],
        "data_dir_writable": path_status["target_peptide_design_root"]["writable"],
        "probe_dir_writable": path_status["probe_root"]["writable"],
        "pepmlm_model_path_configured": bool(config_status["pepmlm_model_path_configured"]),
        "pepmlm_hf_model_id_configured": bool(config_status["pepmlm_hf_model_id_configured"]),
        "pepmlm_allow_download": bool(config_status["pepmlm_allow_download"]),
        "pepmlm_offline_only": bool(config_status["pepmlm_offline_only"]),
        "backend_env_status": pepmlm_probe["backend_env_status"] if pepmlm_probe else _collect_backend_env_status(_collect_backend_environment_context()),
    }


def get_target_peptide_model_probe(model_id: str) -> TargetPeptideDesignModelProbeResult:
    probe_time = _utcnow()
    context = _collect_backend_environment_context()
    pepmlm_env_payload = _collect_pepmlm_env_probe() if model_id == "PepMLM" else None
    payload = _build_model_probe_result(model_id, context, probe_time, pepmlm_env_payload)
    model_probe = TargetPeptideDesignModelProbeResult.model_validate(payload)
    saved_path = _persist_probe_payload(f"{model_id.lower()}_probe", model_probe.model_dump(mode="json"), probe_time)
    _ = saved_path
    return model_probe


def get_target_peptide_model_probes() -> TargetPeptideDesignModelProbesResponse:
    probe_time = _utcnow()
    context = _collect_backend_environment_context()
    pepmlm_env_payload = _collect_pepmlm_env_probe()
    probes = [
        _build_model_probe_result(model["model_id"], context, probe_time, pepmlm_env_payload if model["model_id"] == "PepMLM" else None)
        for model in list_target_peptide_models()
    ]
    response_payload = {
        "probe_time": probe_time,
        "probes": probes,
        "scientific_boundary": SCIENTIFIC_BOUNDARY_NOTE,
        "summary": _summarize_probes(probes, probe_time, pepmlm_env_payload),
    }
    response = TargetPeptideDesignModelProbesResponse.model_validate(response_payload)
    _persist_probe_payload('models_probe', response.model_dump(mode='json'), probe_time)
    return response
