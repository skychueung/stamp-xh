"""STAMP Platform — Job Cancel, Retry & Error Recovery Tests (v0.10-P2d).

Tests the POST /cancel and POST /retry endpoints, cooperative cancellation,
and structured error messages. All outputs remain NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import create_project
from app.crud.jobs import create_job, update_job_status
from app.database import Base, get_db
from app.main import create_app
from app.schemas import JobCreate, ProjectCreate
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
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="Cancel Retry Test Project"))
    return proj


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
# 1. Cancel pending job
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_pending_job(async_client, test_project, db_session):
    """POST /cancel on a pending job should succeed."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["previous_status"] == "pending"


# ============================================================================
# 2. Cancel running job
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_running_job(async_client, test_project, db_session):
    """POST /cancel on a running job should succeed."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="running", progress=50)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "cancelled"
    assert data["previous_status"] == "running"


# ============================================================================
# 3. Cancel already-cancelled job is idempotent
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_cancelled_job_is_idempotent(async_client, test_project, db_session):
    """POST /cancel on an already-cancelled job should return 200 with current state."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="cancelled", progress=0)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["data"]["status"] == "cancelled"


# ============================================================================
# 4. Cancel succeeded job returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_succeeded_job_returns_400(async_client, test_project, db_session):
    """POST /cancel on a succeeded job must return 400 Bad Request."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="succeeded", progress=100)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 5. Cancel failed job returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_cancel_failed_job_returns_400(async_client, test_project, db_session):
    """POST /cancel on a failed job must return 400 Bad Request."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="failed", progress=0, error_message="Oops")

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 6. Retry failed job creates new job
# ============================================================================


@pytest.mark.asyncio
async def test_retry_failed_job_creates_new_job(async_client, test_project, db_session):
    """POST /retry on a failed job should create a new pending job."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAIAVALAGFATVAQA"},
        ),
    )
    update_job_status(db_session, job.id, status="failed", progress=0, error_message="Oops")

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()["data"]
    assert data["original_job_id"] == job.id
    assert data["new_job_id"] != job.id
    assert data["status"] == "pending"

    # Verify new job copies input_json
    new_resp = await async_client.get(f"/api/v1/jobs/{data['new_job_id']}")
    new_data = new_resp.json()["data"]
    assert new_data["job_type"] == "bepipred3_scan"
    assert new_data["input_json"]["sequence"] == "MKKTAIAIAVALAGFATVAQA"


# ============================================================================
# 7. Retry cancelled job creates new job
# ============================================================================


@pytest.mark.asyncio
async def test_retry_cancelled_job_creates_new_job(async_client, test_project, db_session):
    """POST /retry on a cancelled job should create a new pending job."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="cancelled", progress=0)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()["data"]
    assert data["status"] == "pending"


# ============================================================================
# 8. Retry succeeded job returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_retry_succeeded_job_returns_400(async_client, test_project, db_session):
    """POST /retry on a succeeded job must return 400 Bad Request."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="succeeded", progress=100)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 9. Retry running job returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_retry_running_job_returns_400(async_client, test_project, db_session):
    """POST /retry on a running job must return 400 Bad Request."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    update_job_status(db_session, job.id, status="running", progress=50)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/retry")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# 10. Cooperative cancellation: background task does not write succeeded
# ============================================================================


@pytest.mark.asyncio
async def test_cooperative_cancellation_skips_success(db_session, test_project, monkeypatch):
    """If a job is cancelled before sidecar returns, run_real_job must not
    overwrite it to succeeded."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAVALAGFATVAQA"},
        ),
    )
    # Transition to running
    update_job_status(db_session, job.id, status="running", progress=10)
    # Immediately cancel
    update_job_status(db_session, job.id, status="cancelled", progress=10)

    # run_real_job should detect cancelled and return without writing succeeded
    updated = run_real_job(db_session, job_id=job.id)
    assert updated.status == "cancelled"
    assert updated.output_json is None or "candidate_count" not in str(updated.output_json)


# ============================================================================
# 11. Sidecar timeout error is structured
# ============================================================================


@pytest.mark.asyncio
async def test_sidecar_timeout_has_structured_error(db_session, test_project, monkeypatch):
    """When sidecar times out, error_message must contain [SIDECAR_TIMEOUT]."""

    def _raise_timeout(*a, **k):
        from app.services.bepipred3_adapter import BepiPred3SidecarError
        raise BepiPred3SidecarError("Sidecar timeout after 60.0s")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _raise_timeout,
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAVALAGFATVAQA"},
        ),
    )
    updated = run_real_job(db_session, job_id=job.id)
    assert updated.status == "failed"
    assert "[SIDECAR_TIMEOUT]" in updated.error_message


# ============================================================================
# 12. Sidecar unavailable error is structured
# ============================================================================


@pytest.mark.asyncio
async def test_sidecar_unavailable_has_structured_error(db_session, test_project, monkeypatch):
    """When sidecar is unavailable, error_message must contain [SIDECAR_UNAVAILABLE]."""

    def _raise_conn(*a, **k):
        from app.services.bepipred3_adapter import BepiPred3SidecarError
        raise BepiPred3SidecarError("Sidecar connection refused")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _raise_conn,
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAVALAGFATVAQA"},
        ),
    )
    updated = run_real_job(db_session, job_id=job.id)
    assert updated.status == "failed"
    assert "[SIDECAR_UNAVAILABLE]" in updated.error_message


# ============================================================================
# 13. User cancelled error is structured
# ============================================================================


@pytest.mark.asyncio
async def test_user_cancelled_has_structured_error(async_client, test_project, db_session):
    """When user cancels a job, error_message must contain [USER_CANCELLED]."""
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="bepipred3_scan", input_json={}),
    )
    resp = await async_client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert resp.status_code == status.HTTP_200_OK
    # Refresh from DB
    from app.crud.jobs import get_job
    refreshed = get_job(db_session, job.id)
    assert "[USER_CANCELLED]" in refreshed.error_message


# ============================================================================
# 14. Scientific integrity: no forbidden metrics
# ============================================================================


@pytest.mark.asyncio
async def test_error_output_no_forbidden_metrics(db_session, test_project, monkeypatch):
    """Even error output_json must not contain forbidden experimental metrics."""
    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        lambda *a, **k: {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0},
    )

    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAVALAGFATVAQA"},
        ),
    )
    updated = run_real_job(db_session, job_id=job.id)
    output_str = str(updated.output_json).lower()
    forbidden = ["mic", "mbc", "hemolysis", "toxicity", "iptm", "pdockq", "docking_score", "delta_g", "experimentally validated", "wet-lab"]
    for term in forbidden:
        assert term not in output_str, f"Forbidden term '{term}' found in output_json"
