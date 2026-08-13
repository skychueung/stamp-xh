# STAMP v1.0 Demo Release Notes

**Version:** v1.0.0  
**Date:** 2026-05-12  
**Branch:** `v1.0-demo-teacher-ready-release`

---

## What's New

### For Teachers and Demonstrators

- **One-command demo startup:** `scripts/start-stamp-demo.ps1` launches backend + frontend.
- **Health check:** `scripts/check-all-health.ps1` verifies backend, frontend, database, and demo data.
- **Safe shutdown:** `scripts/stop-demo-services.ps1` stops only STAMP processes (no `taskkill` all Python).
- **Complete teacher suite:** One-page summary, 10-minute talk script, screenshot list, risk statement.
- **15-minute demo flow:** Step-by-step guide from project creation to report export.

### For Developers

- **MMPBSA parser:** Reads `FINAL_RESULTS_MMPBSA.dat` into structured JSON.
- **Persistence guard:** Enforces production criteria (trajectory, frames, convergence) before DB writes.
- **Frontend Readiness Card:** Displays pilot/production status with scientific boundary banners.
- **Demo dataset importer:** `scripts/import-demo-dataset.py` loads synthetic fixtures into SQLite.

### For Deployers

- **PowerShell startup scripts:** Backend, frontend, and orchestrated start.
- **Deployment guide:** Local development, production checklist, troubleshooting.
- **Optional Docker:** `docker-compose.demo.yml` and `Dockerfile.backend` for containerization.

---

## Bug Fixes and Improvements

- None — v1.0 is a documentation and packaging release on top of v0.13.

---

## Breaking Changes

- None — v1.0 is backward-compatible with v0.11 and v0.13 APIs.

---

## Deprecations

- None.

---

## Security Notes

- No API keys are present in source code.
- `.env.example` uses placeholder values.
- Database file (`stamp_p5_lite.db`) is `.gitignore`d.

---

## Upgrade Path

From v0.11 or v0.13:
```bash
git fetch origin
git checkout v1.0-demo-teacher-ready-release
# Pull latest if needed
git pull origin v1.0-demo-teacher-ready-release
```

---

## Download

```bash
git clone --branch v1.0-demo-teacher-ready-release https://github.com/skychueung/stamp-targeted-peptide-platform.git
cd stamp-targeted-peptide-platform
git checkout v1.0.0
```

---

## Support

- **Demo flow:** `docs/guides/v1.0_DEMO_FLOW.md`
- **Deployment:** `docs/deployment/v1.0-DEPLOYMENT_GUIDE.md`
- **Teacher materials:** `docs/reports/v1.0_TEACHER_MATERIALS.md`
- **Release seal:** `docs/releases/V1_DEMO_FINAL_RELEASE_SEAL.md`
