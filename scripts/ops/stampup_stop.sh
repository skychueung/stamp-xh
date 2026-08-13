#!/bin/bash
# STAMPUP dev-copy stop script.

set -euo pipefail

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

for p in "$DEV_FRONTEND_PORT" "$DEV_BACKEND_PORT"; do
  case "$p" in
    8001|8080)
      echo "[STAMPUP] Refusing to run: dev port collision with formal ports." >&2
      exit 1
      ;;
  esac
done

case "$DEV_PROJECT" in
  /home/xh/stamp|/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform|/home/xh)
    echo "[STAMPUP] Refusing to run: unsafe project path '$DEV_PROJECT'." >&2
    exit 1
    ;;
esac

mkdir -p "$DEV_LOG_DIR" "$DEV_REPORT_DIR" "$DEV_DATA_DIR"
LOG_FILE="$DEV_LOG_DIR/stampup_stop.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_stop_$(date +%Y%m%d_%H%M%S).md"

stop_port() {
  local port="$1"
  local label="$2"
  local pids

  case "$port" in
    8001|8080)
      echo "[STAMPUP] Refusing to stop formal port $port." | tee -a "$LOG_FILE"
      exit 1
      ;;
  esac

  pids=$(ss -lntp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | sort -u || true)
  if [ -z "$pids" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $label port $port not running" | tee -a "$LOG_FILE"
    return 0
  fi

  for pid in $pids; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] stopping $label pid=$pid port=$port" | tee -a "$LOG_FILE"
    kill "$pid"
  done
}

stop_port "$DEV_FRONTEND_PORT" "frontend"
stop_port "$DEV_BACKEND_PORT" "backend"

cat > "$REPORT_FILE" <<EOF
# STAMPUP Stop Report

- Time: $(date '+%Y-%m-%d %H:%M:%S %z')
- Project: $DEV_PROJECT
- Frontend port: $DEV_FRONTEND_PORT
- Backend port: $DEV_BACKEND_PORT
- Log file: $LOG_FILE
- Reports dir: $DEV_REPORT_DIR
EOF

echo "[STAMPUP] Stop report: $REPORT_FILE"
