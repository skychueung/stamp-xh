# STAMP v1.5 P1.1 — SSH stamp218 Auto-Deploy Standardization Report

**Date:** 2026-05-12  
**Task:** Standardize all server deployments, smoke tests, health checks, and service restarts to use `ssh stamp218`.  
**Local Branch:** `v1.5-md-computation-pilot`  
**Local Commit:** `6a19764` (restored from server)  
**Report Author:** Kimi Code CLI

---

## 1. SSH stamp218 Fix Result

| Check | Result |
|-------|--------|
| `ssh stamp218 "hostname && whoami && pwd"` | ✅ PASS |
| Hostname | `xh-System-Product-Name` |
| User | `xh` |
| Home | `/home/xh` |
| Server IP | `192.168.31.218` |

**Windows SSH Config Path:** `C:\Users\33319\.ssh\config`

```
Host stamp218
    HostName 192.168.31.218
    User xh
    IdentityFile C:\Users\33319\.ssh\stamp_xh_218
    IdentitiesOnly yes
    StrictHostKeyChecking no
```

> Note: A symlink `/home/xh/stamp` was created on the server to avoid PowerShell encoding issues with the Chinese directory name (`靶向肽`). The deploy script now uses `/home/xh/stamp` as the canonical remote path.

---

## 2. Standard Server Directory

```
/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
```

**Symlink (recommended for scripts):**
```
/home/xh/stamp -> /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
```

---

## 3. Auto-Deploy Script

**Path:** `D:\ai\product\kimi\scripts\deploy_v15_server.ps1`

**Capabilities:**
- Uses `ssh stamp218`
- Uses `git archive HEAD` + `scp` for code transfer
- Preserves `data/` directory across deployments
- Creates timestamped backups at `/home/xh/backups/`
- Restarts **only** the uvicorn process on port `8001`
- Verifies health, flexpepdock probe, and queue endpoints
- Confirms other services (8080 frontend, labelu, ws_worker, Dify, MinerU, VSCode server) are untouched

---

## 4. Deployment Execution Summary

| Step | Status |
|------|--------|
| Local `git archive HEAD` | ✅ Created `stamp-deploy-v15.zip` (104,579,952 bytes) |
| `scp` to server | ✅ Uploaded to `/tmp/stamp-deploy-v15.zip` |
| Server backup | ✅ Created `/home/xh/backups/stamp-targeted-peptide-platform-1778590603` |
| `data/` preservation | ✅ Backed up and restored |
| Archive extraction | ✅ `unzip -o` completed |
| Backend restart | ✅ Old PID `3857578` killed, new PID `3909983` started |

---

## 5. Verification Results

### 5a — Health Check

```json
{
  "code": 200,
  "message": "STAMP backend is healthy",
  "data": {
    "status": "healthy",
    "service": "stamp-backend",
    "version": "0.6.0",
    "timestamp": "2026-05-12T12:59:19.483692+00:00"
  }
}
```
✅ **PASS**

### 5b — FlexPepDock Probe

```json
{
  "code": 200,
  "message": "success",
  "data": {
    "status": "AVAILABLE",
    "rosetta_env_script_exists": true,
    "flexpepdock_available": true,
    "rosetta_scripts_available": true,
    "rosetta_db_available": true,
    "rosetta_root": "/home/xh/kxc/tools/rosetta",
    "blocking_reasons": []
  }
}
```
✅ **PASS**

### 5c — Batch Queue Health

```json
{
  "code": 200,
  "message": "Queue healthy — 0 jobs tracked",
  "data": {
    "status": "healthy",
    "total_jobs": 0,
    "breakdown": {
      "pending": 0,
      "running": 0,
      "succeeded": 0,
      "failed": 0,
      "blocked": 0
    }
  }
}
```
✅ **PASS**

### 5d — Backend CWD

| Check | Expected | Actual | Result |
|-------|----------|--------|--------|
| `readlink -f /proc/$PID/cwd` | `/home/xh/stamp/backend` | `/home/xh/stamp/backend` | ✅ PASS |

---

## 6. Current Server Commit

**Important:** The server's git repository HEAD remains at `d77a2c4 v1.4.1-deploy` on `master`. The v1.5 code was deployed via `git archive` + `unzip`, so the deployed files are **not tracked by git** on the server. The actual deployed code matches local commit `6a19764` on branch `v1.5-md-computation-pilot`.

| Source | Commit / Branch |
|--------|-----------------|
| Server git HEAD | `d77a2c4` (master) — stale |
| Deployed code truth | `6a19764` (`v1.5-md-computation-pilot`) — local |

**Recommendation:** On the server, run `git add . && git commit -m "v1.5 P1 deploy"` to bring the git HEAD in line with the deployed code if you wish to use `git pull` for future deployments.

---

## 7. Scientific Boundaries

The following boundaries are enforced in the deployed v1.5 P1 code:

1. **No fabricated scores:** `dry_run()` logs commands but never writes hardcoded docking scores.
2. **Empty artifact guard:** `finalize_batch_item()` downgrades `success=True` to `FAILED` if the artifact directory is empty.
3. **Env missing → BLOCKED:** If `rosetta_env.sh` is missing, `dispatch_batch_item()` marks the item as `BLOCKED`.
4. **Input missing → FAILED:** `validate_input()` returns `FAILED` if `receptor_pdb` or peptide inputs are missing.
5. **Probe never claims SUCCEEDED:** `probe_flexpepdock_environment()` returns only `AVAILABLE` or `BLOCKED`.

---

## 8. Issues & Resolutions

| Issue | Resolution |
|-------|------------|
| Local code incomplete (only 4 router files vs 26 on server) | Reverse-synced complete server codebase via `tar.gz` + `scp` |
| Local not a git repository | `git init`, added remote, created `v1.5-md-computation-pilot` branch |
| PowerShell 5.1 script compatibility | Lowered `#Requires` from 7.0 to 5.1 |
| Chinese path encoding in PowerShell here-strings | Created `/home/xh/stamp` symlink on server |
| `ss` not available on server (older distro) | Fallback to `pkill -f` in restart script |
| GitHub fetch/push timeout | Documented; push will be retried separately |

---

## 9. Exit Criteria Checklist

- [x] `docs/operations/V15_SERVER_DEPLOYMENT_RUNBOOK.md` exists and documents `ssh stamp218` usage
- [x] `scripts/deploy_v15_server.ps1` exists and is executable
- [x] Deploy script archives, uploads, extracts, and preserves `data/`
- [x] Backend on port `8001` restarted successfully
- [x] `/api/health` returns `200` with `status: healthy`
- [x] `/api/v1/flexpepdock-pilot/probe` returns `AVAILABLE`
- [x] `/api/health/queue` returns `healthy`
- [x] Backend CWD is correct
- [x] Other services untouched
- [x] Report generated
- [x] Local git commit created (`6a19764`)
- [ ] Git push to `origin v1.5-md-computation-pilot` — **pending** (GitHub network timeout)

---

## 10. Next Steps

1. **Fix GitHub connectivity** and retry `git push origin v1.5-md-computation-pilot`.
2. **Optional:** On the server, commit the deployed files into git so that future deployments can use `git pull` instead of `git archive` + `unzip`.
3. **Optional:** Add a `.gitattributes` file to handle line endings consistently across Windows and Linux.
