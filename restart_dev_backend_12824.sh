#!/bin/bash
# Safe restart of dev backend 12824
set -euo pipefail

DEV_COPY="/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev"
LOG_DIR="${DEV_COPY}/logs_dev"
LOG_FILE="${LOG_DIR}/backend_12824.log"
PID_FILE="${LOG_DIR}/backend_12824.pid"

cd "${DEV_COPY}/backend"

# Record pre-restart state
echo "=== Pre-restart state ===" >> "${LOG_FILE}"
date >> "${LOG_FILE}"
ss -lntp | grep 12824 >> "${LOG_FILE}" || true

# Find existing pid
OLD_PID=$(ss -lntp | grep 12824 | grep -oP 'pid=\K[0-9]+' | head -1 || true)
if [ -n "${OLD_PID}" ]; then
    echo "Stopping old backend pid=${OLD_PID}" >> "${LOG_FILE}"
    kill "${OLD_PID}" || true
    # Wait for port release
    for i in {1..30}; do
        if ! ss -lntp | grep -q 12824; then
            break
        fi
        sleep 1
    done
fi

# Rotate log
if [ -f "${LOG_FILE}" ]; then
    mv "${LOG_FILE}" "${LOG_FILE}.prev"
fi

# Start new backend
nohup ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12824 > "${LOG_FILE}" 2>&1 &
echo $! > "${PID_FILE}"

NEW_PID=$(cat "${PID_FILE}")
echo "Started new backend pid=${NEW_PID}" >> "${LOG_FILE}"

# Wait for startup
for i in {1..30}; do
    if curl -s http://192.168.31.218:12824/api/health >/dev/null 2>&1; then
        echo "Backend 12824 healthy"
        exit 0
    fi
    sleep 1
done

echo "Backend did not become healthy within 30s" >&2
exit 1
