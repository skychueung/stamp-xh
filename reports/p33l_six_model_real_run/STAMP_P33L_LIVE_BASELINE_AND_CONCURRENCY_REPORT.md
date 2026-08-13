# STAMP P33L — Live Baseline and Concurrency Report

**Task ID:** P33L  
**Title:** STAMP_P33L_SIX_MODEL_ONE_CLICK_REAL_RUN_AND_DELIVERY_GOAL  
**Phase:** Phase 0 — Read-only baseline, conflict and live-truth check  
**Date:** 2026-06-29  
**Server:** xh-System-Product-Name (192.168.31.218)  
**User:** xh  
**Project Root:** `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`  
**Artifact Root:** `/mnt/sdb/kxc/stamp_models`  

---

## 1. Environment Baseline

| Item | Value | Notes |
|---|---|---|
| hostname | `xh-System-Product-Name` | |
| user | `xh` | |
| system time | `Mon Jun 29 03:19:05 AM +08 2026` | captured at baseline start |
| uptime | `03:19:07 up 37 days, 17:06, 24 users, load average: 3.30, 3.08, 3.20` | |
| OS root (`/`) | `/dev/nvme0n1p2`, 1.8T, 1.7T used, 44G avail, 98% | critical; ensure cleanup before large artifact writes |
| Data mount (`/mnt/sda`) | `/dev/sda2`, 15T, 12T used, 3.3T avail, 78% | |
| Model mount (`/mnt/sdb`) | `/dev/sdb2`, 15T, 6.6T used, 8.1T avail, 45% | intended artifact root |
| Memory | 125 GiB total, 101 GiB used, 944 MiB free, 24 GiB available | |
| Swap | 0B | |

---

## 2. Port Health

| Port | Service | Listen PID | HTTP Probe | Notes |
|---|---|---|---|---|
| 8001 | Formal backend | `python3` pid 3074240 | `200 http://localhost:8001/api/health` | Formal backend healthy; read-only for P33L |
| 8080 | Formal frontend (Docker `stamp-frontend`) | — | `200 http://localhost:8080/` | Formal frontend healthy; read-only for P33L |
| 12823 | Dev frontend (node pid 3163433) | `node` | `200 http://localhost:12823/` | Dev frontend healthy |
| 12824 | Dev backend (python pid 3769755) | `python` | `200 http://localhost:12824/api/health` | Dev backend healthy |

All four required ports are listening and returning HTTP 200.

---

## 3. Model Registry / API State

Endpoint verified at baseline:

- `GET http://localhost:12824/api/v1/model-registry/status` → `200`
- `GET http://localhost:12824/api/v1/model-registry/models` → `200`

Observed classification (exactly 9 models):

| Model | Product Group | UI Selectable | UI Execution State | Supports Real Run | Real Run Enabled | Execution Locked | Delivery Status |
|---|---|---|---|---|---|---|---|
| PepMLM | `available_six` | true | `probe_dry_run_available` | true | false | true | `delivered_for_probe_dry_run_ui` |
| EvoBind2 | `available_six` | true | `probe_dry_run_available` | false | false | true | `delivered_for_probe_dry_run_ui` |
| DiffPepBuilder | `available_six` | true | `probe_dry_run_available` | false | false | true | `delivered_for_probe_dry_run_ui` |
| PepFlow | `available_six` | true | `probe_dry_run_available` | false | false | true | `delivered_for_probe_dry_run_ui` |
| PepHAR | `available_six` | true | `probe_dry_run_available` | false | false | true | `delivered_for_probe_dry_run_ui` |
| PPFlow | `available_six` | true | `probe_dry_run_available` | false | false | true | `delivered_for_probe_dry_run_ui` |
| PepGLAD | `reserved_placeholder` | false | `locked_placeholder` | false | false | true | `out_of_scope_evidence_preserved` |
| RFpeptides | `reserved_placeholder` | false | `locked_placeholder` | false | false | true | `out_of_scope_evidence_preserved` |
| PepPrCLIP | `excluded` | false | `excluded` | true | false | true | `blocked_pending_miniclip_license_token` |

Key findings:

- All six P33L target models remain in `available_six` as delivered by P33K.
- All nine models have `real_run_enabled=false`; `execution_locked` is derived as `true` for every entry.
- PepGLAD and RFpeptides remain reserved placeholders.
- PepPrCLIP remains excluded.
- The endpoint `/api/model-registry/status` (quoted in P33K test report) currently returns `404`; the actual mount is `/api/v1/model-registry/status`. This is documented as a path-prefix baseline finding and does not block Phase 0.

---

## 4. Gate / Lock / Process / GPU Concurrency

### 4.1 P33L Gate Files

Searched `/tmp`, `/run`, `/home/xh/kxc/stampup` (depth 3) for `*p33l*gate*`, `*p33l*lock*`, `*p33l*job*`:

- **Result:** 0 files found.

### 4.2 Target Model Processes

Searched processes for `p33l`, `P33L`, `pepmlm`, `evobind2`, `diffpepbuilder`, `pepflow`, `pephar`, `ppflow`:

- **Result:** No live P33L or target-model real-run processes.
- A pre-existing PepMLM sidecar process (`pepmlm_sidecar_controlled_load.py`, started Jun 09) was observed. It is **not** a P33L job and is not terminated.

### 4.3 GPU Workload

```text
NVIDIA-SMI 580.126.09             Driver Version: 580.126.09     CUDA Version: 13.0
GPU 0: NVIDIA GeForce RTX 4090, 19600MiB / 24564MiB used, 0% util
GPU 1: NVIDIA GeForce RTX 4090, 13995MiB / 24564MiB used, 0% util

Compute processes:
GPU 0  PID 1380373  VLLM::EngineCore  10390MiB
GPU 0  PID 2455406  python             9196MiB
GPU 1  PID 2656106  python            13986MiB
```

- No STAMP peptide model compute processes detected.
- Existing processes are unrelated services (VLLM and persistent python workloads).
- P33L must respect GPU memory occupancy and only use remaining capacity or wait.

### 4.4 GPU Lock Service

- File present: `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend/app/services/gpu_lock_service.py`
- SHA256: `f2c21d8a35e58ea445ccb3b01d0b452998fdc2ca7420c3dd26b356608fc6053e`
- Functionality to be verified in Phase 1 readiness audit.

---

## 5. Code Baseline SHA256 (Pre-Execution)

| File | SHA256 |
|---|---|
| `backend/app/services/target_peptide_model_registry.py` | `d60531a50296ead75e3e8c2b1d0a3733b17532adc1267d8598110c7d509b37c0` |
| `backend/app/schemas/model_registry.py` | `ba0df95ce53b01aef76291b6be9dc9b7d8aa8249023b25658accd83909182026` |
| `backend/app/routers/model_registry.py` | `6427260d98fb9ad45c2bfd6c05eb73a57d1455940150e927060ef22e08998429` |
| `backend/app/services/target_peptide_model_probe.py` | `5ee2fad6dbb25838da849e83ecb9b2e9e588d81a764d9ab319e1984c919f5989` |
| `backend/app/services/gpu_lock_service.py` | `f2c21d8a35e58ea445ccb3b01d0b452998fdc2ca7420c3dd26b356608fc6053e` |
| `backend/app/services/compute_wrappers/evobind2_runner.py` | `95698c8e50016bc93346544c59dbeb541363b268835f0d070261263aa3859e19` |
| `backend/app/services/model_adapters/diffpepbuilder_adapter.py` | `becd35d2310063c35a89905310bf932dd6e533b81b65495401e0b5c5daf6891a` |
| `backend/app/services/model_adapters/evobind2_adapter.py` | `3931fb6c3f8abc43a1cc23a3f10ddcc651f941354dab18e10a1e0c243828e1a9` |
| `backend/app/services/model_adapters/pepflow_adapter.py` | `e8818632542d94d8c9fd921dd0c94242a2fbcd8ee7e533feac7068d3ba27b188` |
| `backend/app/services/model_adapters/pephar_adapter.py` | `7485880f2dc3f3e41cc984a96065d0c28479e8a424525ff8a3a0df950a410944` |
| `backend/app/services/model_adapters/pepmlm_adapter.py` | `5c5f9f703d1a81e290855bbaa8b320699eb6eaf79e605f7e1054514d2e7c5553` |
| `backend/app/services/model_adapters/pepmlm_registry_adapter.py` | `90048e05d21532bcfdbcffbeccb889998f0d50278bfd68cfabb9130af1b9fae9` |
| `backend/app/services/model_adapters/ppflow_adapter.py` | `e1d413d3b0d3f94ecf930f330655d94874692be84cc8f6ffc69237814d15554d` |
| `backend/app/services/pepflow_real_runner.py` | `63750de2a965dcf418aa1b79dbf4942dfe9ca19b9892dcde1e576fff2745565d` |
| `backend/app/services/pephar_real_runner.py` | `c0db8b07f0e8a458666352c7f771cff6cc9b12ba73fdf78320c337cc27efabea` |
| `backend/app/services/pepmlm_adapter.py` | `4ab3e924e33d320478d8444c670d75fada95974c895c9b25c6d6c6156231c66d` |
| `backend/app/services/ppflow_real_runner.py` | `c7494c6862ef29132181eb751654b7a84aa9d972016803424fad30fc74453416` |
| `backend/app/services/ppflow_runner_service.py` | `a49a3a493835e582befa13312e038d1be30ac9ee6767e5d72f687d260f0875c8` |

The registry, schema and router SHAs match the P33K delivery manifest, confirming the P33K patch is still in place.

---

## 6. Multi-Agent Conflict Check

- No other active P33L gate, lock or job files observed.
- No P33L model compute processes observed.
- Dev backend (12824) and dev frontend (12823) are running; no concurrent writes to Registry, adapter, runner, UI, env, gate or artifact directories detected by this read-only scan.
- **Action:** Continue, but monitor for conflicts during Phase 2 patch application.

---

## 7. Baseline Conclusion

| Gate | Value |
|---|---|
| Current task gate | `P33L_TASK_READY_EXECUTION_AUTHORIZATION_PENDING` |
| Phase 0 result | **PASS** |
| Phase 0 gate | `P33L_BASELINE_OK_CONCURRENCY_CLEAR` |

All required ports are healthy, no P33L gates/locks/jobs exist, no target-model processes are running, GPU workload is non-P33L, and the six target models remain in the `available_six` group with real execution locked. The baseline does not reveal any hard blocker.

Cautions:

1. Root filesystem (`/`) is 98% full. P33L must write all large artifacts to `/mnt/sdb/kxc/stamp_models`.
2. GPU 0 and GPU 1 already hold unrelated resident memory; P33L must implement a wait/acquire strategy rather than preemption.
3. The endpoint prefix for model-registry is `/api/v1/model-registry`, not `/api/model-registry`. Any Real Run route design in Phase 2 must align with the actual mount.

---

## 8. Next Phase

Proceed to **Phase 1 — Six-Model Real-Run Readiness Audit (zero model load)**.
