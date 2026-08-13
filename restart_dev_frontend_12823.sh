#!/bin/bash
set -euo pipefail
DEV_COPY="/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev"
LOG_DIR="${DEV_COPY}/logs_dev"
LOG_FILE="${LOG_DIR}/frontend_12823.log"
PID_FILE="${LOG_DIR}/frontend_12823.pid"

cd "${DEV_COPY}"
mkdir -p "${LOG_DIR}"

echo "=== Pre-restart state ===" >> "${LOG_FILE}"
date >> "${LOG_FILE}"
ss -lntp | grep 12823 >> "${LOG_FILE}" || true

OLD_PID=$(ss -lntp | grep 12823 | grep -oP "pid=\K[0-9]+" | head -1 || true)
if [ -n "${OLD_PID}" ]; then
    echo "Stopping old frontend pid=${OLD_PID}" >> "${LOG_FILE}"
    kill "${OLD_PID}" || true
    for i in {1..30}; do
        if ! ss -lntp | grep -q 12823; then
            break
        fi
        sleep 1
    done
fi

if [ -f "${LOG_FILE}" ]; then
    mv "${LOG_FILE}" "${LOG_FILE}.prev"
fi

nohup ./node_modules/.bin/vite preview --host 0.0.0.0 --port 12823 > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

NEW_PID=$(cat "${PID_FILE}")
echo "Started new frontend pid=${NEW_PID}" >> "${LOG_FILE}"

for i in {1..30}; do
    if curl -s http://192.168.31.218:12823/ >/dev/null 2>&1; then
        echo "Frontend 12823 healthy"
        exit 0
    fi
    sleep 1
done

echo "Frontend did not become healthy within 30s" >&2
exit 1
