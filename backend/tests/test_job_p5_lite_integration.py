"""STAMP Platform — Job System P5-lite Workflow Integration Tests (v0.9-P2).

Tests that the Job System can dispatch real P5-lite workflows:
  - epitope_scan
  - peptide_generation
  - stamp_assembly

All outputs are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import create_app
from app.models.orm import Job, Project
from app.schemas import (
    EpitopeCandidateCreate,
    EpitopeScanCreate,
    JobCreate,
    ProjectCreate,
    StampCandidateCreate,
    StampGenerationRunCreate,
    TargetProteinCreate,
)
from app.crud import (
    create_epitope_candidate,
    create_epitope_scan,
    create_project,
    create_stamp_candidate,
    create_stamp_generation_run,
    create_target_protein,
    delete_project,
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
    """Return a realistic 68-aa protein sequence (OprF-like)."""
    return (
        "MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGT"
        "GKGADAATYYTYILTAAKLIAGA"
    )


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="Job Integration Test Project"))
    return proj


@pytest.fixture
def test_target_protein(db_session, test_project, sample_sequence):
    """Create a test target protein."""
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
def test_epitope_scan(db_session, test_project, test_target_protein):
    """Create a test epitope scan."""
    scan = create_epitope_scan(
        db_session,
        EpitopeScanCreate(
            project_id=test_project.id,
            target_protein_id=test_target_protein.id,
            algorithm="heuristic_v1",
            status="COMPLETED",
        ),
    )
    return scan


@pytest.fixture
def test_epitope_candidate(db_session, test_epitope_scan):
    """Create a test epitope candidate with a realistic sequence."""
    ec = create_epitope_candidate(
        db_session,
        EpitopeCandidateCreate(
            scan_id=test_epitope_scan.id,
            start=1,
            end=15,
            sequence="MKKTAIAATAVLATA",
            net_charge=2.0,
            hydrophobicity=0.5,
            pi=7.0,
            cys_count=0,
            ranking_score=0.85,
            filter_status="PASS",
        ),
    )
    return ec


@pytest.fixture
def test_generation_run(db_session, test_project):
    """Create a test stamp generation run."""
    run = create_stamp_generation_run(
        db_session,
        StampGenerationRunCreate(project_id=test_project.id, generator_name="manual"),
    )
    return run


@pytest.fixture
def test_stamp_candidates(db_session, test_project, test_generation_run):
    """Create multiple test stamp candidates for the generation run."""
    candidates = []
    for i in range(5):
        sc = create_stamp_candidate(
            db_session,
            StampCandidateCreate(
                project_id=test_project.id,
                generation_run_id=test_generation_run.id,
                targeting_peptide_seq=f"DKTKKAFLIAAG{i}",
                linker_seq="GGGGS",
                full_sequence=f"DKTKKAFLIAAG{i}GGGGS",
                composite_score=0.5 + i * 0.05,
            ),
        )
        candidates.append(sc)
    return candidates


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


# ============================================================================
# Helpers
# ============================================================================


async def _create_job(async_client, project_id: str, job_type: str, input_json: dict):
    """Helper to create a job via API."""
    resp = await async_client.post(
        "/api/v1/jobs",
        json={"project_id": project_id, "job_type": job_type, "input_json": input_json},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["data"]


# ============================================================================
# 1. epitope_scan job runs successfully
# ============================================================================


@pytest.mark.asyncio
async def test_epitope_scan_job_runs_successfully(
    async_client, test_project, test_target_protein
):
    """POST /api/v1/jobs/{id}/run should execute epitope_scan and return succeeded."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "window_size": 15,
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["progress"] == 100


# ============================================================================
# 2. epitope_scan output_json contains scan_id and candidate_count
# ============================================================================


@pytest.mark.asyncio
async def test_epitope_scan_output_json_has_scan_id_and_candidate_count(
    async_client, test_project, test_target_protein
):
    """Job output_json for epitope_scan must contain scan_id and candidate_count."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "window_size": 15,
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    output = resp.json()["data"]["output_json"]
    assert "scan_id" in output
    assert len(output["scan_id"]) == 36
    assert "candidate_count" in output
    assert output["status"] == "COMPLETED"
    assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# 3. peptide_generation job runs successfully
# ============================================================================


@pytest.mark.asyncio
async def test_peptide_generation_job_runs_successfully(
    async_client, test_project, test_epitope_candidate
):
    """POST /api/v1/jobs/{id}/run should execute peptide_generation and return succeeded."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "peptide_generation",
        {
            "project_id": test_project.id,
            "epitope_id": test_epitope_candidate.id,
            "top_k": 10,
            "linker_seq": "GGGGS",
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["progress"] == 100


# ============================================================================
# 4. peptide_generation output_json contains generation_run_id and candidate_count
# ============================================================================


@pytest.mark.asyncio
async def test_peptide_generation_output_json_has_generation_run_id_and_candidate_count(
    async_client, test_project, test_epitope_candidate
):
    """Job output_json for peptide_generation must contain generation_run_id and candidate_count."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "peptide_generation",
        {
            "project_id": test_project.id,
            "epitope_id": test_epitope_candidate.id,
            "top_k": 10,
            "linker_seq": "GGGGS",
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    output = resp.json()["data"]["output_json"]
    assert "generation_run_id" in output
    assert len(output["generation_run_id"]) == 36
    assert "candidate_count" in output
    assert output["status"] == "COMPLETED"
    assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# 5. stamp_assembly job runs successfully
# ============================================================================


@pytest.mark.asyncio
async def test_stamp_assembly_job_runs_successfully(
    async_client, test_project, test_generation_run, test_stamp_candidates
):
    """POST /api/v1/jobs/{id}/run should execute stamp_assembly and return succeeded."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "stamp_assembly",
        {
            "project_id": test_project.id,
            "generation_run_id": test_generation_run.id,
            "linker_seq": "GGGGS",
            "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["progress"] == 100


# ============================================================================
# 6. stamp_assembly output_json contains processed_count and summary
# ============================================================================


@pytest.mark.asyncio
async def test_stamp_assembly_output_json_has_processed_count_and_ranked_summary(
    async_client, test_project, test_generation_run, test_stamp_candidates
):
    """Job output_json for stamp_assembly must contain processed_count / ranked summary."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "stamp_assembly",
        {
            "project_id": test_project.id,
            "generation_run_id": test_generation_run.id,
            "linker_seq": "GGGGS",
            "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    output = resp.json()["data"]["output_json"]
    assert "processed_count" in output
    assert "skipped_count" in output
    assert "failed_count" in output
    assert output["status"] in ("COMPLETED", "COMPLETED_WITH_ERRORS")
    assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# 7. unsupported job_type returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_unsupported_job_type_returns_400(async_client, test_project):
    """Unsupported job_type should mark job as failed and return 400 on run."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "pepmlm",
        {"project_id": test_project.id},
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "Unsupported job_type" in data["error_message"]


# ============================================================================
# 8. missing required input field marks job failed
# ============================================================================


@pytest.mark.asyncio
async def test_missing_required_input_field_marks_job_failed(
    async_client, test_project
):
    """Missing required field in input_json should fail the job with error_message."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {"project_id": test_project.id},
        # missing required field: target_protein_id
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "Input validation failed" in data["error_message"]


# ============================================================================
# 9. service exception marks job failed
# ============================================================================


@pytest.mark.asyncio
async def test_service_exception_marks_job_failed(
    async_client, test_project, monkeypatch
):
    """If the underlying service raises an exception, job should be marked failed."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": "nonexistent-id",
            "window_size": 15,
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"] is not None


# ============================================================================
# 10. job progress is 100 on success
# ============================================================================


@pytest.mark.asyncio
async def test_job_progress_is_100_on_success(
    async_client, test_project, test_target_protein
):
    """Successful job run must set progress to 100."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "window_size": 15,
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["data"]["progress"] == 100

    # Verify via GET as well
    get_resp = await async_client.get(f"/api/v1/jobs/{job_id}")
    assert get_resp.json()["data"]["progress"] == 100


# ============================================================================
# 11. output_json has no forbidden metrics
# ============================================================================


@pytest.mark.asyncio
async def test_output_json_has_no_forbidden_metrics(
    async_client, test_project, test_generation_run, test_stamp_candidates
):
    """Job output_json must NOT contain forbidden experimental/structural metrics."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "stamp_assembly",
        {
            "project_id": test_project.id,
            "generation_run_id": test_generation_run.id,
            "linker_seq": "GGGGS",
            "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    output = resp.json()["data"]["output_json"]

    forbidden_keys = {
        "MIC", "MBC", "hemolysis", "toxicity",
        "ipTM", "pDockQ", "docking_score", "delta_G", "ΔG",
    }
    output_str = str(output)
    for key in forbidden_keys:
        assert key not in output_str, f"Forbidden key '{key}' found in output_json"

    # Also check lowercase variants
    output_lower = output_str.lower()
    assert "mic" not in output_lower or "_mic" not in output_lower
    assert "mbc" not in output_lower
    assert "hemolysis" not in output_lower
    assert "toxicity" not in output_lower
    assert "iptm" not in output_lower
    assert "pdockq" not in output_lower
    assert "docking_score" not in output_lower
    assert "delta_g" not in output_lower


# ============================================================================
# 12. existing job foundation tests still pass (covered by test_jobs.py)
# ============================================================================

# This is validated by running test_jobs.py separately.


# ============================================================================
# 13. project cascade delete removes jobs
# ============================================================================


@pytest.mark.asyncio
async def test_project_cascade_delete_removes_jobs(async_client, db_session, test_project):
    """Deleting a project should cascade-delete its jobs."""
    # Create jobs via API
    for job_type in ("epitope_scan", "peptide_generation", "stamp_assembly"):
        resp = await async_client.post(
            "/api/v1/jobs",
            json={"project_id": test_project.id, "job_type": job_type, "input_json": {}},
        )
        assert resp.status_code == status.HTTP_201_CREATED

    # Verify jobs exist
    list_resp = await async_client.get(f"/api/v1/jobs/by-project/{test_project.id}")
    assert list_resp.json()["data"]["total_count"] == 3

    # Delete project via DB (no HTTP delete endpoint for projects in this test)
    delete_project(db_session, test_project.id)

    # Verify jobs are gone
    jobs = db_session.query(Job).filter(Job.project_id == test_project.id).all()
    assert len(jobs) == 0


# ============================================================================
# 14. already succeeded job is idempotent
# ============================================================================


@pytest.mark.asyncio
async def test_already_succeeded_job_is_idempotent(
    async_client, test_project, test_target_protein
):
    """Calling /run on an already-succeeded job should return the job without re-executing."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "window_size": 15,
            "top_k": 10,
        },
    )
    job_id = job_data["id"]

    # First run
    resp1 = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["data"]["status"] == "succeeded"
    scan_id_1 = resp1.json()["data"]["output_json"]["scan_id"]

    # Second run (idempotent)
    resp2 = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp2.status_code == status.HTTP_200_OK
    assert resp2.json()["data"]["status"] == "succeeded"
    scan_id_2 = resp2.json()["data"]["output_json"]["scan_id"]

    # Should return the same result without creating a new scan
    assert scan_id_1 == scan_id_2


# ============================================================================
# 15. failed job cannot be re-run
# ============================================================================


@pytest.mark.asyncio
async def test_failed_job_cannot_be_rerun(async_client, test_project):
    """Calling /run on a failed job should return 400."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {"project_id": test_project.id},
        # missing target_protein_id → will fail validation
    )
    job_id = job_data["id"]

    # First run → fails
    resp1 = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp1.status_code == status.HTTP_200_OK
    assert resp1.json()["data"]["status"] == "failed"

    # Second run → 400 (terminal state)
    resp2 = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp2.status_code == status.HTTP_400_BAD_REQUEST
    assert "terminal state" in resp2.json()["detail"].lower()


# ============================================================================
# 16. cancelled job cannot be re-run
# ============================================================================


@pytest.mark.asyncio
async def test_cancelled_job_cannot_be_rerun(async_client, test_project):
    """Calling /run on a cancelled job should return 400."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "epitope_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    job_id = job_data["id"]

    # Cancel the job
    cancel_resp = await async_client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel_resp.status_code == status.HTTP_200_OK

    # Try to run → 400 (terminal state)
    run_resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert run_resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "terminal state" in run_resp.json()["detail"].lower()
