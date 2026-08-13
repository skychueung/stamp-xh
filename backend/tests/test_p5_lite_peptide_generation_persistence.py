"""STAMP Platform — P5-lite P3 Peptide Generation Persistence Tests.

Tests the full backend loop:
  POST /api/v1/peptide-generations/run -> DB generation_run record
  -> rule-based targeting peptide generation -> candidate persistence
  -> status lifecycle -> result query.
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

# Use in-memory SQLite for these tests
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
    proj = create_project(db_session, ProjectCreate(name="Test Project"))
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


@pytest_asyncio.fixture
async def client(db_session):
    """Yield an async HTTP test client with DB override for in-memory SQLite."""
    app = create_app()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_db, None)


# ============================================================================
# Test 1: POST /run creates generation_run and returns COMPLETED
# ============================================================================


@pytest.mark.asyncio
async def test_run_peptide_generation_creates_run_and_returns_completed(
    client, test_project, test_epitope_candidate
):
    """POST /api/v1/peptide-generations/run should create a run and return COMPLETED."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["generation_run_id"] is not None
    assert len(body["generation_run_id"]) == 36  # UUID
    assert body["candidate_count"] > 0
    assert len(body["top_candidates"]) > 0
    assert body["error_message"] is None


# ============================================================================
# Test 2: Generation run status transitions correctly in DB
# ============================================================================


@pytest.mark.asyncio
async def test_generation_run_status_transitions_in_db(
    client, db_session, test_project, test_epitope_candidate
):
    """After a run, the DB record should show COMPLETED with timestamps set."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    run_id = resp.json()["generation_run_id"]

    run = get_stamp_generation_run(db_session, run_id)
    assert run is not None
    assert run.status == "COMPLETED"
    assert run.started_at is not None
    assert run.finished_at is not None
    assert run.error_message is None


# ============================================================================
# Test 3: Candidates persisted in stamp_candidates table
# ============================================================================


@pytest.mark.asyncio
async def test_candidates_persisted_in_db(
    client, db_session, test_project, test_epitope_candidate
):
    """After a run, candidates should be persisted in the stamp_candidates table."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    run_id = resp.json()["generation_run_id"]
    candidate_count = resp.json()["candidate_count"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == candidate_count
    assert len(candidates) > 0

    for cand in candidates:
        assert cand.targeting_peptide_seq is not None
        assert len(cand.targeting_peptide_seq) > 0
        assert cand.linker_seq == "GGGGS"
        assert cand.full_sequence is not None
        assert cand.full_sequence.startswith(cand.targeting_peptide_seq)
        assert cand.composite_score is not None


# ============================================================================
# Test 4: GET /stamp-generation-runs/{run_id}/candidates returns persisted candidates
# ============================================================================


@pytest.mark.asyncio
async def test_get_generation_run_candidates_returns_persisted_candidates(
    client, db_session, test_project, test_epitope_candidate
):
    """GET /stamp-generation-runs/{run_id}/candidates should return all persisted candidates."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    run_id = resp.json()["generation_run_id"]

    resp2 = await client.get(f"/api/v1/stamp-generation-runs/{run_id}/candidates")
    assert resp2.status_code == status.HTTP_200_OK
    body = resp2.json()
    data = body["data"]
    assert data["count"] > 0
    assert len(data["candidates"]) > 0

    for c in data["candidates"]:
        assert "targeting_peptide_seq" in c
        assert "linker_seq" in c
        assert "full_sequence" in c
        assert "composite_score" in c
        assert "validation_status" in c


# ============================================================================
# Test 5: epitope_id not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_run_peptide_generation_epitope_not_found(client, test_project):
    """POST with a non-existent epitope_id should return 404."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": "00000000-0000-0000-0000-000000000000",
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test 6: project_id mismatch returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_run_peptide_generation_project_id_mismatch(
    client, db_session, test_project, test_epitope_candidate
):
    """POST with a mismatched project_id should return 400."""
    project_b = create_project(db_session, ProjectCreate(name="Project B"))

    payload = {
        "project_id": project_b.id,  # Project B's ID
        "epitope_id": test_epitope_candidate.id,  # But epitope belongs to project A
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Test 7: Empty generation result does not fabricate data
# ============================================================================


@pytest.mark.asyncio
async def test_empty_candidates_no_fabrication(
    client, db_session, test_project, test_epitope_candidate, monkeypatch
):
    """A generation returning 0 candidates produces COMPLETED with 0 candidates."""

    def _mock_generate(*args, **kwargs):
        return {
            "code": 200,
            "message": "success",
            "mode": "RULE_BASED_TARGETING_PEPTIDE_GENERATION",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "input_summary": {
                "source_epitope_id": test_epitope_candidate.id,
                "source_sequence": test_epitope_candidate.sequence,
                "source_length": len(test_epitope_candidate.sequence),
                "source_net_charge": 0.0,
                "source_target_name": "Test",
                "source_species": "Test",
                "requested_count": 10,
            },
            "candidates": [],
        }

    monkeypatch.setattr(
        "app.services.peptide_generation_persistence.generate_targeting_peptides",
        _mock_generate,
    )

    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["candidate_count"] == 0
    assert body["top_candidates"] == []

    run_id = body["generation_run_id"]
    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) == 0


# ============================================================================
# Test 8: validation_status defaults to NOT_EXPERIMENTALLY_VALIDATED
# ============================================================================


@pytest.mark.asyncio
async def test_validation_status_default_not_experimentally_validated(
    client, db_session, test_project, test_epitope_candidate
):
    """All persisted stamp candidates must have validation_status == NOT_EXPERIMENTALLY_VALIDATED."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    run_id = resp.json()["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) > 0

    for cand in candidates:
        assert cand.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# Test 9: No fabricated experimental metrics
# ============================================================================


@pytest.mark.asyncio
async def test_no_fabricated_experimental_metrics(
    client, db_session, test_project, test_epitope_candidate
):
    """Stamp candidate metrics must NOT contain fabricated experimental data."""
    payload = {
        "project_id": test_project.id,
        "epitope_id": test_epitope_candidate.id,
        "top_k": 10,
        "linker_seq": "GGGGS",
    }
    resp = await client.post("/api/v1/peptide-generations/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    run_id = resp.json()["generation_run_id"]

    candidates = list_stamp_candidates_by_generation_run(db_session, run_id)
    assert len(candidates) > 0

    forbidden_keys = {
        "MIC_ug_ml",
        "MBC_ug_ml",
        "hemolysis_percent",
        "toxicity",
        "ipTM",
        "pDockQ",
        "docking_score",
        "delta_g",
        "ΔG",
        "binding_affinity_delta_g",
    }

    for cand in candidates:
        metrics = cand.metrics or {}
        for key in forbidden_keys:
            assert key not in metrics, f"Forbidden key '{key}' found in metrics"
        # Also ensure MIC / MBC / hemolysis are not present under any casing
        for k in metrics.keys():
            assert "mic" not in k.lower(), f"MIC-like key '{k}' found in metrics"
            assert "mbc" not in k.lower(), f"MBC-like key '{k}' found in metrics"
            assert "hemolysis" not in k.lower(), f"hemolysis-like key '{k}' found in metrics"
            assert "toxicity" not in k.lower(), f"toxicity-like key '{k}' found in metrics"
            assert "iptm" not in k.lower(), f"ipTM-like key '{k}' found in metrics"
            assert "pdockq" not in k.lower(), f"pDockQ-like key '{k}' found in metrics"
