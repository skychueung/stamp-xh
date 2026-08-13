# STAMP P33L — Reasonix Pre-Execution Verdict

**Task ID:** P33L  
**Phase:** Phase 3 final correction  
**Date:** 2026-06-29  
**Reviewer:** Reasonix (pending final review after Kimi correction + Claude review)  
**Scope:** Final Phase 2-3 correction covering runner authenticity, fully frozen manifest, frontend Target Design Run & Deliver, runtime quota monitoring, and expanded test suite.

---

## 1. Verdict

```text
REASONIX_P33L_SIX_MODEL_REAL_RUN_PREEXEC_VERDICT_PENDING
```

The previous unconditional GO is **suspended** while the final Phase 2-3 correction is in progress. The final unconditional GO will only be issued after:

1. Kimi completes all correction items in this scope.
2. Full backend tests and frontend build pass.
3. New manifest SHA is frozen.
4. Claude completes final review and marks `CLAUDE_P33L_FINAL_REVIEW_READY`.

---

## 2. Suspension Reason

The user authorization previously captured in `STAMP_P33L_USER_EXECUTION_AUTHORIZATION.txt` has been marked **INVALID/UNVERIFIED** and renamed to `STAMP_P33L_USER_EXECUTION_AUTHORIZATION_INVALID_UNVERIFIED.txt` as audit evidence.

Outstanding items requiring correction:

1. **Runner authenticity**: DiffPepBuilder and PepHAR wrappers must use official real inference entry points with verified checkpoint/config paths and SHA values, not smoke-runner wrappers.
2. **Manifest completeness**: All `<P33L_MANIFEST_SHA>`, template variables, and placeholders must be removed; every command, argument, input, runner, env var, and checkpoint path/SHA must be exact for all six models.
3. **Frontend**: Target Design page must implement Run & Deliver with backend-authorization-gated controls, model-switching without auto-submit, job status/cancel/result/manifest/download display, and `NOT_EXPERIMENTALLY_VALIDATED` marking.
4. **Runtime quota monitoring**: Quota enforcement must be active during model execution and terminate immediately on violation.
5. **Test coverage**: Cancel, download path traversal, quota, timeout, PID cleanup, manifest writer, wrapper block, duplicate submit, process-restart persistence, fail-stop, and frontend no-auto-submit tests must all exist and pass.

---

## 3. Current Gate

| Previous Gate | New Gate |
|---|---|
| `P33L_EXECUTION_AUTHORIZED` | `P33L_EXECUTION_AUTHORIZATION_PENDING` |

---

## 4. Constraints (Unchanged)

- No model execution.
- No checkpoint loading.
- No real gate creation.
- PID/process-group-level cleanup only; no `pkill` or `rm -rf` broad cleanup.
- One attempt per model, fixed order, idempotent, fail-stop.

---

## 5. Next Steps

1. Kimi completes code and document corrections.
2. Run full backend tests and frontend build.
3. Compute after-SHA manifest.
4. Freeze new manifest SHA.
5. Kimi stops writing.
6. Claude performs final review.
7. Reasonix issues final unconditional GO.
8. Stop and wait for user authorization with the **new** manifest SHA.
