#!/bin/bash
# Activate the STAMPUP PepMLM isolated runtime environment.

set -euo pipefail

STAMPUP_ROOT=/home/xh/kxc/stampup
DEV_PROJECT=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
DEV_FRONTEND_PORT=12823
DEV_BACKEND_PORT=12824
DEV_LOG_DIR=$DEV_PROJECT/logs_dev
DEV_REPORT_DIR=$DEV_PROJECT/reports
DEV_DATA_DIR=$DEV_PROJECT/data_dev
DEV_MODELS_DIR=$DEV_PROJECT/models_dev
DEV_ENV_DIR=$STAMPUP_ROOT/tools/envs/pepmlm
DEV_PIP_CACHE_DIR=$STAMPUP_ROOT/tools/pip_cache

CURRENT_PWD="$(pwd -P)"
if [ "$CURRENT_PWD" != "$DEV_PROJECT" ]; then
  echo "[STAMPUP] Refusing to activate PepMLM env from '$CURRENT_PWD'. Use '$DEV_PROJECT'." >&2
  exit 1
fi

case "$DEV_PROJECT" in
  /home/xh/stamp|/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform|/home/xh)
    echo "[STAMPUP] Refusing to activate PepMLM env: unsafe project path '$DEV_PROJECT'." >&2
    exit 1
    ;;
esac

if [ -f "$DEV_ENV_DIR/bin/activate" ]; then
  # shellcheck disable=SC1090
  source "$DEV_ENV_DIR/bin/activate"
elif [ -x "$DEV_ENV_DIR/bin/python" ]; then
  export PATH="$DEV_ENV_DIR/bin:$PATH"
  export CONDA_PREFIX="$DEV_ENV_DIR"
  export CONDA_DEFAULT_ENV="pepmlm"
else
  echo "[STAMPUP] PepMLM runtime is missing: $DEV_ENV_DIR" >&2
  exit 1
fi

export STAMPUP_ROOT DEV_PROJECT DEV_FRONTEND_PORT DEV_BACKEND_PORT DEV_LOG_DIR DEV_REPORT_DIR DEV_DATA_DIR DEV_MODELS_DIR
export PIP_CACHE_DIR="$DEV_PIP_CACHE_DIR"
export HF_HOME="$DEV_MODELS_DIR/hf_home"
export TRANSFORMERS_CACHE="$DEV_MODELS_DIR/transformers_cache"
export TORCH_HOME="$DEV_MODELS_DIR/torch_cache"
export PEPMLM_MODEL_PATH="$DEV_MODELS_DIR/pepmlm/ChatterjeeLab_PepMLM-650M"
export PEPMLM_SOURCE_PATH="$DEV_MODELS_DIR/pepmlm/source/pepmlm"
export PEPMLM_DEVICE="cuda"
export PEPMLM_ALLOW_DOWNLOAD="false"
export PEPMLM_OFFLINE_ONLY="true"
export TRANSFORMERS_OFFLINE="1"
export HF_HUB_OFFLINE="1"
export PYTHONNOUSERSITE="1"
export STAMPUP_ENV_CHECK_SCRIPT="$DEV_PROJECT/scripts/ops/stampup_pepmlm_env_check.sh"
export STAMPUP_RECOMMENDED_RUNTIME_ENV="$DEV_PROJECT/scripts/ops/stampup_pepmlm_env.sh"
