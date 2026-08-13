"""STAMP Platform -- PepMLM REAL_MODEL Contract Tests (v0.10-P3c).

Validates that REAL_MODEL responses are correctly normalized and persisted
with the expected provenance markers. No real model is loaded in these tests --
all assertions use injected mock responses.
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
from app.models.orm import Project
from app.schemas import JobCreate, ProjectCreate
from app.crud import create_project, get_stamp_generation_run, list_stamp_candidates_by_generation_run

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
    return create_project(db_session, ProjectCreate(name="PepMLM REAL_MODEL Test Project"))


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
# Helpers: inject REAL_MODEL output into a job directly (no sidecar needed)
# ============================================================================


async def _create_job_with_real_output(client, db_session, project_id: str, output_json: dict) -> str:
    """Create a pepmlm_generation job and manually set its output_json."""
    payload = {
        "project_id": project_id,
        "job_type": "pepmlm_generation",
        "input_json": {
            "project_id": project_id,
            "epitope_sequence": "MKTLLIAIAIVAAGVATVQAATAEQVNTLKGNVAAGAANLNETTSGVQNYTQFDFNLDKES",
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 3,
            "linker_seq": "GGGGS",
        },
    }
    create_resp = await client.post("/api/v1/jobs", json=payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    job_id = create_resp.json()["data"]["id"]

    # Mark as succeeded with injected REAL_MODEL output using the same session
    from app.crud.jobs import update_job_status
    update_job_status(
        db_session,
        job_id,
        status="succeeded",
        progress=100,
        message="Execution completed successfully",
        output_json=output_json,
    )

    return job_id


# ============================================================================
# 1. normalize_pepmlm_response supports REAL_MODEL
# ============================================================================


def test_normalize_pepmlm_response_real_model():
    """REAL_MODEL raw response must produce PEPMLM_HTTP_SIDECAR_REAL."""
    from app.services.pepmlm_adapter import normalize_pepmlm_response

    raw = {
        "status": "success",
        "mode": "PEPMLM_REAL_MODEL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 3,
        "generated_peptides": [
            {"id": "pep_001", "sequence": "KTKAKAALAKAS", "score": 0.1225, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 8.16, "charge": 4.0, "pi": 8.6, "gravy": -0.358, "hydrophobicity": 0.358},
            {"id": "pep_002", "sequence": "KATAKQAAIKLG", "score": 0.1410, "rank": 2, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 7.09, "charge": 3.0, "pi": 8.2, "gravy": -0.067, "hydrophobicity": 0.067},
            {"id": "pep_003", "sequence": "TEATKKSAIAKGAAALNK", "score": 0.1147, "rank": 3, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 8.72, "charge": 3.0, "pi": 8.2, "gravy": -0.339, "hydrophobicity": 0.339},
        ],
        "model_info": {"model_name": "TianlaiChen/PepMLM-650M", "device": "cpu"},
    }

    result = normalize_pepmlm_response(raw, sidecar_url="http://127.0.0.1:5011")

    assert result["mode"] == "PEPMLM_HTTP_SIDECAR_REAL"
    assert result["real_model_loaded"] is True
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"
    assert result["candidate_count"] == 3

    preview = result["generated_peptides_preview"]
    assert len(preview) == 3
    for p in preview:
        assert p["is_stub"] is False
        assert p["source"] == "pepmlm_650m_real"


# ============================================================================
# 2. REAL_MODEL output_json contains PEPMLM_HTTP_SIDECAR_REAL
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_output_json_mode(client, db_session, test_project):
    """Persisted REAL_MODEL job must have mode=PEPMLM_HTTP_SIDECAR_REAL in output_json."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 3,
        "generated_peptides_preview": [
            {"sequence": "KTKAKAALAKAS", "score": 0.1225, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 8.16},
        ],
        "raw_result_summary": {
            "sidecar_status": "success",
            "candidate_count": 3,
            "mode": "PEPMLM_REAL_MODEL",
            "real_model_loaded": True,
            "model_name": "TianlaiChen/PepMLM-650M",
        },
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    # Verify job output
    job_resp = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_resp.status_code == status.HTTP_200_OK
    job_data = job_resp.json()["data"]
    assert job_data["output_json"]["mode"] == "PEPMLM_HTTP_SIDECAR_REAL"
    assert job_data["output_json"]["real_model_loaded"] is True


# ============================================================================
# 3. REAL_MODEL output_json real_model_loaded = true
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_output_json_real_model_loaded_true(client, db_session, test_project):
    """REAL_MODEL output_json must have real_model_loaded=true."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 3,
        "generated_peptides_preview": [
            {"sequence": "KTKAKAALAKAS", "score": 0.1225, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    job_resp = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_resp.json()["data"]
    assert job_data["output_json"]["real_model_loaded"] is True


# ============================================================================
# 4. generation_status = COMPUTATIONAL_GENERATION_ONLY
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_generation_status(client, db_session, test_project):
    """REAL_MODEL persist response must have generation_status=COMPUTATIONAL_GENERATION_ONLY."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 2,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
            {"sequence": "SEQ2", "score": 0.2, "rank": 2, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    result = persist_resp.json()["data"]
    assert result["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"


# ============================================================================
# 5. validation_status = NOT_EXPERIMENTALLY_VALIDATED
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_validation_status(client, db_session, test_project):
    """REAL_MODEL persist must retain NOT_EXPERIMENTALLY_VALIDATED."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 1,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    result = persist_resp.json()["data"]
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# 6. generated_peptides_preview is_stub = false
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_preview_is_stub_false(client, db_session, test_project):
    """REAL_MODEL preview peptides must have is_stub=false."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 2,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
            {"sequence": "SEQ2", "score": 0.2, "rank": 2, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    job_resp = await client.get(f"/api/v1/jobs/{job_id}")
    job_data = job_resp.json()["data"]
    for p in job_data["output_json"]["generated_peptides_preview"]:
        assert p["is_stub"] is False


# ============================================================================
# 7. forbidden metrics not present
# ============================================================================


@pytest.mark.asyncio
async def test_real_model_no_forbidden_metrics(client, db_session, test_project):
    """REAL_MODEL persisted candidates must NOT contain forbidden experimental metrics."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 2,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 8.0, "charge": 2.0, "pi": 7.5},
            {"sequence": "SEQ2", "score": 0.2, "rank": 2, "source": "pepmlm_650m_real", "is_stub": False, "ppl": 9.0, "charge": 1.0, "pi": 7.0},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    run_id = persist_resp.json()["data"]["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == 2

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


# ============================================================================
# 8. persist REAL_MODEL writes generator_name = pepmlm_650m_real
# ============================================================================


@pytest.mark.asyncio
async def test_persist_real_model_generator_name(client, db_session, test_project):
    """REAL_MODEL persist must write generator_name='pepmlm_650m_real'."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 1,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True, "model_name": "TianlaiChen/PepMLM-650M"},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    result = persist_resp.json()["data"]
    run_id = result["generation_run_id"]

    run = get_stamp_generation_run(db_session, run_id)
    assert run is not None
    assert run.generator_name == "pepmlm_650m_real"
    assert run.generator_version == "v0.10-p3c"
    assert run.parameters.get("real_model_loaded") is True
    assert run.parameters.get("model_name") == "TianlaiChen/PepMLM-650M"


# ============================================================================
# 9. persist REAL_MODEL writes metrics.real_model_loaded = true
# ============================================================================


@pytest.mark.asyncio
async def test_persist_real_model_metrics_real_model_loaded(client, db_session, test_project):
    """REAL_MODEL persisted candidates must have metrics.real_model_loaded=true."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 1,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    run_id = persist_resp.json()["data"]["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == 1
    assert candidates[0].metrics.get("real_model_loaded") is True


# ============================================================================
# 10. persist REAL_MODEL writes metrics.is_stub = false
# ============================================================================


@pytest.mark.asyncio
async def test_persist_real_model_metrics_is_stub_false(client, db_session, test_project):
    """REAL_MODEL persisted candidates must have metrics.is_stub=false."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_REAL",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_ONLY",
        "real_model_loaded": True,
        "candidate_count": 1,
        "generated_peptides_preview": [
            {"sequence": "SEQ1", "score": 0.1, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
        ],
        "raw_result_summary": {"mode": "PEPMLM_REAL_MODEL", "real_model_loaded": True},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    run_id = persist_resp.json()["data"]["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == 1
    assert candidates[0].metrics.get("is_stub") is False
    assert candidates[0].metrics.get("source") == "pepmlm_650m_real"


# ============================================================================
# 11. STUB_ONLY old tests still pass (sanity: real output with stub markers)
# ============================================================================


@pytest.mark.asyncio
async def test_persist_stub_mode_unchanged(client, db_session, test_project):
    """STUB_ONLY persist must still use generator_name='pepmlm_stub' and is_stub=true."""
    output_json = {
        "job_type": "pepmlm_generation",
        "mode": "PEPMLM_HTTP_SIDECAR_STUB",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": "COMPUTATIONAL_GENERATION_STUB_ONLY",
        "real_model_loaded": False,
        "candidate_count": 1,
        "generated_peptides_preview": [
            {"sequence": "STUBA", "score": 0.1, "rank": 1, "source": "pepmlm_stub", "is_stub": True},
        ],
        "raw_result_summary": {"mode": "PEPMLM_STUB_ONLY", "real_model_loaded": False},
        "sidecar_url": "http://127.0.0.1:5011",
    }
    job_id = await _create_job_with_real_output(client, db_session, test_project.id, output_json)

    persist_resp = await client.post(f"/api/v1/jobs/{job_id}/persist-pepmlm-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    run_id = persist_resp.json()["data"]["generation_run_id"]

    run = get_stamp_generation_run(db_session, run_id)
    assert run.generator_name == "pepmlm_stub"
    assert run.generator_version == "v0.10-p3a-stub"

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == 1
    assert candidates[0].metrics.get("is_stub") is True
    assert candidates[0].metrics.get("real_model_loaded") is False
    assert candidates[0].metrics.get("source") == "pepmlm_stub"
