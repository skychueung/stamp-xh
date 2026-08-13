# STAMPUP P6 PepMLM Isolated Environment Report

## 1. Reconciliation
- Host: `xh-System-Product-Name`
- User: `xh`
- Working directory: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- Formal symlink: `/home/xh/stamp -> /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`
- Formal services remain healthy: `8080` and `8001`
- Dev services remain healthy: `12823` and `12824`

## 2. Python / CUDA environment plan
- Isolated runtime location: `/home/xh/kxc/stampup/tools/envs/pepmlm`
- Runtime scheme: `conda clone` from `/home/xh/miniconda3/envs/evodiff` into `stampup/tools/envs/pepmlm`
- Why this path: the server already had a CUDA-enabled PyTorch environment and cloning kept the runtime under `stampup` without downloading the 664 MB PyTorch CUDA wheel again.
- Backend FastAPI process remains on the existing system Python runtime and is not switched to the PepMLM runtime.

## 3. Installed dependencies
- `torch==2.4.1+cu118`
- `transformers==4.57.6`
- `huggingface_hub==0.36.2`
- `accelerate==1.10.1`
- `sentencepiece==0.2.1`
- `protobuf==6.33.6`
- `numpy==1.26.4`

## 4. PepMLM isolated runtime check
- Env check script: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env_check.sh`
- Runtime activation script: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env.sh`
- Latest env check JSON: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/logs_dev/pepmlm/env_checks/pepmlm_env_check_20260602_232340.json`
- Latest env freeze: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/logs_dev/pepmlm/pepmlm_env_freeze.txt`
- PepMLM env Python: `/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python`
- Python version: `3.9.25`
- torch version: `2.4.1+cu118`
- `torch.cuda.is_available()`: `True`
- `torch.cuda.device_count()`: `2`
- GPU names: `NVIDIA GeForce RTX 4090` x2
- `HF_HOME`: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/hf_home`
- `TRANSFORMERS_CACHE`: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/transformers_cache`
- `TORCH_HOME`: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/torch_cache`
- `PEPMLM_MODEL_PATH`: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M`
- `PEPMLM_ALLOW_DOWNLOAD`: `false`
- `PEPMLM_OFFLINE_ONLY`: `true`
- `PEPMLM_SOURCE_PATH`: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm`
- `PEPMLM` probe status in isolated env: `AVAILABLE`
- `backend_env_status`: `DEPENDENCY_MISSING`
- `pepmlm_env_status`: `AVAILABLE`
- No model download was attempted.
- No inference was executed.
- No candidates were generated.
- No scientific metrics were fabricated.

## 5. Probe API results
- `GET /api/v1/target-peptide-design/models/PepMLM/probe` now returns `status=AVAILABLE`
- `pepmlm_env_python` is reported as `/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python`
- `pepmlm_env_check_script` is reported as `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env_check.sh`
- `recommended_runtime_env` is reported as `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env.sh`
- The summary probe endpoint also reports `pepmlm_status=AVAILABLE`
- The backend process runtime itself still reports `DEPENDENCY_MISSING`, which is expected and now explicitly separated from the PepMLM isolated runtime

## 6. Files changed in this task
- `backend/app/services/target_peptide_model_probe.py`
- `backend/app/schemas/target_peptide_design.py`
- `backend/tests/test_target_peptide_model_probe.py`
- `src/lib/targetPeptideDesignApi.ts`
- `src/pages/TargetedPeptideDesignPage.tsx`
- `scripts/ops/stampup_pepmlm_env.sh`
- `scripts/ops/stampup_pepmlm_env_check.sh`

## 7. New / updated scripts
- `scripts/ops/stampup_pepmlm_env.sh`
  - Activates the PepMLM isolated runtime and exports all required stampup-only cache/path variables.
- `scripts/ops/stampup_pepmlm_env_check.sh`
  - Checks torch / transformers / huggingface_hub / CUDA / path writability without running inference.

## 8. Validation results
- Targeted backend tests: `pytest backend/tests/test_target_peptide_design.py backend/tests/test_target_peptide_model_probe.py -q` -> `14 passed`
- Full pytest: still blocked by pre-existing collection import error in `backend/tests/test_flexpepdock_batch.py`
- Frontend build: `npm run build` -> passed
- `bash scripts/ops/stampup_status.sh` -> PASS
- `bash scripts/ops/stampup_healthcheck.sh` -> PASS
- Dev `12823` -> `200 OK`
- Dev `12824/api/health` -> healthy
- Formal `8080` -> `200 OK`
- Formal `8001/api/health` -> healthy
- `/home/xh/stamp` -> unchanged

## 9. 8000 residual check
- Runtime grep over `src/`, `vite.config.ts`, and `.env*` found no default `8000` direct client residuals.
- No new runtime `8000` fallback was introduced in P6.

## 10. Scientific boundary
- Current phase only prepares a PepMLM isolated runtime and environment probe.
- No PepMLM inference was executed.
- No candidates were generated.
- No real scientific results were produced or fabricated.

## 11. Next step
- P7 should introduce a controlled runner / subprocess execution path that uses `scripts/ops/stampup_pepmlm_env.sh` for any later gated PepMLM execution, while keeping the FastAPI backend itself on the existing runtime.
