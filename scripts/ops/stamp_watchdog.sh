#!/bin/bash
# STAMPUP watchdog — checks backend + frontend, restarts if unhealthy

set -euo pipefail

echo "[STAMPUP] Historical entry: prefer scripts/ops/stampup_* for the STAMPUP dev copy." >&2

STAMPUP_ROOT=/home/xh/kxc/stampup
DEV_PROJECT=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
DEV_FRONTEND_PORT=12823
DEV_BACKEND_PORT=12824
DEV_LOG_DIR=$DEV_PROJECT/logs_dev
DEV_REPORT_DIR=$DEV_PROJECT/reports
DEV_DATA_DIR=$DEV_PROJECT/data_dev

CURRENT_PWD="$(pwd -P)"
if [ "$CURRENT_PWD" != "$DEV_PROJECT" ]; then
  echo "[STAMPUP] Refusing to run from '$CURRENT_PWD'. Use '$DEV_PROJECT'." >&2
  exit 1
fi

BACKEND_URL=http://127.0.0.1:12824/api/health
FRONTEND_URL=http://127.0.0.1:12823/pipeline
BACKEND_START="${DEV_PROJECT}/scripts/ops/stampup_start_backend.sh"
FRONTEND_START="${DEV_PROJECT}/scripts/ops/stampup_start_frontend.sh"
MAX_RESTARTS=3
COOLDOWN_FILE="${DEV_LOG_DIR}/stamp_watchdog_cooldown"
LOG="${DEV_LOG_DIR}/stamp_watchdog.log"

mkdir -p "$DEV_LOG_DIR" "$DEV_REPORT_DIR" "$DEV_DATA_DIR"

TS=$(date '+%Y-%m-%d %H:%M:%S')

# Cooldown: skip if restarted too many times in last 10 min
if [ -f "$COOLDOWN_FILE" ]; then
    LAST=$(cat "$COOLDOWN_FILE")
    NOW=$(date +%s)
    COUNT=$(echo "$LAST" | awk -v now="$NOW" '{if(now-$2<600) print $1}')
    if [ "${COUNT:-0}" -ge "$MAX_RESTARTS" ]; then
        echo "[$TS] COOLDOWN active (${COUNT} restarts in 10min), skipping" >> "$LOG"
        exit 0
    fi
fi

# Check backend
BE_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$BACKEND_URL" 2>/dev/null)
if [ "$BE_CODE" = "200" ]; then
    BE_STATUS="healthy"
    BE_ACTION="none"
else
    BE_STATUS="unhealthy(${BE_CODE})"
    # Restart: kill old uvicorn, start new
    pkill -f 'uvicorn app.main:app --host 0.0.0.0 --port 12824' 2>/dev/null
    sleep 2
    bash "$BACKEND_START" >> "$LOG" 2>&1
    BE_ACTION="restarted"
    echo "$(( ${COUNT:-0} + 1 )) $(date +%s)" > "$COOLDOWN_FILE"
fi

# Check frontend
FE_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "$FRONTEND_URL" 2>/dev/null)
if [ "$FE_CODE" = "200" ]; then
    FE_STATUS="healthy"
    FE_ACTION="none"
else
    FE_STATUS="unhealthy(${FE_CODE})"
    bash "$FRONTEND_START" >> "$LOG" 2>&1
    FE_ACTION="restarted"
    echo "$(( ${COUNT:-0} + 1 )) $(date +%s)" > "$COOLDOWN_FILE"
fi

echo "[$TS] backend=$BE_STATUS action=$BE_ACTION | frontend=$FE_STATUS action=$FE_ACTION" >> "$LOG"
