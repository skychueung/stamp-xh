"""Tests for structure_prediction_persistence (v0.10-P6d).

Validates that real LocalColabFold structure metrics are written to
stamp_candidate.metrics['structure_prediction'] without overwriting
other metric keys and without fabricating wet-lab metrics.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.jobs import create_job, update_job_status
from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate
from app.database import Base, get_db
from app.main import create_app
from app.models.orm import Job
from app.schemas import (
    JobCreate,
    ProjectCreate,
    StampCandidateCreate,
)
from app.crud.stamp_candidates import get_stamp_candidate
from app.services.structure_prediction_persistence import (
    FORBIDDEN_METRIC_KEYS,
    persist_structure_prediction_to_candidate,
)

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
    proj = create_project(db_session, ProjectCreate(name="Structure Prediction Persistence Test"))
    return proj


@pytest.fixture
def test_candidate(db_session, test_project):
    cand = create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            targeting_peptide_seq="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP",
            linker_seq="EAAAK",
            full_sequence="MKTAYIAKQRQISFVKSHFSRQDILDLWIYHTQGYFP",
            metrics={"biophysical": {"length": 39, "net_charge": 3.0}},
        ),
    )
    return cand


@pytest.fixture
def test_app(db_session):
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
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_succeeded_structure_prediction_job(db_session, candidate_id, **output_overrides):
    """Create a succeeded structure_prediction job with realistic output."""
    output = {
        "job_type": "structure_prediction",
        "mode": "LOCALCOLABFOLD_IMPORTED_RESULT",
        "model_source": "LocalColabFold",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY",
        "metrics_are_real": True,
        "mean_plddt": 65.23,
        "ptm": 0.28,
        "iptm": None,
        "structure_file": "/home/xh/kxc/tools/localcolabfold/runs/smoke_20260510_111732/gpu_attempt/smoke_gpu_20260510_111732__0_unrelaxed_rank_001_alphafold2_ptm_model_1_seed_000.pdb",
        "pae_file": "/home/xh/kxc/tools/localcolabfold/runs/smoke_20260510_111732/gpu_attempt/smoke_gpu_20260510_111732__0_pae.png",
        "raw_score_json": "/home/xh/kxc/tools/localcolabfold/runs/smoke_20260510_111732/gpu_attempt/smoke_gpu_20260510_111732__0_scores_rank_001_alphafold2_ptm_model_1_seed_000.json",
        "source_result_dir": "/home/xh/kxc/tools/localcolabfold/runs/smoke_20260510_111732/gpu_attempt",
        "candidate_id": candidate_id,
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
    }
    output.update(output_overrides)

    job = create_job(
        db_session,
        JobCreate(
            project_id="test-project-id",
            job_type="structure_prediction",
            input_json={"candidate_id": candidate_id, "result_dir": "/tmp/test"},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        message="Execution completed successfully",
        output_json=output,
    )
    return job


# ---------------------------------------------------------------------------
# Success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_succeeded_job_writes_metrics(
    async_client, db_session, test_project, test_candidate
):
    """A succeeded structure_prediction job can be persisted to candidate metrics."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["candidate_id"] == test_candidate.id
    assert data["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_persist_mean_plddt_value(async_client, db_session, test_project, test_candidate):
    """mean_plddt=65.23 must be written to candidate metrics."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["mean_plddt"] == 65.23


@pytest.mark.asyncio
async def test_persist_ptm_value(async_client, db_session, test_project, test_candidate):
    """ptm=0.28 must be written to candidate metrics."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["ptm"] == 0.28


@pytest.mark.asyncio
async def test_persist_iptm_null(async_client, db_session, test_project, test_candidate):
    """iptm must remain null for monomer run."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["iptm"] is None


@pytest.mark.asyncio
async def test_persist_validation_status(async_client, db_session, test_project, test_candidate):
    """validation_status must remain NOT_EXPERIMENTALLY_VALIDATED."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
async def test_persist_prediction_status(async_client, db_session, test_project, test_candidate):
    """prediction_status must remain COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["prediction_status"] == "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"


@pytest.mark.asyncio
async def test_persist_metrics_are_real(async_client, db_session, test_project, test_candidate):
    """metrics_are_real must be true."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["metrics_are_real"] is True


@pytest.mark.asyncio
async def test_persist_preserves_existing_metrics(
    async_client, db_session, test_project, test_candidate
):
    """Existing candidate.metrics keys must not be overwritten."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    # Refresh candidate from DB
    from app.crud.stamp_candidates import get_stamp_candidate

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert "biophysical" in cand.metrics
    assert "structure_prediction" in cand.metrics
    assert cand.metrics["biophysical"]["length"] == 39


@pytest.mark.asyncio
async def test_persist_forbidden_metrics_are_null(
    async_client, db_session, test_project, test_candidate
):
    """pDockQ / delta_G / docking_score must be null in persisted metrics."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    sp = cand.metrics["structure_prediction"]
    assert sp["forbidden_metrics"]["pDockQ"] is None
    assert sp["forbidden_metrics"]["delta_G"] is None
    assert sp["forbidden_metrics"]["docking_score"] is None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_job_not_found(async_client):
    """Non-existent job must return 404."""
    resp = await async_client.post(
        "/api/v1/jobs/nonexistent-job-id/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_persist_wrong_job_type(async_client, db_session, test_project):
    """Job with wrong job_type must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="epitope_scan",
            input_json={},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={"mean_plddt": 65.23},
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_job_not_succeeded(async_client, db_session, test_project, test_candidate):
    """Job not in succeeded status must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="structure_prediction",
            input_json={"candidate_id": test_candidate.id},
        ),
    )
    # job remains pending

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_missing_output_json(async_client, db_session, test_project, test_candidate):
    """Job with missing output_json must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="structure_prediction",
            input_json={"candidate_id": test_candidate.id},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json=None,
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_missing_candidate_id(async_client, db_session, test_project):
    """Job with missing candidate_id must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="structure_prediction",
            input_json={},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={"mean_plddt": 65.23},
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_candidate_not_found(async_client, db_session, test_project):
    """Candidate that does not exist must return 404."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="structure_prediction",
            input_json={},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={"candidate_id": "nonexistent-candidate", "mean_plddt": 65.23},
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_persist_pdockq_value_rejected(async_client, db_session, test_project, test_candidate):
    """output_json containing non-null pDockQ must return 400."""
    job = _make_succeeded_structure_prediction_job(
        db_session, test_candidate.id, pDockQ=0.75
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_delta_g_value_rejected(async_client, db_session, test_project, test_candidate):
    """output_json containing non-null delta_G must return 400."""
    job = _make_succeeded_structure_prediction_job(
        db_session, test_candidate.id, delta_G=-8.5
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_docking_score_value_rejected(
    async_client, db_session, test_project, test_candidate
):
    """output_json containing non-null docking_score must return 400."""
    job = _make_succeeded_structure_prediction_job(
        db_session, test_candidate.id, docking_score=-7.2
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-structure-prediction-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ---------------------------------------------------------------------------
# Direct service tests
# ---------------------------------------------------------------------------


def test_service_persist_succeeded_job(db_session, test_project, test_candidate):
    """Direct call: succeeded job persists correctly."""
    job = _make_succeeded_structure_prediction_job(db_session, test_candidate.id)
    result = persist_structure_prediction_to_candidate(db_session, job.id)
    assert result["mean_plddt"] == 65.23
    assert result["ptm"] == 0.28
    assert result["iptm"] is None


def test_service_null_mean_plddt_raises(db_session, test_project, test_candidate):
    """Direct call: null mean_plddt in output_json must raise ValueError."""
    job = _make_succeeded_structure_prediction_job(
        db_session, test_candidate.id, mean_plddt=None
    )
    with pytest.raises(ValueError, match="mean_plddt"):
        persist_structure_prediction_to_candidate(db_session, job.id)
