"""Tests for experimental validation API endpoints."""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base, get_db
from app.main import create_app
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory DB session for each test."""
    # Ensure all ORM models are registered before creating tables
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="API Test Project"))


@pytest.fixture
def test_generation_run(db_session, test_project):
    return create_stamp_generation_run(
        db_session, StampGenerationRunCreate(project_id=test_project.id)
    )


@pytest.fixture
def test_candidate(db_session, test_project, test_generation_run):
    return create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="MKWVTFISLL",
            linker_seq="GGGGS",
            full_sequence="MKWVTFISLLGGGGS",
        ),
    )


@pytest.fixture
def test_app(db_session):
    """Create a FastAPI test app with overridden DB dependency."""
    # Ensure all ORM tables are registered and created in the test DB
    Base.metadata.create_all(bind=db_session.bind)

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


# ---------------------------------------------------------------------------
# 7. POST /runs returns 201
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_runs_returns_201(async_client, test_project, test_candidate):
    resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
            "organism": "Staphylococcus aureus",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["experiment_type"] == "MIC"
    assert data["status"] == "PLANNED"


# ---------------------------------------------------------------------------
# 8. GET /runs/{id} returns run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_run_returns_run(async_client, test_project, test_candidate):
    create_resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
        },
    )
    run_id = create_resp.json()["data"]["id"]
    resp = await async_client.get(f"/api/v1/experimental-validation/runs/{run_id}")
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == run_id


# ---------------------------------------------------------------------------
# 9. POST measurement updates status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_measurement_updates_status(async_client, test_project, test_candidate):
    run_resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
        },
    )
    run_id = run_resp.json()["data"]["id"]

    # Candidate should now be EXPERIMENT_PLANNED because a run was created
    cand_resp = await async_client.get(f"/api/v1/stamp-candidates/{test_candidate.id}")
    assert cand_resp.json()["data"]["validation_status"] == "EXPERIMENT_PLANNED"

    # Add measurement
    meas_resp = await async_client.post(
        f"/api/v1/experimental-validation/runs/{run_id}/measurements",
        json={
            "validation_run_id": run_id,
            "candidate_id": test_candidate.id,
            "metric_name": "MIC_ug_ml",
            "value": 2.0,
            "unit": "ug/ml",
            "quality_flag": "PASS",
        },
    )
    assert meas_resp.status_code == 201

    # Update run to COMPLETED
    patch_resp = await async_client.patch(
        f"/api/v1/experimental-validation/runs/{run_id}/status?status=COMPLETED"
    )
    assert patch_resp.status_code == 200

    # Now candidate should be PARTIALLY_VALIDATED (has activity but no safety)
    cand_resp2 = await async_client.get(f"/api/v1/stamp-candidates/{test_candidate.id}")
    assert cand_resp2.json()["data"]["validation_status"] == "PARTIALLY_VALIDATED"


# ---------------------------------------------------------------------------
# 10. Invalid experiment_type returns 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_invalid_experiment_type_returns_422(async_client, test_project, test_candidate):
    resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "INVALID_TYPE",
        },
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# 11. Negative MIC returns 422
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negative_mic_returns_422(async_client, test_project, test_candidate):
    run_resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
        },
    )
    run_id = run_resp.json()["data"]["id"]
    resp = await async_client.post(
        f"/api/v1/experimental-validation/runs/{run_id}/measurements",
        json={
            "validation_run_id": run_id,
            "candidate_id": test_candidate.id,
            "metric_name": "MIC_ug_ml",
            "value": -5.0,
            "unit": "ug/ml",
            "quality_flag": "PASS",
        },
    )
    assert resp.status_code == 422
