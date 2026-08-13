# STAMP P33L — Rollback Plan

**Task ID:** P33L  
**Phase:** Phase 2  
**Date:** 2026-06-29  

---

## 1. Rollback Scenarios

1. Phase 2 patch application fails or introduces regressions.
2. Phase 4 real run fails and must not leave the system in a partially-unlocked state.
3. Phase 5 verification fails and the system must revert to P33K closed-gate state.
4. Any unauthorized gate/process/lock is detected.

---

## 2. Pre-Patch Backup (Required Before Any Phase 2 Changes)

Command:

```bash
rsync -a \
  --exclude=node_modules \
  --exclude=__pycache__ \
  --exclude=.venv \
  --exclude=dist \
  /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/ \
  /home/xh/kxc/stampup/backups/p33l_pre_phase2_<YYYYMMDD_HHMMSS>/
```

Also record the pre-patch SHA manifest (already generated in `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`).

---

## 3. Registry State Backup

Before changing any registry flags:

```bash
python3 -c 'import hashlib, json; ...' \
  > /home/xh/kxc/stampup/backups/p33l_registry_state_<YYYYMMDD_HHMMSS>.json
```

Capture the full `/api/v1/model-registry/status` response.

---

## 4. Rollback Steps

### 4.1 Stop Dev Backend

```bash
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh
```

### 4.2 Restore Code

```bash
rsync -a --delete \
  /home/xh/kxc/stampup/backups/p33l_pre_phase2_<YYYYMMDD_HHMMSS>/ \
  /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/
```

### 4.3 Clean Up Any P33L Gates / Locks / Jobs

```bash
rm -rf /home/xh/kxc/stampup/run_gates/p33l
rm -f /home/xh/kxc/stampup/run_gates/p33l/.gpu_lock
rm -rf /mnt/sdb/kxc/stamp_models/artifacts/p33l
```

### 4.4 Verify No P33L Processes

```bash
ps aux | grep -E 'p33l|P33L' | grep -v grep
# Expected: no output
```

### 4.5 Rebuild Frontend and Restart Dev Backend

```bash
cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
npm run build
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh
```

### 4.6 Verify Registry State

```bash
curl -s http://localhost:12824/api/v1/model-registry/status | python3 -m json.tool
```

Expected:

- Six models in `available_six`, `real_run_enabled=false`, `execution_locked=true`.
- PepGLAD/RFpeptides in `reserved_placeholder`.
- PepPrCLIP in `excluded`.

---

## 5. Post-Rollback SHA Check

Compare restored file SHAs to `STAMP_P33L_SIX_MODEL_PREEXEC_SHA256_MANIFEST.txt`. Any mismatch requires investigation before declaring rollback complete.

---

## 6. Rollback Record

After any rollback, update `STAMP_P33L_ROLLBACK_RECORD.md` with:

- Timestamp.
- Reason for rollback.
- Backup path used.
- Files restored.
- Registry state verified.
- Any residual gates/locks/processes found and cleaned.

---

## 7. Emergency Stop Procedure

If at any point an unsafe operation is detected:

1. Do not proceed to the next model.
2. Close and remove any open gate.
3. Release GPU lock.
4. Kill any P33L subprocess.
5. Run the rollback steps above.
6. Report `P33L_EMERGENCY_ROLLBACK_COMPLETE`.
