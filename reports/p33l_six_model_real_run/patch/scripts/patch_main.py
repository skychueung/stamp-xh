#!/usr/bin/env python3
"""Patch backend/app/main.py to include the P33L router."""

import sys
from pathlib import Path

MAIN_PATH = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend/app/main.py")

if not MAIN_PATH.exists():
    print(f"main.py not found at {MAIN_PATH}", file=sys.stderr)
    sys.exit(1)

text = MAIN_PATH.read_text(encoding="utf-8")

# Add import if missing
import_line = "from app.routers import p33l"
if import_line not in text:
    # Insert after the existing from app.routers import block
    marker = "from app.routers import ("
    if marker in text:
        idx = text.find(marker)
        end = text.find(")", idx)
        text = text[:end + 1] + "\n" + import_line + text[end + 1:]
    else:
        # Fallback: insert near model_registry import
        marker = "from app.routers.model_registry import ("
        idx = text.find(marker)
        text = text[:idx] + import_line + "\n" + text[idx:]

# Add router include if missing
include_line = "app.include_router(p33l.router)"
if include_line not in text:
    # Insert before model_registry router include
    marker = "app.include_router(model_registry_router)"
    idx = text.find(marker)
    text = text[:idx] + include_line + "\n    " + text[idx:]

MAIN_PATH.write_text(text, encoding="utf-8")
print("main.py patched successfully")
