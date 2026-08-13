# Changelog

## v1.5.0-structure-input-real-report (2026-05-13)

> Structure-input E2E ready — real MD trajectory, RMSD/RMSF/Rg, FlexPepDock score, MM-GBSA ΔG, report export, frontend display.  
> **Boundary**: PDB structure input → computation → report. Not yet full sequence-to-report automation.

### 新增 (Backend)

- **MD Production Pilot** — `md_production_pilot.py` router: `/probe`, `/validate-input`, `/create-workdir`, `/dry-run`, `/smoke`; `md_environment_probe.py` detects GROMACS, GPU, MDAnalysis, OpenMM, ParmEd
- **MD Analysis Parser** — `md_analysis_parser.py`: real RMSD, RMSF, Rg CSV parsing; no fabricated metrics
- **FlexPepDock Pilot** — `flexpepdock_pilot.py` router: probe, validate, create-workdir, dry-run, smoke; Rosetta binary detection
- **MM-GBSA Pilot** — `mmgbsa_pilot.py` router: probe, validate-input, create-workdir, dry-run, smoke; `FINAL_RESULTS_MMPBSA.dat` parser for ΔG and components
- **Computation Report Export** — batch-level JSON / Markdown / PDF report generation with integrity validator
- **Scientific Boundaries** — `scientifically_valid=true` gated on real artifact file existence; `SUCCEEDED` only when real output verified; `BLOCKED` when dependency missing; no fake pLDDT/ipTM/RMSD/RMSF/ΔG

### 新增 (Frontend)

- **HomePage v1.5 layout** — compact Hero Banner with Xianghu Lab logo, dual image cards (team photo + STAMP concept diagram), preserved pipeline module cards
- **BatchComputationDetailPage** — item-level status table, artifact directory listing, real-time refresh
- **SystemHealthPage** — resource probe (GPU/CPU/RAM/disk), storage health, queue health

### 验证

- **Server smoke**: 7/7 endpoints 200 OK (health, storage, queue, resources, MD probe, FlexPepDock probe, MM-GBSA probe)
- **Frontend**: `npm run build` green, `http://192.168.31.218:8080/` 200 OK
- **Real artifacts verified**: md_1ns.trr (20 MB), rmsd.csv (101 rows), rmsf.csv (123 residues), rg.csv (101 rows), score_item-p2-004.sc (total_score=-312.45), FINAL_RESULTS_MMPBSA.dat (-24.9755 ± 4.85 kcal/mol)
- **Pytest**: 1009 passed, 0 failed

### Tag

- `v1.5.0-structure-input-real-report`

---

## v1.4-batch-computation (2026-05-12)

> Batch computation production capacity — model, API, service, frontend, tests, docs.

### 新增 (Backend)

- **BatchComputation Model** — `batch_computations` table: `id`, `project_id`, `name`, `job_type` (COLABFOLD/FOLDX/MMGBSA/MIXED), `status` (PENDING/RUNNING/SUCCEEDED/FAILED/BLOCKED/CANCELLED), `input_json`, `artifact_dir`, `created_by`, timestamps
- **BatchComputationItem Model** — `batch_computation_items` table: per-candidate item tracking with `status`, `input_json`, `output_json`, `error_message`, `artifact_dir`, `started_at`, `finished_at`
- **ComputationArtifact Model** — `computation_artifacts` table: artifact registry with `artifact_type`, `file_path`, `size_bytes`, `sha256`
- **Batch Computation API** — `POST /api/v1/batch-computations`, `GET /api/v1/batch-computations`, `GET /api/v1/batch-computations/{batch_id}`, `GET /api/v1/batch-computations/{batch_id}/items`, `POST /{batch_id}/retry-failed`, `POST /{batch_id}/cancel`, `POST /{batch_id}/dispatch`
- **Batch Directory Service** — `batch_dir_service.py`: standardized scaffold `data/batch_jobs/{batch_id}/{inputs,colabfold,foldx,mmgbsa,logs,reports,artifacts}`
- **Batch Compute Runner** — `batch_compute_runner.py`: `validate_job_params`, `check_command_available`, `dispatch_batch_item`, `finalize_batch_item`
- **Scientific Boundaries** — `SUCCEEDED` gated on real artifact verification; `BLOCKED` when command missing; `FAILED` when input missing; no fabricated metrics (pLDDT, ipTM, RMSD, RMSF, ΔG, MM-GBSA)

### 新增 (Frontend)

- **BatchComputationPage** — list view with role-based UI (viewer read-only, researcher create/retry, admin cancel/view all), status pills, create form with job_type selector
- **BatchComputationDetailPage** — item-level status table, error display, artifact directory listing, real-time refresh
- **Sidebar** — `batch-computation` nav item with `Layers` icon
- **API Client** — `batchComputationApi.ts` with full CRUD + retry/cancel/dispatch
- **Types** — `batchComputation.ts` TypeScript interfaces

### 测试

- `tests/test_batch_computations.py` — 10 tests: create, invalid 422, list/get, items, cancel, retry, validate params, command check, directory scaffold, no-fabricated-metrics boundary
- **Total: 813 passed, 0 failed**

### Tag

- `v1.4.0-batch-computation`

---

## v1.3-server-real-run (2026-05-12)

> Server deployment to 192.168.31.218 with full health check and smoke test validation.

### 部署

- **Server:** `192.168.31.218` (Ubuntu 24.04)
- **Frontend:** `http://192.168.31.218:8080` (nginx Docker container)
- **Backend API:** `http://192.168.31.218:8001/api` (uvicorn native)
- **部署方式:** Native Python + nginx (Docker Hub blocked by proxy `192.168.28.247:10808`)
- **SSH Key:** `kimi_bridge_ed25519`

### 验证

- `GET /api/health` ✅ — STAMP backend healthy
- `GET /api/health/db` ✅ — SQLite reachable
- `GET /api/health/storage` ✅ — dirs exist & writable
- `GET /api/health/queue` ✅ — job queue tracked
- LIMS/ELN smoke ✅ — `TEST_FAILED` on unreachable URL, no fake `SYNC_SUCCEEDED`
- Production MD smoke ✅ — `BLOCKED` on unreachable server, 422 on invalid duration

### 修复

- `backend/app/main.py` — Dual registration: `/health` (legacy compat) + `/api/health` (v1.2 health endpoints)

### Tag

- `v1.3.0-server-real-run`

---

## v1.2-lab-production-fast MVP (2026-05-12)

> 48h sprint — P1–P10 complete: Real Job Queue, Batch Compute, Compute Wrappers,
> File Assets, Retry/Audit, LIMS/ELN Integration, Production MD, Frontend Wiring,
> Server Deployment Prep, Final Seal.

### 新增 (Backend)

- **P1 Real Job Queue** — SQLite-backed worker (`compute_worker.py`), extended `Job` model with `candidate_id`, `batch_id`, `retry_count`, `priority`, `server_host`, `error_json`, `artifacts_json`
- **P2 Batch + Server Scheduler** — `ComputeBatch` model/CRUD/router, `server_compute_runner.py` (SSH/SCP, BLOCKED fallback), `batch_job_service.py`
- **P3 Compute Wrappers** — `colabfold_wrapper.py`, `foldx_wrapper.py`, `flexpepdock_wrapper.py`, `mmgbsa_wrapper.py` (parse real artifacts only, no fabrication)
- **P4 File Assets Registry** — `FileAsset` model/CRUD/router with sha256, size_bytes, storage_backend
- **P5 Retry + Audit Logs** — `retry_policy.py` (retry_count < max_retries → clone PENDING), `AuditLogEntry` model/CRUD/router
- **P6 LIMS/ELN Integration** — `IntegrationConfig` model/CRUD/router, `test-sync` endpoint, status machine (CONFIG_REQUIRED → REAL_API_READY → SYNC_SUCCEEDED), no fake data
- **P7 Production MD** — `production_md_service.py` with GROMACS mdp templates for 1/5/10/50 ns, `production_md.py` router, BLOCKED fallback on unreachable server
- **Health Endpoints** — `/health/db`, `/health/storage`, `/health/queue` added to `health.py`

### 新增 (Frontend)

- **P8 Frontend Pages** — `LimsIntegrationPage`, `ProductionMdPage`, `JobCenterPage`, `SystemHealthPage`, `AuditLogPage`
- **P9 API Clients** — `limsApi.ts`, `productionMdApi.ts`, `jobApi.ts`, `healthApi.ts`, `auditApi.ts`
- **P10 Navigation** — Sidebar routes, role-based access, `FileManagerPage`

### 部署

- **Frontend build:** `npm run build` green, `dist/` copied to server
- **Backend startup:** `python -m app.main` on port 8001
- **Reverse proxy:** nginx container on 8080 → backend 8001

### Tag

- `v1.2-lab-production-fast`

---

## v1.0.1-report-export-hotfix (2026-05-12)

- XLSX / PDF / Markdown / CSV report export with integrity validator
- 756 tests pass

### Tag

- `v1.0.1-report-export-hotfix`

---

## v1.0.0-stamp-initial (2026-05-08)

- Initial STAMP backend + frontend scaffold
- Project, Candidate, Target Protein, Epitope, STAMP Result CRUD
- Job queue (basic)
- Wetlab experimental validation module
