"""Tests for interface quality persistence (v0.10-P6j).

Validates that real pDockQ interface-quality metrics are written to
stamp_candidate.metrics['interface_quality'] without overwriting
structure_prediction or other metric keys.
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
from app.crud.stamp_candidates import create_stamp_candidate, get_stamp_candidate
from app.database import Base, get_db
from app.main import create_app
from app.schemas import (
    JobCreate,
    ProjectCreate,
    StampCandidateCreate,
)
from app.services.interface_quality_persistence import (
    FORBIDDEN_METRIC_KEYS,
    persist_interface_quality_to_candidate,
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
    proj = create_project(db_session, ProjectCreate(name="Interface Quality Persistence Test"))
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
            metrics={
                "biophysical": {"length": 39, "net_charge": 3.0},
                "structure_prediction": {
                    "mean_plddt": 42.9,
                    "ptm": 0.315,
                    "iptm": 0.0909,
                    "forbidden_metrics": {
                        "pDockQ": None,
                        "delta_G": None,
                        "docking_score": None,
                    },
                },
            },
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


def _make_succeeded_complex_job(db_session, candidate_id, pdb_path: str | None = None, **output_overrides):
    """Create a succeeded complex_structure_prediction job with realistic output."""
    import os
    # Use real fixture PDB
    fixtures_dir = os.path.join(os.path.dirname(__file__), "fixtures", "complex_interface_parser")
    default_pdb = os.path.join(fixtures_dir, "complex_unrelaxed.pdb")
    default_pae = os.path.join(fixtures_dir, "predicted_aligned_error.json")

    output = {
        "job_type": "complex_structure_prediction",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY",
        "metrics_are_real": True,
        "candidate_id": candidate_id,
        "complex_structure_file": pdb_path or default_pdb,
        "pae_file": default_pae,
        "chain_mapping": {"A": "target", "B": "peptide"},
    }
    output.update(output_overrides)

    job = create_job(
        db_session,
        JobCreate(
            project_id="test-project-id",
            job_type="complex_structure_prediction",
            input_json={"candidate_id": candidate_id},
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
async def test_persist_succeeded_job_writes_interface_quality(
    async_client, db_session, test_project, test_candidate
):
    """A succeeded complex_structure_prediction job can be persisted to candidate metrics."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["candidate_id"] == test_candidate.id
    assert data["status"] == "COMPLETED"
    assert data["pdockq"] is not None
    assert 0.0 <= data["pdockq"] <= 1.0


@pytest.mark.asyncio
async def test_persist_pdockq_value(async_client, db_session, test_project, test_candidate):
    """pDockQ must be a real numeric value in the response."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["pdockq"] == pytest.approx(0.644, abs=0.01)


@pytest.mark.asyncio
async def test_persist_interface_contact_count(async_client, db_session, test_project, test_candidate):
    """interface_contact_count must be present in response."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["interface_contact_count"] == 149


@pytest.mark.asyncio
async def test_persist_interface_plddt_mean(async_client, db_session, test_project, test_candidate):
    """interface_residue_plddt_mean must be present in response."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["interface_residue_plddt_mean"] == pytest.approx(37.62, abs=0.01)


@pytest.mark.asyncio
async def test_persist_validation_status(async_client, db_session, test_project, test_candidate):
    """validation_status must remain NOT_EXPERIMENTALLY_VALIDATED."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
async def test_persist_prediction_status(async_client, db_session, test_project, test_candidate):
    """prediction_status must be COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["prediction_status"] == "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"


@pytest.mark.asyncio
async def test_persist_metrics_are_real(async_client, db_session, test_project, test_candidate):
    """metrics_are_real must be true."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["metrics_are_real"] is True


@pytest.mark.asyncio
async def test_persist_preserves_existing_metrics(
    async_client, db_session, test_project, test_candidate
):
    """Existing candidate.metrics keys must not be overwritten."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert "biophysical" in cand.metrics
    assert "structure_prediction" in cand.metrics
    assert "interface_quality" in cand.metrics
    assert cand.metrics["biophysical"]["length"] == 39


@pytest.mark.asyncio
async def test_persist_interface_quality_not_in_structure_prediction(
    async_client, db_session, test_project, test_candidate
):
    """pDockQ must NOT be written into structure_prediction."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    sp = cand.metrics["structure_prediction"]
    assert sp.get("pDockQ") is None
    assert "pdockq" not in sp


@pytest.mark.asyncio
async def test_persist_forbidden_metrics_are_null(
    async_client, db_session, test_project, test_candidate
):
    """delta_G / docking_score must be null in persisted interface_quality."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    iq = cand.metrics["interface_quality"]
    assert iq["forbidden_metrics"]["delta_G"] is None
    assert iq["forbidden_metrics"]["docking_score"] is None


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_job_not_found(async_client):
    """Non-existent job must return 404."""
    resp = await async_client.post(
        "/api/v1/jobs/nonexistent-job-id/persist-interface-quality-results"
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
        output_json={},
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_job_not_succeeded(async_client, db_session, test_project, test_candidate):
    """Job not in succeeded status must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="complex_structure_prediction",
            input_json={"candidate_id": test_candidate.id},
        ),
    )
    # job remains pending

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_missing_pdb_path(async_client, db_session, test_project, test_candidate):
    """Job with missing complex_structure_file must return 400."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)
    # Explicitly remove the PDB path from output_json
    from app.crud.jobs import update_job_status
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={
            **(job.output_json or {}),
            "complex_structure_file": None,
            "structure_file": None,
        },
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_candidate_not_found(async_client, db_session, test_project):
    """Candidate that does not exist must return 404."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="complex_structure_prediction",
            input_json={},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={
            "candidate_id": "nonexistent-candidate",
            "complex_structure_file": "fake.pdb",
        },
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-interface-quality-results"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Direct service tests
# ---------------------------------------------------------------------------


def test_service_persist_succeeded_job(db_session, test_project, test_candidate):
    """Direct call: succeeded job persists correctly."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)
    result = persist_interface_quality_to_candidate(db_session, job.id)
    assert result["pdockq"] == pytest.approx(0.644, abs=0.01)
    assert result["interface_contact_count"] == 149


def test_service_persist_creates_interface_quality_in_db(db_session, test_project, test_candidate):
    """Direct call: candidate.metrics['interface_quality'] is created."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)
    persist_interface_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert "interface_quality" in cand.metrics
    iq = cand.metrics["interface_quality"]
    assert iq["pdockq"] == pytest.approx(0.644, abs=0.01)
    assert iq["forbidden_metrics"]["delta_G"] is None
    assert iq["forbidden_metrics"]["docking_score"] is None


def test_service_persist_preserves_structure_prediction(db_session, test_project, test_candidate):
    """Direct call: structure_prediction metrics are not overwritten."""
    job = _make_succeeded_complex_job(db_session, test_candidate.id)
    persist_interface_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    sp = cand.metrics["structure_prediction"]
    assert sp["mean_plddt"] == 42.9
    assert sp["ptm"] == 0.315
    assert sp["iptm"] == 0.0909
