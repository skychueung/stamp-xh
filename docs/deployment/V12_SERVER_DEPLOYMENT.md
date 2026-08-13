# STAMP v1.2 Server Deployment Guide

## Prerequisites

- Linux server with Docker + docker-compose
- Python 3.11+ (for native deployment)
- Node.js 20+ (for frontend build)
- SSH access to `192.168.31.218` (heavy compute server)

## Quick Start (Docker)

```bash
# 1. Clone and checkout
git clone https://github.com/skychueung/stamp-targeted-peptide-platform.git
cd stamp-targeted-peptide-platform
git checkout v1.2-lab-production

# 2. Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# 3. Deploy
docker-compose -f docker-compose.v1.2.yml up --build -d

# 4. Verify
bash scripts/healthcheck.sh
```

## Native Deployment

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (separate terminal)
cd ..
npm install
npm run build
# Serve dist/ via nginx or python -m http.server 5173
```

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Liveness |
| `GET /api/health/db` | SQLite connectivity |
| `GET /api/health/storage` | Uploads/jobs/results/archive dirs |
| `GET /api/health/queue` | Job breakdown by status |

## Rollback

Database backups are auto-created by `deploy_server.sh` in `/opt/stamp/backups/`.

```bash
# Restore from backup
cp /opt/stamp/backups/YYYYMMDD_HHMMSS/stamp_v12.db /opt/stamp/backend/data/stamp_v12.db
```
