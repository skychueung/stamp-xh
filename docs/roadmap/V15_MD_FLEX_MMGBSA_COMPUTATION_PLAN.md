# STAMP v1.5 — MD / FlexPepDock / MM-GBSA Computation Plan

## Overview

This document tracks the phased integration of molecular dynamics (MD), FlexPepDock peptide-protein docking, and MM-GBSA binding free energy calculation into the STAMP batch computation framework.

## Phase 0: Environment Audit (COMPLETED)

**Date:** 2026-05-11

| Tool | Status | Detail |
|------|--------|--------|
| Rosetta | ✅ Available | `/home/xh/kxc/tools/rosetta/` |
| FlexPepDock | ✅ Available | After `source rosetta_env.sh` |
| GROMACS | ❌ Missing | Not installed |
| Amber | ❌ Missing | Not installed |
| OpenMM | ❌ Missing | Not installed |
| MDAnalysis | ❌ Missing | Not installed |
| GPU | ✅ Excellent | Dual RTX 4090 (24GB each) |

**Decision:** Proceed with FlexPepDock first (fastest win), defer MD and MM-GBSA until tools are installed.

## Phase 1: FlexPepDock Probe & Runner Skeleton (COMPLETED)

**Date:** 2026-05-12

### Deliverables

- [x] `backend/app/services/flexpepdock_environment_probe.py` — probes Rosetta/FlexPepDock env
- [x] `backend/app/services/flexpepdock_runner.py` — runner skeleton (validate, dry-run, smoke, dispatch)
- [x] `backend/app/routers/flexpepdock_pilot.py` — API endpoints for probe/validate/workdir/dry-run/smoke
- [x] `backend/tests/test_flexpepdock_environment_probe.py` — 8 tests
- [x] `backend/tests/test_flexpepdock_runner.py` — 11 tests
- [x] `backend/app/routers/batch_computations.py` — `FLEXPEPDOCK` added to `VALID_JOB_TYPES` / `VALID_ITEM_TYPES`
- [x] `backend/app/services/batch_compute_runner.py` — `FLEXPEPDOCK` validation and env check
- [x] `backend/app/main.py` — `flexpepdock_pilot_router` registered
- [x] `src/types/batchComputation.ts` — `"FLEXPEPDOCK"` added to `BatchJobType`
- [x] `src/pages/BatchComputationPage.tsx` — FlexPepDock option added to job type selector
- [x] `backend/app/models/orm.py` — comment updated to include `FLEXPEPDOCK`
- [x] `docs/operations/V15_FLEXPEPDOCK_RUNBOOK.md` — runbook created

### Test Results

- **Local pytest:** 845 passed (826 original + 19 new), 4 warnings, 0 failed
- **Frontend build:** Success

### Server Deployment Status

- [ ] Deployed to `192.168.31.218`
- [ ] API `/api/v1/flexpepdock-pilot/probe` verified
- [ ] Git pushed to `v1.5-md-computation-pilot`

## Phase 2: FlexPepDock Full Execution (PLANNED)

**Goal:** Implement actual FlexPepDock docking execution in `dispatch_batch_item()`.

### Tasks

- [ ] Pre-processing: receptor and peptide PDB preparation
- [ ] Low-resolution docking (`-lowres_preoptimize`)
- [ ] High-resolution refinement (`-pep_refine`)
- [ ] Score parsing from silent files
- [ ] Artifact generation and verification
- [ ] Integration with batch finalization

## Phase 3: MD Production Pilot (PLANNED)

**Prerequisite:** Install GROMACS, Amber, OpenMM, MDAnalysis on server.

### Tasks

- [ ] Install GROMACS (`sudo apt install gromacs`)
- [ ] Install AmberTools
- [ ] Install OpenMM (`pip install openmm`)
- [ ] Install MDAnalysis (`pip install MDAnalysis`)
- [ ] Extend `md_environment_probe.py` to verify new tools
- [ ] Implement `md_production_pilot.py` execution endpoints
- [ ] Add `MD` job type to batch framework

## Phase 4: MM-GBSA Binding Free Energy (PLANNED)

**Prerequisite:** Phase 3 (MD trajectories) completed.

### Tasks

- [ ] Extend `gmx_MMPBSA` integration
- [ ] Implement MM-GBSA workflow on MD trajectories
- [ ] Add `MMGBSA` execution (currently skeleton only)
- [ ] Parse and store ΔG_bind results

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| Rosetta env not persistent | BLOCKED status | Probe detects; runner never crashes |
| GROMACS install fails | MD deferred | Document in BLOCKED reasons |
| GPU driver issues | MD slow | Fall back to CPU-only MD |
| Git push network failure | Remote out of sync | Local commit preserved |

## References

- `docs/operations/V15_FLEXPEPDOCK_RUNBOOK.md`
- `backend/app/services/flexpepdock_environment_probe.py`
- `backend/app/services/flexpepdock_runner.py`
- `backend/app/routers/flexpepdock_pilot.py`
