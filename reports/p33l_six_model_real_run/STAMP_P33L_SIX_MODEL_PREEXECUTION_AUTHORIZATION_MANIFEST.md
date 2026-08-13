# STAMP P33L — Six-Model Pre-Execution Authorization Manifest

**Task ID:** P33L  
**Title:** STAMP_P33L_SIX_MODEL_ONE_CLICK_REAL_RUN_AND_DELIVERY_GOAL  
**Phase:** Phase 3 — Frozen pre-execution authorization manifest  
**Date:** 2026-06-29  
**Server:** xh-System-Product-Name (192.168.31.218)  
**Project Root:** `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`  
**Artifact Root:** `/mnt/sdb/kxc/stamp_models/artifacts/p33l/<job_id>/`

---

## 1. Authorization Statement

This manifest freezes the exact plan for the P33L six-model one-click real run. No model may be executed under P33L unless the user explicitly authorizes this manifest by the SHA256 recorded in `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`.

**Required user authorization text:**

> 授权执行 P33L manifest；权威 SHA256 见同目录 `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`；按六模型固定顺序各一次真实运行，失败即停，禁止自动或手工重试。

Without this authorization and the matching `P33L_AUTHORIZED_MANIFEST_SHA` env var on the dev backend, Phase 4 is prohibited. The env var value must equal the SHA256 recorded in `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`.

---

## 2. Execution Policy

| Policy | Value |
|---|---|
| Fixed order | PepMLM → EvoBind2 → DiffPepBuilder → PepFlow → PepHAR → PPFlow |
| Max attempts per model | 1 |
| Concurrent P33L jobs | 1 |
| Concurrent P33L model processes | 1 |
| Failure behavior | Immediate stop; no retry; subsequent models `SKIPPED_DUE_TO_PRIOR_FAILURE` |
| Real-run gate | File-based, per-job, TTL enforced, bound to manifest SHA |
| GPU lock | File-based (`/tmp/stamp_gpu.lock`), one GPU at a time, no preemption |
| Artifact root | `/mnt/sdb/kxc/stamp_models/artifacts/p33l/<job_id>/` |
| Gate root | `/home/xh/kxc/stampup/run_gates/p33l/<model_id>/<job_id>/gate.json` |
| State file | `/home/xh/kxc/stampup/run_gates/p33l/state.json` |
| GPU device pool | `CUDA_VISIBLE_DEVICES` = 0 or 1, selected by lock service |
| Wrapper execution block (tests only) | `P33L_BLOCK_ALL_WRAPPER_EXECUTION=true` |
| Manifest SHA source | `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt` |
| Runtime quota monitor | Active; `SIGTERM` to subprocess process group on disk-quota violation |

---

## 3. Phase 2 Patch Evidence

The complete Phase 2 patch was applied to the dev backend and frontend on 2026-06-29.

### 3.1 Backend

| File | After SHA256 |
|---|---|
| `backend/app/services/p33l/config.py` | `6f6d69db3377e65e6857832bdd44cc4af013fb5562895d16be73938d6a257131` |
| `backend/app/services/p33l/gate.py` | `6500c96dffc1dce0f87793abaee4a49e8822b74dabad752cd95625ef95435d79` |
| `backend/app/services/p33l/__init__.py` | `4c670c6b020ae3d6cd4b8b3680ca873f4c7b147c66a58a243f27eb3c5736449f` |
| `backend/app/services/p33l/manifest.py` | `61d80fc23fa23479657e043a8349b2bb94e236fb10db862cec8e5ec87b47b622` |
| `backend/app/services/p33l/orchestrator.py` | `15488feb0e4f220a56e425e294e72f82d5085ca9652ac71cc7814a4b95d627e8` |
| `backend/app/services/p33l/security.py` | `69eae9fdfecf2b713e83b77355b890255e9634508c938647838b0a9b8f62e83f` |
| `backend/app/services/p33l/state.py` | `3ba1dc9db9baa7b860a7732084bf2776cdcead3a8e8fc7c30e662d608ff1da37` |
| `backend/app/services/p33l/wrapper.py` | `ed548002200528c48f132003a07aa3c9ad27bfb0d10950766dc935a798052c6c` |
| `backend/app/main.py` | `d3131cd262984e9c4761407acaf70fdffb293028570e71613ccaacf21eeff684` |
| `backend/app/routers/p33l.py` | `dd3335cf2743cdf347eacdd030bdec73507f6791c6759d062bccb42c4f3eb9d8` |
| `backend/tests/test_p33l_zero_model.py` | `4490158b82b1305dd5d0bfb94a4d58fe0775a83311b84edaecbb5238cd946dd6` |

### 3.2 Frontend — Target Design Run & Deliver

| File | After SHA256 |
|---|---|
| `src/components/p33l/P33LRunPanel.tsx` | `ddb739918d8279d7f8831dd7143bbaddeaf4f5fe15b7297c18088d6c4973cc71` |
| `src/hooks/useP33L.ts` | `97a9eb34688be88a35c994f3493b35779f9e62188d553199961f101271dcc976` |
| `src/lib/api/p33l.ts` | `8122b8db3a915ed9b44a5655136ff18cbf059367c20cd43f8463a8fe2d7320c8` |
| `src/pages/TargetedPeptideDesignCenterPage.tsx` | `79e99e5c6eec309c384e40c266a5aa86709165813ddafbafa9c4a8d46ba99b90` |

Patch backup directory: `/home/xh/kxc/stampup/backups/p33l_phase2_20260629_040030`

Zero-model test result: `37 passed` in `tests/test_p33l_zero_model.py`.

Frontend build result: `npm run build` succeeded on Node 18.19.1 (Vite version warning only).

---

## 4. Per-Model Execution Plan

### 4.1 Attempt 01 — PepMLM

| Field | Value |
|---|---|
| `model_id` | `pepmlm` |
| `display_name` | PepMLM |
| `adapter` | `backend/app/services/model_adapters/pepmlm_adapter.py` |
| `adapter_sha256` | `5c5f9f703d1a81e290855bbaa8b320699eb6eaf79e605f7e1054514d2e7c5553` |
| `runner` | `backend/app/services/model_adapters/pepmlm_adapter.py` (real `submit()` path) |
| `source` | `/home/xh/kxc/stampup/models_dev/pepmlm/scripts/pepmlm_infer.py` |
| `source_sha256` | `3805fd68bbce940f6318ec460633157b73670195915a490b205ed8e8591d988b` |
| `env_python` | `/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python` |
| `checkpoint` | `/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M/model.safetensors` |
| `checkpoint_sha256` | `e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668` |
| `acceptance_fixture` | `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepmlm/ac90e622-492d-4697-a8fa-ce35b2d2bfc5/input/target.fasta` |
| `fixture_sha256` | `7cd0f2cd0a30f231b286c49f64f4deff6428b258f59e2cc027ea41cae0fccc42` |
| `command_preview` | `<env_python> <source> --model_path <checkpoint_dir> --target_sequence <seq> --peptide_length 9 --num_candidates 3 --device cuda --output_dir <run_dir>/output` |
| `device` | cuda (auto-selected GPU) |
| `timeout_seconds` | 3600 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + `output/candidate_sequences.csv` exists + `run_manifest.json` written |
| `failure_criterion` | Non-zero exit, timeout, missing output, manifest write failure, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, kills subprocess tree by recorded PID |

### 4.2 Attempt 02 — EvoBind2

| Field | Value |
|---|---|
| `model_id` | `evobind2` |
| `display_name` | EvoBind2 |
| `adapter` | `backend/app/services/model_adapters/evobind2_adapter.py` |
| `adapter_sha256` | `3931fb6c3f8abc43a1cc23a3f10ddcc651f941354dab18e10a1e0c243828e1a9` |
| `runner` | `backend/app/services/compute_wrappers/evobind2_runner.py` |
| `runner_sha256` | `95698c8e50016bc93346544c59dbeb541363b268835f0d070261263aa3859e19` |
| `source` | `/home/xh/kxc/stampup/models_dev/evobind2/source/EvoBind/src/mc_design.py` |
| `source_sha256` | `9833d00263f652755b073628d06b9f9d0370703a44b1d2f1f75c1e08bc74d121` |
| `env_python` | `/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/envs/evobind/bin/python` |
| `checkpoint` | `/home/xh/kxc/stampup/stamp-small-change-model/models/evobind2/cache/af2_params/params_model_1.npz` |
| `checkpoint_sha256` | `f95e453e6a290ddf317ba1c9698d53fa110cf007ea979b0eae43e6ad38b4e364` |
| `acceptance_fixture` | `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/evobind2/b8ab6d11-5762-4bdf-a9db-6d30602637fd/input/receptor.fasta` |
| `fixture_sha256` | `faba901952b6ddca4d9a09c5ba5fa60de315ba0ea8889e0198531a96d3b76473` |
| `command_preview` | `<env_python> <source> --receptor_fasta_path <run_dir>/input/receptor.fasta --peptide_length 9 --output_dir <run_dir>/output --model_names model_1 --data_dir /home/xh/kxc/stampup/models_dev/evobind2/cache/af2_data_dir --max_recycles 1 --num_iterations 1 --predict_only=True` |
| `device` | cuda (auto-selected GPU) |
| `timeout_seconds` | 7200 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + `output/unrelaxed_true.pdb` exists + `output/metrics.csv` exists |
| `failure_criterion` | Non-zero exit, timeout, missing output, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, closes EvoBind2 per-run gate, kills subprocess tree by recorded PID |

### 4.3 Attempt 03 — DiffPepBuilder

| Field | Value |
|---|---|
| `model_id` | `diffpepbuilder` |
| `display_name` | DiffPepBuilder |
| `adapter` | `backend/app/services/model_adapters/diffpepbuilder_adapter.py` |
| `adapter_sha256` | `becd35d2310063c35a89905310bf932dd6e533b81b65495401e0b5c5daf6891a` |
| `runner` | `/mnt/sdb/kxc/stamp_models/scripts/stamp_diffpepbuilder_p33l_real_runner.py` |
| `runner_sha256` | `09ed88320f9eef8dd5e8bb40814620e3a8c117d7c21a1e131a8fa9f2ec039d29` |
| `source` | `/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main/experiments/run_inference.py` |
| `source_sha256` | `872868f48e3cf66f0ce159ada589ca2126a3b2ba98470ab3bbcb9ffc4481f7c6` |
| `env_python` | `/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python` |
| `checkpoint` | `/mnt/sdb/kxc/stamp_models/weights/diffpepbuilder/diffpepbuilder_v1.pth` |
| `checkpoint_sha256` | `dbc4283257d27e38a1ce90c9344063b046ab7161745ebed1fd98a4b0439b992a` |
| `model_configs` | `base_config`: `/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main/config/base.yaml` (`f952e17a4fa134cbbd736453b423ee99e14583d9fcbd202db16c10c0af9b2e26`); `inference_config`: `/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main/config/inference.yaml` (`d1e1860ed368f10742f60b7f2ec6088684d3cc501883db844ae5efccbb5225c3`) |
| `acceptance_fixture` | `/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb` |
| `fixture_sha256` | `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc` |
| `command_preview` | `<env_python> <runner_script> --target_pdb <run_dir>/input/target.pdb --output_dir <run_dir>/output --num_candidates 3 --gate-file <gate_path>` |
| `device` | cuda |
| `timeout_seconds` | 3600 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + `run_manifest.json` written + output files non-empty |
| `failure_criterion` | Non-zero exit, timeout, missing output, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, kills subprocess tree by recorded PID |

### 4.4 Attempt 04 — PepFlow

| Field | Value |
|---|---|
| `model_id` | `pepflow` |
| `display_name` | PepFlow |
| `adapter` | `backend/app/services/model_adapters/pepflow_adapter.py` |
| `adapter_sha256` | `e8818632542d94d8c9fd921dd0c94242a2fbcd8ee7e533feac7068d3ba27b188` |
| `runner` | Direct source invocation via P33L wrapper |
| `source` | `/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main/models_con/inference.py` |
| `source_sha256` | `c59b5096da6582adecca967d0506efbd69ece188ef9d0903c927a67490125605` |
| `env_python` | `/mnt/sdb/kxc/stamp_models/envs/pepflow_py310_pypi_candidate/bin/python` |
| `checkpoint` | `/mnt/sdb/kxc/stamp_models/checkpoints/pepflow/p25_install_probe/PepFlow2024_share/model1.pt` |
| `checkpoint_sha256` | `ee3f0458cc47b63f2c5c8bc27f0e9897fab395592a2beb5e627a42f74754fb0a` |
| `model_configs` | `learn_angle_config`: `/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main/configs/learn_angle.yaml` (`35fb093d8e4537de0029244cbd92a079b9b0eb61347714fa38202c2579764dd7`) |
| `acceptance_fixture` | `/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb` |
| `fixture_sha256` | `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc` |
| `command_preview` | `<env_python> <source> --config <source_dir>/configs/learn_angle.yaml --ckpt <checkpoint> --receptor <run_dir>/input/receptor.pdb --output <run_dir>/output --num_samples 3 --num_steps 5 --device cuda` |
| `device` | cuda |
| `timeout_seconds` | 3600 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + output CSV/PDB exists + manifest written |
| `failure_criterion` | Non-zero exit, timeout, missing output, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, kills subprocess tree by recorded PID |

### 4.5 Attempt 05 — PepHAR

| Field | Value |
|---|---|
| `model_id` | `pephar` |
| `display_name` | PepHAR |
| `adapter` | `backend/app/services/model_adapters/pephar_adapter.py` |
| `adapter_sha256` | `7485880f2dc3f3e41cc984a96065d0c28479e8a424525ff8a3a0df950a410944` |
| `runner` | `/mnt/sdb/kxc/stamp_models/scripts/stamp_pephar_p33l_real_runner.py` |
| `runner_sha256` | `7b979aa2b1cd146e82523c5ea3356268aeb073a022c3dcbaa9ffebdd65d3265f` |
| `source` | `/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main/evaluate/sample.py` |
| `source_sha256` | `f84f6a20f95dd644fd8d5952c7a7c61e58612310d80fd2756a2e4e24f2991a85` |
| `env_python` | `/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python` |
| `checkpoint` | Prediction: `/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33/checkpoints/2400.pt` |
| `checkpoint_sha256` | `94eb9933312a4c851e3a6dae44f2435dcfc417648d271ca75e8c22bebc1523f6` |
| `model_configs` | `density_checkpoint`: `/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36/checkpoints/1400.pt` (`06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15`); `density_config`: `/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36/density_v4_x5o2.yml` (`6ccc4e972f069e86834c1675b5a47a03545c5a533600d77699e624b8f0828b24`); `prediction_checkpoint`: `/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33/checkpoints/2400.pt` (`94eb9933312a4c851e3a6dae44f2435dcfc417648d271ca75e8c22bebc1523f6`); `prediction_config`: `/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33/prediction_d2_x2o1.yml` (`e69485f9604772d2d2e99ce2a8f9155dd06e21ef125e171c0a8c964fa0d1f6c4`) |
| `acceptance_fixture` | `/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33f_ppflow_smoke_20260628_195952/ppflow_p33_temp_config_p33/0000_2qbx_2026_06_28__20_00_08/reference.pdb` |
| `fixture_sha256` | `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc` |
| `command_preview` | `<env_python> <runner_script> --model-variant prediction --checkpoint <checkpoint> --config <config> --gate-file <gate_path> --output-dir <run_dir>/output --rec-length 30 --pep-length 10 --qry-length 5 --seed 2024` |
| `device` | cuda |
| `timeout_seconds` | 3600 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + `output/manifest.json` exists + manifest written |
| `failure_criterion` | Non-zero exit, timeout, missing output, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, kills subprocess tree by recorded PID |

### 4.6 Attempt 06 — PPFlow

| Field | Value |
|---|---|
| `model_id` | `ppflow` |
| `display_name` | PPFlow |
| `adapter` | `backend/app/services/model_adapters/ppflow_adapter.py` |
| `adapter_sha256` | `e1d413d3b0d3f94ecf930f330655d94874692be84cc8f6ffc69237814d15554d` |
| `runner` | Direct source invocation via P33L wrapper |
| `source` | `/mnt/sdb/kxc/stamp_models/source/ppflow/extracted_p25_install_probe/ppflow-main/codesign_ppf.py` |
| `source_sha256` | `1bf50964b4f4e34b594b894a274d6c119361e1eba00f2c58e70c41200fc92d08` |
| `env_python` | `/mnt/sdb/kxc/stamp_models/envs/ppflow_real_runner_py39/bin/python` |
| `checkpoint` | `/mnt/sdb/kxc/stamp_models/checkpoints/ppflow/p25_install_probe/ppflow/pretrained.pt` |
| `checkpoint_sha256` | `be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d` |
| `acceptance_fixture` | `/mnt/sdb/kxc/stamp_models/datasets/ppflow/p29g_c_smoke/p29g_c_fixture/receptor_repaired.pdb` |
| `fixture_sha256` | `1091c39a332ff29e917f8124afc472b2d717b9a73ff2e40088fc408a264b999b` |
| `command_preview` | `<env_python> <source> --index 0 -c <source_dir>/configs/test/codesign_ppflow.yml -o <run_dir>/output -t p33l -d cuda -b 1 -ckpt <checkpoint>` |
| `device` | cuda |
| `timeout_seconds` | 3600 |
| `disk_quota_bytes` | 10737418240 (10 GiB) |
| `max_output_files` | 1000 |
| `success_criterion` | Exit code 0 + generated sequences/metrics exist + manifest written |
| `failure_criterion` | Non-zero exit, timeout, missing output, quota exceeded |
| `cleanup` | Orchestrator releases GPU lock, closes P33L gate, kills subprocess tree by recorded PID |

---

## 5. Pre-Execution Checklist (Run Before Attempt 01)

- [x] Phase 2 patch applied and after-SHA verified against this manifest.
- [ ] Dev backend 12824 restarted with `P33L_AUTHORIZED_MANIFEST_SHA=<sha256-from-STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt>`.
- [ ] User has explicitly authorized the manifest SHA recorded in `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`.
- [x] Formal 8001/8080 are read-only and untouched.
- [x] Root filesystem (`/`) has at least 20 GiB free.
- [x] `/mnt/sdb/kxc/stamp_models/artifacts/p33l/` exists and is writable.
- [ ] No existing P33L gates, locks, or jobs.
- [ ] No P33L model processes running.
- [x] GPU lock service functional.

---

## 6. Failure-Stop and Cleanup Commands

### 6.1 Stop entire P33L on any failure

**Primary method (precise, PID-based):**

```bash
# 1. Cancel current job via API
MANIFEST_SHA=$(cat /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/reports/p33l_six_model_real_run/STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt | awk '{print $1}')
curl -X POST "http://localhost:12824/api/v1/p33l/jobs/<job_id>/cancel" \
  -H "P33L-Authorized-Manifest-SHA: $MANIFEST_SHA"

# 2. Verify cleanup
ls /home/xh/kxc/stampup/run_gates/p33l/*/* 2>/dev/null || echo "No P33L gates"
ls -l /tmp/stamp_gpu.lock 2>/dev/null || echo "No GPU lock"
ps -eo pid,pgid,cmd | grep -E "p33l_|P33L" | grep -v grep || echo "No P33L processes"
```

**Manual fallback (still precise, never broad pkill/rm):**

```bash
# Identify the exact job PID from the job status response or run_manifest.json
JOB_PID=<pid_from_job_status>
kill -TERM -- -$JOB_PID   # signal the process group
sleep 5
kill -KILL -- -$JOB_PID 2>/dev/null || true   # force if still alive

# Close the exact gate file
GATE_FILE=/home/xh/kxc/stampup/run_gates/p33l/<model_id>/<job_id>/gate.json
python3 - <<PY
import json, os, time
p = "$GATE_FILE"
if os.path.exists(p):
    with open(p, "r+") as f:
        d = json.load(f)
        d["status"] = "closed"
        d["closed_at"] = time.time()
        f.seek(0); json.dump(d, f); f.truncate()
PY

# Release GPU lock only if held by this job
python3 - <<PY
from app.services.gpu_lock_service import release_gpu_lock
release_gpu_lock("<job_id>")
PY
```

**Forbidden commands (do not use):**

```bash
# DO NOT use these broad commands:
# rm -rf /home/xh/kxc/stampup/run_gates/p33l
# pkill -f 'p33l'
# killall -r '.*p33l.*'
```

### 6.2 Rollback to P33K closed-gate state

See `STAMP_P33L_ROLLBACK_PLAN.md`. Rollback uses the backup directory `/home/xh/kxc/stampup/backups/p33l_phase2_20260629_040030` to restore `app/main.py` and remove `app/services/p33l/` and `app/routers/p33l.py`.

---

## 7. No-Retry Declaration

P33L allows exactly one execution attempt per model. There is no automatic retry, no manual retry, no fallback to another checkpoint/env/device, and no rename/re-job workaround. Any failure terminates the entire task.

---

## 8. Manifest SHA

The SHA256 of this manifest file is recorded in:

- `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`
- Dev backend env var `P33L_AUTHORIZED_MANIFEST_SHA`
- User authorization statement

The authoritative value is the first whitespace-delimited token in `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`.

---

## 9. Gate Vocabulary

| Gate | Meaning |
|---|---|
| `P33L_TASK_READY_EXECUTION_AUTHORIZATION_PENDING` | Task generated, awaiting authorization |
| `P33L_EXECUTION_AUTHORIZATION_PENDING` | User has not yet authorized the manifest SHA |
| `P33L_PREEXECUTION_MANIFEST_FROZEN` | This manifest is frozen and ready for authorization |
| `REASONIX_P33L_SIX_MODEL_REAL_RUN_PREEXEC_GO` | Reasonix pre-execution verdict (conditional on Phase 2 patch) |

Current gate after Phase 3: `P33L_PREEXECUTION_MANIFEST_FROZEN`
