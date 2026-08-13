#!/bin/bash
# Start STAMP frontend dev server for the Targeted Peptide Design dev copy.

set -euo pipefail

echo "[STAMPUP] Historical entry: use scripts/ops/stampup_start_frontend.sh for the STAMPUP dev copy." >&2

PROJECT_DIR=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
NODE_HOME=/home/xh/kxc/stampup/tools/node-v22.12.0-linux-x64
LOG_DIR="${PROJECT_DIR}/logs_dev"

mkdir -p "$LOG_DIR"
cd "$PROJECT_DIR"

PATH="$NODE_HOME/bin:$PATH" nohup "$NODE_HOME/bin/node" "$NODE_HOME/lib/node_modules/npm/bin/npm-cli.js" run dev -- --host 0.0.0.0 \
  >> "${LOG_DIR}/frontend.log" 2>&1 &
echo "[$(date '+%Y-%m-%d %H:%M:%S')] frontend started pid=$!"
