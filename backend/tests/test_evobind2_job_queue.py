"""EvoBind2 Job Queue Skeleton Tests (P2R-S1).

Covers:
  - public_demo_mode returns 403 on compute endpoints
  - dry-run remains available
  - model whitelist / blacklist
  - MSA mode whitelist
  - skeleton execution returns blocked, never succeeded
  - artifacts query never fabricates files
  - cancel behavior for various states

No subprocess. No server access. No model execution.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.public_safety import compute_endpoints_enabled
from app.database import SessionLocal, init_db
from app.routers.evobind2_compute import router as evobind2_compute_router
from app.schemas.evobind2 import EvoBind2JobSubmitRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_session():
    """Yield a fresh DB session for service-layer tests."""
    init_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def compute_enabled_client(monkeypatch):
    """TestClient with compute endpoints enabled."""
    monkeypatch.setattr(
        "app.routers.evobind2_compute.compute_endpoints_enabled", lambda: True
    )
    app = FastAPI()
    app.include_router(evobind2_compute_router)
    return TestClient(app)


@pytest.fixture
def main_client(monkeypatch):
    """TestClient backed by the real production app with data loading stubbed."""
    import app.data.loader

    app.data.loader.eager_load_all = lambda: None
    monkeypatch.setattr(
        "app.routers.evobind2_compute.compute_endpoints_enabled",
        compute_endpoints_enabled,
    )
    from app.main import app

    return TestClient(app)


# ---------------------------------------------------------------------------
# 1. public_demo_mode default returns 403
# ---------------------------------------------------------------------------


def test_submit_job_public_demo_mode_returns_403(main_client: TestClient) -> None:
    """Default config has public_demo_mode=True; compute endpoints must return 403."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 403, f"Expected 403, got {response.status_code}: {response.text}"
    assert "public-demo" in response.text.lower() or "disabled" in response.text.lower()


def test_get_job_public_demo_mode_returns_403(main_client: TestClient) -> None:
    """GET /jobs/{job_id} must also be blocked in public demo mode."""
    response = main_client.get("/api/v1/evobind2/jobs/nonexistent-id")
    assert response.status_code == 403


def test_artifacts_public_demo_mode_returns_403(main_client: TestClient) -> None:
    """GET /jobs/{job_id}/artifacts must also be blocked."""
    response = main_client.get("/api/v1/evobind2/jobs/nonexistent-id/artifacts")
    assert response.status_code == 403


def test_cancel_public_demo_mode_returns_403(main_client: TestClient) -> None:
    """POST /jobs/{job_id}/cancel must also be blocked."""
    response = main_client.post("/api/v1/evobind2/jobs/nonexistent-id/cancel")
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 2. dry-run endpoint remains available
# ---------------------------------------------------------------------------


def test_dry_run_still_available_in_public_demo_mode(main_client: TestClient) -> None:
    """Dry-run is on a separate router and must remain reachable."""
    payload = {
        "run_id": "p2r_s1_dry_001",
        "receptor_fasta": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = main_client.post("/api/v1/evobind2/dry-run", json=payload)
    assert response.status_code == 200, f"Dry-run failed: {response.text}"
    data = response.json()["data"]
    assert data["status"] == "READY"
    assert data["model_name"] == "model_1_ptm"


# ---------------------------------------------------------------------------
# 3. Model whitelist / blacklist (compute enabled)
# ---------------------------------------------------------------------------


def test_submit_blocked_model_multimer_v3(compute_enabled_client: TestClient) -> None:
    """model_1_multimer_v3 must be rejected at schema validation layer."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_multimer_v3",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 422
    assert "mc_design.py/config.py path does not support it" in response.text


def test_submit_unknown_model_rejected(compute_enabled_client: TestClient) -> None:
    """Unknown model names must be rejected."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_99_fantasy",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 422
    assert "Invalid model name" in response.text


def test_submit_allowed_model_1(compute_enabled_client: TestClient, db_session: Session) -> None:
    """model_1 must be accepted."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 201, f"Unexpected: {response.text}"
    data = response.json()["data"]
    assert data["model_name"] == "model_1"


# ---------------------------------------------------------------------------
# 4. MSA mode whitelist
# ---------------------------------------------------------------------------


def test_submit_hhblits_msa_blocked(compute_enabled_client: TestClient) -> None:
    """hhblits MSA mode must be rejected."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "msa_mode": "hhblits",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 422
    assert "hhblits" in response.text.lower() or "not supported" in response.text.lower()


def test_submit_uniref30_msa_blocked(compute_enabled_client: TestClient) -> None:
    """uniref30 MSA mode must be rejected."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "msa_mode": "uniref30",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 422


def test_submit_single_sequence_allowed(compute_enabled_client: TestClient) -> None:
    """single_sequence MSA mode must be accepted."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "msa_mode": "single_sequence",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 201


# ---------------------------------------------------------------------------
# 5. Skeleton execution returns blocked, never succeeded
# ---------------------------------------------------------------------------


def test_submit_returns_blocked_not_succeeded(compute_enabled_client: TestClient) -> None:
    """Job submit must immediately return status=blocked in skeleton phase."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 201
    data = response.json()["data"]
    assert data["status"] == "blocked", f"Expected blocked, got {data['status']}"
    assert "skeleton" in data["message"].lower() or "not enabled" in data.get("error_message", "").lower()


def test_submit_error_message_contains_skeleton(compute_enabled_client: TestClient) -> None:
    """Blocked job must carry a clear skeleton-phase message."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    data = response.json()["data"]
    assert data["status"] == "blocked"
    assert "EvoBind2 real execution is not enabled in this skeleton phase" in (data.get("error_message") or "")


def test_get_job_returns_blocked(compute_enabled_client: TestClient) -> None:
    """GET must reflect the blocked status set at submit time."""
    # Submit first
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    submit_resp = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    job_id = submit_resp.json()["data"]["job_id"]

    # Query
    get_resp = compute_enabled_client.get(f"/api/v1/evobind2/jobs/{job_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()["data"]
    assert data["status"] == "blocked"


# ---------------------------------------------------------------------------
# 6. Safety flags
# ---------------------------------------------------------------------------


def test_submit_returns_safety_flags(compute_enabled_client: TestClient) -> None:
    """Response must include safety_flags with all expected fields."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    data = response.json()["data"]
    flags = data["safety_flags"]
    assert flags["is_candidate_generation"] is False
    assert flags["is_scientific_result"] is False
    assert flags["uses_uniref30"] is False
    assert flags["requires_manual_review"] is True
    assert flags["requires_real_validation"] is True


# ---------------------------------------------------------------------------
# 7. Artifacts query never fabricates files
# ---------------------------------------------------------------------------


def test_artifacts_empty_for_blocked_job(compute_enabled_client: TestClient) -> None:
    """A blocked job has no real artifacts; query must return empty list."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    submit_resp = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    job_id = submit_resp.json()["data"]["job_id"]

    art_resp = compute_enabled_client.get(f"/api/v1/evobind2/jobs/{job_id}/artifacts")
    assert art_resp.status_code == 200
    data = art_resp.json()["data"]
    assert data["artifacts"] == []


def test_artifacts_404_for_nonexistent_job(compute_enabled_client: TestClient) -> None:
    """Querying artifacts for a non-existent job must return 404."""
    response = compute_enabled_client.get("/api/v1/evobind2/jobs/nonexistent/artifacts")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 8. Cancel behavior
# ---------------------------------------------------------------------------


def test_cancel_blocked_job(compute_enabled_client: TestClient) -> None:
    """Cancel a blocked job → cancelled."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    submit_resp = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    job_id = submit_resp.json()["data"]["job_id"]

    cancel_resp = compute_enabled_client.post(f"/api/v1/evobind2/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    data = cancel_resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["previous_status"] == "blocked"


def test_cancel_already_cancelled_is_idempotent(compute_enabled_client: TestClient) -> None:
    """Double-cancel must be idempotent."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
    }
    submit_resp = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    job_id = submit_resp.json()["data"]["job_id"]

    compute_enabled_client.post(f"/api/v1/evobind2/jobs/{job_id}/cancel")
    cancel2 = compute_enabled_client.post(f"/api/v1/evobind2/jobs/{job_id}/cancel")
    assert cancel2.status_code == 200
    assert cancel2.json()["data"]["status"] == "cancelled"


def test_cancel_nonexistent_job_returns_404(compute_enabled_client: TestClient) -> None:
    """Cancel a non-existent job → 404."""
    response = compute_enabled_client.post("/api/v1/evobind2/jobs/nonexistent/cancel")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# 9. Service-layer direct tests
# ---------------------------------------------------------------------------


def test_service_submit_blocks_immediately(db_session: Session) -> None:
    """Direct service call must create a blocked job."""
    from app.services.evobind2_job_service import submit_evobind2_job

    request = EvoBind2JobSubmitRequest(
        project_id=str(uuid.uuid4()),
        target_sequence=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
        model_name="model_1_ptm",
    )
    job = submit_evobind2_job(db_session, request)
    assert job.status == "blocked"
    assert job.job_type == "evobind2_predict"
    assert "skeleton" in job.error_message.lower() or "not enabled" in job.error_message.lower()


def test_service_get_job_filters_by_type(db_session: Session) -> None:
    """get_evobind2_job must return None for non-evobind2 jobs."""
    from app.crud.jobs import create_job
    from app.schemas import JobCreate
    from app.services.evobind2_job_service import get_evobind2_job

    other_job = create_job(
        db_session,
        JobCreate(project_id=str(uuid.uuid4()), job_type="epitope_scan"),
    )
    assert get_evobind2_job(db_session, other_job.id) is None


def test_service_cancel_blocked(db_session: Session) -> None:
    """Cancel a blocked job via service layer."""
    from app.services.evobind2_job_service import (
        submit_evobind2_job,
        cancel_evobind2_job,
    )

    request = EvoBind2JobSubmitRequest(
        project_id=str(uuid.uuid4()),
        target_sequence=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    job = submit_evobind2_job(db_session, request)
    cancelled = cancel_evobind2_job(db_session, job.id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"


def test_service_cancel_succeeded_no_op(db_session: Session) -> None:
    """Cancel a succeeded job must not change its state."""
    from app.crud.jobs import create_job, update_job_status
    from app.schemas import JobCreate
    from app.services.evobind2_job_service import cancel_evobind2_job

    job = create_job(
        db_session,
        JobCreate(project_id=str(uuid.uuid4()), job_type="evobind2_predict"),
    )
    update_job_status(db_session, job.id, status="succeeded", progress=100)
    result = cancel_evobind2_job(db_session, job.id)
    assert result is not None
    assert result.status == "succeeded"


def test_service_artifacts_never_fabricate(db_session: Session) -> None:
    """get_evobind2_job_artifacts must not return non-existent files."""
    from app.services.evobind2_job_service import (
        submit_evobind2_job,
        get_evobind2_job_artifacts,
    )

    request = EvoBind2JobSubmitRequest(
        project_id=str(uuid.uuid4()),
        target_sequence=">test\nMKTAYIAKQR",
        peptide_sequence="AAAAAAAAAA",
        peptide_length=10,
    )
    job = submit_evobind2_job(db_session, request)
    artifacts = get_evobind2_job_artifacts(db_session, job.id)
    assert artifacts == []


# ---------------------------------------------------------------------------
# 10. Design mode blocked
# ---------------------------------------------------------------------------


def test_submit_design_mode_blocked(compute_enabled_client: TestClient) -> None:
    """Design mode must be rejected at schema validation layer."""
    payload = {
        "project_id": str(uuid.uuid4()),
        "target_sequence": ">test\nMKTAYIAKQR",
        "peptide_sequence": "AAAAAAAAAA",
        "peptide_length": 10,
        "mode": "design",
    }
    response = compute_enabled_client.post("/api/v1/evobind2/jobs", json=payload)
    assert response.status_code == 422
    assert "predict_only" in response.text
