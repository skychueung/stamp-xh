#!/bin/bash
# Check the PepMLM isolated runtime environment without running inference.

set -euo pipefail

STAMPUP_ROOT=/home/xh/kxc/stampup
DEV_PROJECT=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
DEV_FRONTEND_PORT=12823
DEV_BACKEND_PORT=12824
DEV_LOG_DIR=$DEV_PROJECT/logs_dev
DEV_REPORT_DIR=$DEV_PROJECT/reports
DEV_DATA_DIR=$DEV_PROJECT/data_dev
DEV_MODELS_DIR=$DEV_PROJECT/models_dev
CHECK_DIR=$DEV_LOG_DIR/pepmlm/env_checks

CURRENT_PWD="$(pwd -P)"
if [ "$CURRENT_PWD" != "$DEV_PROJECT" ]; then
  echo "[STAMPUP] Refusing to run PepMLM env check from '$CURRENT_PWD'. Use '$DEV_PROJECT'." >&2
  exit 1
fi

case "$DEV_PROJECT" in
  /home/xh/stamp|/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform|/home/xh)
    echo "[STAMPUP] Refusing to run PepMLM env check: unsafe project path '$DEV_PROJECT'." >&2
    exit 1
    ;;
esac

mkdir -p "$CHECK_DIR"
# shellcheck disable=SC1090
source "$DEV_PROJECT/scripts/ops/stampup_pepmlm_env.sh"
export STAMPUP_ENV_CHECK_SCRIPT="$DEV_PROJECT/scripts/ops/stampup_pepmlm_env_check.sh"
export STAMPUP_RECOMMENDED_RUNTIME_ENV="$DEV_PROJECT/scripts/ops/stampup_pepmlm_env.sh"

REPORT_FILE="$CHECK_DIR/pepmlm_env_check_$(date +%Y%m%d_%H%M%S).json"
LOG_FILE="$CHECK_DIR/pepmlm_env_check_$(date +%Y%m%d_%H%M%S).log"
export REPORT_FILE

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== STAMPUP PepMLM Env Check $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "host: $(hostname)"
echo "user: $(whoami)"
echo "pwd: $CURRENT_PWD"
echo "venv_python: $(command -v python)"
echo "venv_version: $(python --version 2>&1)"
echo "hf_home: $HF_HOME"
echo "transformers_cache: $TRANSFORMERS_CACHE"
echo "torch_home: $TORCH_HOME"
echo "pepmlm_model_path: $PEPMLM_MODEL_PATH"
echo "pepmlm_source_path: $PEPMLM_SOURCE_PATH"
echo "allow_download: $PEPMLM_ALLOW_DOWNLOAD"
echo "offline_only: $PEPMLM_OFFLINE_ONLY"
echo "No inference executed. No candidates generated."

python - <<'PY'
import importlib
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

report_file = Path(os.environ["REPORT_FILE"])
model_path = Path(os.environ.get("PEPMLM_MODEL_PATH", "")).expanduser()
source_path = Path(os.environ.get("PEPMLM_SOURCE_PATH", "")).expanduser()
models_dir = Path(os.environ.get("DEV_MODELS_DIR", "")).expanduser()
data_dir = Path(os.environ.get("DEV_DATA_DIR", "")).expanduser() / "target_peptide_design"


def safe_import(module_name: str) -> dict[str, object]:
    try:
        module = importlib.import_module(module_name)
        return {
            "available": True,
            "version": getattr(module, "__version__", None),
            "error": None,
        }
    except Exception as exc:
        return {
            "available": False,
            "version": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def path_status(path: Path) -> dict[str, object]:
    result = {
        "path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "readable": False,
        "writable": False,
        "empty": None,
    }
    try:
        result["readable"] = os.access(path, os.R_OK)
        result["writable"] = os.access(path, os.W_OK)
        if path.exists() and path.is_dir():
            try:
                next(path.iterdir())
                result["empty"] = False
            except StopIteration:
                result["empty"] = True
            except Exception:
                result["empty"] = None
    except Exception:
        pass
    return result


def can_write(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".pepmlm_env_probe_write"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


torch_status = safe_import("torch")
transformers_status = safe_import("transformers")
huggingface_status = safe_import("huggingface_hub")

cuda = {
    "available": False,
    "device_count": 0,
    "devices": [],
    "current_device": None,
    "torch_cuda_version": None,
    "error": None,
}
if torch_status["available"]:
    try:
        import torch
        cuda_available = bool(torch.cuda.is_available())
        cuda["available"] = cuda_available
        cuda["device_count"] = int(torch.cuda.device_count()) if cuda_available else 0
        cuda["torch_cuda_version"] = getattr(torch.version, "cuda", None)
        if cuda_available:
            cuda["devices"] = [
                {"index": i, "name": torch.cuda.get_device_name(i)}
                for i in range(cuda["device_count"])
            ]
            cuda["current_device"] = int(torch.cuda.current_device()) if cuda["device_count"] > 0 else None
    except Exception as exc:
        cuda["error"] = f"{type(exc).__name__}: {exc}"

model_exists = model_path.exists()
model_is_dir = model_path.is_dir()
model_empty = None
if model_exists and model_is_dir:
    try:
        model_empty = not any(model_path.iterdir())
    except Exception:
        model_empty = None

source_exists = source_path.exists()
source_is_dir = source_path.is_dir()
source_commit = None
try:
    import subprocess
    if source_exists:
        source_commit = subprocess.run(
            ["git", "-C", str(source_path), "rev-parse", "HEAD"],
            check=False,
            capture_output=True,
            text=True,
        ).stdout.strip() or None
except Exception:
    source_commit = None

status = "CONFIG_REQUIRED"
message = "PepMLM model path or Hugging Face model id is not configured."
if not torch_status["available"] or not transformers_status["available"] or not huggingface_status["available"]:
    status = "DEPENDENCY_MISSING"
    message = "PepMLM isolated runtime dependencies are missing; no inference was executed."
elif not model_exists or not model_is_dir or model_empty:
    status = "CONFIG_REQUIRED"
    message = "PepMLM model artifacts are not fully staged in the isolated runtime."
elif not cuda["available"]:
    status = "GPU_NOT_AVAILABLE"
    message = "PepMLM isolated runtime dependencies are ready, but CUDA is not available."
else:
    status = "AVAILABLE"
    message = "PepMLM isolated runtime dependencies, model path, and CUDA are available; no inference was executed."

payload = {
    "probe_time": datetime.now(timezone.utc).isoformat(),
    "status": status,
    "message": message,
    "backend_env_status": "DEPENDENCY_MISSING",
    "pepmlm_env_status": status,
    "pepmlm_env_python": sys.executable,
    "pepmlm_env_check_script": os.environ.get("STAMPUP_ENV_CHECK_SCRIPT", ""),
    "recommended_runtime_env": os.environ.get("STAMPUP_RECOMMENDED_RUNTIME_ENV", ""),
    "python_version": sys.version.split()[0],
    "dependency_status": {
        "torch": torch_status,
        "transformers": transformers_status,
        "huggingface_hub": huggingface_status,
    },
    "cuda_status": cuda,
    "path_status": {
        "pepmlm_model_path": path_status(model_path),
        "pepmlm_source_path": path_status(source_path),
        "models_dev": path_status(models_dir),
        "data_dev_target_peptide_design": path_status(data_dir),
    },
    "config_status": {
        "pepmlm_model_path": str(model_path),
        "pepmlm_source_path": str(source_path),
        "pepmlm_allow_download": os.environ.get("PEPMLM_ALLOW_DOWNLOAD", "false").lower() == "true",
        "pepmlm_offline_only": os.environ.get("PEPMLM_OFFLINE_ONLY", "true").lower() == "true",
        "hf_home": os.environ.get("HF_HOME", ""),
        "transformers_cache": os.environ.get("TRANSFORMERS_CACHE", ""),
        "torch_home": os.environ.get("TORCH_HOME", ""),
    },
    "writeability": {
        "models_dev": can_write(models_dir),
        "data_dev_target_peptide_design": can_write(data_dir),
    },
    "model_artifacts": {
        "exists": model_exists,
        "is_dir": model_is_dir,
        "empty": model_empty,
    },
    "source_artifacts": {
        "exists": source_exists,
        "is_dir": source_is_dir,
        "git_commit": source_commit,
    },
    "scientific_boundary": "Current phase only performs environment probes; no model download or inference was run.",
    "next_action": (
        "Install missing isolated-runtime dependencies first."
        if status == "DEPENDENCY_MISSING"
        else (
            "Stage missing artifacts into models_dev first."
            if status == "CONFIG_REQUIRED"
            else (
                "Provision GPU-backed runtime for real inference."
                if status == "GPU_NOT_AVAILABLE"
                else "PepMLM isolated runtime is ready; keep inference gated by later workflow approval."
            )
        )
    ),
}

report_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"RESULT_JSON={report_file}")
PY
