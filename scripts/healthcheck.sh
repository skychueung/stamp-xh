#!/usr/bin/env bash
# STAMP v1.2-lab-production-fast — Health Check Script

echo "[STAMPUP] Historical entry: use scripts/ops/stampup_healthcheck.sh for the STAMPUP dev copy." >&2

BASE_URL="${STAMP_API_URL:-http://localhost:12824/api}"
FAIL=0

check() {
    local name="$1"
    local url="$2"
    local resp
    resp=$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")
    if [ "$resp" = "200" ]; then
        echo "[OK] $name"
    else
        echo "[FAIL] $name (HTTP $resp)"
        FAIL=1
    fi
}

echo "=== STAMP v1.2 Health Check ==="
echo "Base URL: $BASE_URL"

check "Liveness" "$BASE_URL/health"
check "Database" "$BASE_URL/health/db"
check "Storage" "$BASE_URL/health/storage"
check "Queue" "$BASE_URL/health/queue"

echo "================================"
if [ "$FAIL" -eq 0 ]; then
    echo "All checks passed."
    exit 0
else
    echo "Some checks failed."
    exit 1
fi
