# STAMP v1.4 Batch Computation — Final Report

**Date:** 2026-05-12  
**Branch:** `v1.4-batch-computation`  
**Base:** `v1.3.0-server-real-run` (`dd5bf20`)  
**Tag:** `v1.4.0-batch-computation`  
**Tests:** 813 passed, 0 failed, 3 warnings (Pydantic class-based config deprecation)

---

## 1. What Was Delivered

### 1.1 Backend — Batch Computation Core

| Component | Files | Description |
|-----------|-------|-------------|
| **ORM Models** | `backend/app/models/orm.py` | `BatchComputation`, `BatchComputationItem`, `ComputationArtifact` |
| **CRUD** | `backend/app/crud/batch_computations.py` | Create, read, update, cancel batch + items |
| **Router** | `backend/app/routers/batch_computations.py` | 7 endpoints (create, list, get, items, retry, cancel, dispatch) |
| **Directory Service** | `backend/app/services/batch_dir_service.py` | Standardized scaffold: `data/batch_jobs/{batch_id}/{inputs,colabfold,foldx,mmgbsa,logs,reports,artifacts}` |
| **Compute Runner** | `backend/app/services/batch_compute_runner.py` | `validate_job_params`, `check_command_available`, `dispatch_batch_item`, `finalize_batch_item` |

**API Endpoints:**
- `POST /api/v1/batch-computations` — create batch + scaffold dir + items
- `GET /api/v1/batch-computations` — list by project_id
- `GET /api/v1/batch-computations/{batch_id}` — get batch details
- `GET /api/v1/batch-computations/{batch_id}/items` — list all items
- `POST /api/v1/batch-computations/{batch_id}/retry-failed` — reset FAILED/BLOCKED → PENDING
- `POST /api/v1/batch-computations/{batch_id}/cancel` — cancel batch + items
- `POST /api/v1/batch-computations/{batch_id}/dispatch` — trigger execution of PENDING items

**Status Machine:**
```
PENDING → RUNNING → SUCCEEDED
        → BLOCKED (command missing)
        → FAILED  (input missing / error)
        → CANCELLED (user action)
```

### 1.2 Frontend — Batch Computation UI

| Component | Files | Description |
|-----------|-------|-------------|
| **List Page** | `src/pages/BatchComputationPage.tsx` | Create form, status pills, role-based actions |
| **Detail Page** | `src/pages/BatchComputationDetailPage.tsx` | Item-level table, error display, artifact listing |
| **API Client** | `src/lib/api/batchComputation.ts` | Full CRUD + retry/cancel/dispatch |
| **Types** | `src/types/batchComputation.ts` | TypeScript interfaces |
| **Navigation** | `src/components/platform/Sidebar.tsx` | `Layers` icon nav item |
| **Routing** | `src/App.tsx` | `/batch-computation`, `/batch-computation/:batchId` |

### 1.3 Tests

`backend/tests/test_batch_computations.py` — 10 tests:
1. `test_create_batch_computation` — create + verify response
2. `test_create_invalid_job_type` — 422 on INVALID job_type
3. `test_list_and_get_batch` — list by project_id, get by id
4. `test_get_batch_items` — item listing
5. `test_cancel_batch` — cancel batch → CANCELLED
6. `test_retry_failed_items` — retry endpoint returns retried_count
7. `test_validate_job_params` — sequence length validation
8. `test_check_command_available` — python3 exists, fake command missing
9. `test_batch_dir_service` — directory scaffold verification
10. `test_finalize_without_artifacts_fails` — empty artifact dir → FAILED (no fabrication)

**Total test count: 813 passed (was 803)**

---

## 2. Scientific Boundaries Enforced

| Boundary | Implementation |
|----------|---------------|
| **No fabricated metrics** | `finalize_batch_item` checks `os.listdir(artifact_dir)`; if empty → `FAILED` regardless of `success=True` |
| **Command check** | `check_command_available()` called before dispatch; missing → `BLOCKED` |
| **Input validation** | `validate_job_params()` enforces sequence length ≥ 5, valid job_type enum |
| **SUCCEEDED gate** | Only set after real output files are verified on disk |
| **No hallucinated pLDDT/ipTM/RMSF/ΔG** | Wrappers are skeleton-only; values come from real ColabFold/FoldX/MM-GBSA output files |

---

## 3. Deployment Status

| Environment | Status | URL |
|-------------|--------|-----|
| **Local dev** | ✅ All tests pass | `http://localhost:8001` |
| **Server** | ⚠️ Needs redeploy | `http://192.168.31.218:8001/api` |

**Server constraint:** Docker Hub blocked by proxy `192.168.28.247:10808`. Native Python + nginx is the working path.

**Redeploy steps (post-server-restore):**
```bash
# On server (192.168.31.218)
cd ~/stamp-targeted-peptide-platform
git fetch origin
git checkout v1.4-batch-computation
cd backend
source .venv/bin/activate
pip install -r requirements.txt
# DB reinit if needed (SQLite schema changed)
python -c "from app.database import Base, engine; Base.metadata.create_all(bind=engine)"
# Start backend
nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 2 > uvicorn.log 2>&1 &

# Frontend
cd ../
npm install
npm run build
sudo docker rm -f stamp-nginx 2>/dev/null
sudo docker run -d --name stamp-nginx -p 8080:80 -v $(pwd)/dist:/usr/share/nginx/html:ro nginx:alpine
```

---

## 4. Git Status

```
Branch: v1.4-batch-computation
Commit: 5018acf — v1.4-batch-computation: models, API, service, frontend, 10 tests
Tag:    v1.4.0-batch-computation
Push:   ✅ GitHub (branch + tag)
```

---

## 5. Known Issues & Next Steps

| Issue | Priority | Note |
|-------|----------|------|
| **Server redeploy** | 🔴 High | Server will be wiped at 09:40; need git pull + restart after restore |
| **Frontend chunk size** | 🟡 Medium | `index.js` > 5 MB; needs code-splitting (React.lazy) |
| **Schema migration** | 🟡 Medium | Currently requires DB reinit; Alembic for production |
| **Compute wrappers** | 🟢 Low | Skeleton only; needs real ColabFold/FoldX/MM-GBSA binaries on server |
| **Batch queue worker** | 🟢 Low | Currently dispatch is manual (`POST /dispatch`); background worker in v1.5 |

---

## 6. Sign-off

- ✅ Backend models (3 new tables)
- ✅ Backend API (7 endpoints)
- ✅ Backend services (directory scaffold, compute runner)
- ✅ Frontend pages (list + detail)
- ✅ Frontend API client + types
- ✅ Navigation integration
- ✅ Tests (10 new, 813 total)
- ✅ CHANGELOG updated
- ✅ Git committed + tagged + pushed
- ⏳ Server redeploy (pending server restore)

**v1.4-batch-computation is CODE-COMPLETE and TESTED.**
