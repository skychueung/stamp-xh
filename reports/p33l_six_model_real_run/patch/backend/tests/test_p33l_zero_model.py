"""Zero-model tests for P33L Phase 2/3.

These tests verify that the P33L orchestrator, wrapper, gate, and router
behave correctly without running any model, loading any checkpoint, or
creating any real execution gate.

Tests use a temporary, isolated state path and run directories under /tmp.
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.p33l import (
    P33LGate,
    P33LOrchestrator,
    P33LState,
    get_model_config,
    ordered_model_ids,
)
from app.services.p33l.security import safe_relative_path

TEST_MANIFEST_SHA = "a" * 64


@pytest.fixture
def isolated_state_path():
    with tempfile.TemporaryDirectory() as tmp:
        yield os.path.join(tmp, "p33l_state.json")


@pytest.fixture
def orchestrator(isolated_state_path):
    return P33LOrchestrator(
        manifest_sha=TEST_MANIFEST_SHA,
        state_path=isolated_state_path,
    )


def test_ordered_models_six_models():
    assert ordered_model_ids() == [
        "pepmlm",
        "evobind2",
        "diffpepbuilder",
        "pepflow",
        "pephar",
        "ppflow",
    ]


def test_get_model_config_known():
    cfg = get_model_config("pepmlm")
    assert cfg.model_id == "pepmlm"
    assert cfg.source_sha256 != ""
    assert cfg.fixture_sha256 != ""


def test_get_model_config_unknown():
    with pytest.raises(ValueError):
        get_model_config("notamodel")


def test_orchestrator_create_job_next_in_order(orchestrator):
    job = orchestrator.create_job("pepmlm", {})
    assert job.model_id == "pepmlm"
    assert job.status == "queued"
    assert job.manifest_sha == TEST_MANIFEST_SHA


def test_orchestrator_create_job_wrong_order(orchestrator):
    with pytest.raises(ValueError, match="not next in fixed order"):
        orchestrator.create_job("ppflow", {})


def test_orchestrator_create_job_after_attempt(orchestrator):
    orchestrator.create_job("pepmlm", {})
    orchestrator.state.record_attempt("pepmlm", "job_1", "succeeded")
    with pytest.raises(ValueError, match="already attempted"):
        orchestrator.create_job("pepmlm", {})


def test_orchestrator_run_job_blocked_by_closed_gate(orchestrator, isolated_state_path, monkeypatch):
    monkeypatch.setenv("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "true")
    job = orchestrator.create_job("pepmlm", {})
    # Even with a valid P33L gate, the wrapper is hard-blocked in test mode
    result_job = orchestrator.run_job(job, {})
    assert result_job.status == "failed"
    assert "gate" in str(result_job.result).lower() or result_job.result.get("exit_code") == 1


def test_gate_lifecycle():
    with tempfile.TemporaryDirectory() as tmp:
        gate_root = os.path.join(tmp, "gates")
        gate = P33LGate(
            model_id="pepmlm",
            job_id="job_1",
            base_dir=gate_root,
            manifest_sha=TEST_MANIFEST_SHA,
            ttl_seconds=3600,
        )
        doc = gate.create()
        assert doc["status"] == "created"
        assert gate.validate() is not None
        gate.close()
        assert gate.validate() is None


def test_gate_manifest_sha_mismatch():
    with tempfile.TemporaryDirectory() as tmp:
        gate_root = os.path.join(tmp, "gates")
        gate = P33LGate(
            model_id="pepmlm",
            job_id="job_1",
            base_dir=gate_root,
            manifest_sha=TEST_MANIFEST_SHA,
            ttl_seconds=3600,
        )
        gate.create()
        wrong_gate = P33LGate(
            model_id="pepmlm",
            job_id="job_1",
            base_dir=gate_root,
            manifest_sha="b" * 64,
            ttl_seconds=3600,
        )
        wrong_gate.gate_path = gate.gate_path
        assert wrong_gate.validate() is None


def test_safe_relative_path_blocks_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError):
            safe_relative_path(tmp, "../etc/passwd")


def test_router_unauthorized_manifest():
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/v1/p33l/real-run",
        json={"model_id": "pepmlm", "input": {}},
        headers={"P33L-Authorized-Manifest-SHA": "x"},
    )
    assert response.status_code == 403


def test_router_status_unauthorized():
    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/api/v1/p33l/status",
        headers={"P33L-Authorized-Manifest-SHA": "x"},
    )
    assert response.status_code == 403


def test_state_persistence(isolated_state_path):
    state = P33LState(state_path=isolated_state_path)
    state.record_attempt("pepmlm", "job_1", "succeeded")
    state2 = P33LState(state_path=isolated_state_path)
    assert state2.is_model_attempted("pepmlm")
    assert state2.next_model() == "evobind2"


def test_state_next_model_all_attempted(isolated_state_path):
    state = P33LState(state_path=isolated_state_path)
    for m in ordered_model_ids():
        state.record_attempt(m, f"job_{m}", "succeeded")
    assert state.next_model() is None
