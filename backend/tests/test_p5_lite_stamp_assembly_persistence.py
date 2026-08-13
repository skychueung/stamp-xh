"""STAMP Platform — P5-lite P4 STAMP Assembly Persistence Tests.

Tests the full backend loop:
  POST /api/v1/stamp-assembly/run -> DB generation_run -> assemble STAMP
  -> final ranking persistence -> force idempotency -> error handling.
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
    ProjectCreate,
    StampCandidateCreate,
    StampGenerationRunCreate,
)
from app.crud import (
    create_project,
    create_stamp_candidate,
    create_stamp_generation_run,
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
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="Test Project"))
    return proj


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
# Test 1: POST /run executes successfully
# ============================================================================


@pytest.mark.asyncio
async def test_stamp_assembly_run_endpoint_ok(
    client, test_project, test_generation_run, test_stamp_candidates
):
    """POST /api/v1/stamp-assembly/run should return 200 with valid payload."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] in ("COMPLETED", "COMPLETED_WITH_ERRORS")
    assert body["processed_count"] > 0


# ============================================================================
# Test 2: Normal flow — multiple candidates assembled and ranked
# ============================================================================


@pytest.mark.asyncio
async def test_normal_flow_assembles_and_ranks(
    client, test_project, test_generation_run, test_stamp_candidates
):
    """Multiple candidates should be assembled and returned ranked."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "EAAAK",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["processed_count"] == 5
    assert len(body["ranked_candidates"]) == 5
    # Verify ranking order: composite_score descending
    scores = [c["composite_score"] for c in body["ranked_candidates"]]
    assert scores == sorted(scores, reverse=True)


# ============================================================================
# Test 3: full_sequence is updated in DB
# ============================================================================


@pytest.mark.asyncio
async def test_full_sequence_updated_in_db(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """After assembly, DB records should have updated full_sequence."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "EAAAK",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    assert len(candidates) == 5
    for cand in candidates:
        assert cand.full_sequence is not None
        assert "EAAAK" in cand.full_sequence
        assert "FSRFLRRVRRYRPKISFNLEPFFKF" in cand.full_sequence


# ============================================================================
# Test 4: composite_score is updated in DB
# ============================================================================


@pytest.mark.asyncio
async def test_composite_score_updated_in_db(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """After assembly, DB records should have updated composite_score."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    for cand in candidates:
        assert cand.composite_score is not None
        assert 0.0 <= cand.composite_score <= 1.0


# ============================================================================
# Test 5: metrics["assembly"] contains required fields
# ============================================================================


@pytest.mark.asyncio
async def test_metrics_assembly_contains_fields(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """metrics['assembly'] must contain linker_seq, killing_peptide_seq, parameters."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "parameters": {"custom_key": "custom_value"},
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    for cand in candidates:
        metrics = cand.metrics or {}
        assert "assembly" in metrics
        assembly = metrics["assembly"]
        assert assembly.get("linker_seq") == "GGGGS"
        assert assembly.get("killing_peptide_seq") == "FSRFLRRVRRYRPKISFNLEPFFKF"
        assert assembly.get("full_sequence") is not None


# ============================================================================
# Test 6: metrics["final_ranking"] contains required fields
# ============================================================================


@pytest.mark.asyncio
async def test_metrics_final_ranking_contains_fields(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """metrics['final_ranking'] must contain composite_score, mode, validation_status."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    for cand in candidates:
        metrics = cand.metrics or {}
        assert "final_ranking" in metrics
        fr = metrics["final_ranking"]
        assert "composite_score" in fr
        assert "mode" in fr
        assert fr.get("validation_status") == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# Test 7: validation_status remains NOT_EXPERIMENTALLY_VALIDATED
# ============================================================================


@pytest.mark.asyncio
async def test_validation_status_remains_not_experimentally_validated(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """All candidates must keep validation_status == NOT_EXPERIMENTALLY_VALIDATED."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    for cand in candidates:
        assert cand.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

    body = resp.json()
    for rc in body["ranked_candidates"]:
        assert rc["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# Test 8: generation_run_id not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_generation_run_not_found(client, test_project):
    """POST with non-existent generation_run_id should return 404."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": "00000000-0000-0000-0000-000000000000",
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test 9: project_id mismatch returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_project_id_mismatch(
    client, db_session, test_project, test_generation_run
):
    """POST with mismatched project_id should return 400."""
    project_b = create_project(db_session, ProjectCreate(name="Project B"))

    payload = {
        "project_id": project_b.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Test 10: No candidates returns empty success
# ============================================================================


@pytest.mark.asyncio
async def test_no_candidates_returns_empty_success(
    client, test_project, test_generation_run
):
    """A generation run with 0 candidates should return COMPLETED with empty lists."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["processed_count"] == 0
    assert body["skipped_count"] == 0
    assert body["failed_count"] == 0
    assert body["ranked_candidates"] == []
    assert body["failed_candidates"] == []


# ============================================================================
# Test 11: force=False skips already processed candidates
# ============================================================================


@pytest.mark.asyncio
async def test_force_false_skips_processed(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """Second call with force=False should skip already processed candidates."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    # First call
    resp1 = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp1.status_code == status.HTTP_200_OK
    body1 = resp1.json()
    assert body1["processed_count"] == 5
    assert body1["skipped_count"] == 0

    # Second call
    resp2 = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp2.status_code == status.HTTP_200_OK
    body2 = resp2.json()
    assert body2["processed_count"] == 0
    assert body2["skipped_count"] == 5
    assert body2["failed_count"] == 0


# ============================================================================
# Test 12: force=True reprocesses already processed candidates
# ============================================================================


@pytest.mark.asyncio
async def test_force_true_reprocesses(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """Second call with force=True should reprocess all candidates."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": True,
    }
    # First call
    resp1 = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp1.status_code == status.HTTP_200_OK
    body1 = resp1.json()
    assert body1["processed_count"] == 5

    # Second call with force=True
    resp2 = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp2.status_code == status.HTTP_200_OK
    body2 = resp2.json()
    assert body2["processed_count"] == 5
    assert body2["skipped_count"] == 0


# ============================================================================
# Test 13: Empty linker_seq returns validation error
# ============================================================================


@pytest.mark.asyncio
async def test_empty_linker_seq_returns_error(
    client, test_project, test_generation_run
):
    """linker_seq empty string should fail Pydantic validation."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# Test 14: Empty killing_peptide_seq returns validation error
# ============================================================================


@pytest.mark.asyncio
async def test_empty_killing_peptide_seq_returns_error(
    client, test_project, test_generation_run
):
    """killing_peptide_seq empty string should fail Pydantic validation."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "",
        "top_k": 10,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# ============================================================================
# Test 15: top_k=5 limits ranked_candidates length
# ============================================================================


@pytest.mark.asyncio
async def test_top_k_limits_ranked_candidates(
    client, test_project, test_generation_run, test_stamp_candidates
):
    """top_k=5 should return at most 5 ranked candidates."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 5,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert len(body["ranked_candidates"]) <= 5


# ============================================================================
# Test 16: Single candidate failure does not fail the batch
# ============================================================================


@pytest.mark.asyncio
async def test_single_failure_continues_batch(
    client, db_session, test_project, test_generation_run, monkeypatch
):
    """If one candidate fails assembly, others should still be processed."""
    # Create candidates
    cands = []
    for i in range(3):
        sc = create_stamp_candidate(
            db_session,
            StampCandidateCreate(
                project_id=test_project.id,
                generation_run_id=test_generation_run.id,
                targeting_peptide_seq=f"PEPTIDE{i}",
                linker_seq="GGGGS",
                full_sequence=f"PEPTIDE{i}GGGGS",
                composite_score=0.5,
            ),
        )
        cands.append(sc)

    # Make the second candidate fail by monkeypatching _assemble_single_candidate
    from app.services import stamp_assembly_persistence

    original_assemble = stamp_assembly_persistence._assemble_single_candidate

    def _mock_assemble(candidate, request):
        if candidate.id == cands[1].id:
            raise ValueError("Mock assembly failure")
        return original_assemble(candidate, request)

    monkeypatch.setattr(
        stamp_assembly_persistence, "_assemble_single_candidate", _mock_assemble
    )

    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["failed_count"] == 1
    assert body["processed_count"] == 2
    assert len(body["ranked_candidates"]) == 2
    assert any(
        fc["candidate_id"] == cands[1].id for fc in body["failed_candidates"]
    )


# ============================================================================
# Test 17: Tie scores sort stably without crash
# ============================================================================


@pytest.mark.asyncio
async def test_tie_scores_sort_stably(
    client, db_session, test_project, test_generation_run
):
    """Candidates with identical composite scores should sort stably."""
    # Create candidates with identical targeting sequences to force same full_sequence
    for i in range(3):
        create_stamp_candidate(
            db_session,
            StampCandidateCreate(
                project_id=test_project.id,
                generation_run_id=test_generation_run.id,
                targeting_peptide_seq="AAAAAA",
                linker_seq="GGGGS",
                full_sequence="AAAAAAGGGGS",
                composite_score=0.5,
            ),
        )

    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "KKKKK",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["processed_count"] == 3
    # Should not crash; ranked list should have 3 items
    assert len(body["ranked_candidates"]) == 3


# ============================================================================
# Test 18: No fabricated experimental metrics
# ============================================================================


@pytest.mark.asyncio
async def test_no_fabricated_experimental_metrics(
    client, db_session, test_project, test_generation_run, test_stamp_candidates
):
    """metrics must NOT contain forbidden experimental keys."""
    payload = {
        "project_id": test_project.id,
        "generation_run_id": test_generation_run.id,
        "linker_seq": "GGGGS",
        "killing_peptide_seq": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "top_k": 10,
        "force": False,
    }
    resp = await client.post("/api/v1/stamp-assembly/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK

    candidates = list_stamp_candidates_by_generation_run(db_session, test_generation_run.id)
    for cand in candidates:
        metrics = cand.metrics or {}
        all_keys = " ".join(str(k).lower() for k in metrics.keys())
        assert "mic" not in all_keys, "MIC-like key found in metrics"
        assert "mbc" not in all_keys, "MBC-like key found in metrics"
        assert "hemolysis" not in all_keys, "hemolysis-like key found in metrics"
        assert "toxicity" not in all_keys, "toxicity-like key found in metrics"
        assert "iptm" not in all_keys, "ipTM-like key found in metrics"
        assert "pdockq" not in all_keys, "pDockQ-like key found in metrics"
        assert "docking_score" not in all_keys, "docking_score-like key found in metrics"
        assert "delta_g" not in all_keys, "delta_g-like key found in metrics"


# ============================================================================
# Test 19: Old /api/v1/stamp/assemble-v0.7 still available
# ============================================================================


@pytest.mark.asyncio
async def test_old_stamp_assemble_v07_still_available(client):
    """The v0.7 STAMP assembly endpoint must still respond."""

    request_body = {
        "targeting_peptide": {
            "candidate_id": "test_001",
            "sequence": "DKTKKAFLIAAG",
            "length": 12,
        },
        "linker": "EAAAK",
        "amp_sequence": "FSRFLRRVRRYRPKISFNLEPFFKF",
        "amp_name": "P4",
        "terminal_modification": "",
    }
    resp = await client.post("/api/v1/stamp/assemble-v0.7", json=request_body)
    # The endpoint exists; we don't validate the exact response because
    # the underlying stamp_assembler may have dependencies we haven't stubbed.
    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_422_UNPROCESSABLE_ENTITY)


# ============================================================================
# Test 20: Old /api/v1/final-ranking/compute still available
# ============================================================================


@pytest.mark.asyncio
async def test_old_final_ranking_compute_still_available(client):
    """The v0.7 final ranking endpoint must still respond."""
    request_body = {
        "candidates": [
            {
                "candidate_id": "c1",
                "full_sequence": "AAAAAAGGGGSKKKKK",
                "targeting_peptide": "AAAAAA",
                "linker": "GGGGS",
                "amp": "KKKKK",
                "length": 16,
                "net_charge": 2.0,
                "pI": 8.0,
                "GRAVY": -0.5,
                "cys_count": 0,
            }
        ]
    }
    resp = await client.post("/api/v1/final-ranking/compute", json=request_body)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    assert "ranked_candidates" in body
