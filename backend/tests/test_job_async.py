"""STAMP Platform — Async Job Execution Tests (v0.10-P2b).

Tests the POST /api/v1/jobs/{job_id}/start endpoint and background-task
lifecycle. All outputs remain NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import create_project, create_target_protein
from app.crud.jobs import create_job, update_job_status
from app.database import Base, get_db
from app.main import create_app
from app.schemas import JobCreate, ProjectCreate, TargetProteinCreate
from app.services.job_service import run_real_job

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory DB session for each test."""
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def sample_sequence() -> str:
    """Return a realistic 68-aa protein sequence."""
    return (
        "MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGT"
        "GKGADAATYYTYILTAAKLIAGA"
    )


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="Async Job Test Project"))
    return proj


@pytest.fixture
def test_target_protein(db_session, test_project, sample_sequence):
    """Create a test target protein."""
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="Test OprF",
            sequence=sample_sequence,
            sequence_hash="testhash123",
            length=len(sample_sequence),
            source_type="manual",
        ),
    )
    return tp


@pytest.fixture
def test_app(db_session):
    """Create a FastAPI test app with overridden DB dependency."""
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture
async def async_client(test_app):
    """Create an async HTTP test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _create_job(async_client, project_id: str, job_type: str, input_json: dict):
    """Helper to create a job via API."""
    resp = await async_client.post(
        "/api/v1/jobs",
        json={"project_id": project_id, "job_type": job_type, "input_json": input_json},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["data"]


# ============================================================================
# 1. /start on pending job returns 202 + running
# ============================================================================


@pytest.mark.asyncio
async def test_start_pending_job_returns_accepted(async_client, test_project, monkeypatch):
    """POST /start on a pending job must return 202 with status=running, progress=5."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": str(uuid.uuid4()),
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )

    resp = await async_client.post(f"/api/v1/jobs/{job_data['id']}/start")
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()["data"]
    assert data["job_id"] == job_data["id"]
    assert data["status"] == "running"
    assert data["progress"] == 5


# ============================================================================
# 2. /start does NOT block waiting for inference
# ============================================================================


@pytest.mark.asyncio
async def test_start_does_not_block(async_client, test_project):
    """The /start endpoint must return immediately (HTTP 202) without waiting
    for the long-running sidecar inference to finish."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": str(uuid.uuid4()),
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )

    resp = await async_client.post(f"/api/v1/jobs/{job_data['id']}/start")
    # If this were blocking, the response would not arrive until sidecar finished.
    # We assert 202 and running — the background task is still in progress.
    assert resp.status_code == status.HTTP_202_ACCEPTED
    assert resp.json()["data"]["status"] == "running"


# ============================================================================
# 3. Background task succeeds → status=succeeded, progress=100
# ============================================================================


@pytest.mark.asyncio
async def test_background_task_succeeds(db_session, test_project, test_target_protein, monkeypatch):
    """After the background runner completes successfully, job must be
    status=succeeded with progress=100 and valid output_json."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {
            "ranked_peptides": [
                {"sequence": "TESTPEP", "start": 1, "end": 7, "score": 0.5}
            ],
            "retained_count": 1,
            "dropped_count": 0,
        },
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
                "sidecar_url": "http://127.0.0.1:5001/api/predict",
            },
        ),
    )

    updated = run_real_job(db_session, job_id=job.id)
    assert updated is not None
    assert updated.status == "succeeded"
    assert updated.progress == 100
    assert updated.output_json is not None


# ============================================================================
# 4. Background task fails → status=failed, error_message set
# ============================================================================


@pytest.mark.asyncio
async def test_background_task_fails(db_session, test_project, test_target_protein, monkeypatch):
    """If the background runner raises an exception, job must become
    status=failed with a non-empty error_message."""

    def _raise_error(*a, **k):
        raise RuntimeError("Simulated sidecar failure")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _raise_error,
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
                "sidecar_url": "http://127.0.0.1:5001/api/predict",
            },
        ),
    )

    updated = run_real_job(db_session, job_id=job.id)
    assert updated is not None
    assert updated.status == "failed"
    assert updated.error_message is not None
    assert "Simulated sidecar failure" in updated.error_message


# ============================================================================
# 5. Idempotent: running job repeated /start does not duplicate
# ============================================================================


@pytest.mark.asyncio
async def test_start_running_job_is_idempotent(async_client, test_project, db_session):
    """Calling /start on an already-running job must return the current job
    state without spawning a duplicate background task."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="running", progress=42)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/start")
    assert resp.status_code == status.HTTP_202_ACCEPTED
    data = resp.json()["data"]
    assert data["status"] == "running"
    assert data["progress"] == 42


# ============================================================================
# 6. Terminal-state guard: succeeded job /start returns as-is
# ============================================================================


@pytest.mark.asyncio
async def test_start_succeeded_job_returns_as_is(async_client, test_project, db_session):
    """Calling /start on a succeeded job must return status=succeeded
    without re-execution."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(
        db_session, job.id, status="succeeded", progress=100, output_json={"ok": True}
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/start")
    assert resp.status_code == status.HTTP_202_ACCEPTED
    assert resp.json()["data"]["status"] == "succeeded"


# ============================================================================
# 7. Terminal-state guard: failed job /start returns as-is
# ============================================================================


@pytest.mark.asyncio
async def test_start_failed_job_returns_as_is(async_client, test_project, db_session):
    """Calling /start on a failed job must return status=failed
    without auto-retry."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(
        db_session,
        job.id,
        status="failed",
        progress=0,
        error_message="Previous failure",
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/start")
    assert resp.status_code == status.HTTP_202_ACCEPTED
    assert resp.json()["data"]["status"] == "failed"


# ============================================================================
# 8. Polling: GET /jobs/{job_id} returns current status
# ============================================================================


@pytest.mark.asyncio
async def test_polling_get_job(async_client, test_project, db_session):
    """The existing GET /jobs/{job_id} endpoint must support polling
    so the frontend can track async progress."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="running", progress=55)

    resp = await async_client.get(f"/api/v1/jobs/{job.id}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "running"
    assert data["progress"] == 55


# ============================================================================
# 9. Scientific-integrity: output_json boundaries
# ============================================================================


@pytest.mark.asyncio
async def test_output_json_has_validation_status(db_session, test_project, test_target_protein, monkeypatch):
    """output_json must contain NOT_EXPERIMENTALLY_VALIDATED
    and COMPUTATIONAL_PREDICTION_ONLY."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
                "sidecar_url": "http://127.0.0.1:5001/api/predict",
            },
        ),
    )

    updated = run_real_job(db_session, job_id=job.id)
    assert updated.output_json["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert updated.output_json["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"


@pytest.mark.asyncio
async def test_output_json_no_forbidden_metrics(db_session, test_project, test_target_protein, monkeypatch):
    """output_json must NOT contain any forbidden experimental/structural metrics."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
                "sidecar_url": "http://127.0.0.1:5001/api/predict",
            },
        ),
    )

    updated = run_real_job(db_session, job_id=job.id)
    output_str = str(updated.output_json).lower()
    forbidden = [
        "mic", "mbc", "hemolysis", "toxicity", "iptm", "pdockq",
        "docking_score", "delta_g", "ΔG", "experimentally validated",
        "wet-lab confirmed",
    ]
    for f in forbidden:
        assert f.lower() not in output_str, f"Forbidden metric '{f}' found in output_json"


# ============================================================================
# 10. Compatibility: synchronous /run endpoint still works
# ============================================================================


@pytest.mark.asyncio
async def test_sync_run_endpoint_still_works(async_client, test_project, test_target_protein, monkeypatch):
    """The existing synchronous POST /jobs/{id}/run must remain functional."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )

    resp = await async_client.post(f"/api/v1/jobs/{job_data['id']}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["progress"] == 100
