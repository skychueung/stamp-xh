"""Tests for energy quality persistence (v0.10-P6m).

Validates that real FoldX interaction-energy metrics are written to
stamp_candidate.metrics['energy_quality'] without overwriting
interface_quality or structure_prediction.
"""

from __future__ import annotations

from pathlib import Path

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
from app.services.energy_quality_persistence import (
    EnergyQualityError,
    persist_energy_quality_to_candidate,
    persist_energy_quality_to_candidate_by_fxout,
)

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "foldx_output"
REAL_FXOUT = FIXTURES_DIR / "Interaction_complex_unrelaxed_Repair_AC.fxout"


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
    proj = create_project(db_session, ProjectCreate(name="Energy Quality Persistence Test"))
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
                "interface_quality": {
                    "pdockq": 0.644,
                    "interface_contact_count": 149,
                    "forbidden_metrics": {"delta_G": None, "docking_score": None},
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


def _make_succeeded_energy_job(db_session, candidate_id, fxout_path: str | None = None, **output_overrides):
    """Create a succeeded job with realistic FoldX output."""
    output = {
        "job_type": "energy_estimation",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY",
        "metrics_are_real": True,
        "candidate_id": candidate_id,
        "interaction_fxout": fxout_path or str(REAL_FXOUT),
    }
    output.update(output_overrides)

    job = create_job(
        db_session,
        JobCreate(
            project_id="test-project-id",
            job_type="energy_estimation",
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
# Router success cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_succeeded_job_writes_energy_quality(
    async_client, db_session, test_project, test_candidate
):
    """A succeeded job can be persisted to candidate metrics."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["candidate_id"] == test_candidate.id
    assert data["status"] == "COMPLETED"
    assert data["interaction_energy_kcal_mol"] is not None
    assert data["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)


@pytest.mark.asyncio
async def test_persist_energy_terms(async_client, db_session, test_project, test_candidate):
    """Energy terms must be present in response."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    terms = data["energy_terms"]
    assert terms["vdw_clashes"] == pytest.approx(89.0375, abs=0.001)
    assert terms["backbone_hbond"] == pytest.approx(-4.28945, abs=0.0001)


@pytest.mark.asyncio
async def test_persist_quality_flags(async_client, db_session, test_project, test_candidate):
    """Quality flags must be present in response."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    qf = data["quality_flags"]
    assert qf["unfavorable_interaction_energy"] is True
    assert qf["high_vdw_clashes"] is True


@pytest.mark.asyncio
async def test_persist_validation_status(async_client, db_session, test_project, test_candidate):
    """validation_status must remain NOT_EXPERIMENTALLY_VALIDATED."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
async def test_persist_prediction_status(async_client, db_session, test_project, test_candidate):
    """prediction_status must be COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"


@pytest.mark.asyncio
async def test_persist_metrics_are_real(async_client, db_session, test_project, test_candidate):
    """metrics_are_real must be true."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["metrics_are_real"] is True


@pytest.mark.asyncio
async def test_persist_preserves_existing_metrics(
    async_client, db_session, test_project, test_candidate
):
    """Existing candidate.metrics keys must not be overwritten."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert "biophysical" in cand.metrics
    assert "structure_prediction" in cand.metrics
    assert "interface_quality" in cand.metrics
    assert "energy_quality" in cand.metrics
    assert cand.metrics["biophysical"]["length"] == 39


@pytest.mark.asyncio
async def test_persist_energy_quality_not_in_structure_prediction(
    async_client, db_session, test_project, test_candidate
):
    """energy_quality must NOT be written into structure_prediction."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    sp = cand.metrics["structure_prediction"]
    assert "interaction_energy_kcal_mol" not in sp
    assert "energy_terms" not in sp
    assert sp["mean_plddt"] == 42.9


@pytest.mark.asyncio
async def test_persist_energy_quality_not_in_interface_quality(
    async_client, db_session, test_project, test_candidate
):
    """energy_quality fields must NOT be written into interface_quality."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    iq = cand.metrics["interface_quality"]
    assert "interaction_energy_kcal_mol" not in iq
    assert "energy_terms" not in iq
    assert iq["pdockq"] == 0.644


@pytest.mark.asyncio
async def test_persist_forbidden_metrics_are_null(
    async_client, db_session, test_project, test_candidate
):
    """docking_score / mmgbsa_delta_G / experimental_delta_G must be null."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_200_OK

    cand = get_stamp_candidate(db_session, test_candidate.id)
    eq = cand.metrics["energy_quality"]
    assert eq["forbidden_metrics"]["docking_score"] is None
    assert eq["forbidden_metrics"]["mmgbsa_delta_G"] is None
    assert eq["forbidden_metrics"]["experimental_delta_G"] is None


# ---------------------------------------------------------------------------
# Router error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_job_not_found(async_client):
    """Non-existent job must return 404."""
    resp = await async_client.post(
        "/api/v1/jobs/nonexistent-job-id/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_persist_job_not_succeeded(async_client, db_session, test_project, test_candidate):
    """Job not in succeeded status must return 400."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="energy_estimation",
            input_json={"candidate_id": test_candidate.id},
        ),
    )
    # job remains pending

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_missing_fxout_path(async_client, db_session, test_project, test_candidate):
    """Job with missing interaction_fxout must return 400."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    from app.crud.jobs import update_job_status
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={
            **(job.output_json or {}),
            "interaction_fxout": None,
            "foldx_interaction_fxout": None,
        },
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.asyncio
async def test_persist_candidate_not_found(async_client, db_session, test_project):
    """Candidate that does not exist must return 404."""
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="energy_estimation",
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
            "interaction_fxout": str(REAL_FXOUT),
        },
    )

    resp = await async_client.post(
        f"/api/v1/jobs/{job.id}/persist-energy-quality-results"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# Direct service tests
# ---------------------------------------------------------------------------


def test_service_persist_succeeded_job(db_session, test_project, test_candidate):
    """Direct call: succeeded job persists correctly."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    result = persist_energy_quality_to_candidate(db_session, job.id)
    assert result["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)
    assert result["status"] == "COMPLETED"


def test_service_persist_creates_energy_quality_in_db(db_session, test_project, test_candidate):
    """Direct call: candidate.metrics['energy_quality'] is created."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert "energy_quality" in cand.metrics
    eq = cand.metrics["energy_quality"]
    assert eq["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)
    assert eq["forbidden_metrics"]["docking_score"] is None
    assert eq["forbidden_metrics"]["mmgbsa_delta_G"] is None
    assert eq["forbidden_metrics"]["experimental_delta_G"] is None


def test_service_persist_preserves_structure_prediction(db_session, test_project, test_candidate):
    """Direct call: structure_prediction metrics are not overwritten."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    sp = cand.metrics["structure_prediction"]
    assert sp["mean_plddt"] == 42.9
    assert sp["ptm"] == 0.315
    assert sp["iptm"] == 0.0909


def test_service_persist_preserves_interface_quality(db_session, test_project, test_candidate):
    """Direct call: interface_quality metrics are not overwritten."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    iq = cand.metrics["interface_quality"]
    assert iq["pdockq"] == 0.644
    assert iq["interface_contact_count"] == 149


def test_service_persist_by_fxout(db_session, test_project, test_candidate):
    """Direct call: persist by candidate_id + fxout path."""
    result = persist_energy_quality_to_candidate_by_fxout(
        db_session, test_candidate.id, str(REAL_FXOUT)
    )
    assert result["status"] == "COMPLETED"
    assert result["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)


def test_service_persist_by_fxout_skip_when_exists(db_session, test_project, test_candidate):
    """Direct call: skip when energy_quality already exists and overwrite=False."""
    test_candidate.metrics = {**(test_candidate.metrics or {}), "energy_quality": {"dummy": 1}}
    db_session.commit()

    result = persist_energy_quality_to_candidate_by_fxout(
        db_session, test_candidate.id, str(REAL_FXOUT), overwrite=False
    )
    assert result["status"] == "SKIPPED"


def test_service_persist_by_fxout_overwrite_when_flag(db_session, test_project, test_candidate):
    """Direct call: overwrite when energy_quality exists and overwrite=True."""
    test_candidate.metrics = {**(test_candidate.metrics or {}), "energy_quality": {"dummy": 1}}
    db_session.commit()

    result = persist_energy_quality_to_candidate_by_fxout(
        db_session, test_candidate.id, str(REAL_FXOUT), overwrite=True
    )
    assert result["status"] == "COMPLETED"
    assert result["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)


def test_service_persist_no_candidate_raises(db_session, test_project):
    """Direct call: missing candidate raises EnergyQualityError."""
    with pytest.raises(EnergyQualityError, match="not found"):
        persist_energy_quality_to_candidate_by_fxout(
            db_session, "nonexistent-candidate", str(REAL_FXOUT)
        )


# ---------------------------------------------------------------------------
# Validation_status and prediction_status enforcement
# ---------------------------------------------------------------------------


def test_service_validation_status_in_db(db_session, test_project, test_candidate):
    """validation_status in DB must be NOT_EXPERIMENTALLY_VALIDATED."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert cand.metrics["energy_quality"]["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_service_prediction_status_in_db(db_session, test_project, test_candidate):
    """prediction_status in DB must be COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    assert cand.metrics["energy_quality"]["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------


def test_service_provenance_in_db(db_session, test_project, test_candidate):
    """Provenance must contain FoldX executable or command info."""
    job = _make_succeeded_energy_job(db_session, test_candidate.id)
    persist_energy_quality_to_candidate(db_session, job.id)

    cand = get_stamp_candidate(db_session, test_candidate.id)
    prov = cand.metrics["energy_quality"]["provenance"]
    assert "foldx_executable" in prov
    assert "foldx_command" in prov
