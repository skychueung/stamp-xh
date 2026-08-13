"""Runner Logs Router — Unified log center for STAMP compute runners.

v1.5-md-computation-pilot

Endpoints:
    GET /api/v1/runner-logs/{batch_id}/{item_id}
        Query: ?full=true  → return full stdout/stderr instead of tail
        Returns metadata + stdout/stderr content

    GET /api/v1/runner-logs/{batch_id}/{item_id}/download
        Download all log files as a ZIP archive.

Security:
    - No API tokens or secrets are returned.
    - Only file contents from the canonical log directory are served.
"""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.batch_computations import get_batch_computation
from app.models.orm import BatchComputationItem
from app.services.runner_logger import (
    get_log_metadata,
    read_log,
    read_log_tail,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/runner-logs", tags=["Runner Logs"])

DEFAULT_TAIL_LINES = 200


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RunnerLogResponse(BaseModel):
    batch_id: str
    item_id: str
    job_type: str
    exists: bool
    command: Optional[str]
    returncode: Optional[str]
    started_at: Optional[str]
    finished_at: Optional[str]
    stdout_exists: bool
    stderr_exists: bool
    stdout_size: int
    stderr_size: int
    stdout: str
    stderr: str
    is_tail: bool


class RunnerLogDownloadResponse(BaseModel):
    download_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_log_dir(batch_id: str, item_id: str, job_type: str) -> Path:
    """Resolve the canonical log directory path."""
    from app.services.batch_dir_service import BATCH_JOBS_BASE
    return Path(BATCH_JOBS_BASE) / batch_id / job_type.lower() / item_id / "logs"


def _get_item_job_type(db: Session, batch_id: str, item_id: str) -> str:
    """Fetch the job_type for a batch item, validating existence."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    item = (
        db.query(BatchComputationItem)
        .filter(
            BatchComputationItem.id == item_id,
            BatchComputationItem.batch_id == batch_id,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Item not found in batch")
    return item.job_type


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/{batch_id}/{item_id}", response_model=RunnerLogResponse)
def get_runner_logs(
    batch_id: str,
    item_id: str,
    full: bool = Query(False, description="Return full log content instead of last 200 lines"),
    db: Session = Depends(get_db),
):
    """Get runner logs for a batch item.

    By default returns the last 200 lines of stdout/stderr.
    Pass ?full=true to retrieve the entire file contents.
    """
    job_type = _get_item_job_type(db, batch_id, item_id)
    log_dir = _resolve_log_dir(batch_id, item_id, job_type)
    meta = get_log_metadata(str(log_dir))

    stdout_path = log_dir / "stdout.log"
    stderr_path = log_dir / "stderr.log"

    if full:
        stdout = read_log(str(stdout_path))
        stderr = read_log(str(stderr_path))
        is_tail = False
    else:
        stdout = read_log_tail(str(stdout_path), n=DEFAULT_TAIL_LINES)
        stderr = read_log_tail(str(stderr_path), n=DEFAULT_TAIL_LINES)
        is_tail = True

    return RunnerLogResponse(
        batch_id=batch_id,
        item_id=item_id,
        job_type=job_type,
        exists=meta.exists,
        command=meta._read_text("command.txt"),
        returncode=meta._read_text("returncode.txt"),
        started_at=meta._read_text("started_at"),
        finished_at=meta._read_text("finished_at"),
        stdout_exists=meta.to_dict()["stdout_exists"],
        stderr_exists=meta.to_dict()["stderr_exists"],
        stdout_size=meta.to_dict()["stdout_size"],
        stderr_size=meta.to_dict()["stderr_size"],
        stdout=stdout,
        stderr=stderr,
        is_tail=is_tail,
    )


@router.get("/{batch_id}/{item_id}/download")
def download_runner_logs(
    batch_id: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """Download all log files for a batch item as a ZIP archive."""
    job_type = _get_item_job_type(db, batch_id, item_id)
    log_dir = _resolve_log_dir(batch_id, item_id, job_type)

    if not log_dir.exists():
        raise HTTPException(status_code=404, detail="Log directory not found")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(log_dir.iterdir()):
            if f.is_file():
                zf.write(f, f.name)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=runner_logs_{batch_id}_{item_id}.zip"
        },
    )
