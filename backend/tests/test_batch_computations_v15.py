"""Tests for BatchComputation v1.5 extensions.

Covers:
- artifact listing endpoint
- log reading endpoint
- report endpoint
- download endpoints (zip, json, csv, md)
- output_json inclusion in BatchItemResponse
"""

from __future__ import annotations

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


@pytest.mark.asyncio
async def test_item_response_includes_output_json(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Test Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
        "input_json": {"sequence": "MKKTAIAATAVLATA"},
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    batch_id = create_resp.json()["id"]

    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    assert items_resp.status_code == 200
    items = items_resp.json()
    assert len(items) == 1
    assert "output_json" in items[0]


@pytest.mark.asyncio
async def test_artifact_listing_empty(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Artifact Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]
    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    item_id = items_resp.json()[0]["id"]

    artifacts_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items/{item_id}/artifacts")
    assert artifacts_resp.status_code == 200
    assert artifacts_resp.json() == []


@pytest.mark.asyncio
async def test_log_reading_empty(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Log Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]
    items_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items")
    item_id = items_resp.json()[0]["id"]

    logs_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/items/{item_id}/logs")
    assert logs_resp.status_code == 200
    data = logs_resp.json()
    assert data["exists"] is False
    assert data["stdout"] == ""
    assert data["stderr"] == ""


@pytest.mark.asyncio
async def test_report_endpoint(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "Report Batch",
        "job_type": "MMGBSA",
        "candidate_ids": ["cand-1", "cand-2"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    report_resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/report")
    assert report_resp.status_code == 200
    data = report_resp.json()
    assert data["batch_id"] == batch_id
    assert data["job_type"] == "MMGBSA"
    assert data["total_items"] == 2
    assert "md_results" in data
    assert "flexpepdock_results" in data
    assert "mmgbsa_results" in data


@pytest.mark.asyncio
async def test_download_json(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "DL Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/download?format=json")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_download_csv(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "DL Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/download?format=csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "text/csv; charset=utf-8"
    body = resp.text
    assert "item_id" in body


@pytest.mark.asyncio
async def test_download_md(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "DL Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/download?format=md")
    assert resp.status_code == 200
    body = resp.text
    assert "# Batch Report" in body


@pytest.mark.asyncio
async def test_download_zip(async_client: AsyncClient):
    payload = {
        "project_id": "proj-1",
        "name": "DL Batch",
        "job_type": "COLABFOLD",
        "candidate_ids": ["cand-1"],
    }
    create_resp = await async_client.post("/api/v1/batch-computations", json=payload)
    batch_id = create_resp.json()["id"]

    resp = await async_client.get(f"/api/v1/batch-computations/{batch_id}/download?format=zip")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/zip"
