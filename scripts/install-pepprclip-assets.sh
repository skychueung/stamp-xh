#!/usr/bin/env bash
set -euo pipefail

# Installs the upstream checkpoint required by the production PepPrCLIP runner.
# Use an already staged file or HF_TOKEN; secret values are never printed.
REPO_ID="${STAMP_PEPPRCLIP_REPO_ID:-ubiquitx/pepprclip}"
ROOT="${STAMP_PEPPRCLIP_ROOT:-/home/xh/kxc/stampup/models_dev/pepprclip}"
CHECKPOINT_NAME="canonical_miniclip_4-22-23.ckpt"
CANDIDATES_NAME="candidate_peptides_lengths_5_to_30_25Keach.pkl"

if [[ -z "${STAMP_PEPPRCLIP_CHECKPOINT_SOURCE:-}" && -z "${HF_TOKEN:-}" ]]; then
  echo "Set STAMP_PEPPRCLIP_CHECKPOINT_SOURCE or HF_TOKEN" >&2
  exit 2
fi
mkdir -p "$ROOT/weights"

python_bin="${STAMP_ASSET_PYTHON:-python3}"
"$python_bin" - "$REPO_ID" "$ROOT" "${HF_TOKEN:-}" <<'PY'
import hashlib
import os
import shutil
import sys
from pathlib import Path

repo_id, root_raw, token = sys.argv[1:]
root = Path(root_raw)
assets = {"canonical_miniclip_4-22-23.ckpt":
          (root / "weights" / "canonical_miniclip_4-22-23.ckpt", 24_610_559)}
if os.environ.get("STAMP_PEPPRCLIP_DOWNLOAD_LIBRARY") == "1":
    assets["candidate_peptides_lengths_5_to_30_25Keach.pkl"] = (
        root / "candidate_peptides_lengths_5_to_30_25Keach.pkl", 3_528_976_415
    )
for filename, (destination, expected_size) in assets.items():
    source_env = ("STAMP_PEPPRCLIP_CHECKPOINT_SOURCE" if filename.endswith(".ckpt")
                  else "STAMP_PEPPRCLIP_LIBRARY_SOURCE")
    staged = os.environ.get(source_env)
    if staged:
        cached = Path(staged).expanduser().resolve()
        if not cached.is_file():
            raise SystemExit(f"staged source missing for {filename}: {cached}")
    else:
        from huggingface_hub import hf_hub_download
        cached = Path(hf_hub_download(repo_id=repo_id, filename=filename, token=token))
    if cached.stat().st_size != expected_size:
        raise SystemExit(f"size mismatch for {filename}: {cached.stat().st_size} != {expected_size}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    shutil.copyfile(cached, temporary)
    os.replace(temporary, destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(f"installed {filename} size={expected_size} sha256={digest}")
PY

echo "PepPrCLIP assets installed under $ROOT"
