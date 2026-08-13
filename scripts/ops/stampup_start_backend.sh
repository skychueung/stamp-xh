#!/bin/bash
# STAMPUP dev-copy backend start script.

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

mkdir -p \
  "$DEV_LOG_DIR" \
  "$DEV_REPORT_DIR" \
  "$DEV_DATA_DIR/db" \
  "$DEV_DATA_DIR/artifacts" \
  "$DEV_DATA_DIR/uploads" \
  "$DEV_DATA_DIR/jobs" \
  "$DEV_PROJECT/models_dev"

LOG_FILE="$DEV_LOG_DIR/stampup_backend.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_start_backend_$(date +%Y%m%d_%H%M%S).md"

if ss -lntp | grep -q ":${DEV_BACKEND_PORT} "; then
  echo "[STAMPUP] Refusing to start backend: port ${DEV_BACKEND_PORT} is already in use." | tee -a "$LOG_FILE"
  exit 1
fi

cd "$DEV_PROJECT/backend"
nohup /usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port "$DEV_BACKEND_PORT" \
  >> "$LOG_FILE" 2>&1 &
PID=$!

sleep 2

cat > "$REPORT_FILE" <<EOF
# STAMPUP Backend Start Report

- Time: $(date '+%Y-%m-%d %H:%M:%S %z')
- Project: $DEV_PROJECT
- Backend port: $DEV_BACKEND_PORT
- Log file: $LOG_FILE
- PID: $PID
- Data dir: $DEV_DATA_DIR
- Reports dir: $DEV_REPORT_DIR
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] backend started pid=$PID" | tee -a "$LOG_FILE"
echo "[STAMPUP] Backend start report: $REPORT_FILE"
