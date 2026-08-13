"""Zero-model tests for P33L Phase 2/3 final correction.

These tests verify that the P33L orchestrator, wrapper, gate, router,
manifest writer, quota monitor, and cleanup behave correctly without running
any model, loading any checkpoint, or creating any real execution gate.

Tests use a temporary, isolated state path and run directories under /tmp.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.routers.p33l import _orchestrators as _p33l_router_orchestrators
from app.services.p33l import (
    P33LGate,
    P33LOrchestrator,
    P33LState,
    get_model_config,
    ordered_model_ids,
)
from app.services.p33l.manifest import write_manifest
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





@pytest.fixture
def authorized_app(monkeypatch, isolated_state_path):
    monkeypatch.setenv("P33L_AUTHORIZED_MANIFEST_SHA", TEST_MANIFEST_SHA)
    _p33l_router_orchestrators.clear()

    def _orch_factory(manifest_sha):
        if manifest_sha not in _p33l_router_orchestrators:
            _p33l_router_orchestrators[manifest_sha] = P33LOrchestrator(
                manifest_sha=manifest_sha,
                state_path=isolated_state_path,
            )
        return _p33l_router_orchestrators[manifest_sha]

    monkeypatch.setattr("app.routers.p33l._get_orchestrator", _orch_factory)
    return create_app()


# ---------------------------------------------------------------------------
# Configuration and ordering
# ---------------------------------------------------------------------------


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


def test_get_model_config_diffpepbuilder_real_runner():
    cfg = get_model_config("diffpepbuilder")
    assert "p33l_real_runner" in cfg.runner_script_path
    assert cfg.runner_script_sha256 != ""
    assert cfg.source_path.endswith("run_inference.py")
    assert cfg.source_sha256 != ""


def test_get_model_config_pephar_real_runner_and_two_checkpoints():
    cfg = get_model_config("pephar")
    assert "p33l_real_runner" in cfg.runner_script_path
    assert cfg.runner_script_sha256 != ""
    assert cfg.source_path.endswith("evaluate/sample.py")
    assert cfg.source_sha256 != ""
    names = {m["name"] for m in cfg.model_configs}
    assert {"density_checkpoint", "density_config", "prediction_checkpoint", "prediction_config"} <= names


def test_get_model_config_unknown():
    with pytest.raises(ValueError):
        get_model_config("notamodel")


# ---------------------------------------------------------------------------
# Job creation and ordering
# ---------------------------------------------------------------------------


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


def test_orchestrator_fail_stop_after_prior_failure(orchestrator):
    orchestrator.state.record_attempt("pepmlm", "job_1", "failed")
    with pytest.raises(ValueError, match="Prior model .* failed"):
        orchestrator.create_job("evobind2", {})


# ---------------------------------------------------------------------------
# Gate lifecycle
# ---------------------------------------------------------------------------


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


def test_gate_ttl_expired():
    with tempfile.TemporaryDirectory() as tmp:
        gate_root = os.path.join(tmp, "gates")
        gate = P33LGate(
            model_id="pepmlm",
            job_id="job_1",
            base_dir=gate_root,
            manifest_sha=TEST_MANIFEST_SHA,
            ttl_seconds=1,
        )
        gate.create()
        assert gate.validate() is not None
        time.sleep(1.1)
        assert gate.validate() is None


# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------


def test_safe_relative_path_blocks_traversal():
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.raises(ValueError):
            safe_relative_path(tmp, "../etc/passwd")


def test_safe_relative_path_allows_whitelisted_file():
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "manifest" / "run_manifest.json"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("{}")
        resolved = safe_relative_path(tmp, "manifest/run_manifest.json")
        assert resolved == str(f.resolve())


# ---------------------------------------------------------------------------
# Router authorization
# ---------------------------------------------------------------------------


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


def test_router_real_run_authorized_blocked_execution(authorized_app):
    with patch.dict(os.environ, {"P33L_BLOCK_ALL_WRAPPER_EXECUTION": "true"}):
        client = TestClient(authorized_app)
        response = client.post(
            "/api/v1/p33l/real-run",
            json={"model_id": "pepmlm", "input": {}},
            headers={"P33L-Authorized-Manifest-SHA": TEST_MANIFEST_SHA},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["model_id"] == "pepmlm"


def test_router_cancel_unknown_job(authorized_app):
    client = TestClient(authorized_app)
    response = client.post(
        "/api/v1/p33l/jobs/does-not-exist/cancel",
        headers={"P33L-Authorized-Manifest-SHA": TEST_MANIFEST_SHA},
    )
    assert response.status_code == 404


def test_router_download_path_traversal(authorized_app):
    client = TestClient(authorized_app)
    with patch.dict(os.environ, {"P33L_BLOCK_ALL_WRAPPER_EXECUTION": "true"}):
        run_resp = client.post(
            "/api/v1/p33l/real-run",
            json={"model_id": "pepmlm", "input": {}},
            headers={"P33L-Authorized-Manifest-SHA": TEST_MANIFEST_SHA},
        )
    job_id = run_resp.json()["data"]["job_id"]
    response = client.get(
        f"/api/v1/p33l/jobs/{job_id}/download/../../../etc/passwd",
        headers={"P33L-Authorized-Manifest-SHA": TEST_MANIFEST_SHA},
    )
    assert response.status_code in (400, 403, 404)


# ---------------------------------------------------------------------------
# Wrapper block
# ---------------------------------------------------------------------------


def test_wrapper_blocked_by_test_env(orchestrator, monkeypatch):
    monkeypatch.setenv("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "true")
    job = orchestrator.create_job("pepmlm", {})
    result_job = orchestrator.run_job(job, {})
    assert result_job.status == "failed"
    assert result_job.result.get("exit_code") == 1


def test_wrapper_blocked_with_closed_gate():
    from app.services.p33l.wrapper import ModelRealRunWrapper

    with tempfile.TemporaryDirectory() as tmp:
        gate_path = os.path.join(tmp, "gate.json")
        run_dir = os.path.join(tmp, "run")
        os.makedirs(run_dir, exist_ok=True)
        # Gate file does not exist -> closed
        result = ModelRealRunWrapper.submit(
            model_id="pepmlm",
            job_id="job_1",
            input_payload={},
            run_dir=run_dir,
            gate_path=gate_path,
            manifest_sha=TEST_MANIFEST_SHA,
        )
        assert result["status"] == "blocked"


# ---------------------------------------------------------------------------
# Cancel and PID cleanup
# ---------------------------------------------------------------------------


def test_cancel_job_kills_subprocess(orchestrator, monkeypatch):
    monkeypatch.setenv("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "false")
    job = orchestrator.create_job("pepmlm", {})

    # Replace wrapper start with a long-running sleep subprocess
    def _start_sleep(**_kwargs):
        return subprocess.Popen(
            ["sleep", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    with patch("app.services.p33l.orchestrator.ModelRealRunWrapper.start", _start_sleep):
        # Use a thread to run the job so we can cancel it concurrently
        import threading

        result = {"job": None}

        def run():
            result["job"] = orchestrator.run_job(job, {})

        t = threading.Thread(target=run)
        t.start()
        time.sleep(0.5)
        cancelled = orchestrator.cancel_job(job.job_id)
        t.join(timeout=5)
        assert cancelled.status == "cancelled"
        # Ensure the sleep process is gone
        try:
            os.kill(job.pid, 0)
            pytest.fail("subprocess still alive after cancel")
        except (ProcessLookupError, OSError):
            pass


def test_kill_process_tree_by_pid():
    # Start a subprocess group and verify _kill_process_tree terminates it
    proc = subprocess.Popen(
        ["sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    P33LOrchestrator._kill_process_tree(proc.pid)
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pytest.fail("process not killed")
    assert proc.returncode != 0 or proc.poll() is not None


# ---------------------------------------------------------------------------
# Timeout
# ---------------------------------------------------------------------------


def test_job_timeout_terminates_long_subprocess(orchestrator, monkeypatch):
    monkeypatch.setenv("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "false")
    job = orchestrator.create_job("pepmlm", {})

    def _start_sleep(**_kwargs):
        return subprocess.Popen(
            ["sleep", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    # Temporarily reduce timeout for the test model? Instead patch config lookup.
    cfg = get_model_config("pepmlm")
    fast_cfg = cfg.__class__(**{**cfg.__dict__, "timeout_seconds": 1})
    with patch("app.services.p33l.orchestrator.get_model_config", lambda _mid: fast_cfg):
        with patch("app.services.p33l.orchestrator.ModelRealRunWrapper.start", _start_sleep):
            result_job = orchestrator.run_job(job, {})
    assert result_job.status == "timeout"


# ---------------------------------------------------------------------------
# Runtime quota
# ---------------------------------------------------------------------------


def test_runtime_quota_monitor_detects_violation():
    from app.services.p33l.orchestrator import _RuntimeQuotaMonitor

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(
            ["sleep", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        monitor = _RuntimeQuotaMonitor(
            pid=proc.pid,
            run_dir=tmp,
            quota_bytes=10,
            max_files=1000,
            interval=0.1,
        )
        # Create files that exceed the tiny quota
        (Path(tmp) / "big.bin").write_bytes(b"x" * 100)
        monitor.start()
        deadline = time.time() + 3
        while time.time() < deadline and not monitor.violation:
            time.sleep(0.1)
        monitor.stop()
        assert monitor.violation is not None
        assert "disk quota exceeded" in monitor.violation
        P33LOrchestrator._kill_process_tree(proc.pid)


def test_orchestrator_fails_on_quota_violation(orchestrator, monkeypatch):
    monkeypatch.setenv("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "false")
    job = orchestrator.create_job("pepmlm", {})

    def _start_writer(**_kwargs):
        # Subprocess writes files larger than tiny quota
        script = "import os, time; os.makedirs('output', exist_ok=True); f=open('output/big.bin','wb'); f.write(b'x'*1024); f.flush(); time.sleep(30)"
        return subprocess.Popen(
            ["python3", "-c", script],
            cwd=job.run_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    cfg = get_model_config("pepmlm")
    small_cfg = cfg.__class__(**{**cfg.__dict__, "disk_quota_bytes": 100, "max_output_files": 1000})
    with patch("app.services.p33l.orchestrator.get_model_config", lambda _mid: small_cfg):
        with patch("app.services.p33l.orchestrator.ModelRealRunWrapper.start", _start_writer):
            result_job = orchestrator.run_job(job, {})
    assert result_job.status == "failed"
    assert "quota" in str(result_job.result.get("quota_error", "")).lower()


# ---------------------------------------------------------------------------
# Manifest writer
# ---------------------------------------------------------------------------


def test_manifest_writer_includes_not_experimentally_validated(orchestrator):
    job = orchestrator.create_job("pepmlm", {})
    result = {
        "status": "succeeded",
        "exit_code": 0,
        "disk_used_bytes": 100,
        "file_count": 2,
    }
    write_manifest(job.run_dir, job, result, {"fixture_sha256": "abc"})
    manifest_path = Path(job.run_dir) / "manifest" / "run_manifest.json"
    assert manifest_path.exists()
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["disclaimer"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert manifest["computational_prediction_only"] is True
    assert manifest["task_id"] == "P33L"


def test_manifest_writer_records_model_configs_pephar(isolated_state_path):
    cfg = get_model_config("pephar")
    orch = P33LOrchestrator(manifest_sha=TEST_MANIFEST_SHA, state_path=isolated_state_path)
    # Advance to PepHAR by recording earlier models attempted
    for m in ["pepmlm", "evobind2", "diffpepbuilder", "pepflow"]:
        orch.state.record_attempt(m, f"job_{m}", "succeeded")
    job = orch.create_job("pephar", {})
    result = {"status": "blocked", "exit_code": 1}
    write_manifest(job.run_dir, job, result, {"fixture_sha256": "abc"})
    manifest_path = Path(job.run_dir) / "manifest" / "run_manifest.json"
    import json

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    configs = manifest["provenance"]["model_configs"]
    names = {c["name"] for c in configs}
    assert "density_checkpoint" in names
    assert "prediction_checkpoint" in names


# ---------------------------------------------------------------------------
# Persistence and idempotency
# ---------------------------------------------------------------------------


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


def test_process_restart_attempt_persistence(isolated_state_path):
    # Simulate process restart: first orchestrator records attempt, second loads it
    orch1 = P33LOrchestrator(manifest_sha=TEST_MANIFEST_SHA, state_path=isolated_state_path)
    orch1.state.record_attempt("pepmlm", "job_1", "succeeded")

    orch2 = P33LOrchestrator(manifest_sha=TEST_MANIFEST_SHA, state_path=isolated_state_path)
    assert orch2.state.is_model_attempted("pepmlm")
    with pytest.raises(ValueError, match="already attempted"):
        orch2.create_job("pepmlm", {})


# ---------------------------------------------------------------------------
# Duplicate submit / idempotency
# ---------------------------------------------------------------------------


def test_duplicate_submit_rejected(orchestrator):
    orchestrator.create_job("pepmlm", {})
    orchestrator.state.record_attempt("pepmlm", "job_1", "succeeded")
    with pytest.raises(ValueError, match="already attempted"):
        orchestrator.create_job("pepmlm", {})


def test_fixed_order_enforced(orchestrator):
    orchestrator.create_job("pepmlm", {})
    orchestrator.state.record_attempt("pepmlm", "job_1", "succeeded")
    # Skip evobind2 and try diffpepbuilder
    with pytest.raises(ValueError, match="not next in fixed order"):
        orchestrator.create_job("diffpepbuilder", {})


# ---------------------------------------------------------------------------
# Static call-chain verification (no execution)
# ---------------------------------------------------------------------------


def test_diffpepbuilder_command_uses_official_inference_and_real_runner():
    cfg = get_model_config("diffpepbuilder")
    cmd = cfg.command_args({
        "run_dir": "/tmp/run",
        "gate_path": "/tmp/gate.json",
        "config": cfg,
        "fixture_path": cfg.fixture_path,
    })
    assert cfg.runner_script_path in cmd
    assert cfg.source_path.endswith("experiments/run_inference.py")
    assert cfg.checkpoint_path in cmd


def test_pephar_command_uses_two_checkpoints():
    cfg = get_model_config("pephar")
    cmd = cfg.command_args({
        "run_dir": "/tmp/run",
        "gate_path": "/tmp/gate.json",
        "config": cfg,
        "fixture_path": cfg.fixture_path,
        "model_variant": "prediction",
    })
    assert cfg.runner_script_path in cmd
    assert any("density_v4_x5o2" in arg for arg in cmd)
    assert any("prediction_d2_x2o1" in arg for arg in cmd)


def test_pepflow_command_uses_project_root_config():
    cfg = get_model_config("pepflow")
    cmd = cfg.command_args({
        "run_dir": "/tmp/run",
        "config": cfg,
        "fixture_path": cfg.fixture_path,
    })
    assert cfg.source_path in cmd
    assert any("PepFlowww-main/configs/learn_angle.yaml" in arg for arg in cmd)


# ---------------------------------------------------------------------------
# Frontend no-auto-submit guard (backend contract)
# ---------------------------------------------------------------------------


def test_router_real_run_requires_explicit_post(authorized_app):
    """Model switching (GET /status) must not trigger a run."""
    client = TestClient(authorized_app)
    status_resp = client.get(
        "/api/v1/p33l/status",
        headers={"P33L-Authorized-Manifest-SHA": TEST_MANIFEST_SHA},
    )
    assert status_resp.status_code == 200
    # No jobs should have been created by the status call
    data = status_resp.json()["data"]
    assert data["total_jobs"] == 0
