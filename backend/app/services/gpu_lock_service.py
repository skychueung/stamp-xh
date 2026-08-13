"""GPU Lock Service (v1.5 Wave 3).

Prevents multiple concurrent MD jobs from competing for the same GPU resources.
Uses a simple file-based lock so it works across uvicorn worker processes.
"""

from __future__ import annotations

import logging
import json
import os
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger("stamp")

DEFAULT_LOCK_PATH = Path(tempfile.gettempdir()) / "stamp_gpu.lock"
DEFAULT_LOCK_TIMEOUT_SECONDS = 3600  # 1 hour


def _read_lock_record(lock_path: Path) -> dict:
    """Read both the v2 JSON lock and the legacy ``owner:timestamp`` format."""
    try:
        text = lock_path.read_text(encoding="utf-8").strip()
        if text.startswith("{"):
            data = json.loads(text)
            created = float(data.get("created_epoch") or 0)
            return {
                "owner": str(data.get("owner") or "") or None,
                "pid": data.get("pid"),
                "created_epoch": created,
                "created_at": data.get("created_at"),
                "ttl_seconds": float(data.get("ttl_seconds") or 0),
            }
        parts = text.split(":", 1)
        if len(parts) == 2:
            owner, timestamp_str = parts
            return {"owner": owner, "pid": None, "created_epoch": float(timestamp_str),
                    "created_at": None, "ttl_seconds": 0}
    except (OSError, ValueError, json.JSONDecodeError):
        pass
    return {"owner": None, "pid": None, "created_epoch": 0.0,
            "created_at": None, "ttl_seconds": 0.0}


def _read_lock_info(lock_path: Path) -> tuple[str | None, float]:
    """Backward-compatible tuple view used by existing callers/tests."""
    record = _read_lock_record(lock_path)
    return record["owner"], record["created_epoch"]


def _record(job_id: str, now: float, ttl_seconds: float) -> bytes:
    return json.dumps({
        "owner": job_id,
        "pid": os.getpid(),
        "created_epoch": now,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "ttl_seconds": ttl_seconds,
    }, separators=(",", ":")).encode("utf-8")


def acquire_gpu_lock(
    job_id: str,
    lock_path: Path | None = None,
    timeout_seconds: float = DEFAULT_LOCK_TIMEOUT_SECONDS,
) -> bool:
    """Attempt to acquire the GPU lock for a job."""
    path = lock_path or DEFAULT_LOCK_PATH
    now = time.time()

    path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(3):
        try:
            fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                os.write(fd, _record(job_id, now, timeout_seconds))
            finally:
                os.close(fd)
            logger.info("GPU lock acquired by job %s", job_id)
            return True
        except FileExistsError:
            record = _read_lock_record(path)
            holder = record["owner"]
            holder_time = float(record["created_epoch"] or 0)
            effective_ttl = float(record["ttl_seconds"] or timeout_seconds)
            if holder == job_id:
                return True
            if holder and now - holder_time < effective_ttl:
                    logger.warning(
                        "GPU lock held by job %s since %.0f seconds ago. "
                        "Job %s cannot acquire GPU.",
                        holder,
                        now - holder_time,
                        job_id,
                    )
                    return False
            logger.warning("Removing stale or malformed GPU lock for job %s", job_id)
            try:
                path.unlink()
            except FileNotFoundError:
                pass
        except OSError as exc:
            logger.error("Failed to acquire GPU lock: %s", exc)
            return False
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
    record = _read_lock_record(path)
    holder_pid, holder_time = record["owner"], record["created_epoch"]
    now = time.time()
    return {
        "locked": True,
        "holder": holder_pid,
        "owner": holder_pid,
        "pid": record.get("pid"),
        "created_at": record.get("created_at"),
        "ttl_seconds": record.get("ttl_seconds"),
        "held_since_seconds": round(now - holder_time, 1) if holder_time else None,
    }
