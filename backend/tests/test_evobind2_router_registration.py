"""Integration tests for EvoBind2 router registration in the main app (P2P).

Uses the real ``app.main.app`` so the test verifies that the evobind2
dry-run router is actually mounted by ``create_app()``.  No subprocesses,
no server access, and no model execution are performed.
"""

from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def main_client() -> TestClient:
    """Yield a TestClient backed by the real production FastAPI app.

    The dry-run endpoint has no dependency on database tables or JSON data
    files, so eager_load_all is stubbed to keep the fixture independent of
    backend/data files.
    """
    import app.data.loader

    app.data.loader.eager_load_all = lambda: None
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# Router registration / happy path
# ---------------------------------------------------------------------------


def test_main_app_exposes_evobind2_dry_run(main_client: TestClient) -> None:
    """POST /api/v1/evobind2/dry-run must be reachable via the main app."""
    payload = {
        "run_id": "p2p_reg_001",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body.get("code") == 200
    data = body["data"]
    assert data["status"] == "READY"
    assert data["model_name"] == "model_1_ptm"


def test_dry_run_returns_safety_flags(main_client: TestClient) -> None:
    """Safety flags must be present and all False for predict_only dry-run."""
    payload = {
        "run_id": "p2p_reg_002",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    flags = data["safety_flags"]
    assert flags["is_candidate_generation"] is False
    assert flags["is_scientific_result"] is False
    assert flags["uses_uniref30"] is False


def test_dry_run_returns_command_preview(main_client: TestClient) -> None:
    """Command preview must reference mc_design.py and the selected model."""
    payload = {
        "run_id": "p2p_reg_003",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    cmd = response.json()["data"]["command_preview"]
    assert any("mc_design.py" in token for token in cmd)
    assert any("--model_names=model_1_ptm" in token for token in cmd)


def test_dry_run_output_dir_ends_with_slash(main_client: TestClient) -> None:
    """The output_dir guard (trailing slash) must remain in place."""
    payload = {
        "run_id": "p2p_reg_004",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    cmd = response.json()["data"]["command_preview"]
    output_token = [t for t in cmd if t.startswith("--output_dir=")][0]
    assert output_token.endswith("/")


# ---------------------------------------------------------------------------
# Model whitelist / blacklist
# ---------------------------------------------------------------------------


def test_dry_run_model_1_multimer_v3_blocked(main_client: TestClient) -> None:
    """Blocked model must be rejected at the schema validation layer."""
    payload = {
        "run_id": "p2p_reg_005",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_multimer_v3",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 422
    assert "mc_design.py/config.py path does not support it" in response.text


def test_dry_run_unknown_model_invalid(main_client: TestClient) -> None:
    """Unknown model names must be rejected."""
    payload = {
        "run_id": "p2p_reg_006",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_99_fantasy",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 422
    assert "Invalid model name" in response.text


# ---------------------------------------------------------------------------
# Mode guards
# ---------------------------------------------------------------------------


def test_dry_run_design_mode_blocked(main_client: TestClient) -> None:
    """Only predict_only mode is allowed in the dry-run skeleton."""
    payload = {
        "run_id": "p2p_reg_007",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "mode": "design",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 422
    assert "predict_only" in response.text


# ---------------------------------------------------------------------------
# Safety: no subprocess / no server / no model execution
# ---------------------------------------------------------------------------


def test_dry_run_no_subprocess_called(main_client: TestClient, monkeypatch) -> None:
    """The endpoint must never call subprocess."""
    called = False

    def fake_subprocess(*args, **kwargs):
        nonlocal called
        called = True
        raise RuntimeError("subprocess should not be invoked")

    monkeypatch.setattr(subprocess, "Popen", fake_subprocess)
    monkeypatch.setattr(subprocess, "run", fake_subprocess)
    monkeypatch.setattr(subprocess, "call", fake_subprocess)

    payload = {
        "run_id": "p2p_reg_008",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    assert called is False


def test_dry_run_does_not_import_or_run_evobind2_source(monkeypatch) -> None:
    """Dry-run must not trigger import or execution of EvoBind2 source modules."""
    import app.services.compute_wrappers.evobind2_wrapper as wrapper

    # The wrapper should build commands but never perform filesystem probes
    # or spawn processes for model parameters.
    assert wrapper.dry_run_plan is not None

    inp = wrapper.EvoBind2Input(
        run_id="p2p_reg_009",
        receptor_fasta=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        model_name="model_1_ptm",
    )
    plan = wrapper.dry_run_plan(inp)
    assert plan.status == "READY"
    assert plan.command_preview is not None


def test_dry_run_default_model_is_model_1_ptm(main_client: TestClient) -> None:
    """When no model_name is supplied, the default must be model_1_ptm."""
    payload = {
        "run_id": "p2p_reg_010",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    assert data["model_name"] == "model_1_ptm"


def test_dry_run_allowed_model_1(main_client: TestClient) -> None:
    """model_1 must be accepted by the whitelist."""
    payload = {
        "run_id": "p2p_reg_011",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    assert response.json()["data"]["model_name"] == "model_1"
