"""STAMP Platform — PepMLM Sidecar Adapter Tests (v0.10-P3a).

Tests the HTTP adapter, response normalization, and error handling.
All tests use contract stubs — no real model is loaded.
"""

from __future__ import annotations

import pytest

from app.services.pepmlm_adapter import (
    PepMLMSidecarError,
    call_pepmlm_sidecar,
    check_pepmlm_sidecar_health,
    normalize_pepmlm_response,
)


# ============================================================================
# 1. Response normalization preserves STUB_ONLY markers
# ============================================================================


def test_normalize_pepmlm_response_preserves_stub_markers():
    """Normalization must keep all STUB_ONLY / real_model_loaded markers."""
    raw = {
        "status": "success",
        "mode": "PEPMLM_STUB_ONLY",
        "candidate_count": 3,
        "generated_peptides": [
            {"sequence": "STUBA", "score": 0.1, "rank": 1, "source": "pepmlm_stub", "is_stub": True},
            {"sequence": "STUBB", "score": 0.2, "rank": 2, "source": "pepmlm_stub", "is_stub": True},
        ],
    }
    result = normalize_pepmlm_response(raw, sidecar_url="http://127.0.0.1:5011")

    assert result["job_type"] == "pepmlm_generation"
    assert result["mode"] == "PEPMLM_HTTP_SIDECAR_STUB"
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_STUB_ONLY"
    assert result["real_model_loaded"] is False
    assert result["candidate_count"] == 3
    assert result["sidecar_url"] == "http://127.0.0.1:5011"

    preview = result["generated_peptides_preview"]
    assert len(preview) == 2
    assert preview[0]["is_stub"] is True
    assert preview[0]["source"] == "pepmlm_stub"

    summary = result["raw_result_summary"]
    assert summary["mode"] == "PEPMLM_STUB_ONLY"
    assert summary["real_model_loaded"] is False


def test_normalize_pepmlm_response_empty_candidates():
    """Empty candidate list must be handled gracefully."""
    raw = {
        "status": "success",
        "mode": "PEPMLM_STUB_ONLY",
        "candidate_count": 0,
        "generated_peptides": [],
    }
    result = normalize_pepmlm_response(raw)
    assert result["candidate_count"] == 0
    assert result["generated_peptides_preview"] == []
    assert result["real_model_loaded"] is False


# ============================================================================
# 2. Error formatting
# ============================================================================


def test_pepmlm_sidecar_error_message():
    """PepMLMSidecarError should carry structured message."""
    exc = PepMLMSidecarError("[SIDECAR_UNAVAILABLE] Cannot connect")
    assert "SIDECAR_UNAVAILABLE" in str(exc)


# ============================================================================
# 3. Sidecar unavailable raises correct error type
# ============================================================================


def test_check_pepmlm_sidecar_health_raises_on_unavailable():
    """When sidecar is not running, health check must raise PepMLMSidecarError."""
    with pytest.raises(PepMLMSidecarError) as exc_info:
        check_pepmlm_sidecar_health(base_url="http://127.0.0.1:59999", timeout=1.0)
    assert "SIDECAR_UNAVAILABLE" in str(exc_info.value)


def test_call_pepmlm_sidecar_raises_on_unavailable():
    """When sidecar is not running, generate must raise PepMLMSidecarError."""
    with pytest.raises(PepMLMSidecarError) as exc_info:
        call_pepmlm_sidecar(
            epitope_sequence="MKKTA",
            base_url="http://127.0.0.1:59999",
            timeout=1.0,
        )
    assert "SIDECAR_UNAVAILABLE" in str(exc_info.value)


# ============================================================================
# 4. REAL_MODEL response normalization
# ============================================================================


def test_normalize_pepmlm_response_real_model_markers():
    """Normalization must detect REAL_MODEL and set correct markers."""
    raw = {
        "status": "success",
        "mode": "PEPMLM_REAL_MODEL",
        "real_model_loaded": True,
        "candidate_count": 3,
        "generated_peptides": [
            {"sequence": "KTKAKAALAKAS", "score": 0.1225, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 8.16, "charge": 4.0, "pi": 8.6},
        ],
        "model_info": {"model_name": "TianlaiChen/PepMLM-650M"},
    }
    result = normalize_pepmlm_response(raw, sidecar_url="http://127.0.0.1:5011")

    assert result["job_type"] == "pepmlm_generation"
    assert result["mode"] == "PEPMLM_HTTP_SIDECAR_REAL"
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"
    assert result["real_model_loaded"] is True
    assert result["candidate_count"] == 3

    preview = result["generated_peptides_preview"]
    assert len(preview) == 1
    assert preview[0]["is_stub"] is False
    assert preview[0]["source"] == "pepmlm_650m_real"
    assert preview[0]["ppl"] == 8.16
    assert preview[0]["charge"] == 4.0

    summary = result["raw_result_summary"]
    assert summary["mode"] == "PEPMLM_REAL_MODEL"
    assert summary["real_model_loaded"] is True
    assert summary["model_name"] == "TianlaiChen/PepMLM-650M"


def test_normalize_pepmlm_response_stub_markers_preserved():
    """STUB_ONLY responses must still be normalized correctly."""
    raw = {
        "status": "success",
        "mode": "PEPMLM_STUB_ONLY",
        "real_model_loaded": False,
        "candidate_count": 2,
        "generated_peptides": [
            {"sequence": "STUBA", "score": 0.1, "rank": 1, "source": "pepmlm_stub", "is_stub": True},
        ],
    }
    result = normalize_pepmlm_response(raw)
    assert result["mode"] == "PEPMLM_HTTP_SIDECAR_STUB"
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_STUB_ONLY"
    assert result["real_model_loaded"] is False



# ============================================================================
# P5A: unified Model Registry PepMLM adapter tests
# ============================================================================


from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter


def test_pepmlm_adapter_probe_is_read_only():
    """PepMLM probe must not execute the model or generate candidates."""
    adapter = PepMLMAdapter()
    result = adapter.probe()
    assert result.model_id == "pepmlm"
    assert result.status in ("PROBED", "DEGRADED", "UNAVAILABLE")
    assert result.safety_flags.executed_model is False
    assert result.safety_flags.generated_candidates is False
    assert result.safety_flags.computational_prediction_only is True
    assert result.detail["real_run_enabled"] is False


def test_pepmlm_adapter_dry_run_returns_command_preview():
    """PepMLM dry-run must plan without execution and return a command preview."""
    adapter = PepMLMAdapter()
    payload = ModelDryRunPayload(target_sequence=">target\nMKTAYIAKQRQIK", peptide_length=10)
    result = adapter.dry_run(payload)
    assert result.model_id == "pepmlm"
    assert result.status in ("READY", "BLOCKED")
    assert result.safety_flags.executed_model is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
    if result.status == "READY":
        assert result.command_preview
        assert "pepmlm_infer.py" in " ".join(result.command_preview)


def test_pepmlm_adapter_submit_blocked_by_default():
    """PepMLM real submission must be blocked unless PEPMLM_REAL_RUN_ENABLED is set."""
    adapter = PepMLMAdapter()
    payload = ModelDryRunPayload(target_sequence=">target\nMKTAYIAKQRQIK", peptide_length=10)
    result = adapter.submit(payload)
    assert result.status == "BLOCKED"
    assert result.safety_flags.executed_model is False
    assert result.safety_flags.generated_candidates is False
