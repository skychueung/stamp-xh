# STAMP v1.0 Demo Final Runbook

**For:** Workshop operators, demo presenters, teaching assistants  
**Date:** 2026-05-12  
**Estimated setup time:** 5 minutes  
**Estimated demo time:** 15 minutes

---

## Pre-Demo Checklist

- [ ] Python 3.11+ installed
- [ ] Node.js 18+ installed
- [ ] Git cloned / branch checked out: `v1.0-demo-teacher-ready-release`
- [ ] Backend dependencies installed: `cd backend; pip install -r requirements.txt`
- [ ] Frontend dependencies installed: `npm install`
- [ ] Database initialized: `python -c "from app.database import init_db; init_db()"`
- [ ] Demo dataset imported (optional): `python scripts/import-demo-dataset.py`
- [ ] Ports 8000 and 5173 available

---

## Quick Start (One Command)

```powershell
.\scripts\start-stamp-demo.ps1
```

This opens two PowerShell windows:
1. Backend at http://localhost:8000
2. Frontend at http://localhost:5173

Wait 10 seconds, then open http://localhost:5173 in your browser.

---

## Manual Start (If One-Command Fails)

### Terminal 1 — Backend
```powershell
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Terminal 2 — Frontend
```powershell
npm install
npm run dev
```

---

## Health Check

```powershell
.\scripts\check-all-health.ps1
```

Expected output:
```
✅ Backend
✅ Frontend
✅ Demo dataset
✅ Database
```

---

## Demo Flow

Follow `docs/guides/v1.0_DEMO_FLOW.md` (15 minutes).

**Key teaching moments:**
1. **Epitope Screening:** Show surface exposure score and why it matters.
2. **Peptide Generation:** Highlight the MM-GBSA Readiness Card.
3. **Readiness Card:** Ask audience: "Can we use this ΔG to rank candidates?" (Answer: No, it's pilot data.)
4. **Final Ranking:** Show export buttons and scientific boundary footer.

---

## Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| Backend port 8000 in use | Another uvicorn running | `scripts/stop-demo-services.ps1` then retry |
| Frontend port 5173 in use | Another vite running | `scripts/stop-demo-services.ps1` then retry |
| `ModuleNotFoundError` | Dependencies not installed | `pip install -r requirements.txt` |
| Database locked | Multiple backend instances | Stop all uvicorn processes, restart |
| Blank page | Frontend build error | Check `npm run build` output for TypeScript errors |
| CORS error | Wrong `CORS_ORIGINS` | Edit `.env`, restart backend |

---

## Shutdown

```powershell
.\scripts\stop-demo-services.ps1
```

This safely stops uvicorn and vite without killing other Python processes.

---

## Post-Demo

- [ ] Run `scripts/stop-demo-services.ps1`
- [ ] Collect feedback
- [ ] Save any interesting screenshots to `docs/screenshots/`
- [ ] File issues at GitHub if bugs found

---

## Emergency Contacts

- **Code issues:** File GitHub issue on `stamp-targeted-peptide-platform`
- **Scientific questions:** Refer to `docs/reports/v1.0_TEACHER_RISK_BOUNDARY_STATEMENT.md`
- **Demo script:** `docs/reports/v1.0_TEACHER_10MIN_TALK_SCRIPT.md`
