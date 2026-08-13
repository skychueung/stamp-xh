# STAMP P33L — Runner / Adapter / UI Gap Report

**Task ID:** P33L  
**Phase:** Phase 1  
**Date:** 2026-06-29  

---

## 1. Gap Matrix

| # | Gap | PepMLM | EvoBind2 | DiffPepBuilder | PepFlow | PepHAR | PPFlow | Severity |
|---|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| G1 | Registry `real_run_enabled=False` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Required by design |
| G2 | Registry `supports_real_run=False` | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | Medium |
| G3 | Adapter `submit()` blocks or missing | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Critical |
| G4 | No unified P33L job orchestration | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Critical |
| G5 | Runner skeleton or smoke-only | ❌ | Partial | ✅ | ✅ | ✅ | ✅ | Critical |
| G6 | No manifest writer / incomplete | Partial | ✅ | Partial | ✅ | ✅ | ✅ | High |
| G7 | No GPU lock (except PepMLM) | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | High |
| G8 | No timeout / quota / cleanup for all models | Partial | Partial | Partial | ✅ | ✅ | ✅ | High |
| G9 | Real-run gate file missing | ✅ | N/A | ✅ | ✅ | ✅ | ✅ | Required by design |
| G10 | UI Real Run panel / backend gating | N/A | N/A | N/A | N/A | N/A | N/A | High |

Legend: ✅ = gap present / needs work; ❌ = no gap; Partial = partially implemented.

---

## 2. Gap Detail

### G1 — Registry `real_run_enabled=False`
**Impact:** All six models are execution-locked.  
**Disposition:** This is the correct baseline. A P33L execution policy must temporarily override or bypass this flag only inside a controlled, limited-lifetime gate. It must NOT be persisted as `real_run_enabled=True` until Phase 5 after all six models succeed.

### G2 — Registry `supports_real_run=False`
**Impact:** Five of six models do not advertise real-run capability. PepMLM advertises `True` but is still gated.  
**Disposition:** Capability flags should reflect the underlying adapter/runner once Phase 2 implementation is complete. They should not be flipped before readiness is proven.

### G3 — Adapter `submit()` blocks or missing
**Impact:** No model can be submitted for real execution through the current adapter interface.  
**Disposition:** Phase 2 must implement (or wrap) a real-run `submit()` path for each model. The default state must remain blocked unless a valid P33L execution gate is open for the specific job.

### G4 — No unified P33L job orchestration
**Impact:** There is no single backend service that creates a job, checks authorization, locks a GPU, dispatches the adapter, monitors the run, writes manifests, and cleans up.  
**Disposition:** Design a `P33LJobOrchestrator` (or extend existing batch compute runner) with strict one-at-a-time semantics and per-model single-attempt policy.

### G5 — Runner skeleton or smoke-only
**Impact:** DiffPepBuilder, PepFlow, PepHAR, and PPFlow cannot perform a real target-conditioned design run. EvoBind2 has a real runner but it is not wired to one-click submission.  
**Disposition:**
- PepMLM: use existing real runner.
- EvoBind2: wire existing runner to the orchestrator; implement per-run gate creation.
- DiffPepBuilder / PepFlow / PepHAR / PPFlow: either implement minimal real-design wrappers or use their existing inference scripts (`mc_design.py`, `inference.py`, smoke runners upgraded with real input handling, `codesign_ppf.py`) behind a controlled adapter.

### G6 — No manifest writer / incomplete
**Impact:** Success/failure evidence cannot be frozen and audited.  
**Disposition:** The orchestrator must write a uniform `run_manifest.json` for every job, including exit code, SHA, input provenance, resource usage, and `NOT_EXPERIMENTALLY_VALIDATED` disclaimer.

### G7 — No GPU lock (except PepMLM)
**Impact:** Concurrent model runs or interference with existing GPU workloads is possible.  
**Disposition:** Extend the existing `gpu_lock_service.py` file-based lock to all six models, or use a single orchestrator-level lock that holds one GPU exclusively during a P33L job.

### G8 — No timeout / quota / cleanup
**Impact:** A run could hang, fill disk, or leave gates/processes open.  
**Disposition:** The orchestrator must enforce per-model hard timeout, disk quota, output file count limit, and a `finally`-style cleanup of gates, subprocesses, and temporary locks regardless of success/failure.

### G9 — Real-run gate file missing
**Impact:** Even PepMLM, which has the most complete runner, cannot start because the gate file is absent.  
**Disposition:** Phase 3 manifest must define the exact gate creation command. The orchestrator creates the gate only after all pre-checks pass and destroys it in cleanup.

### G10 — UI Real Run panel / backend gating
**Impact:** The frontend currently shows Probe/Dry Run only.  
**Disposition:** Add a Real Run / Run & Deliver panel that is visible only when the backend reports `p33l_execution_authorized=true` for the current session. All action enabling must come from the backend; frontend must not unlock locally.

---

## 3. UI-Specific Observations

- The dev frontend at `http://192.168.31.218:12823/target-design` currently supports model switching, probe, and dry-run.
- Real Run buttons are absent or disabled because the backend reports `real_run_enabled=false` for all models.
- Phase 2 UI changes must:
  - Add a `Run & Deliver` action that calls a new backend endpoint.
  - Display job status (`queued → running → succeeded/failed`).
  - Show `NOT_EXPERIMENTALLY_VALIDATED` disclaimers on outputs and downloads.
  - Disable/hide Real Run when not authorized.
  - Prevent duplicate job creation on repeated clicks or page refresh.

---

## 4. Recommendations for Phase 2

1. **Do not flip `real_run_enabled` in the registry yet.** Use a transient P33L execution gate instead.
2. **Create a single `P33LJobOrchestrator`** that owns gate creation, GPU lock, adapter invocation, manifest writing, and cleanup.
3. **Implement per-model `submit_real_run()` wrappers** rather than changing each adapter's default `submit()` semantics.
4. **Reuse existing inference scripts** where possible to minimize source changes.
5. **Enforce the fixed execution order** and `failure-stop` policy in the orchestrator, not in individual adapters.
6. **Write the manifest schema first** so every runner/orchestrator outputs a uniform artifact.
7. **Add backend-gated UI** that never unlocks based on frontend state alone.

---

## 5. Conclusion

The Phase 1 gap report confirms that P33L cannot proceed to real execution without Phase 2 design and implementation. The gaps are engineering/governance gaps, not missing checkpoints or environments. All six models have the necessary source, weights, and environments; what is missing is a controlled, one-click, audited, fail-stop real-run execution layer.
