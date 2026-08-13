"""STAMP Platform — P5-lite P2 Epitope Scan Persistence Tests.

Tests the full backend loop:
  POST /api/v1/epitope-scans/run -> DB scan record -> real biophysical scan
  -> candidate persistence -> status lifecycle -> result query.
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
from app.models.orm import EpitopeCandidate, EpitopeScan, Project, TargetProtein
from app.schemas import TargetProteinCreate, ProjectCreate, EpitopeScanCreate
from app.crud import (
    create_project,
    create_target_protein,
    create_epitope_scan,
    get_epitope_scan,
    list_epitope_candidates_by_scan,
)

# Use in-memory SQLite for these tests
TEST_DB_URL = "sqlite:///:memory:"

# Shared engine across all tests in this module (required because sqlite :memory:
# is per-connection; sharing the engine ensures all code sees the same DB)
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
# Test 1: POST /run creates scan and returns COMPLETED
# ============================================================================


@pytest.mark.asyncio
async def test_run_scan_creates_scan_and_returns_completed(
    client, test_project, test_target_protein
):
    """POST /api/v1/epitope-scans/run should create a scan and return COMPLETED."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)

    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    # The endpoint returns EpitopeScanRunResponse directly (not ApiResponse-wrapped)
    assert body["status"] == "COMPLETED"
    assert body["scan_id"] is not None
    assert len(body["scan_id"]) == 36  # UUID
    assert body["candidate_count"] == 10
    assert len(body["top_candidates"]) == 10


# ============================================================================
# Test 2: Scan status transitions correctly in DB
# ============================================================================


@pytest.mark.asyncio
async def test_scan_status_transitions_in_db(
    client, db_session, test_project, test_target_protein
):
    """After a scan, the DB record should show COMPLETED with timestamps set."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    scan_id = resp.json()["scan_id"]

    # Query the DB directly
    scan = get_epitope_scan(db_session, scan_id)
    assert scan is not None
    assert scan.status == "COMPLETED"
    assert scan.started_at is not None
    assert scan.finished_at is not None
    assert scan.error_message is None


# ============================================================================
# Test 3: Candidates persisted in epitope_candidates table
# ============================================================================


@pytest.mark.asyncio
async def test_candidates_persisted_in_db(
    client, db_session, test_project, test_target_protein
):
    """After a scan, candidates should be persisted in the epitope_candidates table."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    scan_id = resp.json()["scan_id"]
    candidate_count = resp.json()["candidate_count"]

    # Query candidates directly from DB
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == candidate_count
    assert len(candidates) == 10

    for cand in candidates:
        assert cand.start >= 1
        assert cand.end > cand.start
        assert cand.sequence is not None
        assert len(cand.sequence) > 0
        assert cand.ranking_score is not None


# ============================================================================
# Test 4: GET /{scan_id}/candidates returns persisted candidates
# ============================================================================


@pytest.mark.asyncio
async def test_get_scan_candidates_returns_persisted_candidates(
    client, db_session, test_project, test_target_protein
):
    """GET /{scan_id}/candidates should return all persisted candidates."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    scan_id = resp.json()["scan_id"]

    # Query via API — this endpoint returns ApiResponse-wrapped data
    resp2 = await client.get(f"/api/v1/epitope-scans/{scan_id}/candidates")
    assert resp2.status_code == status.HTTP_200_OK
    body = resp2.json()
    # Wrapped in ApiResponse
    data = body["data"]
    assert data["count"] == 10
    assert len(data["candidates"]) == 10

    # Verify each candidate has required fields
    for c in data["candidates"]:
        assert "start" in c
        assert "end" in c
        assert "sequence" in c
        assert "ranking_score" in c


# ============================================================================
# Test 5: target_protein_id not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_run_scan_target_protein_not_found(client, test_project):
    """POST with a non-existent target_protein_id should return 404."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": "00000000-0000-0000-0000-000000000000",
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test 6: project_id mismatch returns 400
# ============================================================================


@pytest.mark.asyncio
async def test_run_scan_project_id_mismatch(
    client, db_session, test_project, test_target_protein
):
    """POST with a mismatched project_id should return 400."""
    # Create a second project
    project_b = create_project(db_session, ProjectCreate(name="Project B"))

    payload = {
        "project_id": project_b.id,  # Project B's ID
        "target_protein_id": test_target_protein.id,  # But target belongs to project A
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ============================================================================
# Test 7: Empty candidate result does not fabricate data
# ============================================================================


@pytest.mark.asyncio
async def test_run_scan_empty_candidates_no_fabrication(
    client, db_session, test_project
):
    """A sequence shorter than window_size produces COMPLETED with 0 candidates."""
    # Create a target protein with a very short sequence (10 aa < window_size 15)
    short_tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="Short Protein",
            sequence="MKKTAIAATA",  # 10 aa — shorter than window_size=15
            sequence_hash="shorthash",
            length=10,
            source_type="manual",
        ),
    )

    payload = {
        "project_id": test_project.id,
        "target_protein_id": short_tp.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["status"] == "COMPLETED"
    assert body["candidate_count"] == 0
    assert body["top_candidates"] == []

    # Verify DB also has no candidates
    scan_id = body["scan_id"]
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 0


# ============================================================================
# Test 8: surface_exposure_score remains None
# ============================================================================


@pytest.mark.asyncio
async def test_surface_exposure_score_remains_none(
    client, db_session, test_project, test_target_protein
):
    """All persisted candidates should have surface_exposure_score == None."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    scan_id = resp.json()["scan_id"]

    # Query candidates directly from DB
    candidates = list_epitope_candidates_by_scan(db_session, scan_id)
    assert len(candidates) == 10

    for cand in candidates:
        assert cand.surface_exposure_score is None


# ============================================================================
# Test 9: GET /api/v1/epitope-candidates/{candidate_id} returns single candidate
# ============================================================================


@pytest.mark.asyncio
async def test_get_epitope_candidate_by_id(
    client, db_session, test_project, test_target_protein
):
    """GET /api/v1/epitope-candidates/{candidate_id} should return a single candidate."""
    payload = {
        "project_id": test_project.id,
        "target_protein_id": test_target_protein.id,
        "window_size": 15,
        "top_k": 10,
    }
    resp = await client.post("/api/v1/epitope-scans/run", json=payload)
    assert resp.status_code == status.HTTP_200_OK
    scan_id = resp.json()["scan_id"]

    # Get candidates via API to pick one ID
    resp2 = await client.get(f"/api/v1/epitope-scans/{scan_id}/candidates")
    assert resp2.status_code == status.HTTP_200_OK
    data = resp2.json()["data"]
    assert data["count"] > 0
    candidate_id = data["candidates"][0]["id"]

    # Query single candidate
    resp3 = await client.get(f"/api/v1/epitope-candidates/{candidate_id}")
    assert resp3.status_code == status.HTTP_200_OK
    body = resp3.json()
    assert body["code"] == 200
    cand = body["data"]
    assert cand["id"] == candidate_id
    assert "sequence" in cand
    assert "start" in cand
    assert "end" in cand
    assert "ranking_score" in cand
    assert "surface_exposure_score" in cand


# ============================================================================
# Test 10: GET /api/v1/epitope-candidates/{candidate_id} not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_get_epitope_candidate_not_found(client):
    """GET with a non-existent candidate_id should return 404."""
    resp = await client.get("/api/v1/epitope-candidates/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND
