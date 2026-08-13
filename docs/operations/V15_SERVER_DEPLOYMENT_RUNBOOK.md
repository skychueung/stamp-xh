# STAMP v1.5 Server Deployment Runbook

**Date:** 2026-05-12  
**Server:** stamp218 (192.168.31.218)  
**User:** xh  
**Branch:** v1.5-md-computation-pilot  
**Standard Project Directory:** `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`

---

## 1. Standard Connection

```powershell
ssh stamp218
```

Or with explicit path:

```powershell
ssh -i "$env:USERPROFILE\.ssh\stamp_xh_218" -o StrictHostKeyChecking=no -o IdentitiesOnly=yes xh@192.168.31.218
```

**Windows SSH Config Path:** `C:\Users\33319\.ssh\config`

```
Host stamp218
    HostName 192.168.31.218
    User xh
    IdentityFile C:\Users\33319\.ssh\stamp_xh_218
    IdentitiesOnly yes
    StrictHostKeyChecking no
```

---

## 2. Standard Server Directory

```bash
cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
```

All backend, frontend, data, and scripts live under this root.

---

## 3. Common Commands

### Check Git Status on Server

```powershell
ssh stamp218 "cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform && git status"
```

> Note: The server's git HEAD may lag behind the deployed code because deployments are performed via `git archive` + `scp` + `unzip`. The deployed code is the source of truth.

### Health Check

```powershell
ssh stamp218 "curl -s http://127.0.0.1:8001/api/health | python3 -m json.tool"
```

### FlexPepDock Environment Probe

```powershell
ssh stamp218 "curl -s http://127.0.0.1:8001/api/v1/flexpepdock-pilot/probe | python3 -m json.tool"
```

### Batch Queue Health

```powershell
ssh stamp218 "curl -s http://127.0.0.1:8001/api/health/queue | python3 -m json.tool"
```

### Verify Backend CWD

```powershell
ssh stamp218 "readlink -f /proc/\$(ss -tlnp | grep 8001 | awk '{print \$7}' | cut -d',' -f2 | cut -d'=' -f2)/cwd"
```

### Check Running Uvicorn Process

```powershell
ssh stamp218 "ps aux | grep uvicorn"
```

---

## 4. Deployment Procedure

### Automated (Recommended)

Run the standardized deployment script from Windows:

```powershell
.\scripts\deploy_v15_server.ps1
```

The script will:
1. Archive the current local branch (`git archive HEAD`).
2. `scp` the archive to the server.
3. Back up `data/` and the current deployment directory.
4. Extract the archive with overwrite (`unzip -o`).
5. Restore `data/`.
6. Restart only the uvicorn process on port `8001`.
7. Verify `/api/health`, `/api/v1/flexpepdock-pilot/probe`, and `/api/health/queue`.
8. Confirm that ports `8080`, `labelu`, `ws_worker`, `Dify`, `MinerU`, and `VSCode server` are untouched.

### Manual Fallback

If the automated script fails, perform the steps manually:

1. **Archive local code**
   ```powershell
   cd D:\ai\product\kimi
   git archive HEAD -o stamp-deploy.zip
   ```

2. **Upload to server**
   ```powershell
   scp stamp-deploy.zip stamp218:/tmp/
   ```

3. **SSH to server and deploy**
   ```bash
   cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
   cp -a data /tmp/data.bak.$(date +%s)
   cp -a . /home/xh/backups/stamp-$(date +%s)
   unzip -o /tmp/stamp-deploy.zip
   mv /tmp/data.bak.$(date +%s) data
   ```

4. **Restart backend**
   ```bash
   pkill -f "uvicorn app.main:app --host 0.0.0.0 --port 8001"
   cd backend
   nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > ../uvicorn.log 2>&1 &
   ```

5. **Verify**
   ```bash
   curl -s http://127.0.0.1:8001/api/health
   curl -s http://127.0.0.1:8001/api/v1/flexpepdock-pilot/probe
   curl -s http://127.0.0.1:8001/api/health/queue
   ```

---

## 5. Rollback

Each automated deployment creates a timestamped backup at:

```
/home/xh/backups/stamp-targeted-peptide-platform-<timestamp>
```

To roll back:

```bash
ssh stamp218
sudo systemctl stop stamp-backend  # if using systemd
pkill -f uvicorn
cp -a /home/xh/backups/stamp-targeted-peptide-platform-<timestamp> /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform
cd /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 > ../uvicorn.log 2>&1 &
```

---

## 6. Safety Checklist

- [ ] `data/` directory preserved (batch jobs, SQLite DB, manifests).
- [ ] Only port `8001` uvicorn restarted; other services untouched.
- [ ] Health endpoint returns `200` with `status: healthy`.
- [ ] FlexPepDock probe returns `AVAILABLE`.
- [ ] Queue health returns `healthy` with expected job counts.
- [ ] Backend CWD is `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend`.

---

## 7. Scientific Boundaries (v1.5 P1)

The following boundaries are enforced in the deployed code:

1. **No fabricated scores:** `dry_run()` logs commands but never writes hardcoded docking scores.
2. **Empty artifact guard:** `finalize_batch_item()` downgrades `success=True` to `FAILED` if the artifact directory is empty.
3. **Env missing → BLOCKED:** If `rosetta_env.sh` is missing, `dispatch_batch_item()` marks the item as `BLOCKED`.
4. **Input missing → FAILED:** `validate_input()` returns `FAILED` if `receptor_pdb` or peptide inputs are missing.
5. **Probe never claims SUCCEEDED:** `probe_flexpepdock_environment()` returns only `AVAILABLE` or `BLOCKED`.
