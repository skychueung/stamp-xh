"""Mock API tests for EvoBind2 router skeleton (P2O).

No subprocess calls. No server access.  Creates a temporary FastAPI app
with the router included, then uses TestClient.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers.evobind2 import router as evobind2_router


@pytest.fixture
def client():
    """Create a temporary FastAPI app with the EvoBind2 router."""
    app = FastAPI()
    app.include_router(evobind2_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Happy path: model_1_ptm
# ---------------------------------------------------------------------------


def test_dry_run_model_1_ptm_returns_success(client):
    payload = {
        "run_id": "p2o_test_001",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "READY"
    assert data["model_name"] == "model_1_ptm"


def test_dry_run_returns_safety_flags(client):
    payload = {
        "run_id": "p2o_test_002",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    flags = data["safety_flags"]
    assert flags["is_candidate_generation"] is False
    assert flags["is_scientific_result"] is False
    assert flags["uses_uniref30"] is False


def test_dry_run_returns_command_preview_with_mc_design(client):
    payload = {
        "run_id": "p2o_test_003",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    cmd = data["command_preview"]
    assert any("mc_design.py" in token for token in cmd)


def test_dry_run_command_preview_has_model_name(client):
    payload = {
        "run_id": "p2o_test_004",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    cmd = data["command_preview"]
    assert any("--model_names=model_1_ptm" in token for token in cmd)


def test_dry_run_output_dir_ends_with_slash(client):
    payload = {
        "run_id": "p2o_test_005",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    cmd = data["command_preview"]
    output_token = [t for t in cmd if t.startswith("--output_dir=")][0]
    assert output_token.endswith("/")


# ---------------------------------------------------------------------------
# model_1 also allowed
# ---------------------------------------------------------------------------


def test_dry_run_model_1_allowed(client):
    payload = {
        "run_id": "p2o_test_006",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_name"] == "model_1"


# ---------------------------------------------------------------------------
# Blocked models
# ---------------------------------------------------------------------------


def test_dry_run_model_1_multimer_v3_blocked(client):
    payload = {
        "run_id": "p2o_test_007",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_multimer_v3",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    # Schema validation blocks at request level
    assert response.status_code == 422
    assert "mc_design.py/config.py path does not support it" in response.text


def test_dry_run_unknown_model_invalid(client):
    payload = {
        "run_id": "p2o_test_008",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_99_fantasy",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 422
    assert "Invalid model name" in response.text


# ---------------------------------------------------------------------------
# Design mode blocked
# ---------------------------------------------------------------------------


def test_dry_run_design_mode_blocked(client):
    payload = {
        "run_id": "p2o_test_009",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "mode": "design",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 422
    assert "predict_only" in response.text


# ---------------------------------------------------------------------------
# No subprocess / no server / no model execution
# ---------------------------------------------------------------------------


def test_dry_run_no_subprocess_called(client, monkeypatch):
    """Verify dry-run never calls subprocess."""
    import subprocess

    called = False

    def fake_popen(*args, **kwargs):
        nonlocal called
        called = True
        raise RuntimeError("subprocess should not be called")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    monkeypatch.setattr(subprocess, "run", fake_popen)
    monkeypatch.setattr(subprocess, "call", fake_popen)

    payload = {
        "run_id": "p2o_test_010",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    assert called is False


# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------


def test_dry_run_defaults(client):
    payload = {
        "run_id": "p2o_test_011",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_name"] == "model_1_ptm"
    assert data["mode"] == "predict_only"
    assert data["used_gpu"] is True


# ---------------------------------------------------------------------------
# Env preview
# ---------------------------------------------------------------------------


def test_dry_run_env_preview_has_xla_vars(client):
    payload = {
        "run_id": "p2o_test_012",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    env = data["env_preview"]
    assert env["XLA_PYTHON_CLIENT_PREALLOCATE"] == "false"
    assert "CUDA_VISIBLE_DEVICES" in env


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_dry_run_artifacts_present(client):
    payload = {
        "run_id": "p2o_test_013",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    artifacts = data["artifacts"]
    assert "metrics_csv" in artifacts
    assert "pdb" in artifacts
    assert "gpu_sample_csv" in artifacts
    assert "run_log" in artifacts


# ---------------------------------------------------------------------------
# Auto GPU selection
# ---------------------------------------------------------------------------


def test_dry_run_auto_gpu_defaults_to_zero(client):
    payload = {
        "run_id": "p2o_test_014",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "selected_gpu": "auto",
    }
    response = client.post("/api/v1/evobind2/dry-run", json=payload)
    data = response.json()["data"]
    assert data["selected_gpu"] == 0
