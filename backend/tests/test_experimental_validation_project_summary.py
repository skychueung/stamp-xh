"""Tests for experimental validation project summary API."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base, get_db
from app.main import create_app
import app.models.orm  # noqa: F401
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="Summary Test Project"))


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
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# 1. Project summary returns status counts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_summary_returns_status_counts(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/summary"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["project_id"] == test_project.id
    assert data["total_candidates"] == 1
    assert "validation_status_counts" in data
    assert data["validation_status_counts"]["NOT_EXPERIMENTALLY_VALIDATED"] == 1


# ---------------------------------------------------------------------------
# 2. No measurements → coverage = 0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_summary_no_measurements_coverage_zero(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/summary"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["coverage"]["candidates_with_any_measurement"] == 0
    assert data["coverage"]["experimental_coverage_percent"] == 0.0


# ---------------------------------------------------------------------------
# 3. MIC measurement → measurement_counts correct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_summary_mic_measurement_count(async_client, test_project, test_candidate):
    # Create run + measurement
    run_resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "MIC",
        },
    )
    run_id = run_resp.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/experimental-validation/runs/{run_id}/measurements",
        json={
            "validation_run_id": run_id,
            "candidate_id": test_candidate.id,
            "metric_name": "MIC_ug_ml",
            "value": 2.5,
            "unit": "ug/ml",
        },
    )

    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/summary"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["measurement_counts"]["MIC_ug_ml"] == 1
    assert data["coverage"]["candidates_with_mic"] == 1


# ---------------------------------------------------------------------------
# 4. Hemolysis measurement → safety coverage correct
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_summary_hemolysis_safety_coverage(async_client, test_project, test_candidate):
    run_resp = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={
            "project_id": test_project.id,
            "candidate_id": test_candidate.id,
            "experiment_type": "HEMOLYSIS",
        },
    )
    run_id = run_resp.json()["data"]["id"]

    await async_client.post(
        f"/api/v1/experimental-validation/runs/{run_id}/measurements",
        json={
            "validation_run_id": run_id,
            "candidate_id": test_candidate.id,
            "metric_name": "hemolysis_percent",
            "value": 12.5,
            "unit": "%",
        },
    )

    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/summary"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["measurement_counts"]["hemolysis_percent"] == 1
    assert data["coverage"]["candidates_with_safety"] == 1


# ---------------------------------------------------------------------------
# 5. Top priority candidates populated when validated
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_summary_top_priority_candidates(async_client, test_project, test_candidate):
    # Need activity + safety + PASS to become EXPERIMENTALLY_VALIDATED
    run1 = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={"project_id": test_project.id, "candidate_id": test_candidate.id, "experiment_type": "MIC"},
    )
    run1_id = run1.json()["data"]["id"]
    await async_client.patch(f"/api/v1/experimental-validation/runs/{run1_id}/status?status=COMPLETED")
    await async_client.post(
        f"/api/v1/experimental-validation/runs/{run1_id}/measurements",
        json={"validation_run_id": run1_id, "candidate_id": test_candidate.id, "metric_name": "MIC_ug_ml", "value": 2.0, "unit": "ug/ml", "quality_flag": "PASS"},
    )

    run2 = await async_client.post(
        "/api/v1/experimental-validation/runs",
        json={"project_id": test_project.id, "candidate_id": test_candidate.id, "experiment_type": "HEMOLYSIS"},
    )
    run2_id = run2.json()["data"]["id"]
    await async_client.patch(f"/api/v1/experimental-validation/runs/{run2_id}/status?status=COMPLETED")
    await async_client.post(
        f"/api/v1/experimental-validation/runs/{run2_id}/measurements",
        json={"validation_run_id": run2_id, "candidate_id": test_candidate.id, "metric_name": "hemolysis_percent", "value": 5.0, "unit": "%", "quality_flag": "PASS"},
    )

    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/summary"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert len(data["top_priority_candidates"]) >= 1
    top = data["top_priority_candidates"][0]
    assert top["candidate_id"] == test_candidate.id
    assert top["validation_status"] == "EXPERIMENTALLY_VALIDATED"
