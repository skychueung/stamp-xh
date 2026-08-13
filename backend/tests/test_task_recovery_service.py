"""Tests for Task Recovery Service (v1.5 Wave 3)."""

from __future__ import annotations

import pytest

from app.services.task_recovery_service import (
    _is_recoverable,
    _next_retry_at,
    attempt_job_recovery,
    RECOVERABLE_ERRORS,
    NON_RECOVERABLE_ERRORS,
)


def test_recoverable_errors():
    for code in RECOVERABLE_ERRORS:
        assert _is_recoverable(code) is True


def test_non_recoverable_errors():
    for code in NON_RECOVERABLE_ERRORS:
        assert _is_recoverable(code) is False


def test_is_recoverable_none():
    assert _is_recoverable(None) is True


def test_next_retry_at_increases():
    t0 = _next_retry_at(0)
    t1 = _next_retry_at(1)
    t2 = _next_retry_at(2)
    assert t1 > t0
    assert t2 > t1


def test_attempt_recovery_skips_non_blocked():
    from unittest.mock import MagicMock
    job = MagicMock()
    job.status = "SUCCEEDED"
    job.error_json = None
    result = attempt_job_recovery(None, job)
    assert result["status"] == "SKIPPED"


def test_attempt_recovery_gives_up_on_non_recoverable():
    from unittest.mock import MagicMock
    job = MagicMock()
    job.status = "BLOCKED"
    job.error_json = {"error_code": "WRAPPER_NOT_READY"}
    job.job_type = "production_md"
    result = attempt_job_recovery(None, job)
    assert result["status"] == "GIVEN_UP"
