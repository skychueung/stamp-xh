"""Tests for the PepMLM real-run job queue and Model Registry submit endpoints (P5C)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_real_run_token(monkeypatch):
    """Ensure the one-time real-run token is not set unless a test explicitly sets it."""
    monkeypatch.delenv("PEPMLM_REAL_RUN_TOKEN", raising=False)
    monkeypatch.delenv("PEPMLM_REAL_RUN_ENABLED", raising=False)


# ---------------------------------------------------------------------------
# Submit endpoint gate behaviour
# ---------------------------------------------------------------------------


def test_pepmlm_submit_blocked_when_gate_closed() -> None:
    payload = {
        "target_sequence": ">target\nMKTIIALSYIFCLVFADYKDDDDK",
        "peptide_length": 12,
        "num_candidates": 3,
        "device": "auto",
        "seed": 42,
    }
    response = client.post("/api/v1/models/pepmlm/submit", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "blocked"


def test_pepmlm_submit_pending_when_token_set(monkeypatch) -> None:
    monkeypatch.setenv("PEPMLM_REAL_RUN_TOKEN", "p5c_test_token")
    payload = {
        "target_sequence": ">target\nMKTIIALSYIFCLVFADYKDDDDK",
        "peptide_length": 12,
        "num_candidates": 3,
    }
    response = client.post("/api/v1/models/pepmlm/submit", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "pending"
    assert "job_id" in data


def test_pepmlm_submit_sync_runs_adapter_and_returns_status(monkeypatch) -> None:
    monkeypatch.setenv("PEPMLM_REAL_RUN_TOKEN", "p5c_test_token")

    def _fake_submit(self, payload: ModelDryRunPayload, run_id: str | None = None):
        from app.schemas.model_registry import ModelDryRunResult, ModelSafetyFlags
        from app.services.target_peptide_model_registry import SCIENTIFIC_BOUNDARY_NOTE

        return ModelDryRunResult(
            model_id="pepmlm",
            display_name="PepMLM",
            status="SUCCEEDED",
            message="Fake PepMLM run succeeded",
            run_id=run_id or "fake_run_id",
            artifacts={
                "input/target.fasta": "/tmp/fake/target.fasta",
                "output/candidate_sequences.csv": "/tmp/fake/candidate_sequences.csv",
            },
            command_preview=["python", "fake.py"],
            env_preview={},
            safety_flags=ModelSafetyFlags(
                executed_model=True,
                generated_candidates=True,
                generated_structure=False,
                generated_msa=False,
                is_scientific_result=True,
                computational_prediction_only=True,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            ),
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    monkeypatch.setattr(PepMLMAdapter, "submit", _fake_submit)

    payload = {
        "target_sequence": ">target\nMKTIIALSYIFCLVFADYKDDDDK",
        "peptide_length": 12,
        "num_candidates": 3,
        "seed": 42,
    }
    response = client.post("/api/v1/models/pepmlm/submit?sync=true", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "succeeded"
    assert data["run_id"]
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_non_pepmlm_submit_blocked() -> None:
    payload = {
        "target_sequence": ">target\nMKTIIALSYIFCLVFADYKDDDDK",
        "peptide_length": 12,
        "num_candidates": 3,
    }
    response = client.post("/api/v1/models/evobind2/submit", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# Job status endpoint
# ---------------------------------------------------------------------------


def test_pepmlm_job_status_after_submit(monkeypatch) -> None:
    monkeypatch.setenv("PEPMLM_REAL_RUN_TOKEN", "p5c_test_token")
    payload = {
        "target_sequence": ">target\nMKTIIALSYIFCLVFADYKDDDDK",
        "peptide_length": 12,
        "num_candidates": 3,
    }
    submit_response = client.post("/api/v1/models/pepmlm/submit", json=payload)
    job_id = submit_response.json()["data"]["job_id"]

    status_response = client.get(f"/api/v1/models/pepmlm/jobs/{job_id}")
    assert status_response.status_code == 200
    data = status_response.json()["data"]
    assert data["job_id"] == job_id
    assert data["model_id"] == "pepmlm"
    assert data["status"] == "pending"
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_pepmlm_job_status_unknown_job() -> None:
    response = client.get("/api/v1/models/pepmlm/jobs/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Job service helpers
# ---------------------------------------------------------------------------


def test_pepmlm_job_service_filters_by_job_type() -> None:
    from app.services.pepmlm_job_service import get_pepmlm_job

    db = SessionLocal()
    try:
        assert get_pepmlm_job(db, "b8ab6d11-5762-4bdf-a9db-6d30602637fd") is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def test_pepmlm_cancel_pending_job(monkeypatch) -> None:
    from app.services.pepmlm_job_service import cancel_pepmlm_job, get_pepmlm_job, submit_pepmlm_job

    monkeypatch.setenv("PEPMLM_REAL_RUN_TOKEN", "p5c_test_token")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
        num_candidates=3,
    )

    db = SessionLocal()
    try:
        job = submit_pepmlm_job(db, payload, project_id="p5c_test")
        job_id = job.id

        cancelled = cancel_pepmlm_job(db, job_id)
        assert cancelled is not None
        assert cancelled.status == "cancelled"

        fetched = get_pepmlm_job(db, job_id)
        assert fetched is not None
        assert fetched.status == "cancelled"
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Artifact listing
# ---------------------------------------------------------------------------


def test_pepmlm_list_artifacts_for_unknown_job_no_absolute_paths() -> None:
    response = client.get("/api/v1/models/pepmlm/jobs/unknown_job_id/artifacts")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    for artifact in data["artifacts"]:
        assert "/home/" not in artifact["path"]
