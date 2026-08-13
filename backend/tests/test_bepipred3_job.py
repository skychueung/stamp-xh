"""STAMP Platform - BepiPred3 Sidecar Job Integration Tests (v0.10-P1b-fix-2).

Tests the bepipred3_scan job_type through the Job System.
All sidecar calls are mocked - no real BepiPred3 service is required.
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
from app.models.orm import Job
from app.schemas import (
    JobCreate,
    ProjectCreate,
    TargetProteinCreate,
)
from app.crud import (
    create_project,
    create_target_protein,
)
from app.services.job_service import SUPPORTED_JOB_TYPES

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
    """Return a realistic 68-aa protein sequence."""
    return (
        "MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGT"
        "GKGADAATYYTYILTAAKLIAGA"
    )


@pytest.fixture
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="BepiPred3 Test Project"))
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


async def _create_job(async_client, project_id: str, job_type: str, input_json: dict):
    """Helper to create a job via API."""
    resp = await async_client.post(
        "/api/v1/jobs",
        json={"project_id": project_id, "job_type": job_type, "input_json": input_json},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["data"]


# ============================================================================
# 1. bepipred3_scan is in SUPPORTED_JOB_TYPES
# ============================================================================


def test_bepipred3_scan_in_supported_job_types():
    """bepipred3_scan must be listed in SUPPORTED_JOB_TYPES."""
    assert "bepipred3_scan" in SUPPORTED_JOB_TYPES


# ============================================================================
# 2. sidecar normal return -> job succeeded
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_sidecar_success(async_client, test_project, test_target_protein, monkeypatch):
    """When sidecar returns valid data, job should succeed."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.85},
                {"sequence": "VLATASAQVAAGTST", "start": 10, "end": 24, "score": 0.72},
            ],
            "retained_count": 2,
            "dropped_count": 0,
        }

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"
    assert data["progress"] == 100


# ============================================================================
# 3. output_json contains NOT_EXPERIMENTALLY_VALIDATED
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_output_json_has_validation_status(
    async_client, test_project, test_target_protein, monkeypatch
):
    """output_json must contain validation_status = NOT_EXPERIMENTALLY_VALIDATED."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        return {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0}

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    output = resp.json()["data"]["output_json"]
    assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert output["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"


# ============================================================================
# 4. output_json contains prediction_status
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_output_json_has_prediction_status(
    async_client, test_project, test_target_protein, monkeypatch
):
    """output_json must contain prediction_status = COMPUTATIONAL_PREDICTION_ONLY."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        return {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0}

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    output = resp.json()["data"]["output_json"]
    assert output["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"
    assert output["mode"] == "BEPIPRED3_HTTP_SIDECAR"


# ============================================================================
# 5. sidecar unavailable -> job failed
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_sidecar_unavailable(async_client, test_project, test_target_protein, monkeypatch):
    """When sidecar raises connection error, job should be marked failed."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        from app.services.bepipred3_adapter import BepiPred3SidecarError
        raise BepiPred3SidecarError("Sidecar connection refused: [Errno 111]")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "connection refused" in data["error_message"].lower() or "sidecar" in data["error_message"].lower()


# ============================================================================
# 6. sidecar timeout -> job failed
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_sidecar_timeout(async_client, test_project, test_target_protein, monkeypatch):
    """When sidecar times out, job should be marked failed."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        from app.services.bepipred3_adapter import BepiPred3SidecarError
        raise BepiPred3SidecarError("Sidecar timeout after 60.0s")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "timeout" in data["error_message"].lower()


# ============================================================================
# 7. input_json missing sequence and target_protein_id -> job failed
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_missing_sequence_and_target_protein_id(async_client, test_project):
    """Missing both sequence and target_protein_id should fail the job."""
    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {"project_id": test_project.id},
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert data["error_message"] is not None
    assert "sequence" in data["error_message"].lower() or "target_protein_id" in data["error_message"].lower()


# ============================================================================
# 8. output_json has no forbidden metrics
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_output_json_has_no_forbidden_metrics(
    async_client, test_project, test_target_protein, monkeypatch
):
    """output_json must NOT contain forbidden experimental/structural metrics."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "AAAAA", "start": 1, "end": 5, "score": 0.5}
            ],
            "retained_count": 1,
            "dropped_count": 0,
        }

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    output_str = str(resp.json()["data"]["output_json"]).lower()

    forbidden = ["mic", "mbc", "hemolysis", "toxicity", "iptm", "pdockq", "docking_score", "delta_g", "experimentally validated", "wet-lab"]
    for term in forbidden:
        assert term not in output_str, f"Forbidden term \x27{term}\x27 found in output_json"


# ============================================================================
# 9. sidecar returns invalid response format -> job failed
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_sidecar_invalid_response(async_client, test_project, test_target_protein, monkeypatch):
    """When sidecar returns malformed response, job should be marked failed."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        # Return something that is not valid dict shape expected by normalizer
        return "this is not a dict"

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "invalid sidecar response" in data["error_message"].lower()


# ============================================================================
# 10. sidecar returns HTTP error -> job failed
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_sidecar_http_error(async_client, test_project, test_target_protein, monkeypatch):
    """When sidecar returns HTTP 500, job should be marked failed."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        from app.services.bepipred3_adapter import BepiPred3SidecarError
        raise BepiPred3SidecarError("Sidecar returned HTTP 500: internal error")

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "failed"
    assert "http 500" in data["error_message"].lower() or "sidecar" in data["error_message"].lower()


# ============================================================================
# 11. sequence provided directly (no DB lookup needed)
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_with_direct_sequence(async_client, test_project, monkeypatch):
    """When sequence is provided directly, job should succeed without DB lookup."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        assert sequence == "MKKTAIAATAVLATA"
        return {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0}

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "sequence": "MKKTAIAATAVLATA",
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["status"] == "succeeded"


# ============================================================================
# 12. candidate_count reflects sidecar result
# ============================================================================


@pytest.mark.asyncio
async def test_bepipred3_candidate_count_matches_sidecar(
    async_client, test_project, test_target_protein, monkeypatch
):
    """candidate_count in output_json should match sidecar candidates length."""

    def _mock_call_sidecar(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "AAAAA", "start": 1, "end": 5, "score": 0.5},
                {"sequence": "CCCCC", "start": 3, "end": 7, "score": 0.6},
                {"sequence": "GGGGG", "start": 5, "end": 9, "score": 0.7},
            ],
            "retained_count": 3,
            "dropped_count": 0,
        }

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar",
        _mock_call_sidecar,
    )

    job_data = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    job_id = job_data["id"]

    resp = await async_client.post(f"/api/v1/jobs/{job_id}/run")
    output = resp.json()["data"]["output_json"]
    assert output["candidate_count"] == 3
    assert output["raw_result_summary"]["candidate_count"] == 3
    assert len(output["ranked_peptides_preview"]) == 3


# ============================================================================
# 13. adapter sends correct JSON body to sidecar
# ============================================================================


def test_bepipred3_adapter_sends_correct_json_body(monkeypatch):
    """call_bepipred3_sidecar must POST JSON with name, sequence, and params."""
    captured = {}

    def _mock_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["payload"] = json
        class FakeResp:
            status_code = 200
            def json(self):
                return {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0}
            @property
            def text(self):
                return "{}"
        return FakeResp()

    monkeypatch.setattr("app.services.bepipred3_adapter.httpx.post", _mock_post)

    from app.services.bepipred3_adapter import call_bepipred3_sidecar
    result = call_bepipred3_sidecar(
        sequence="MKKTAIAATAVLATA",
        base_url="http://127.0.0.1:5001/api/predict",
        parameters={"threshold": 0.5, "name": "my_protein"},
    )

    assert captured["url"] == "http://127.0.0.1:5001/api/predict"
    payload = captured["payload"]
    assert payload["name"] == "my_protein"
    assert payload["sequence"] == "MKKTAIAATAVLATA"
    assert payload["params"]["threshold"] == 0.5
    assert result["ranked_peptides"] == []


# ============================================================================
# 14. normalize maps various peptide field names
# ============================================================================


def test_normalize_maps_peptide_fields():
    """normalize_bepipred3_response should map sequence/peptide/fragment, start/Start_Position, etc."""
    from app.services.bepipred3_adapter import normalize_bepipred3_response

    raw = {
        "ranked_peptides": [
            {"peptide": "AAA", "Start_Position": 1, "End_Position": 3, "Score": 0.9},
            {"fragment": "BBB", "start": 4, "end": 6, "ranking_score": 0.8},
            {"sequence": "CCC", "start": 7, "end": 9, "score": 0.7},
        ],
        "retained_count": 3,
        "dropped_count": 1,
    }

    result = normalize_bepipred3_response(raw, sidecar_url="http://127.0.0.1:5001/api/predict")
    preview = result["ranked_peptides_preview"]
    assert len(preview) == 3
    assert preview[0] == {"sequence": "AAA", "start": 1, "end": 3, "score": 0.9}
    assert preview[1] == {"sequence": "BBB", "start": 4, "end": 6, "score": 0.8}
    assert preview[2] == {"sequence": "CCC", "start": 7, "end": 9, "score": 0.7}
    assert result["raw_result_summary"]["retained_count"] == 3
    assert result["raw_result_summary"]["dropped_count"] == 1
    assert result["candidate_count"] == 3


def test_normalize_missing_ranked_peptides():
    """When ranked_peptides is missing, candidate_count should be 0 and missing flag set."""
    from app.services.bepipred3_adapter import normalize_bepipred3_response

    raw = {"retained_count": 0, "dropped_count": 0}
    result = normalize_bepipred3_response(raw)
    assert result["candidate_count"] == 0
    assert result["raw_result_summary"]["missing_ranked_peptides"] is True
    assert result["ranked_peptides_preview"] == []


# ============================================================================
# 15. init_db startup persists (jobs table exists via TestClient lifespan)
# ============================================================================


@pytest.mark.asyncio
async def test_init_db_startup_creates_jobs_table(async_client, test_project):
    """Lifespan init_db must create the jobs table so we can create and list jobs."""
    resp = await async_client.get(f"/api/v1/jobs/by-project/{test_project.id}")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    # by-project endpoint returns {jobs: [...], project_id, total_count}
    assert isinstance(data, dict)
    assert "jobs" in data
    assert isinstance(data["jobs"], list)
