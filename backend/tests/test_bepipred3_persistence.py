"""STAMP Platform — BepiPred3 Result Persistence Tests (v0.10-P1c).

Tests persistence of bepipred3_scan job results into epitope_scans + epitope_candidates.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud import (
    create_project,
    create_target_protein,
)
from app.crud.epitopes import list_epitope_candidates_by_scan
from app.crud.jobs import create_job, update_job_status
from app.database import Base, get_db
from app.main import create_app
from app.models.orm import Job
from app.schemas import (
    JobCreate,
    ProjectCreate,
    TargetProteinCreate,
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
def sample_sequence() -> str:
    return "MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGTGKGADAATYYTYILTAAKLIAGA"


@pytest.fixture
def test_project(db_session):
    proj = create_project(db_session, ProjectCreate(name="BepiPred3 Persistence Test"))
    return proj


@pytest.fixture
def test_target_protein(db_session, test_project, sample_sequence):
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
# Helpers
# ---------------------------------------------------------------------------


def _create_succeeded_bepipred3_job(
    db_session,
    project_id: str,
    target_protein_id: str,
    output_json: dict,
    input_json: dict | None = None,
) -> Job:
    """Create a bepipred3_scan job in succeeded state."""
    job_in = JobCreate(
        project_id=project_id,
        job_type="bepipred3_scan",
        input_json=input_json
        or {
            "project_id": project_id,
            "target_protein_id": target_protein_id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )
    job = create_job(db_session, job_in)
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        message="Execution completed successfully",
        output_json=output_json,
    )
    db_session.refresh(job)
    return job


# ---------------------------------------------------------------------------
# 1. Empty result → scan created, candidate_count = 0, no candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_empty_result_creates_scan_no_candidates(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "job_type": "bepipred3_scan",
        "mode": "BEPIPRED3_HTTP_SIDECAR",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_PREDICTION_ONLY",
        "candidate_count": 0,
        "raw_result_summary": {"candidate_count": 0, "retained_count": 0, "dropped_count": 0},
        "ranked_peptides_preview": [],
        "sidecar_url": "http://127.0.0.1:5001/api/predict",
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()["data"]
    assert data["job_id"] == job.id
    assert data["candidate_count"] == 0
    assert data["created_candidate_ids"] == []
    assert data["status"] == "COMPLETED"
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert data["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"
    assert "scan_id" in data

    # Verify no candidates in DB
    candidates = list_epitope_candidates_by_scan(db_session, data["scan_id"])
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# 2. Empty result does not create epitope_candidates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_empty_result_no_db_candidates(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "job_type": "bepipred3_scan",
        "mode": "BEPIPRED3_HTTP_SIDECAR",
        "candidate_count": 0,
        "ranked_peptides_preview": [],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    scan_id = resp.json()["data"]["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 0


# ---------------------------------------------------------------------------
# 3. Non-empty ranked_peptides → candidates written
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_non_empty_results_creates_candidates(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "job_type": "bepipred3_scan",
        "mode": "BEPIPRED3_HTTP_SIDECAR",
        "candidate_count": 3,
        "ranked_peptides": [
            {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.85},
            {"sequence": "AQVAAGTSTWEYAQT", "start": 16, "end": 30, "score": 0.72},
            {"sequence": "DPNQLTQQLTEAVQK", "start": 31, "end": 45, "score": 0.60},
        ],
        "ranked_peptides_preview": [
            {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.85},
        ],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()["data"]
    assert data["candidate_count"] == 3
    assert len(data["created_candidate_ids"]) == 3

    scan_id = data["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 3


# ---------------------------------------------------------------------------
# 4. Candidate field mapping correct (sequence/start/end/ranking_score)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_candidate_field_mapping(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "ranked_peptides": [
            {"peptide": "AAA", "Start_Position": 1, "End_Position": 3, "Score": 0.9},
            {"fragment": "BBB", "start": 4, "end": 6, "ranking_score": 0.8},
            {"sequence": "CCC", "start": 7, "end": 9, "score": 0.7},
        ],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    scan_id = resp.json()["data"]["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 3

    by_seq = {c.sequence: c for c in candidates}
    assert by_seq["AAA"].start == 1
    assert by_seq["AAA"].end == 3
    assert by_seq["AAA"].ranking_score == 0.9

    assert by_seq["BBB"].start == 4
    assert by_seq["BBB"].end == 6
    assert by_seq["BBB"].ranking_score == 0.8

    assert by_seq["CCC"].start == 7
    assert by_seq["CCC"].end == 9
    assert by_seq["CCC"].ranking_score == 0.7


# ---------------------------------------------------------------------------
# 5. candidate.metrics.source = bepipred3_sidecar
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_candidate_metrics_source(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "ranked_peptides": [
            {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.85},
        ],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    scan_id = resp.json()["data"]["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 1
    assert candidates[0].metrics.get("source") == "bepipred3_sidecar"


# ---------------------------------------------------------------------------
# 6. Forbidden metrics are filtered out
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_forbidden_metrics_filtered(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "ranked_peptides": [
            {
                "sequence": "AAAAA",
                "start": 1,
                "end": 5,
                "score": 0.5,
                "MIC": 10.0,
                "MBC": 20.0,
                "hemolysis_percent": 5.0,
                "toxicity_score": 0.1,
                "ipTM": 0.8,
                "pDockQ": 0.7,
                "docking_score": -8.5,
                "delta_G": -12.3,
                "experimentally_validated": True,
            },
        ],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    scan_id = resp.json()["data"]["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 1

    metrics = candidates[0].metrics
    forbidden_keys = [
        "MIC", "MBC", "hemolysis_percent", "toxicity_score",
        "ipTM", "pDockQ", "docking_score", "delta_G", "experimentally_validated",
    ]
    for key in forbidden_keys:
        assert key not in metrics, f"Forbidden key '{key}' should not be in metrics"

    # Safe keys should remain
    assert metrics.get("sequence") == "AAAAA"
    assert metrics.get("score") == 0.5


# ---------------------------------------------------------------------------
# 7. Job not found → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_job_not_found(async_client):
    resp = await async_client.post("/api/v1/jobs/nonexistent-job-id/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ---------------------------------------------------------------------------
# 8. Wrong job_type → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_wrong_job_type(async_client, db_session, test_project):
    job = create_job(
        db_session,
        JobCreate(project_id=test_project.id, job_type="epitope_scan", input_json={}),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={"candidate_count": 1},
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "bepipred3_scan" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 9. Job not succeeded → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_job_not_succeeded(async_client, db_session, test_project, test_target_protein):
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
            },
        ),
    )
    # Leave in pending status

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "succeeded" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 10. Missing output_json → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_missing_output_json(async_client, db_session, test_project, test_target_protein):
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={
                "project_id": test_project.id,
                "target_protein_id": test_target_protein.id,
            },
        ),
    )
    update_job_status(db_session, job.id, status="succeeded", progress=100)

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "output_json" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 11. Missing target_protein_id in input_json → 400
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_missing_target_protein_id(async_client, db_session, test_project):
    job = create_job(
        db_session,
        JobCreate(
            project_id=test_project.id,
            job_type="bepipred3_scan",
            input_json={"project_id": test_project.id, "sequence": "MKKTAIAATAVLATA"},
        ),
    )
    update_job_status(
        db_session,
        job.id,
        status="succeeded",
        progress=100,
        output_json={
            "ranked_peptides": [],
            "candidate_count": 0,
        },
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "target_protein_id" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# 12. Peptides with missing fields are skipped, others persisted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_skips_invalid_peptides(async_client, db_session, test_project, test_target_protein):
    output = {
        "ranked_peptides": [
            {"sequence": "VALID", "start": 1, "end": 5, "score": 0.9},
            {"sequence": "MISSING_START", "end": 10},  # missing start
            {"start": 11, "end": 15},  # missing sequence
            {"sequence": "VALID2", "start": 20, "end": 24, "score": 0.8},
        ],
    }
    job = _create_succeeded_bepipred3_job(
        db_session, test_project.id, test_target_protein.id, output
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()["data"]
    assert data["candidate_count"] == 2
    assert data["skipped_count"] == 2

    scan_id = data["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    sequences = {c.sequence for c in candidates}
    assert sequences == {"VALID", "VALID2"}


# ---------------------------------------------------------------------------
# 13. Epitope scan record fields are correct
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_persist_scan_record_fields(
    async_client, db_session, test_project, test_target_protein
):
    output = {
        "ranked_peptides": [],
        "sidecar_url": "http://custom:5001/api/predict",
    }
    job = _create_succeeded_bepipred3_job(
        db_session,
        test_project.id,
        test_target_protein.id,
        output,
        input_json={
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://custom:5001/api/predict",
            "parameters": {"threshold": 0.5},
        },
    )

    resp = await async_client.post(f"/api/v1/jobs/{job.id}/persist-bepipred3-results")
    assert resp.status_code == status.HTTP_200_OK

    scan_id = resp.json()["data"]["scan_id"]
    from app.crud.epitopes import get_epitope_scan
    scan = get_epitope_scan(db_session, scan_id)
    assert scan is not None
    assert scan.project_id == test_project.id
    assert scan.target_protein_id == test_target_protein.id
    assert scan.algorithm == "bepipred3_sidecar"
    assert scan.algorithm_version == "v0.10-p1c"
    assert scan.status == "COMPLETED"
    assert scan.parameters["threshold"] == 0.5
    assert scan.parameters["job_id"] == job.id
    assert scan.parameters["mode"] == "BEPIPRED3_HTTP_SIDECAR"
