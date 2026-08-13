#!/bin/bash
# STAMPUP dev-copy restart script.

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

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$DEV_LOG_DIR/stampup_restart.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_restart_$(date +%Y%m%d_%H%M%S).md"

mkdir -p "$DEV_LOG_DIR" "$DEV_REPORT_DIR" "$DEV_DATA_DIR"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] restart requested"
  bash "$SCRIPT_DIR/stampup_stop.sh"
  sleep 1
  bash "$SCRIPT_DIR/stampup_start_backend.sh"
  sleep 2
  bash "$SCRIPT_DIR/stampup_start_frontend.sh"
  sleep 2
  bash "$SCRIPT_DIR/stampup_healthcheck.sh"
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] restart completed"
} | tee -a "$LOG_FILE"

cat > "$REPORT_FILE" <<EOF
# STAMPUP Restart Report

- Time: $(date '+%Y-%m-%d %H:%M:%S %z')
- Project: $DEV_PROJECT
- Frontend port: $DEV_FRONTEND_PORT
- Backend port: $DEV_BACKEND_PORT
- Log file: $LOG_FILE
- Reports dir: $DEV_REPORT_DIR
EOF

echo "[STAMPUP] Restart report: $REPORT_FILE"
