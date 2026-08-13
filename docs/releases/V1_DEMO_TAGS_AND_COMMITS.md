# STAMP v1.0 Demo Tags and Commits

**Date:** 2026-05-12  
**Branch:** `v1.0-demo-teacher-ready-release`

---

## Final Tag

| Tag | Target Commit | Description |
|-----|--------------|-------------|
| `v1.0.0` | `9093ffe` | STAMP v1.0 demo / teacher-ready release |

---

## Commit History (last 10)

| Hash | Message | Phase |
|------|---------|-------|
| `9093ffe` | v1.0: Add deployment guide, demo dataset, demo flow, startup script, autopilot checklist, and teacher materials | v1.0-final |
| `2a5e952` | v0.13-final: Seal MMPBSA parser + persistence guard + frontend readiness card | v0.13-final |
| `7e258a9` | v0.13-P5: Frontend MM-GBSA Readiness Card + types | v0.13-P5 |
| `15640a0` | v0.13-P4: Add MM-GBSA persistence guard with production criteria enforcement | v0.13-P4 |
| `db5d6b3` | v0.13-P3: Add MMPBSA result parser with scientific boundary enforcement | v0.13-P3 |
| `9a57954` | docs: seal v0.11 wetlab validation workflow | v0.11-final |
| `c9088a6` | feat: export wetlab validation reports (v0.11-P5) | v0.11-P5 |
| `70afd38` | feat: add candidate prioritization decision panel (v0.11-P4) | v0.11-P4 |
| `0240a6d` | feat: add experimental validation dashboard and csv import (v0.11-P3) | v0.11-P3 |
| `1611d4c` | feat: add experimental validation entry UI (v0.11-P2) | v0.11-P2 |

---

## Historical Tags

| Tag | Commit | Description |
|-----|--------|-------------|
| `v1.0.0` | `9093ffe` | v1.0 demo / teacher-ready release |
| `v0.11-final-wetlab-validation-workflow` | `c9088a6` | v0.11 wet-lab validation |
| `v0.11-p5-wetlab-validation-report-export` | `c9088a6` | v0.11-P5 report export |
| `v0.11-p4-candidate-prioritization-panel` | `70afd38` | v0.11-P4 prioritization |
| `v0.11-p3-experimental-validation-dashboard` | `0240a6d` | v0.11-P3 dashboard |
| `v0.11-p2-experimental-data-entry-ui` | `1611d4c` | v0.11-P2 data entry |
| `v0.11-p1-experimental-validation-data-model` | `621e578` | v0.11-P1 data model |

---

## Files by v1.0 Commit

### Deployment & Scripts
- `docs/deployment/v1.0-DEPLOYMENT_GUIDE.md`
- `start-backend.ps1`
- `scripts/start-frontend.ps1`
- `scripts/start-all-local-services.ps1`
- `scripts/check-all-health.ps1`
- `scripts/stop-demo-services.ps1`
- `scripts/health-check-demo.ps1`
- `scripts/start-stamp-demo.ps1`
- `scripts/stop-stamp-demo.ps1`
- `scripts/import-demo-dataset.py`
- `docker-compose.demo.yml`
- `Dockerfile.backend`

### Demo & Guide
- `backend/tests/fixtures/v1.0_demo_dataset.json`
- `docs/guides/v1.0_DEMO_FLOW.md`
- `docs/guides/v0.13_FINAL_DEMO_FLOW.md`

### Teacher Materials
- `docs/reports/v0.13_TEACHER_READY_SUMMARY.md`
- `docs/reports/v1.0_TEACHER_READY_SUMMARY.md`
- `docs/reports/v1.0_TEACHER_MATERIALS.md`
- `docs/reports/v1.0_TEACHER_ONE_PAGE_SUMMARY.md`
- `docs/reports/v1.0_TEACHER_10MIN_TALK_SCRIPT.md`
- `docs/reports/v1.0_TEACHER_DEMO_SCREENSHOT_LIST.md`
- `docs/reports/v1.0_TEACHER_RISK_BOUNDARY_STATEMENT.md`

### Autopilot
- `docs/reports/v1.0_AUTOPILOT_CHECKLIST.md`
- `docs/reports/v1.0_AUTOPILOT_NIGHT_RUN_REPORT.md`

### Release Docs
- `docs/releases/v0.13_FINAL_RELEASE_SEAL.md`
- `docs/releases/v0.13_TAGS_AND_COMMITS.md`
- `docs/releases/V1_DEMO_FINAL_RELEASE_SEAL.md`
- `docs/releases/V1_DEMO_RELEASE_NOTES.md`
- `docs/releases/V1_DEMO_TAGS_AND_COMMITS.md`
- `docs/guides/V1_DEMO_FINAL_RUNBOOK.md`
