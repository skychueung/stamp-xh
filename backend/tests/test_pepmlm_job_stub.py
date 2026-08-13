"""STAMP Platform — PepMLM Job Stub Integration Tests (v0.10-P3a).

Tests the full Job System loop for pepmlm_generation with a stub sidecar:
  create job → start async → sidecar stub → succeeded → persist → DB verify.
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
from app.schemas import (
    EpitopeCandidateCreate,
    EpitopeScanCreate,
    ProjectCreate,
    TargetProteinCreate,
)
from app.crud import (
    create_epitope_candidate,
    create_epitope_scan,
    create_project,
    create_target_protein,
    get_stamp_generation_run,
    list_stamp_candidates_by_generation_run,
)


# ============================================================================
# Mock: STUB_ONLY sidecar response for isolation from REAL_MODEL env
# ============================================================================


def _mock_call_pepmlm_sidecar(*, epitope_sequence, base_url, top_k=10, linker_seq="GGGGS", parameters=None, timeout=None):
    """Return a deterministic STUB_ONLY response regardless of sidecar mode."""
    return {
        "status": "success",
        "mode": "PEPMLM_STUB_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_STUB_ONLY",
        "real_model_loaded": False,
        "candidate_count": 3,
        "generated_peptides": [
            {
                "sequence": "STUBPEPTIDEA",
                "score": 0.1,
                "rank": 1,
                "source": "pepmlm_stub",
                "is_stub": True,
            },
            {
                "sequence": "STUBPEPTIDEB",
                "score": 0.2,
                "rank": 2,
                "source": "pepmlm_stub",
                "is_stub": True,
            },
            {
                "sequence": "STUBPEPTIDEC",
                "score": 0.3,
                "rank": 3,
                "source": "pepmlm_stub",
                "is_stub": True,
            },
        ],
    }


@pytest.fixture
def mock_pepmlm_stub(monkeypatch):
    """Monkeypatch app.services.job_service.call_pepmlm_sidecar to return STUB_ONLY."""
    import app.services.job_service as js
    monkeypatch.setattr(js, "call_pepmlm_sidecar", _mock_call_pepmlm_sidecar)

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}
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
    return create_project(db_session, ProjectCreate(name="PepMLM Test Project"))


@pytest.fixture
def test_target_protein(db_session, test_project):
    return create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="Test Protein",
            sequence="MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGTGKGADAATYYTYILTAAKLIAGA",
            sequence_hash="testhash123",
            length=68,
            source_type="manual",
        ),
    )


@pytest.fixture
def test_epitope_scan(db_session, test_project, test_target_protein):
    return create_epitope_scan(
        db_session,
        EpitopeScanCreate(
            project_id=test_project.id,
            target_protein_id=test_target_protein.id,
            algorithm="bepipred3",
            status="COMPLETED",
        ),
    )


@pytest.fixture
def test_epitope_candidate(db_session, test_epitope_scan):
    return create_epitope_candidate(
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


@pytest_asyncio.fixture
async def client(db_session):
    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ============================================================================
# Test 1: pepmlm_generation job creation
# ============================================================================


@pytest.mark.asyncio
async def test_create_pepmlm_generation_job(client, test_project):
    """Creating a pepmlm_generation job should succeed."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTAIAATAVLATA",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 5,
            "linker_seq": "GGGGS",
        },
    }
    resp = await client.post("/api/v1/jobs", json=payload)
    assert resp.status_code == status.HTTP_201_CREATED
    body = resp.json()
    assert body["data"]["job_type"] == "pepmlm_generation"
    assert body["data"]["status"] == "pending"


# ============================================================================
# Test 2: pepmlm_generation synchronous run with stub sidecar
# ============================================================================


@pytest.mark.asyncio
async def test_run_pepmlm_generation_stub_succeeds(client, test_project, mock_pepmlm_stub):
    """Running a pepmlm_generation job should succeed with stub sidecar."""
    # First create the job
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTAIAATAVLATA",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    # Run it synchronously
    run_resp = await client.post(f"/api/v1/jobs/{job_id}/run")
    assert run_resp.status_code == status.HTTP_200_OK
    body = run_resp.json()["data"]
    assert body["status"] == "succeeded"
    assert body["job_type"] == "pepmlm_generation"

    output = body["output_json"]
    assert output["mode"] == "PEPMLM_HTTP_SIDECAR_STUB"
    assert output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert output["generation_status"] == "COMPUTATIONAL_GENERATION_STUB_ONLY"
    assert output["real_model_loaded"] is False
    assert output["candidate_count"] == 3


# ============================================================================
# Test 3: epitope_id resolution (no direct sequence)
# ============================================================================


@pytest.mark.asyncio
async def test_pepmlm_generation_resolves_epitope_id(
    client, db_session, test_project, test_epitope_candidate, mock_pepmlm_stub
):
    """Job should resolve epitope_id to sequence from DB."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_id": test_epitope_candidate.id,
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    run_resp = await client.post(f"/api/v1/jobs/{job_id}/run")
    assert run_resp.status_code == status.HTTP_200_OK
    body = run_resp.json()["data"]
    assert body["status"] == "succeeded"


# ============================================================================
# Test 4: missing both epitope_id and epitope_sequence → failed
# ============================================================================


@pytest.mark.asyncio
async def test_pepmlm_generation_fails_without_epitope(client, test_project):
    """Job should fail if neither epitope_id nor epitope_sequence is provided."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    run_resp = await client.post(f"/api/v1/jobs/{job_id}/run")
    assert run_resp.status_code == status.HTTP_200_OK
    body = run_resp.json()["data"]
    assert body["status"] == "failed"
    assert "epitope_sequence" in body["error_message"].lower() or "required" in body["error_message"].lower()


# ============================================================================
# Test 5: sidecar unavailable → job failed
# ============================================================================


@pytest.mark.asyncio
async def test_pepmlm_generation_fails_when_sidecar_unavailable(client, test_project):
    """Job should fail gracefully when sidecar is not running."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTA",
            "sidecar_url": "http://127.0.0.1:59999",
            "top_k": 3,
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    run_resp = await client.post(f"/api/v1/jobs/{job_id}/run")
    assert run_resp.status_code == status.HTTP_200_OK
    body = run_resp.json()["data"]
    assert body["status"] == "failed"
    assert "SIDECAR_UNAVAILABLE" in body["error_message"]


# ============================================================================
# Test 6: persist-pepmlm-results writes to stamp_generation_runs
# ============================================================================


@pytest.mark.asyncio
async def test_persist_pepmlm_results_creates_generation_run(
    client, db_session, test_project, mock_pepmlm_stub
):
    """Persist endpoint should create a stamp_generation_runs record."""
    # Create and run job
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTAIAATAVLATA",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    await client.post(f"/api/v1/jobs/{job_id}/run")

    # Persist
    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    result = persist_resp.json()["data"]

    assert result["job_id"] == job_id
    assert result["status"] == "COMPLETED"
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_STUB_ONLY"
    assert result["candidate_count"] == 3
    assert len(result["created_candidate_ids"]) == 3

    run_id = result["generation_run_id"]
    run = get_stamp_generation_run(db_session, run_id)
    assert run is not None
    assert run.generator_name == "pepmlm_stub"
    assert run.generator_version == "v0.10-p3a-stub"


# ============================================================================
# Test 7: persist writes stamp_candidates with stub markers
# ============================================================================


@pytest.mark.asyncio
async def test_persist_pepmlm_results_candidates_have_stub_markers(
    client, db_session, test_project, mock_pepmlm_stub
):
    """Persisted candidates must have is_stub=true and correct validation_status."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTAIAATAVLATA",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    await client.post(f"/api/v1/jobs/{job_id}/run")
    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    run_id = persist_resp.json()["data"]["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) > 0

    for cand in candidates:
        assert cand.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
        assert cand.metrics is not None
        assert cand.metrics.get("is_stub") is True
        assert cand.metrics.get("real_model_loaded") is False
        assert cand.metrics.get("source") == "pepmlm_stub"


# ============================================================================
# Test 8: persist fails for non-succeeded job
# ============================================================================


@pytest.mark.asyncio
async def test_persist_pepmlm_results_fails_for_non_succeeded_job(client, test_project):
    """Persist should fail if job is not succeeded."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTA",
            "sidecar_url": "http://127.0.0.1:59999",
            "top_k": 3,
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    # Don't run — job is still pending
    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Test 9: persist fails for wrong job_type
# ============================================================================


@pytest.mark.asyncio
async def test_persist_pepmlm_results_fails_for_wrong_job_type(client, test_project):
    """Persist should fail if job_type is not pepmlm_generation."""
    payload = {
        "project_id": test_project.id,
        "job_type": "bepipred3_scan",
        "input_json": {},
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Test 10: forbidden metrics not present
# ============================================================================


@pytest.mark.asyncio
async def test_pepmlm_candidates_no_forbidden_metrics(
    client, db_session, test_project, mock_pepmlm_stub
):
    """Persisted candidates must NOT contain forbidden experimental metrics."""
    payload = {
        "project_id": test_project.id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": test_project.id,
            "epitope_sequence": "MKKTAIAATAVLATA",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    job_id = create_resp.json()["data"]["id"]

    await client.post(f"/api/v1/jobs/{job_id}/run")
    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    run_id = persist_resp.json()["data"]["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) > 0

    forbidden_keys = {
        "MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent", "toxicity",
        "ipTM", "pDockQ", "docking_score", "delta_g", "ΔG",
        "binding_affinity_delta_g",
    }

    for cand in candidates:
        metrics = cand.metrics or {}
        for key in forbidden_keys:
            assert key not in metrics, f"Forbidden key '{key}' found in metrics"
        for k in metrics.keys():
            assert "mic" not in k.lower(), f"MIC-like key '{k}' found"
            assert "mbc" not in k.lower(), f"MBC-like key '{k}' found"
            assert "hemolysis" not in k.lower(), f"hemolysis-like key '{k}' found"
            assert "toxicity" not in k.lower(), f"toxicity-like key '{k}' found"
            assert "iptm" not in k.lower(), f"ipTM-like key '{k}' found"
            assert "pdockq" not in k.lower(), f"pDockQ-like key '{k}' found"
