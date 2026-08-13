"""Tests for v1.2-lab-production-fast Day 1 skeleton (P1+P2+P4+P5)."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.audit_logs import list_audit_logs
from app.crud.compute_batches import create_batch, get_batch, list_batches_by_project, update_batch_status
from app.crud.file_assets import create_asset, get_asset, list_assets_by_job
from app.crud.jobs import create_job, get_job
from app.database import Base, get_db
from app.main import create_app
from app.schemas import JobCreate
from app.services.audit_log_service import log_job_failed, log_job_submit, log_job_success
from app.services.retry_policy import should_retry

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
# Job model extension
# ---------------------------------------------------------------------------

def test_job_extended_fields(db_session):
    job = create_job(db_session, JobCreate(project_id="proj-1", job_type="report_export", input_json={"x": 1}))
    job.candidate_id = "cand-1"
    job.batch_id = "batch-1"
    job.retry_count = 0
    job.max_retries = 3
    job.server_host = "192.168.31.218"
    job.priority = 5
    job.error_json = {"code": "TEST"}
    job.artifacts_json = {"files": []}
    db_session.commit()
    db_session.refresh(job)

    fetched = get_job(db_session, job.id)
    assert fetched.candidate_id == "cand-1"
    assert fetched.batch_id == "batch-1"
    assert fetched.retry_count == 0
    assert fetched.max_retries == 3
    assert fetched.server_host == "192.168.31.218"
    assert fetched.priority == 5
    assert fetched.error_json == {"code": "TEST"}
    assert fetched.artifacts_json == {"files": []}


# ---------------------------------------------------------------------------
# ComputeBatch CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_batch(db_session):
    batch = create_batch(db_session, "proj-1", "structure_pipeline", ["c1", "c2"], ["colabfold", "foldx"])
    assert batch.id is not None
    assert batch.status == "PENDING"

    fetched = get_batch(db_session, batch.id)
    assert fetched.project_id == "proj-1"
    assert fetched.candidate_ids == ["c1", "c2"]


def test_list_batches_by_project(db_session):
    create_batch(db_session, "proj-1", "t1", ["c1"], ["s1"])
    create_batch(db_session, "proj-1", "t2", ["c2"], ["s2"])
    create_batch(db_session, "proj-2", "t3", ["c3"], ["s3"])
    results = list_batches_by_project(db_session, "proj-1")
    assert len(results) == 2


def test_update_batch_status(db_session):
    batch = create_batch(db_session, "proj-1", "t", ["c1"], ["s1"])
    updated = update_batch_status(db_session, batch.id, "RUNNING", summary_json={"running": 1})
    assert updated.status == "RUNNING"
    assert updated.summary_json["running"] == 1


# ---------------------------------------------------------------------------
# FileAsset CRUD
# ---------------------------------------------------------------------------

def test_create_and_get_asset(db_session):
    asset = create_asset(db_session, "job-1", "cand-1", "batch-1", "pdb", "model.pdb", "/data/model.pdb", 1024, "abc123")
    assert asset.id is not None
    assert asset.file_type == "pdb"

    fetched = get_asset(db_session, asset.id)
    assert fetched.sha256 == "abc123"
    assert fetched.size_bytes == 1024


def test_list_assets_by_job(db_session):
    create_asset(db_session, "job-1", None, None, "log", "a.log", "/a.log", 10)
    create_asset(db_session, "job-1", None, None, "pdb", "b.pdb", "/b.pdb", 20)
    create_asset(db_session, "job-2", None, None, "csv", "c.csv", "/c.csv", 30)
    results = list_assets_by_job(db_session, "job-1")
    assert len(results) == 2


# ---------------------------------------------------------------------------
# AuditLog CRUD
# ---------------------------------------------------------------------------

def test_create_and_list_audit_logs(db_session):
    log_job_submit(db_session, "job-1", user_id="user-a")
    log_job_success(db_session, "job-1", user_id="user-a")
    log_job_failed(db_session, "job-2", {"code": "FAIL"}, user_id="user-b")

    entries = list_audit_logs(db_session, entity_type="job")
    assert len(entries) == 3

    user_a_entries = list_audit_logs(db_session, user_id="user-a")
    assert len(user_a_entries) == 2


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

def test_should_retry_retryable(db_session):
    job = create_job(db_session, JobCreate(project_id="proj-1", job_type="colabfold", input_json={}))
    job.status = "FAILED"
    job.retry_count = 0
    job.max_retries = 3
    job.error_json = {"error_code": "COMPUTE_TIMEOUT"}
    db_session.commit()
    assert should_retry(job) is True


def test_should_retry_max_retries_exceeded(db_session):
    job = create_job(db_session, JobCreate(project_id="proj-1", job_type="colabfold", input_json={}))
    job.status = "FAILED"
    job.retry_count = 3
    job.max_retries = 3
    job.error_json = {"error_code": "COMPUTE_TIMEOUT"}
    db_session.commit()
    assert should_retry(job) is False


def test_should_retry_non_retryable(db_session):
    job = create_job(db_session, JobCreate(project_id="proj-1", job_type="colabfold", input_json={}))
    job.status = "FAILED"
    job.retry_count = 0
    job.max_retries = 3
    job.error_json = {"error_code": "INPUT_INVALID"}
    db_session.commit()
    assert should_retry(job) is False


# ---------------------------------------------------------------------------
# Batch router API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_batch_create_and_get(async_client):
    resp = await async_client.post(
        "/api/v1/batches?project_id=proj-1&batch_type=structure_pipeline&candidate_ids=c1&candidate_ids=c2&pipeline_stages=colabfold&pipeline_stages=foldx"
    )
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()["data"]
    batch_id = data["batch_id"]

    resp2 = await async_client.get(f"/api/v1/batches/{batch_id}")
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["data"]["batch_type"] == "structure_pipeline"


@pytest.mark.asyncio
async def test_batch_list(async_client):
    await async_client.post(
        "/api/v1/batches?project_id=proj-x&batch_type=t&candidate_ids=c1&pipeline_stages=s1"
    )
    resp = await async_client.get("/api/v1/batches?project_id=proj-x")
    assert resp.status_code == status.HTTP_200_OK
    assert len(resp.json()["data"]) >= 1


# ---------------------------------------------------------------------------
# File asset router API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_asset_create_and_get(async_client):
    resp = await async_client.post(
        "/api/v1/assets?job_id=job-1&file_type=pdb&original_filename=model.pdb&storage_path=/data/model.pdb&size_bytes=1024&sha256=abc123"
    )
    assert resp.status_code == status.HTTP_201_CREATED
    asset_id = resp.json()["data"]["asset_id"]

    resp2 = await async_client.get(f"/api/v1/assets/{asset_id}")
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["data"]["sha256"] == "abc123"


# ---------------------------------------------------------------------------
# Audit log router API
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_query(async_client):
    resp = await async_client.get("/api/v1/audit-log?entity_type=job&limit=10")
    assert resp.status_code == status.HTTP_200_OK
    # Should return list (may be empty if no events seeded)
    assert isinstance(resp.json()["data"], list)


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated metrics in batch/export
# ---------------------------------------------------------------------------

def test_batch_no_fabricated_metrics(db_session):
    batch = create_batch(db_session, "proj-1", "full_validation", ["c1"], ["mmgbsa"])
    assert batch.status == "PENDING"
    # batch summary should not invent success counts
    assert batch.summary_json["succeeded"] == 0
