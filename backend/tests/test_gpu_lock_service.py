"""Tests for GPU Lock Service (v1.5 Wave 3)."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path


from app.services.gpu_lock_service import (
    acquire_gpu_lock,
    release_gpu_lock,
    gpu_lock_context,
    probe_gpu_lock_status,
)


def test_acquire_and_release_lock():
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_1.lock"
    if lock_path.exists():
        lock_path.unlink()

    acquired = acquire_gpu_lock("job-001", lock_path=lock_path)
    assert acquired is True

    status = probe_gpu_lock_status(lock_path=lock_path)
    assert status["locked"] is True
    assert status["holder"] == "job-001"
    assert status["owner"] == "job-001"
    assert isinstance(status["pid"], int)
    assert status["created_at"].endswith("Z")
    assert status["ttl_seconds"] == 3600

    released = release_gpu_lock("job-001", lock_path=lock_path)
    assert released is True

    status = probe_gpu_lock_status(lock_path=lock_path)
    assert status["locked"] is False

    if lock_path.exists():
        lock_path.unlink()


def test_second_job_cannot_acquire():
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_2.lock"
    if lock_path.exists():
        lock_path.unlink()

    acquired1 = acquire_gpu_lock("job-001", lock_path=lock_path)
    assert acquired1 is True

    acquired2 = acquire_gpu_lock("job-002", lock_path=lock_path)
    assert acquired2 is False

    release_gpu_lock("job-001", lock_path=lock_path)
    if lock_path.exists():
        lock_path.unlink()


def test_stale_lock_force_release():
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_3.lock"
    if lock_path.exists():
        lock_path.unlink()

    old_time = time.time() - 7200
    lock_path.write_text(f"job-old:{old_time}", encoding="utf-8")

    acquired = acquire_gpu_lock("job-new", lock_path=lock_path, timeout_seconds=3600)
    assert acquired is True

    status = probe_gpu_lock_status(lock_path=lock_path)
    assert status["holder"] == "job-new"

    if lock_path.exists():
        lock_path.unlink()


def test_gpu_lock_context():
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_4.lock"
    if lock_path.exists():
        lock_path.unlink()

    with gpu_lock_context("job-ctx", lock_path=lock_path) as acquired:
        assert acquired is True
        status = probe_gpu_lock_status(lock_path=lock_path)
        assert status["locked"] is True

    status = probe_gpu_lock_status(lock_path=lock_path)
    assert status["locked"] is False

    if lock_path.exists():
        lock_path.unlink()


def test_release_wrong_job_is_ignored():
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_5.lock"
    if lock_path.exists():
        lock_path.unlink()

    acquire_gpu_lock("job-a", lock_path=lock_path)
    release_gpu_lock("job-b", lock_path=lock_path)

    status = probe_gpu_lock_status(lock_path=lock_path)
    assert status["locked"] is True
    assert status["holder"] == "job-a"

    release_gpu_lock("job-a", lock_path=lock_path)
    if lock_path.exists():
        lock_path.unlink()
