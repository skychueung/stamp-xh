#!/bin/bash
# STAMPUP dev-copy status script.

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
LOG_FILE="$DEV_LOG_DIR/stampup_status.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_status_$(date +%Y%m%d_%H%M%S).md"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "====== STAMPUP STATUS $(date '+%Y-%m-%d %H:%M:%S') ======"
echo "host: $(hostname)"
echo "user: $(whoami)"
echo "pwd: $CURRENT_PWD"
echo "symlink: $(readlink -f /home/xh/stamp)"
echo ""
echo "--- HTTP ---"
FRONT_CODE=$(curl -I -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_FRONTEND_PORT}/" || echo 000)
BACK_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_BACKEND_PORT}/api/health" || echo 000)
echo "frontend / => ${FRONT_CODE}"
echo "backend /api/health => ${BACK_CODE}"
echo ""
echo "--- PROCESSES ---"
ss -lntp | grep -E "${DEV_BACKEND_PORT}|${DEV_FRONTEND_PORT}" || true
echo ""
echo "--- DIRECTORIES ---"
ls -ld "$DEV_LOG_DIR" "$DEV_REPORT_DIR" "$DEV_DATA_DIR"
echo ""
echo "--- RECENT BACKEND LOG ---"
tail -n 10 "$DEV_LOG_DIR/backend.log" 2>/dev/null || echo "  (no backend.log yet)"
echo ""
echo "--- RECENT FRONTEND LOG ---"
tail -n 10 "$DEV_LOG_DIR/frontend.log" 2>/dev/null || echo "  (no frontend.log yet)"

cat > "$REPORT_FILE" <<EOF
# STAMPUP Status Report

- Time: $(date '+%Y-%m-%d %H:%M:%S %z')
- Project: $DEV_PROJECT
- Frontend port: $DEV_FRONTEND_PORT
- Backend port: $DEV_BACKEND_PORT
- Frontend code: $FRONT_CODE
- Backend code: $BACK_CODE
- Log file: $LOG_FILE
- Reports dir: $DEV_REPORT_DIR
EOF

echo "[STAMPUP] Status report: $REPORT_FILE"
