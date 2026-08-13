#!/bin/bash
# STAMPUP dev-copy frontend start script.

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

NODE_HOME=/home/xh/kxc/stampup/tools/node-v22.12.0-linux-x64
if [ ! -x "$NODE_HOME/bin/node" ]; then
  echo "[STAMPUP] Node runtime not found: $NODE_HOME/bin/node" >&2
  exit 1
fi

mkdir -p \
  "$DEV_LOG_DIR" \
  "$DEV_REPORT_DIR" \
  "$DEV_DATA_DIR/db" \
  "$DEV_DATA_DIR/artifacts" \
  "$DEV_DATA_DIR/uploads" \
  "$DEV_DATA_DIR/jobs" \
  "$DEV_PROJECT/models_dev"

LOG_FILE="$DEV_LOG_DIR/stampup_frontend.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_start_frontend_$(date +%Y%m%d_%H%M%S).md"

if ss -lntp | grep -q ":${DEV_FRONTEND_PORT} "; then
  echo "[STAMPUP] Refusing to start frontend: port ${DEV_FRONTEND_PORT} is already in use." | tee -a "$LOG_FILE"
  exit 1
fi

cd "$DEV_PROJECT"
PATH="$NODE_HOME/bin:$PATH" nohup "$NODE_HOME/bin/node" "$NODE_HOME/lib/node_modules/npm/bin/npm-cli.js" run dev -- --host 0.0.0.0 \
  >> "$LOG_FILE" 2>&1 &
PID=$!

sleep 3

cat > "$REPORT_FILE" <<EOF
# STAMPUP Frontend Start Report

- Time: $(date '+%Y-%m-%d %H:%M:%S %z')
- Project: $DEV_PROJECT
- Frontend port: $DEV_FRONTEND_PORT
- Log file: $LOG_FILE
- PID: $PID
- Node home: $NODE_HOME
- Reports dir: $DEV_REPORT_DIR
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] frontend started pid=$PID" | tee -a "$LOG_FILE"
echo "[STAMPUP] Frontend start report: $REPORT_FILE"
