# STAMP P33L — One-Click Real Run Architecture

**Task ID:** P33L  
**Phase:** Phase 2  
**Date:** 2026-06-29  
**Scope:** Design-only. No model execution, no checkpoint load, no gate creation.

---

## 1. Design Goal

Enable a single backend-authorized `Run & Deliver` action on the dev Target Design page that, for exactly one model at a time:

1. Validates P33L authorization, input, quota, and concurrency.
2. Creates a unique, time-bound execution gate and job directory.
3. Acquires a GPU lock.
4. Dispatches the model-specific real runner via a thin adapter wrapper.
5. Monitors the run to success/failure/timeout.
6. Writes a uniform `run_manifest.json` and `sha256_manifest.txt`.
7. Cleans up the gate, lock, and subprocesses regardless of outcome.
8. Returns job status and a whitelist-restricted download URL.

The design must not modify model source code, checkpoints, or scientific parameters.

---

## 2. High-Level Flow

```text
User clicks "Run & Deliver" on /target-design
        │
        ▼
Frontend POST /api/v1/p33l/real-run
        │
        ▼
P33LExecutionPolicy.check()  ──► 401 if not authorized
        │
        ▼
P33LJobOrchestrator.create_job(model_id, input, user)
        │
        ├── check_model_in_scope(model_id)  (six models only)
        ├── check_no_prior_attempt(model_id) in this P33L
        ├── check_previous_models_all_succeeded()  (fixed order, fail-stop)
        ├── validate_input_schema(model_id, input)
        ├── check_disk_quota()
        ├── check_gpu_available()
        └── generate job_id, gate_id
        │
        ▼
P33LGate.create(gate_id, model_id, job_id, ttl=RUN_TTL)
        │
        ▼
GPULock.acquire(device_id)
        │
        ▼
ModelRealRunWrapper.submit(model_id, job_id, input, run_dir)
        │
        ├── PepMLM: route to PepMLMAdapter real path
        ├── EvoBind2: create per-run gate + call evobind2_runner
        ├── DiffPepBuilder: invoke hardened smoke runner upgraded for real input
        ├── PepFlow: invoke inference.py with receptor PDB
        ├── PepHAR: invoke density/prediction inference with real input
        └── PPFlow: invoke codesign_ppf.py with target PDB
        │
        ▼
Monitor subprocess (timeout, logs, exit code)
        │
        ▼
ManifestWriter.write(run_dir, result, provenance)
        │
        ▼
Cleanup: release GPULock, close gate, kill orphan subprocesses
        │
        ▼
Return job status + download link
```

---

## 3. Backend Components

### 3.1 `P33LExecutionPolicy` (new)

Single source of truth for whether real runs are authorized in this session.

```python
class P33LExecutionPolicy:
    MANIFEST_SHA: str  # set at import from frozen manifest
    AUTHORIZED_MODELS: frozenset[str] = {"pepmlm","evobind2","diffpepbuilder","pepflow","pephar","ppflow"}
    ORDERED_MODELS: list[str] = ["pepmlm","evobind2","diffpepbuilder","pepflow","pephar","ppflow"]

    @classmethod
    def is_authorized(cls, manifest_sha: str) -> bool:
        return manifest_sha == cls.MANIFEST_SHA
```

- Authorized only when the request includes the manifest SHA that matches the frozen Phase 3 manifest.
- Loads the SHA from an env var `P33L_AUTHORIZED_MANIFEST_SHA` set at dev backend startup.
- If the env var is absent, real-run endpoints return 403.

### 3.2 `P33LJobOrchestrator` (new)

- Maintains in-memory state of the P33L run sequence (not persisted to DB; reset on backend restart).
- Enforces fixed order and one-attempt-per-model.
- Creates the run directory under `/mnt/sdb/kxc/stamp_models/artifacts/p33l/<job_id>/`.
- Delegates model execution to `ModelRealRunWrapper`.
- Guarantees cleanup via `finally`.

### 3.3 `P33LGate` (new)

File-based gate with strict ownership and TTL checks.

- Gate path: `/home/xh/kxc/stampup/run_gates/p33l/<model_id>/<gate_id>/gate.json`
- Contains: `model_id`, `job_id`, `created_at`, `expires_at`, `authorized_by_manifest_sha`.
- Created with mode `0o700`, owner `xh`.
- TTL enforced by both creator and cleanup; expired gates are rejected.
- Symlink/hard-link traversal rejected.

### 3.4 `GPULock` (extend existing)

- Reuse `backend/app/services/gpu_lock_service.py`.
- For non-PepMLM models, acquire the same file-based lock before subprocess start.
- Default to GPU 1 if GPU 0 is fully occupied by VLLM/other services; block/wait if both are busy.
- Release in `finally`.

### 3.5 `ModelRealRunWrapper` (new)

Thin per-model wrapper that translates the orchestrator's uniform call into model-specific execution.

| Model | Wrapper Action | Executable | Key Args |
|---|---|---|---|
| PepMLM | Route to `PepMLMAdapter.submit()` | `pepmlm_infer.py` | `--model_path`, `--target_sequence`, `--peptide_length`, `--num_candidates`, `--device`, `--output_dir` |
| EvoBind2 | Create per-run gate, call `evobind2_runner.execute_evobind2_run_safe()` | `mc_design.py` | `--receptor_fasta_path`, `--peptide_length`, `--output_dir`, `--model_names`, `--data_dir`, `--predict_only=True` |
| DiffPepBuilder | Upgrade hardened smoke runner to accept `--target_pdb` and `--num_candidates` | `stamp_diffpepbuilder_p31b_smoke_runner_hardened_v2.py` (modified) | `--target_pdb`, `--output_dir`, `--num_candidates`, `--gate-file` |
| PepFlow | Call `inference.py` with receptor PDB | `models_con/inference.py` | `--config`, `--ckpt`, `--receptor`, `--output`, `--num_samples`, `--num_steps`, `--device` |
| PepHAR | Call density/prediction inference scripts | `inference.py` (PepHAR) | `--config`, `--checkpoint`, `--input_pdb`, `--output_dir`, `--model_variant` |
| PPFlow | Call `codesign_ppf.py` | `codesign_ppf.py` | `--index`, `-c`, `-o`, `-t`, `-d`, `-b`, `-ckpt` |

### 3.6 `P33LManifestWriter` (new)

Writes two files in every run directory:

- `run_manifest.json`: job metadata, input provenance, command, exit code, timestamps, resource summary, model provenance, `NOT_EXPERIMENTALLY_VALIDATED` disclaimer.
- `sha256_manifest.txt`: SHA256 of every file in the run directory plus the input file.

### 3.7 API Routes (new router)

- `POST /api/v1/p33l/real-run` — create and start a job.
- `GET /api/v1/p33l/jobs/{job_id}` — poll status.
- `POST /api/v1/p33l/jobs/{job_id}/cancel` — cancel (cleanup gate/lock/process).
- `GET /api/v1/p33l/jobs/{job_id}/download/{file_path}` — whitelist-restricted download.

All routes require the `P33L-Authorized-Manifest-SHA` header.

---

## 4. Frontend Changes

- Add `Run & Deliver` button to `TargetedPeptideDesignCenterPage.tsx`.
- Button enabled only when backend status includes `p33l_execution_authorized=true` for the selected model.
- Click opens confirmation modal displaying the manifest SHA and the model name.
- Submit `POST /api/v1/p33l/real-run` with header `P33L-Authorized-Manifest-SHA`.
- Poll `GET /api/v1/p33l/jobs/{job_id}` every 10 s, display `queued → running → succeeded/failed`.
- On success, show result summary, `NOT_EXPERIMENTALLY_VALIDATED` banner, and download links.
- On failure, show error and evidence reference; no fake success state.
- Disable duplicate submissions while a job is active.

---

## 5. Data Flow

### 5.1 Input

- Source: user-provided via UI form or acceptance fixture.
- Validation: schema checked by `P33LJobOrchestrator.validate_input_schema()`.
- Storage: input written to `<run_dir>/input/` with SHA recorded.
- Reuse: if user provides no scientific input, use the model's existing minimal smoke fixture marked as `acceptance_fixture`.

### 5.2 Output

- All output under `/mnt/sdb/kxc/stamp_models/artifacts/p33l/<job_id>/`.
- Required files:
  - `run_manifest.json`
  - `sha256_manifest.txt`
  - `output/` (model-specific)
  - `logs/` (stdout/stderr, sanitized)
  - `input/` (input copy)
- Download API enforces whitelist to this directory only.

---

## 6. Security & Boundaries

- Real-run endpoints require manifest SHA header.
- Only six models allowed; order enforced.
- One model at a time; one attempt per model.
- GPU lock prevents concurrency conflicts.
- Gate TTL prevents stale gates.
- Input validation prevents path traversal.
- Download whitelist prevents arbitrary file access.
- No modifications to model source, checkpoint, or scientific parameters.
- Formal 8001/8080 untouched.

---

## 7. Failure Modes

| Scenario | Behavior |
|---|---|
| Authorization SHA mismatch | 403, no gate created |
| Model out of order | 409, job refused |
| Model already attempted | 409, job refused |
| Input validation fails | 400, no gate created |
| GPU unavailable | 503, queue/block |
| Subprocess timeout | Kill process, write failure manifest, cleanup, stop P33L |
| Subprocess non-zero exit | Write failure manifest, cleanup, stop P33L |
| Manifest write fails | Cleanup, stop P33L, preserve logs |
| Cleanup fails | Escalate to alert; do not continue to next model |

---

## 8. Success Criteria for Phase 2 Design

- Architecture covers all six models with fixed order and fail-stop policy.
- Every component has a single responsibility.
- No model source/checkpoint/scientific parameter changes required.
- Rollback plan can restore P33K closed-gate state.
- Proposed patch diff is concrete enough to be reviewed before application.
