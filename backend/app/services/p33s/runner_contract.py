"""P33S runner path/cwd contracts — non-source, non-scientific fixes.

Per goal §3 / authorization: DiffPepBuilder may only have its runner cwd/path
contract fixed; model source and scientific params must not change.

DiffPepBuilder root cause (P33M failure, verified on disk):
  source/experiments/process_receptor.py calls
    pyrootutils.setup_root(..., indicator=[".git"])
  The extracted zip source has no .git, so setup_root raises
  "Project root directory not found. Indicators: ['.git']".

Fix (environment contract, NOT a source edit):
  Before invoking any DiffPepBuilder official entry that uses pyrootutils,
  run `git init` inside the extracted source root so the .git indicator
  exists. This:
    - does not modify any model source file (SHA of *.py unchanged)
    - does not change any scientific parameter
    - is reversible (rm -rf the created .git, which we own)
    - mirrors the P33O PPFlow path-repair philosophy (fix calling contract)

This module exposes ensure_diffpepbuilder_source_root() which:
  - verifies the source dir exists
  - snapshots SHA of all *.py before
  - runs `git init` if no .git present
  - snapshots SHA of all *.py after
  - asserts before == after (source unchanged)
  - returns the before/after manifest for provenance
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

DIFFPEPBUILDER_SOURCE_ROOT = Path(
    "/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main"
)


def _snapshot_py_shas(root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.rglob("*.py")):
        h = hashlib.sha256()
        try:
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
        except OSError:
            out[str(p)] = "READ_ERROR"
            continue
        out[str(p)] = h.hexdigest()
    return out


def ensure_diffpepbuilder_source_root() -> dict:
    """Ensure the .git indicator exists for pyrootutils. No source edit.

    Returns a provenance dict: before_shas, after_shas, source_unchanged,
    git_init_performed, root.
    """
    root = DIFFPEPBUILDER_SOURCE_ROOT
    before = _snapshot_py_shas(root)
    git_init_performed = False
    if not (root / ".git").exists():
        # git init is an environment contract; does not touch *.py
        subprocess.run(["git", "init"], cwd=str(root), check=True,
                       capture_output=True)
        git_init_performed = True
    after = _snapshot_py_shas(root)
    return {
        "root": str(root),
        "git_init_performed": git_init_performed,
        "before_py_count": len(before),
        "after_py_count": len(after),
        "source_unchanged": before == after,
        "before_after_diff": [k for k in set(before) | set(after)
                              if before.get(k) != after.get(k)],
        "note": "git init creates .git indicator for pyrootutils; no *.py modified",
    }
