#!/usr/bin/env bash
# STAMP v1.2-lab-production-fast — Server Deployment Script
# Run on target server (192.168.31.218 or equivalent)

set -euo pipefail

echo "[STAMPUP] Historical deploy entry: use scripts/ops/stampup_* for the STAMPUP dev copy." >&2

if [[ "$(pwd -P)" == "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev" ]]; then
    echo "[STAMPUP] Refusing to run the legacy deployment script from the STAMPUP dev copy." >&2
    exit 1
fi

STAMP_DIR="${STAMP_DIR:-/opt/stamp}"
BACKUP_DIR="${STAMP_DIR}/backups/$(date +%Y%m%d_%H%M%S)"

echo "=== STAMP v1.2 Server Deployment ==="
echo "Target dir: $STAMP_DIR"
echo "Backup dir: $BACKUP_DIR"

# 1. Backup existing data
mkdir -p "$BACKUP_DIR"
if [ -f "$STAMP_DIR/backend/data/stamp_v12.db" ]; then
    cp "$STAMP_DIR/backend/data/stamp_v12.db" "$BACKUP_DIR/"
    echo "[OK] Database backed up"
fi

# 2. Pull latest code (if git repo)
if [ -d "$STAMP_DIR/.git" ]; then
    cd "$STAMP_DIR"
    git fetch origin
    git checkout v1.2-lab-production || true
    git pull origin v1.2-lab-production || echo "[WARN] Git pull failed — using local code"
fi

# 3. Install backend dependencies
cd "$STAMP_DIR/backend"
python -m pip install -r requirements.txt

# 4. Ensure storage directories
mkdir -p data/uploads data/jobs data/results data/archive

# 5. Database init (safe — create_all skips existing tables)
python -c "from app.database import init_db; init_db()"

# 6. Frontend build
cd "$STAMP_DIR"
npm install
npm run build

# 7. Docker compose (optional)
if command -v docker-compose &> /dev/null; then
    docker-compose -f docker-compose.v1.2.yml down || true
    docker-compose -f docker-compose.v1.2.yml up --build -d
    echo "[OK] Docker services started"
else
    echo "[INFO] docker-compose not found — starting services manually"
    # Start backend in background (systemd or screen/tmux recommended)
    # uvicorn app.main:app --host 0.0.0.0 --port 8000 &
fi

# 8. Health check
sleep 3
bash "$STAMP_DIR/scripts/healthcheck.sh"

echo "=== Deployment complete ==="
