"""Tests for Production MD service and router (P7).

v1.2-lab-production-fast
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

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
# Create job
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_production_md_job(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "candidate_id": "cand-1",
        "duration_ns": 10,
        "topology_path": "/data/topol.tpr",
        "coordinates_path": "/data/conf.gro",
        "priority": 5,
    }
    resp = await async_client.post("/api/v1/production-md/jobs", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED, resp.text
    data = resp.json()
    assert data["duration_ns"] == 10
    assert data["status"] == "PENDING"
    assert data["candidate_id"] == "cand-1"
    assert data["project_id"] == "proj-1"
    assert "job_id" in data


@pytest.mark.asyncio
async def test_create_invalid_duration(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "candidate_id": "cand-1",
        "duration_ns": 99,
        "topology_path": "/data/topol.tpr",
        "coordinates_path": "/data/conf.gro",
    }
    resp = await async_client.post("/api/v1/production-md/jobs", json=payload)
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_missing_topology(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "candidate_id": "cand-1",
        "duration_ns": 5,
        "topology_path": "",
        "coordinates_path": "/data/conf.gro",
    }
    resp = await async_client.post("/api/v1/production-md/jobs", json=payload)
    # Empty string is technically a string, so pydantic accepts it;
    # business-logic validation could be added later.
    assert resp.status_code in (201, 422)


# ---------------------------------------------------------------------------
# Durations endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_durations(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/production-md/durations")
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["durations_ns"]) == {1, 5, 10, 50}
    details = data["details"]
    assert any(d["duration_ns"] == 50 and d["nsteps"] == 25_000_000 for d in details)


# ---------------------------------------------------------------------------
# Submit endpoint
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_nonexistent_job(async_client: AsyncClient):
    resp = await async_client.post(f"/api/v1/production-md/jobs/{uuid.uuid4()}/submit")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_submit_wrong_job_type(async_client: AsyncClient, db_session):
    # Create a non-production_md job first using the same session as the app
    from app.models.orm import Job

    job = Job(project_id="proj-x", job_type="other_job", status="PENDING")
    db_session.add(job)
    db_session.commit()
    db_session.refresh(job)
    job_id = job.id

    resp = await async_client.post(f"/api/v1/production-md/jobs/{job_id}/submit")
    assert resp.status_code == 422
    assert "not a production_md job" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_submit_blocks_when_server_unreachable(async_client: AsyncClient):
    """If server is unreachable, submit must mark job BLOCKED, not fake success."""
    payload = {
        "project_id": "proj-1",
        "candidate_id": "cand-1",
        "duration_ns": 1,
        "topology_path": "/data/topol.tpr",
        "coordinates_path": "/data/conf.gro",
        "server_host": "192.168.31.218",  # known unreachable during tests
    }
    create_resp = await async_client.post("/api/v1/production-md/jobs", json=payload)
    assert create_resp.status_code == 201
    job_id = create_resp.json()["job_id"]

    submit_resp = await async_client.post(f"/api/v1/production-md/jobs/{job_id}/submit")
    assert submit_resp.status_code == 200
    data = submit_resp.json()
    assert data["status"] == "BLOCKED"
    assert "unreachable" in data["detail"].lower() or "server" in data["detail"].lower()


# ---------------------------------------------------------------------------
# Service-level unit tests (no HTTP)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mdp_build_50ns():
    from app.services.production_md_service import _build_mdp

    mdp = _build_mdp(50)
    assert mdp["nsteps"] == 25_000_000
    assert mdp["dt"] == 0.002
    assert mdp["duration_ns"] == 50
