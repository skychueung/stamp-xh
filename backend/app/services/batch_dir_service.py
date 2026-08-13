"""Batch computation directory structure service.

v1.4-batch-computation

Generates standardized directory trees for batch jobs:

data/batch_jobs/{batch_id}/
  inputs/
  colabfold/
  foldx/
  mmgbsa/
  logs/
  reports/
  artifacts/

Each item gets a sub-directory under the stage directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.core.config import settings

BATCH_JOBS_BASE = settings.stamp_batch_jobs_dir


def ensure_batch_dir(batch_id: str) -> str:
    """Create and return the root directory for a batch computation."""
    root = Path(BATCH_JOBS_BASE) / batch_id
    for sub in ("inputs", "colabfold", "foldx", "mmgbsa", "logs", "reports", "artifacts"):
        (root / sub).mkdir(parents=True, exist_ok=True)
    return str(root.resolve())


def ensure_item_dir(batch_id: str, item_id: str, job_type: str) -> str:
    """Create and return the directory for a specific batch item.

    Args:
        batch_id: Batch UUID.
        item_id: Item UUID.
        job_type: COLABFOLD / FOLDX / MMGBSA — determines sub-directory.

    Returns:
        Absolute path to the item directory.
    """
    root = Path(BATCH_JOBS_BASE) / batch_id
    stage_dir = root / job_type.lower()
    stage_dir.mkdir(parents=True, exist_ok=True)
    item_dir = stage_dir / item_id
    item_dir.mkdir(parents=True, exist_ok=True)
    return str(item_dir.resolve())


def get_item_log_path(batch_id: str, item_id: str, job_type: str) -> str:
    """Return the legacy flat log file path for a batch item."""
    root = Path(BATCH_JOBS_BASE) / batch_id
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return str((log_dir / f"{item_id}_{job_type.lower()}.log").resolve())


def get_item_logs_dir(batch_id: str, item_id: str, job_type: str) -> str:
    """Return the structured logs directory for a batch item.

    Path: data/batch_jobs/{batch_id}/{job_type}/{item_id}/logs/
    """
    root = Path(BATCH_JOBS_BASE) / batch_id
    logs_dir = root / job_type.lower() / item_id / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return str(logs_dir.resolve())


def get_batch_report_dir(batch_id: str) -> str:
    """Return the reports directory for a batch."""
    root = Path(BATCH_JOBS_BASE) / batch_id / "reports"
    root.mkdir(parents=True, exist_ok=True)
    return str(root.resolve())
