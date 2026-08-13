"""
v0.10-P4 Integrated Workflow Tests: BepiPred3 → PepMLM

Validates the full BepiPred3-to-PepMLM pipeline:
  1. BepiPred3 scan job → persist → epitope_candidates
  2. Select epitope → PepMLM generation job → persist → stamp_candidates
  3. Empty epitope results handled honestly (no fabrication)
  4. Scientific integrity boundaries preserved throughout

All sidecar calls are mocked — no real sidecar services required.
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
from app.schemas import JobCreate, ProjectCreate, TargetProteinCreate
from app.crud import create_project, create_target_protein
from app.crud.epitopes import list_epitope_candidates_by_scan
from app.crud.stamp_candidates import list_stamp_candidates_by_generation_run

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
def sample_sequence() -> str:
    return "MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGTGKGADAATYYTYILTAAKLIAGA"


@pytest.fixture
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="P4 Integrated Test Project"))


@pytest.fixture
def test_target_protein(db_session, test_project, sample_sequence):
    return create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="Test Target",
            sequence=sample_sequence,
            sequence_hash="testhash_p4",
            length=len(sample_sequence),
            source_type="manual",
        ),
    )


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


async def _create_job(async_client, project_id: str, job_type: str, input_json: dict):
    resp = await async_client.post(
        "/api/v1/jobs",
        json={"project_id": project_id, "job_type": job_type, "input_json": input_json},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["data"]


# ============================================================================
# 1. Empty BepiPred3 result: workflow terminates without fabrication
# ============================================================================


@pytest.mark.asyncio
async def test_empty_epitope_result_no_fabrication(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """When BepiPred3 returns zero candidates, no PepMLM job should be triggered."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {"ranked_peptides": [], "retained_count": 0, "dropped_count": 0}

    monkeypatch.setattr(
        "app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3
    )

    # Create and run BepiPred3 job
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
    assert resp.json()["data"]["status"] == "succeeded"

    # Persist BepiPred3 results
    persist_resp = await async_client.post(f"/api/v1/jobs/{job_id}/persist-bepipred3-results")
    assert persist_resp.status_code == status.HTTP_200_OK
    persist_data = persist_resp.json()["data"]
    assert persist_data["candidate_count"] == 0
    scan_id = persist_data["scan_id"]

    # Verify no epitope candidates in DB
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 0

    # Verify no PepMLM job was created (by checking project jobs)
    jobs_resp = await async_client.get(f"/api/v1/jobs/by-project/{test_project.id}")
    project_jobs = jobs_resp.json()["data"]["jobs"]
    pepmlm_jobs = [j for j in project_jobs if j["job_type"] == "pepmlm_generation"]
    assert len(pepmlm_jobs) == 0


# ============================================================================
# 2. Non-empty BepiPred3 result → PepMLM job → stamp_candidates
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_bepipred3_to_pepmlm_stub(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """Full pipeline with STUB PepMLM: BepiPred3 → epitope → PepMLM → stamp_candidates."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.85},
                {"sequence": "VLATASAQVAAGTST", "start": 10, "end": 24, "score": 0.72},
            ],
            "retained_count": 2,
            "dropped_count": 0,
        }

    def _mock_pepmlm(epitope_sequence, base_url=None, top_k=10, linker_seq="GGGGS", parameters=None):
        return {
            "status": "success",
            "mode": "PEPMLM_STUB_ONLY",
            "real_model_loaded": False,
            "generated_peptides": [
                {"id": "stub_001", "sequence": "STUBSEQAAAAAAA", "score": 0.5, "rank": 1, "source": "pepmlm_stub", "is_stub": True},
                {"id": "stub_002", "sequence": "STUBSEQBBBBBBB", "score": 0.4, "rank": 2, "source": "pepmlm_stub", "is_stub": True},
            ],
            "candidate_count": 2,
        }

    monkeypatch.setattr("app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3)
    monkeypatch.setattr("app.services.job_service.call_pepmlm_sidecar", _mock_pepmlm)

    # Step 1: BepiPred3 job
    bp_job = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )
    bp_resp = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/run")
    assert bp_resp.json()["data"]["status"] == "succeeded"

    # Step 2: Persist BepiPred3
    bp_persist = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/persist-bepipred3-results")
    assert bp_persist.status_code == status.HTTP_200_OK
    scan_id = bp_persist.json()["data"]["scan_id"]
    assert bp_persist.json()["data"]["candidate_count"] == 2

    # Step 3: Get epitope candidates, select top
    epitopes = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(epitopes) == 2
    top_epitope = sorted(epitopes, key=lambda e: e.ranking_score or 0, reverse=True)[0]

    # Step 4: PepMLM job using epitope_id
    pepmlm_job = await _create_job(
        async_client,
        test_project.id,
        "pepmlm_generation",
        {
            "project_id": test_project.id,
            "epitope_id": top_epitope.id,
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 5,
            "linker_seq": "GGGGS",
        },
    )
    pepmlm_resp = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/run")
    assert pepmlm_resp.json()["data"]["status"] == "succeeded"
    pepmlm_output = pepmlm_resp.json()["data"]["output_json"]
    assert pepmlm_output["mode"] == "PEPMLM_HTTP_SIDECAR_STUB"
    assert pepmlm_output["real_model_loaded"] is False

    # Step 5: Persist PepMLM
    pepmlm_persist = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/persist-pepmlm-results")
    assert pepmlm_persist.status_code == status.HTTP_200_OK
    persist_data = pepmlm_persist.json()["data"]
    generation_run_id = persist_data["generation_run_id"]
    assert persist_data["candidate_count"] == 2
    assert persist_data["generation_status"] == "COMPUTATIONAL_GENERATION_STUB_ONLY"
    assert persist_data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    # Step 6: Verify stamp candidates
    stamp_cands = list_stamp_candidates_by_generation_run(db_session, generation_run_id)
    assert len(stamp_cands) == 2
    for cand in stamp_cands:
        assert cand.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
        assert cand.metrics.get("is_stub") is True
        assert cand.metrics.get("real_model_loaded") is False
        assert cand.metrics.get("source") == "pepmlm_stub"


# ============================================================================
# 3. PepMLM REAL_MODEL contract generates stamp_candidates
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_pepmlm_real_model(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """Full pipeline with REAL_MODEL PepMLM: verify generator_name and metrics."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "MKKTAIAATAVLATA", "start": 1, "end": 15, "score": 0.90},
            ],
            "retained_count": 1,
            "dropped_count": 0,
        }

    def _mock_pepmlm(epitope_sequence, base_url=None, top_k=10, linker_seq="GGGGS", parameters=None):
        return {
            "status": "success",
            "mode": "PEPMLM_REAL_MODEL",
            "real_model_loaded": True,
            "generated_peptides": [
                {
                    "id": "real_001",
                    "sequence": "TAKASLALALAAAIG",
                    "score": 0.3,
                    "rank": 1,
                    "source": "pepmlm_650m_real",
                    "is_stub": False,
                    "ppl": 10.73,
                    "charge": 1.0,
                    "pi": 7.4,
                },
            ],
            "candidate_count": 1,
            "model_info": {"model_name": "TianlaiChen/PepMLM-650M", "device": "cpu"},
        }

    monkeypatch.setattr("app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3)
    monkeypatch.setattr("app.services.job_service.call_pepmlm_sidecar", _mock_pepmlm)

    # BepiPred3
    bp_job = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )
    await async_client.post(f"/api/v1/jobs/{bp_job['id']}/run")
    bp_persist = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/persist-bepipred3-results")
    scan_id = bp_persist.json()["data"]["scan_id"]
    epitopes = list_epitope_candidates_by_scan(db_session, scan_id)
    top_epitope = epitopes[0]

    # PepMLM REAL_MODEL
    pepmlm_job = await _create_job(
        async_client,
        test_project.id,
        "pepmlm_generation",
        {
            "project_id": test_project.id,
            "epitope_id": top_epitope.id,
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 5,
            "linker_seq": "GGGGS",
        },
    )
    pepmlm_resp = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/run")
    pepmlm_output = pepmlm_resp.json()["data"]["output_json"]
    assert pepmlm_output["mode"] == "PEPMLM_HTTP_SIDECAR_REAL"
    assert pepmlm_output["real_model_loaded"] is True
    assert pepmlm_output["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"

    # Persist
    pepmlm_persist = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/persist-pepmlm-results")
    persist_data = pepmlm_persist.json()["data"]
    assert persist_data["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"
    assert persist_data["real_model_loaded"] is True
    generation_run_id = persist_data["generation_run_id"]

    # Verify DB
    from app.crud import get_stamp_generation_run
    run = get_stamp_generation_run(db_session, generation_run_id)
    assert run.generator_name == "pepmlm_650m_real"
    assert run.generator_version == "v0.10-p3c"

    stamp_cands = list_stamp_candidates_by_generation_run(db_session, generation_run_id)
    assert len(stamp_cands) == 1
    cand = stamp_cands[0]
    assert cand.metrics.get("is_stub") is False
    assert cand.metrics.get("real_model_loaded") is True
    assert cand.metrics.get("source") == "pepmlm_650m_real"
    assert cand.metrics.get("ppl") == 10.73


# ============================================================================
# 4. Forbidden metrics absent across the entire pipeline
# ============================================================================


@pytest.mark.asyncio
async def test_forbidden_metrics_absent_throughout_pipeline(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """No forbidden experimental/structural metrics in any persisted output."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "AAAAA", "start": 1, "end": 5, "score": 0.5, "MIC_ug_ml": 10.0, "toxicity": "low"},
            ],
            "retained_count": 1,
            "dropped_count": 0,
        }

    def _mock_pepmlm(epitope_sequence, base_url=None, top_k=10, linker_seq="GGGGS", parameters=None):
        return {
            "status": "success",
            "mode": "PEPMLM_REAL_MODEL",
            "real_model_loaded": True,
            "generated_peptides": [
                {
                    "id": "real_001", "sequence": "SEQSEQ", "score": 0.3, "rank": 1,
                    "source": "pepmlm_650m_real", "is_stub": False,
                    "ppl": 8.0, "charge": 2.0, "pi": 7.5,
                    "ipTM": 0.95, "pDockQ": 0.88, "docking_score": -12.5,
                },
            ],
            "candidate_count": 1,
        }

    monkeypatch.setattr("app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3)
    monkeypatch.setattr("app.services.job_service.call_pepmlm_sidecar", _mock_pepmlm)

    # BepiPred3
    bp_job = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
            "sidecar_url": "http://127.0.0.1:5001/api/predict",
        },
    )
    await async_client.post(f"/api/v1/jobs/{bp_job['id']}/run")
    bp_persist = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/persist-bepipred3-results")
    scan_id = bp_persist.json()["data"]["scan_id"]
    epitopes = list_epitope_candidates_by_scan(db_session, scan_id)

    # Verify BepiPred3 candidates have forbidden metrics stripped
    for ep in epitopes:
        metrics = ep.metrics or {}
        for forbidden in ["mic", "mbc", "hemolysis", "toxicity", "iptm", "pdockq", "docking_score", "delta_g"]:
            for k in metrics.keys():
                assert forbidden not in k.lower(), f"Forbidden key '{k}' found in epitope metrics"

    # PepMLM
    pepmlm_job = await _create_job(
        async_client,
        test_project.id,
        "pepmlm_generation",
        {
            "project_id": test_project.id,
            "epitope_id": epitopes[0].id,
            "sidecar_url": "http://127.0.0.1:5011",
            "top_k": 5,
            "linker_seq": "GGGGS",
        },
    )
    await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/run")
    pepmlm_persist = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/persist-pepmlm-results")
    generation_run_id = pepmlm_persist.json()["data"]["generation_run_id"]

    # Verify PepMLM candidates have forbidden metrics stripped
    stamp_cands = list_stamp_candidates_by_generation_run(db_session, generation_run_id)
    for cand in stamp_cands:
        metrics = cand.metrics or {}
        for forbidden in ["mic", "mbc", "hemolysis", "toxicity", "iptm", "pdockq", "docking_score", "delta_g"]:
            for k in metrics.keys():
                assert forbidden not in k.lower(), f"Forbidden key '{k}' found in stamp metrics"


# ============================================================================
# 5. validation_status and prediction_status correct at every stage
# ============================================================================


@pytest.mark.asyncio
async def test_validation_status_not_experimentally_validated(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """All persisted results must have validation_status=NOT_EXPERIMENTALLY_VALIDATED."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [{"sequence": "AAAAA", "start": 1, "end": 5, "score": 0.5}],
            "retained_count": 1,
            "dropped_count": 0,
        }

    def _mock_pepmlm(epitope_sequence, base_url=None, top_k=10, linker_seq="GGGGS", parameters=None):
        return {
            "status": "success",
            "mode": "PEPMLM_REAL_MODEL",
            "real_model_loaded": True,
            "generated_peptides": [
                {"id": "r1", "sequence": "SEQ1", "score": 0.3, "rank": 1, "source": "pepmlm_650m_real", "is_stub": False},
            ],
            "candidate_count": 1,
        }

    monkeypatch.setattr("app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3)
    monkeypatch.setattr("app.services.job_service.call_pepmlm_sidecar", _mock_pepmlm)

    # BepiPred3 job output
    bp_job = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    bp_resp = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/run")
    bp_output = bp_resp.json()["data"]["output_json"]
    assert bp_output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert bp_output["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"

    bp_persist = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/persist-bepipred3-results")
    bp_persist_data = bp_persist.json()["data"]
    assert bp_persist_data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert bp_persist_data["prediction_status"] == "COMPUTATIONAL_PREDICTION_ONLY"

    # PepMLM job output
    scan_id = bp_persist_data["scan_id"]
    from app.crud.epitopes import list_epitope_candidates_by_scan
    epitopes = list_epitope_candidates_by_scan(db_session, scan_id)

    pepmlm_job = await _create_job(
        async_client,
        test_project.id,
        "pepmlm_generation",
        {
            "project_id": test_project.id,
            "epitope_id": epitopes[0].id,
            "sidecar_url": "http://127.0.0.1:5011",
        },
    )
    pepmlm_resp = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/run")
    pepmlm_output = pepmlm_resp.json()["data"]["output_json"]
    assert pepmlm_output["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert pepmlm_output["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"

    pepmlm_persist = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/persist-pepmlm-results")
    pepmlm_persist_data = pepmlm_persist.json()["data"]
    assert pepmlm_persist_data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert pepmlm_persist_data["generation_status"] == "COMPUTATIONAL_GENERATION_ONLY"


# ============================================================================
# 6. Workflow returns expected IDs
# ============================================================================


@pytest.mark.asyncio
async def test_workflow_returns_expected_ids(
    async_client, test_project, test_target_protein, monkeypatch, db_session
):
    """The full workflow must produce valid project_id, scan_id, and generation_run_id."""

    def _mock_bepipred3(sequence, base_url=None, timeout=60.0, parameters=None):
        return {
            "ranked_peptides": [
                {"sequence": "AAAAA", "start": 1, "end": 5, "score": 0.5},
            ],
            "retained_count": 1,
            "dropped_count": 0,
        }

    def _mock_pepmlm(epitope_sequence, base_url=None, top_k=10, linker_seq="GGGGS", parameters=None):
        return {
            "status": "success",
            "mode": "PEPMLM_STUB_ONLY",
            "real_model_loaded": False,
            "generated_peptides": [
                {"id": "s1", "sequence": "STUBA", "score": 0.3, "rank": 1, "source": "pepmlm_stub", "is_stub": True},
            ],
            "candidate_count": 1,
        }

    monkeypatch.setattr("app.services.job_service.call_bepipred3_sidecar", _mock_bepipred3)
    monkeypatch.setattr("app.services.job_service.call_pepmlm_sidecar", _mock_pepmlm)

    # Run BepiPred3
    bp_job = await _create_job(
        async_client,
        test_project.id,
        "bepipred3_scan",
        {
            "project_id": test_project.id,
            "target_protein_id": test_target_protein.id,
        },
    )
    await async_client.post(f"/api/v1/jobs/{bp_job['id']}/run")
    bp_persist = await async_client.post(f"/api/v1/jobs/{bp_job['id']}/persist-bepipred3-results")
    scan_id = bp_persist.json()["data"]["scan_id"]

    epitopes = list_epitope_candidates_by_scan(db_session, scan_id)
    top_epitope = epitopes[0]

    # Run PepMLM
    pepmlm_job = await _create_job(
        async_client,
        test_project.id,
        "pepmlm_generation",
        {
            "project_id": test_project.id,
            "epitope_id": top_epitope.id,
        },
    )
    await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/run")
    pepmlm_persist = await async_client.post(f"/api/v1/jobs/{pepmlm_job['id']}/persist-pepmlm-results")
    generation_run_id = pepmlm_persist.json()["data"]["generation_run_id"]

    # Assert IDs are valid UUID-like strings (36 chars with hyphens)
    assert len(scan_id) == 36
    assert len(generation_run_id) == 36
    assert pepmlm_persist.json()["data"]["job_id"] == pepmlm_job["id"]
    assert pepmlm_persist.json()["data"]["candidate_count"] == 1
