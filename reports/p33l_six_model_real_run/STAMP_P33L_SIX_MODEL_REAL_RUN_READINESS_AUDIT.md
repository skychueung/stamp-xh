# STAMP P33L — Six-Model Real-Run Readiness Audit

**Task ID:** P33L  
**Phase:** Phase 1 — Readiness audit (zero model load)  
**Date:** 2026-06-29  
**Server:** xh-System-Product-Name (192.168.31.218)  
**Project Root:** `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`

---

## 1. Audit Method

This audit is strictly read-only:

- Static file analysis of registry, adapters, runners, schemas, and tests.
- Path-existence checks on source, checkpoint, env, fixture, and artifact directories.
- API status snapshot from `/api/v1/model-registry/status` (dev 12824).
- No model import, no checkpoint load, no subprocess execution of model code, no gate creation.

---

## 2. Executive Summary

| Model | Registry `supports_real_run` | Registry `real_run_enabled` | Adapter `submit()` | Real Runner Executable | Phase 1 Verdict |
|---|---|---|---|---|---|
| PepMLM | True | False | Implemented but gated closed | Yes (via adapter + worker) | BLOCKED (gate closed) |
| EvoBind2 | False | False | BLOCKED | Yes (runner present, per-run gate required) | BLOCKED |
| DiffPepBuilder | False | False | BLOCKED | Smoke runner only (no real-design runner) | BLOCKED |
| PepFlow | False | False | Not implemented (base BLOCKED) | Skeleton only | BLOCKED |
| PepHAR | False | False | Not implemented (base BLOCKED) | Smoke runner only | BLOCKED |
| PPFlow | False | False | BLOCKED | Skeleton only | BLOCKED |

All six P33L target models are currently **BLOCKED** for one-click real execution. The blockers are governance gates (`real_run_enabled=False`, `supports_real_run=False`) and incomplete real-run execution paths (adapters and runners that fail closed or are skeletons). No model has a fully wired, backend-authorized, one-click real-run submission path.

This is the expected pre-authorization state. Phase 2 must design the minimal, safe changes required to open a controlled P33L execution gate, and Phase 3 must freeze the exact manifest before any model is executed.

---

## 3. Per-Model Readiness Detail

### 3.1 PepMLM

- **Registry:** `smoke_rerun_verified`, `supports_real_run=True`, `real_run_enabled=False`.
- **Adapter:** Two adapters exist:
  - `PepMLMAdapter` implements real `submit()` calling `pepmlm_infer.py` via subprocess.
  - `PepMLMRegistryAdapter` (used by the model-registry router) hard-codes `submit()` and `dry_run()` to `BLOCKED`.
- **Runner:** Real inference script exists: `models_dev/pepmlm/scripts/pepmlm_infer.py`. Worker (`pepmlm_worker.py`) handles GPU lock and gate cleanup.
- **Paths:** Weights, tokenizer, env, and prior P30B artifact all exist.
- **Gaps:**
  - Registry adapter blocks public `submit()`.
  - `.real_run_enabled` gate file absent.
  - No automatic cleanup of failed run directories.
- **Verdict:** BLOCKED (gate/routing, not capability).

### 3.2 EvoBind2

- **Registry:** `controlled_smoke_verified`, `supports_real_run=False`, `real_run_enabled=False`.
- **Adapter:** `submit()` is fail-closed and explicitly states the gate-open path is intentionally unimplemented in P4A.
- **Runner:** `evobind2_runner.py` is a real executable runner but requires a manually created per-run gate file. No manifest writer. No GPU lock.
- **Paths:** Legacy source, AF2 params, data dir, HHblits, and env all present.
- **Gaps:**
  - Real-run submission unimplemented in adapter.
  - Per-run gate creation not wired to one-click flow.
  - No manifest writer.
  - No GPU lock / multi-GPU scheduling.
  - `design` mode blocked; only `predict_only` available.
- **Verdict:** BLOCKED.

### 3.3 DiffPepBuilder

- **Registry:** `controlled_smoke_verified`, `supports_real_run=False`, `real_run_enabled=False`.
- **Adapter:** `submit()` unconditionally blocks with reason `submit_unconditionally_blocked_in_p17`.
- **Runner:** `stamp_diffpepbuilder_p31b_smoke_runner_hardened_v2.py` is executable, but it is a minimal CPU smoke runner (dummy forward pass), not a target-conditioned design runner.
- **Paths:** Source, checkpoint (`diffpepbuilder_v1.pth`), env, and P32B evidence exist.
- **Gaps:**
  - No real-design runner.
  - Adapter dry-run references missing config path (`config/base.yaml`).
  - `RUNNER_SCRIPT` points to v1 instead of hardened v2.
  - Missing forward-probe report referenced by adapter.
  - No GPU lock.
- **Verdict:** BLOCKED.

### 3.4 PepFlow

- **Registry:** `controlled_smoke_verified`, `supports_real_run=False`, `real_run_enabled=False`.
- **Adapter:** Does not override `submit()`; inherits base `BLOCKED`.
- **Runner:** `pepflow_real_runner.py` is a skeleton; `run()` raises `PepFlowRunnerBlocked`.
- **Paths:** Source, checkpoints (`model1.pt`, `model2.pt`), envs, and P32B evidence exist.
- **Gaps:**
  - No real-run submission implementation.
  - Runner skeleton has no subprocess, timeout, cleanup, GPU lock, or manifest file writer.
  - Only smoke runners are executable; no receptor-driven design runner is wired in.
  - Registry `output_artifact_types` is empty.
- **Verdict:** BLOCKED.

### 3.5 PepHAR

- **Registry:** `controlled_smoke_verified`, `supports_real_run=False`, `real_run_enabled=False`.
- **Adapter:** Inherits base `BLOCKED` `submit()`.
- **Runner:** `stamp_pephar_p31c_smoke_runner.py` is executable but uses synthetic dummy input; `pephar_real_runner.py` skeleton is not wired.
- **Paths:** Source, density/prediction checkpoints, configs, env, and P32B evidence exist.
- **Gaps:**
  - No real-run submission.
  - Missing gate file.
  - Smoke runner cannot accept real target input or produce deliverable artifacts.
  - Input type inconsistency (registry `target_sequence` vs adapter dry-run `complex_pdb_path`).
  - `output_artifact_types` empty.
- **Verdict:** BLOCKED.

### 3.6 PPFlow

- **Registry:** `controlled_smoke_verified` (P33G), `supports_real_run=False`, `real_run_enabled=False`.
- **Adapter:** `submit()` unconditionally blocks with `ppflow_real_run_not_implemented`.
- **Runner:** `ppflow_real_runner.py` is a skeleton; `run_ppflow_subprocess()` never calls `subprocess.run`.
- **Paths:** Source, checkpoint (`pretrained.pt` 224 MB), safe-load summary, envs, and P33G artifact exist.
- **Gaps:**
  - No executable real-run path.
  - Adapter dry-run references missing config (`configs/train/ppflow_pepglad.yml`).
  - No persistent manifest writer, timeout, cleanup, or GPU lock in real path.
  - No dedicated fixture PDB.
- **Verdict:** BLOCKED.

---

## 4. Common Patterns

1. **Governance gates are closed for all six models.** This is correct and must remain so until Phase 5.
2. **Adapters fail closed.** Every adapter either returns `BLOCKED` from `submit()` or inherits the base blocked method.
3. **Runners are mostly skeletons or smoke runners.** Only PepMLM and EvoBind2 have real executable runners; the rest have smoke runners or skeletons.
4. **No unified one-click job orchestration.** There is no shared P33L job service, gate protocol, or Real Run API endpoint that coordinates the six models.
5. **GPU lock exists only for PepMLM.** Other models have no GPU reservation mechanism.
6. **Manifest writers are partial or absent.** PepMLM has the most complete manifest flow; others lack disk persistence.
7. **Artifact roots exist and are writable.** `/mnt/sdb/kxc/stamp_models/artifacts/<model>/` is present for all six models.

---

## 5. Phase 2 Implications

Phase 2 must design a minimal, safe, uniform real-run layer without modifying model source, checkpoint, or scientific parameters. The design must address:

- A P33L-specific execution policy that temporarily enables real runs only inside a controlled gate.
- A unified job service that creates one job per model, acquires GPU lock, invokes the appropriate adapter/runner, writes manifests, and cleans up.
- Adapter `submit()` implementations (or a wrapper) that route to real runners while preserving the fail-closed default.
- Runner wiring for DiffPepBuilder, PepFlow, PepHAR, and PPFlow (either upgrading existing runners or creating minimal executable wrappers).
- Input validation, quota enforcement, timeout, and download whitelist.
- UI Real Run panel that is backend-gated.
- Rollback plan that restores the P33K closed-gate state if anything fails.

---

## 6. Phase 1 Gate

| Gate | Value |
|---|---|
| Phase 1 result | **COMPLETE** |
| Per-model verdict | All `BLOCKED` (expected pre-authorization state) |
| Phase 1 gate | `P33L_READINESS_AUDIT_BLOCKED_AS_EXPECTED` |

No model is ready for unsupervised real execution. Phase 2 design is required before Phase 3 authorization.
