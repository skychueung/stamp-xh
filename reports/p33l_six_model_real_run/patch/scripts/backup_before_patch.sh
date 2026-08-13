#!/usr/bin/env bash
set -euo pipefail

BACKUP_DIR="/home/xh/kxc/stampup/backups/p33l_phase2_$(date +%Y%m%d_%H%M%S)"
PROJ="/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend"

mkdir -p "$BACKUP_DIR"

cp "$PROJ/app/main.py" "$BACKUP_DIR/main.py"

if [ -d "$PROJ/app/services/p33l" ]; then
  cp -r "$PROJ/app/services/p33l" "$BACKUP_DIR/p33l"
fi

if [ -f "$PROJ/app/routers/p33l.py" ]; then
  cp "$PROJ/app/routers/p33l.py" "$BACKUP_DIR/p33l_router.py"
fi

if [ -d "$PROJ/app/services/p33l" ]; then
  find "$PROJ/app/services/p33l" -type f | sort | xargs -r sha256sum > "$BACKUP_DIR/before_p33l_sha256.txt"
fi

sha256sum "$PROJ/app/main.py" > "$BACKUP_DIR/before_main_sha256.txt"

echo "BACKUP_DIR=$BACKUP_DIR"
