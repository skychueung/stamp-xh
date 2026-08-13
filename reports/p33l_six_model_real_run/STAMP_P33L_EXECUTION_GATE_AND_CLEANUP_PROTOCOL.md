# STAMP P33L — Execution Gate and Cleanup Protocol

**Task ID:** P33L  
**Phase:** Phase 2  
**Date:** 2026-06-29  

---

## 1. Gate Principles

- Every real run must have a unique, time-bound gate.
- Gate creation is the last step before subprocess launch.
- Gate closure is the first step in cleanup.
- A gate must contain enough information to audit the authorization chain.
- Stale gates must be rejected and cleaned up.

---

## 2. Gate File Format

Path:

```
/home/xh/kxc/stampup/run_gates/p33l/<model_id>/<gate_id>/gate.json
```

Content:

```json
{
  "task_id": "P33L",
  "model_id": "pepmlm",
  "job_id": "<uuid>",
  "gate_id": "<uuid>",
  "authorized_by_manifest_sha": "<sha256>",
  "created_at": "2026-06-29T03:30:00+00:00",
  "expires_at": "2026-06-29T04:30:00+00:00",
  "created_by": "xh",
  "status": "OPEN|CLOSED|EXPIRED"
}
```

File permissions: `0o600`, owner `xh`.

---

## 3. Gate Lifecycle

### 3.1 Create

1. Verify manifest SHA matches `P33L_AUTHORIZED_MANIFEST_SHA` env var.
2. Verify model is in scope and in correct order.
3. Verify no prior attempt for this model in current P33L session.
4. Create directory with mode `0o700`.
5. Write `gate.json` with status `OPEN`.
6. Verify file owner and mode.
7. Verify path does not traverse symlinks.

### 3.2 Validate Before Run

Before invoking the runner:

1. Check gate file exists and is readable.
2. Check `status == OPEN`.
3. Check `expires_at > now()`.
4. Check `authorized_by_manifest_sha` matches current request header.
5. Reject if any check fails.

### 3.3 Close

In the `finally` block after run:

1. Write `status: CLOSED` to gate file.
2. Unlink gate file.
3. Remove gate directory if empty.
4. Log closure with timestamp.

### 3.4 Expired Gates

- A periodic cleanup job (or startup check) scans `/home/xh/kxc/stampup/run_gates/p33l/`.
- Gates with `expires_at < now()` are marked `EXPIRED` and unlinked.
- Expired gates block any run attempt that references them.

---

## 4. GPU Lock Protocol

### 4.1 Lock File

```
/home/xh/kxc/stampup/run_gates/p33l/.gpu_lock
```

Content:

```json
{
  "job_id": "<uuid>",
  "model_id": "<model>",
  "device_id": 0,
  "acquired_at": "...",
  "expires_at": "..."
}
```

### 4.2 Acquire

1. Check if lock file exists and is not stale.
2. If stale, remove and re-acquire.
3. If active, block/wait (no preemption).
4. Write lock file with TTL = run timeout + 5 minutes.

### 4.3 Release

1. Remove lock file in `finally`.
2. If removal fails, log alert and do not proceed to next model.

---

## 5. Cleanup Protocol

### 5.1 Always Run in `finally`

```python
try:
    result = run_model(...)
finally:
    close_gate(gate_id)
    release_gpu_lock()
    kill_subprocess_tree(subproc)
    remove_temp_files()
    write_final_manifest(result or failure_state)
```

### 5.2 Subprocess Cleanup

- On timeout or cancellation, send `SIGTERM`.
- Wait up to 30 seconds.
- If still alive, send `SIGKILL`.
- Kill entire process group to catch child processes.

### 5.3 Temporary Files

- Remove any files written outside `<run_dir>`.
- Do not delete `<run_dir>`; it is the audit artifact.
- **Forbidden cleanup commands:** never use `rm -rf /home/xh/kxc/stampup/run_gates/p33l`, `pkill -f 'p33l'`, `killall -r '.*p33l.*'`, or any other broad process/filesystem sweep. Cleanup must target the exact job PID, gate path, and lock file.

### 5.4 Gate/Lock Verification After Cleanup

After each model, verify:

- Gate directory for that model is empty or absent.
- GPU lock file is absent.
- No orphan subprocesses for that model.

If any remain, stop P33L and alert.

---

## 6. Failure-Stop Policy

- If any model fails (non-zero exit, timeout, manifest error, cleanup failure), immediately stop the entire P33L sequence.
- Mark all subsequent models as `SKIPPED_DUE_TO_PRIOR_FAILURE`.
- Do not retry the failed model.
- Do not modify env/source/runner/input to make it succeed.
- Output `STAMP_P33L_<MODEL>_FAILED_STOPPED_REPORT.md`.

---

## 7. Pre-Flight Checklist Before Each Model

- [ ] Manifest SHA verified.
- [ ] Model is next in fixed order.
- [ ] Prior models all succeeded.
- [ ] Input validated and copied.
- [ ] Disk quota available.
- [ ] GPU lock acquired.
- [ ] Gate created and valid.
- [ ] Runner/adapter SHA matches manifest.
- [ ] Timeout and cleanup handlers registered.

---

## 8. Post-Flight Checklist After Each Model

- [ ] Subprocess exit code captured.
- [ ] Manifest and SHA files written.
- [ ] Gate closed and removed.
- [ ] GPU lock released.
- [ ] No orphan processes.
- [ ] Result recorded in orchestrator state.
