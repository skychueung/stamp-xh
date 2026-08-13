"""GPU Lock Service (v1.5 Wave 3).

Prevents multiple concurrent MD jobs from competing for the same GPU resources.
Uses a simple file-based lock so it works across uvicorn worker processes.
"""

from __future__ import annotations

import logging
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger("stamp")

DEFAULT_LOCK_PATH = Path(tempfile.gettempdir()) / "stamp_gpu.lock"
DEFAULT_LOCK_TIMEOUT_SECONDS = 3600  # 1 hour


def _read_lock_info(lock_path: Path) -> tuple[str | None, float]:
    """Read the current lock holder and timestamp from the lock file."""
    try:
        text = lock_path.read_text(encoding="utf-8").strip()
        parts = text.split(":", 1)
        if len(parts) == 2:
            pid, timestamp_str = parts
            return pid, float(timestamp_str)
    except (OSError, ValueError):
        pass
    return None, 0.0


def acquire_gpu_lock(
    job_id: str,
    lock_path: Path | None = None,
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> bool:
    """Attempt to acquire the GPU lock for a job."""
    path = lock_path or DEFAULT_LOCK_PATH
    now = time.time()

    try:
        if path.exists():
            holder_pid, holder_time = _read_lock_info(path)
            if holder_pid and holder_pid != job_id:
                if now - holder_time < timeout_seconds:
                    logger.warning(
                        "GPU lock held by job %s since %.0f seconds ago. "
                        "Job %s cannot acquire GPU.",
                        holder_pid,
                        now - holder_time,
                        job_id,
                    )
                    return False
                else:
                    logger.warning(
                        "GPU lock held by job %s is stale (%.0f seconds old). "
                        "Force-releasing for job %s.",
                        holder_pid,
                        now - holder_time,
                        job_id,
                    )
            path.write_text(f"{job_id}:{now}", encoding="utf-8")
            logger.info("GPU lock acquired by job %s", job_id)
            return True
        else:
            path.write_text(f"{job_id}:{now}", encoding="utf-8")
            logger.info("GPU lock acquired by job %s", job_id)
            return True
    except OSError as exc:
        logger.error("Failed to acquire GPU lock: %s", exc)
        return False


def release_gpu_lock(
    job_id: str,
    lock_path: Path | None = None,
) -> bool:
    """Release the GPU lock if held by the given job."""
    path = lock_path or DEFAULT_LOCK_PATH
    try:
        if not path.exists():
            return True
        holder_pid, _ = _read_lock_info(path)
        if holder_pid == job_id:
            path.unlink()
            logger.info("GPU lock released by job %s", job_id)
            return True
        logger.warning(
            "Job %s tried to release GPU lock held by %s — ignoring.",
            job_id,
            holder_pid,
        )
        return True
    except OSError as exc:
        logger.error("Failed to release GPU lock: %s", exc)
        return False


@contextmanager
def gpu_lock_context(
    job_id: str,
    lock_path: Path | None = None,
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> Generator[bool, None, None]:
    """Context manager that acquires and releases the GPU lock."""
    acquired = acquire_gpu_lock(job_id, lock_path, timeout_seconds)
    try:
        yield acquired
    finally:
        if acquired:
            release_gpu_lock(job_id, lock_path)


def probe_gpu_lock_status(lock_path: Path | None = None) -> dict:
    """Return the current GPU lock status for display in the probe endpoint."""
    path = lock_path or DEFAULT_LOCK_PATH
    if not path.exists():
        return {
            "locked": False,
            "holder": None,
            "held_since_seconds": None,
        }
    holder_pid, holder_time = _read_lock_info(path)
    now = time.time()
    return {
        "locked": True,
        "holder": holder_pid,
        "held_since_seconds": round(now - holder_time, 1) if holder_time else None,
    }
