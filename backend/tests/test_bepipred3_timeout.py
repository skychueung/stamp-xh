"""STAMP Platform — BepiPred3 Dynamic Timeout Policy Tests (v0.10-P2c).

Tests calculate_bepipred3_timeout and timeout error messages.
"""

from __future__ import annotations

import pytest

from app.services.bepipred3_adapter import (
    BepiPred3SidecarError,
    calculate_bepipred3_timeout,
    call_bepipred3_sidecar,
    MAX_TIMEOUT_SECONDS,
)


# ============================================================================
# 1. calculate_bepipred3_timeout
# ============================================================================


def test_short_sequence_timeout_60():
    """Sequences <= 100 aa should get 60s timeout."""
    assert calculate_bepipred3_timeout(10) == 60.0
    assert calculate_bepipred3_timeout(50) == 60.0
    assert calculate_bepipred3_timeout(100) == 60.0


def test_medium_sequence_timeout_180():
    """Sequences 101–500 aa should get 180s timeout."""
    assert calculate_bepipred3_timeout(101) == 180.0
    assert calculate_bepipred3_timeout(250) == 180.0
    assert calculate_bepipred3_timeout(500) == 180.0


def test_long_sequence_timeout_300():
    """Sequences > 500 aa should get 300s timeout."""
    assert calculate_bepipred3_timeout(501) == 300.0
    assert calculate_bepipred3_timeout(1000) == 300.0


def test_override_timeout_used():
    """Caller override should take precedence over length-based default."""
    assert calculate_bepipred3_timeout(50, override_timeout=120.0) == 120.0
    assert calculate_bepipred3_timeout(1000, override_timeout=90.0) == 90.0


def test_override_timeout_clamped_to_max():
    """Override timeout must not exceed MAX_TIMEOUT_SECONDS."""
    huge = MAX_TIMEOUT_SECONDS + 100
    assert calculate_bepipred3_timeout(50, override_timeout=huge) == MAX_TIMEOUT_SECONDS
    assert calculate_bepipred3_timeout(1000, override_timeout=huge) == MAX_TIMEOUT_SECONDS


# ============================================================================
# 2. Timeout error message clarity
# ============================================================================


def test_timeout_error_message_contains_sequence_length(monkeypatch):
    """When sidecar times out, error message must mention sequence length
    and suggest CPU/GPU context."""

    def _mock_post(url, json, timeout):
        import httpx
        raise httpx.TimeoutException("Request timed out")

    monkeypatch.setattr("app.services.bepipred3_adapter.httpx.post", _mock_post)

    seq = "A" * 250
    with pytest.raises(BepiPred3SidecarError) as exc_info:
        call_bepipred3_sidecar(sequence=seq, timeout=None)

    msg = str(exc_info.value)
    assert "250" in msg, f"Expected sequence length 250 in error message, got: {msg}"
    assert "CPU" in msg or "gpu" in msg.lower(), f"Expected CPU/GPU hint in error message, got: {msg}"


# ============================================================================
# 3. Parameters dict override
# ============================================================================


def test_parameters_timeout_override(monkeypatch):
    """input_json.parameters.timeout should override the computed timeout."""
    captured_timeouts = []

    def _mock_post(url, json, timeout):
        captured_timeouts.append(timeout)
        import httpx
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("app.services.bepipred3_adapter.httpx.post", _mock_post)

    seq = "A" * 50
    with pytest.raises(BepiPred3SidecarError):
        call_bepipred3_sidecar(
            sequence=seq,
            timeout=None,
            parameters={"timeout": 999.0},
        )

    assert captured_timeouts[0] == MAX_TIMEOUT_SECONDS  # clamped

    captured_timeouts.clear()
    with pytest.raises(BepiPred3SidecarError):
        call_bepipred3_sidecar(
            sequence=seq,
            timeout=None,
            parameters={"timeout": 45.0},
        )

    assert captured_timeouts[0] == 45.0
