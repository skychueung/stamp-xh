#!/bin/bash
# STAMP one-shot status check

echo "[STAMPUP] Historical entry: use scripts/ops/stampup_status.sh for the STAMPUP dev copy." >&2

echo "====== STAMP STATUS $(date '+%Y-%m-%d %H:%M:%S') ======"
echo "host: $(hostname)  user: $(whoami)"
echo ""

PROJECT_DIR=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
LOG_DIR="${PROJECT_DIR}/logs_dev"

check_http() {
    local label=$1 url=$2
    local code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null)
    if [ "$code" = "200" ]; then
        echo "  ✓ $label → $code"
    else
        echo "  ✗ $label → ${code:-timeout}"
    fi
}

echo "--- HTTP ---"
check_http "frontend /"         http://127.0.0.1:12823/
check_http "frontend /pipeline" http://127.0.0.1:12823/pipeline
check_http "backend /health"    http://127.0.0.1:12824/api/health
check_http "queue health"       http://127.0.0.1:12824/api/health/queue
check_http "resources health"   http://127.0.0.1:12824/api/health/resources

echo ""
echo "--- BACKEND PROCESS ---"
if pgrep -f 'uvicorn app.main:app --host 0.0.0.0 --port 12824' > /dev/null; then
    echo "  ✓ uvicorn running (pid=$(pgrep -f 'uvicorn app.main:app --host 0.0.0.0 --port 12824'))"
else
    echo "  ✗ uvicorn NOT running"
fi

echo ""
echo "--- FRONTEND PROCESS ---"
if pgrep -f 'vite.*12823' > /dev/null; then
    echo "  ✓ vite running (pid=$(pgrep -f 'vite.*12823'))"
else
    echo "  ✗ vite NOT running"
fi

echo ""
echo "--- DISK ---"
df -h /home/xh/kxc/stampup | tail -1

echo ""
echo "--- RECENT WATCHDOG LOG (last 10) ---"
tail -n 10 "${LOG_DIR}/stamp_watchdog.log" 2>/dev/null || echo "  (no log yet)"
