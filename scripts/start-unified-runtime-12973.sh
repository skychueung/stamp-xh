#!/usr/bin/env bash
set -euo pipefail

ROOT="${STAMP_DEPLOY_ROOT:-/home/xh/kxc/stamp-v3/.goal-worktrees/five-model-unified-runtime}"
RUNTIME="${STAMP_MODEL_RUNTIME_ROOT:-/home/xh/kxc/runtime/five-model-unified}"
RUN="${STAMP_RUN_DIR:-/home/xh/kxc/run/stamp-five-model}"
PYTHON="${STAMP_BACKEND_PYTHON:-/home/xh/kxc/stamp-v3/backend/.venv/bin/python}"
mkdir -p "$RUNTIME" "$RUN"

export STAMP_MODEL_RUNTIME_ROOT="$RUNTIME"
export STAMP_DATABASE_URL="sqlite:///$RUNTIME/stamp.db"
export STAMP_SECRET_KEY="${STAMP_SECRET_KEY:-local-production-change-through-env}"
export STAMP_PEPMLM_DEVICE="${STAMP_PEPMLM_DEVICE:-cuda:1}"
export PYTHONPATH="$ROOT/backend${PYTHONPATH:+:$PYTHONPATH}"

stop_pidfile() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file")"
    if kill -0 "$pid" 2>/dev/null; then kill "$pid"; fi
    for _ in {1..20}; do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
  fi
}

stop_pidfile "$RUN/web.pid"
stop_pidfile "$RUN/pipeline-worker.pid"
stop_pidfile "$RUN/worker.pid"
stop_pidfile "$RUN/backend.pid"

cd "$ROOT"
if [[ ! -d node_modules ]]; then npm ci; fi
npm run build

nohup "$PYTHON" -m uvicorn app.main:app --app-dir "$ROOT/backend" \
  --host 0.0.0.0 --port 12974 >"$RUN/backend.log" 2>&1 &
echo $! >"$RUN/backend.pid"

for _ in {1..60}; do
  curl -fsS http://127.0.0.1:12974/api/health >/dev/null 2>&1 && break
  sleep 1
done

nohup "$PYTHON" -m app.workers.model_worker \
  >"$RUN/worker.log" 2>&1 &
echo $! >"$RUN/worker.pid"

nohup "$PYTHON" -m app.workers.pipeline_worker --loop \
  >"$RUN/pipeline-worker.log" 2>&1 &
echo $! >"$RUN/pipeline-worker.pid"

nohup "$PYTHON" "$ROOT/scripts/unified_web_12973.py" \
  --root "$ROOT/dist" --backend http://127.0.0.1:12974 --port 12973 \
  >"$RUN/web.log" 2>&1 &
echo $! >"$RUN/web.pid"

for _ in {1..60}; do
  curl -fsS http://127.0.0.1:12973/api/health >/dev/null 2>&1 && exit 0
  sleep 1
done
echo "startup health check failed" >&2
exit 1
