#!/bin/bash
# STAMPUP dev-copy health check script.

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
LOG_FILE="$DEV_LOG_DIR/stampup_healthcheck.log"
REPORT_FILE="$DEV_REPORT_DIR/stampup_healthcheck_$(date +%Y%m%d_%H%M%S).md"

exec > >(tee -a "$LOG_FILE") 2>&1

echo "=== STAMPUP Health Check $(date '+%Y-%m-%d %H:%M:%S') ==="
echo "host: $(hostname)"
echo "user: $(whoami)"
echo "pwd: $CURRENT_PWD"
echo "symlink: $(readlink -f /home/xh/stamp)"
echo ""
echo "--- FRONTEND ---"
FRONT_CODE=$(curl -I -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_FRONTEND_PORT}/" || echo 000)
echo "frontend / => ${FRONT_CODE}"
FE_PIPELINE_CODE=$(curl -I -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_FRONTEND_PORT}/pipeline" || echo 000)
echo "frontend /pipeline => ${FE_PIPELINE_CODE}"
echo ""
echo "--- BACKEND ---"
BACK_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_BACKEND_PORT}/api/health" || echo 000)
echo "backend /api/health => ${BACK_CODE}"
QUEUE_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_BACKEND_PORT}/api/health/queue" || echo 000)
echo "backend /api/health/queue => ${QUEUE_CODE}"
RES_CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://127.0.0.1:${DEV_BACKEND_PORT}/api/health/resources" || echo 000)
echo "backend /api/health/resources => ${RES_CODE}"
echo ""
echo "--- PORTS ---"
ss -lntp | grep -E "${DEV_BACKEND_PORT}|${DEV_FRONTEND_PORT}" || true

{
  echo "# STAMPUP Healthcheck Report"
  echo ""
  echo "- Time: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- Project: $DEV_PROJECT"
  echo "- Log file: $LOG_FILE"
  echo "- Frontend port: $DEV_FRONTEND_PORT"
  echo "- Backend port: $DEV_BACKEND_PORT"
  echo "- Frontend /: $FRONT_CODE"
  echo "- Frontend /pipeline: $FE_PIPELINE_CODE"
  echo "- Backend /api/health: $BACK_CODE"
  echo "- Backend /api/health/queue: $QUEUE_CODE"
  echo "- Backend /api/health/resources: $RES_CODE"
  echo "- Symlink: $(readlink -f /home/xh/stamp)"
  echo "- Reports dir: $DEV_REPORT_DIR"
} > "$REPORT_FILE"

if [ "$FRONT_CODE" = "200" ] && [ "$FE_PIPELINE_CODE" = "200" ] && [ "$BACK_CODE" = "200" ]; then
  echo "[STAMPUP] Healthcheck PASS"
  exit 0
fi

echo "[STAMPUP] Healthcheck FAIL"
exit 1
