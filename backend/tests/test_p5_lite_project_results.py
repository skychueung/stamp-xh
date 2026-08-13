"""STAMP Platform — P5-lite P5 Project Results Query Tests.

Tests aggregated read-only project-level endpoints.
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
def test_project(db_session):
    """Create a test project."""
    proj = create_project(db_session, ProjectCreate(name="Test Project"))
    return proj


@pytest.fixture
def test_target_protein(db_session, test_project):
    """Create a test target protein."""
    tp = create_target_protein(
        db_session,
        TargetProteinCreate(
            project_id=test_project.id,
            name="Test OprF",
            sequence="MKKTAIAATAVLATASAQVAAGTSTWEYAQTTDPNQLTQQLTEAVQKLLENKDVQKIAGTGKGADAATYYTYILTAAKLIAGA",
            sequence_hash="testhash123",
            length=68,
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
    """Create a test epitope candidate."""
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
def test_generation_run(db_session, test_project, test_epitope_candidate):
    """Create a test generation run."""
    run = create_stamp_generation_run(
        db_session,
        StampGenerationRunCreate(
            project_id=test_project.id,
            epitope_id=test_epitope_candidate.id,
            generator_name="heuristic_targeting_peptide_v1",
            generator_version="p5_lite_v0.8",
            status="COMPLETED",
        ),
    )
    return run


@pytest.fixture
def test_stamp_candidates(db_session, test_project, test_epitope_candidate, test_generation_run):
    """Create test stamp candidates with varying assembly states."""
    c1 = create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            epitope_id=test_epitope_candidate.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="EEDDAEEDAEDDA",
            linker_seq="GGGGS",
            full_sequence="EEDDAEEDAEDDAGGGGSKKKKK",
            composite_score=0.85,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            metrics={
                "assembly": {
                    "full_sequence": "EEDDAEEDAEDDAGGGGSKKKKK",
                    "length": 23,
                },
                "final_ranking": {
                    "composite_score": 0.85,
                },
            },
        ),
    )
    c2 = create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            epitope_id=test_epitope_candidate.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="AAAAAADDDEE",
            linker_seq="GGGGS",
            full_sequence="AAAAAADDDEEGGGGSKKKKK",
            composite_score=0.72,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            metrics={
                "assembly": {
                    "full_sequence": "AAAAAADDDEEGGGGSKKKKK",
                    "length": 21,
                },
                "final_ranking": {
                    "composite_score": 0.72,
                },
            },
        ),
    )
    # c3: no assembly metrics -> should be excluded from stamp-results
    c3 = create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            epitope_id=test_epitope_candidate.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="MMMNNN",
            linker_seq="GGGGS",
            full_sequence="MMMNNNGGGGSKKKKK",
            composite_score=0.60,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            metrics={
                "generator": {"mode": "RULE_BASED"},
            },
        ),
    )
    return [c1, c2, c3]


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
# Test 1: GET /summary success
# ============================================================================


@pytest.mark.asyncio
async def test_project_summary_success(
    client, test_project, test_target_protein, test_epitope_scan, test_epitope_candidate,
    test_generation_run, test_stamp_candidates,
):
    """GET /api/v1/projects/{project_id}/summary should return correct counts."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/summary")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["project_id"] == test_project.id
    assert data["project_name"] == test_project.name
    assert data["target_protein_count"] == 1
    assert data["epitope_scan_count"] == 1
    assert data["epitope_candidate_count"] == 1
    assert data["generation_run_count"] == 1
    assert data["stamp_candidate_count"] == 3
    assert data["assembled_candidate_count"] == 3
    assert data["ranked_candidate_count"] == 3


# ============================================================================
# Test 2: project_id not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_project_summary_not_found(client):
    """GET with non-existent project_id should return 404."""
    resp = await client.get("/api/v1/projects/00000000-0000-0000-0000-000000000000/summary")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test 3: Empty project summary returns count=0
# ============================================================================


@pytest.mark.asyncio
async def test_project_summary_empty_project(client, db_session):
    """Summary for a project with no children should return zeros."""
    empty_proj = create_project(db_session, ProjectCreate(name="Empty Project"))
    resp = await client.get(f"/api/v1/projects/{empty_proj.id}/summary")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    data = body["data"]
    assert data["target_protein_count"] == 0
    assert data["epitope_scan_count"] == 0
    assert data["epitope_candidate_count"] == 0
    assert data["generation_run_count"] == 0
    assert data["stamp_candidate_count"] == 0
    assert data["assembled_candidate_count"] == 0
    assert data["ranked_candidate_count"] == 0


# ============================================================================
# Test 4: GET /pipeline-results success
# ============================================================================


@pytest.mark.asyncio
async def test_project_pipeline_results_success(
    client, test_project, test_target_protein, test_epitope_scan, test_epitope_candidate,
    test_generation_run, test_stamp_candidates,
):
    """GET /api/v1/projects/{project_id}/pipeline-results should return full pipeline."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/pipeline-results")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["project_id"] == test_project.id
    assert len(data["target_proteins"]) == 1
    assert len(data["epitope_scans"]) == 1
    assert len(data["epitope_candidates"]) == 1
    assert len(data["generation_runs"]) == 1
    assert len(data["stamp_candidates"]) == 3


# ============================================================================
# Test 5: pipeline-results contains expected keys
# ============================================================================


@pytest.mark.asyncio
async def test_project_pipeline_results_keys(
    client, test_project, test_stamp_candidates,
):
    """Pipeline results should contain all required entity lists."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/pipeline-results")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert "target_proteins" in data
    assert "epitope_scans" in data
    assert "epitope_candidates" in data
    assert "generation_runs" in data
    assert "stamp_candidates" in data


# ============================================================================
# Test 6: GET /stamp-results success
# ============================================================================


@pytest.mark.asyncio
async def test_project_stamp_results_success(
    client, test_project, test_stamp_candidates,
):
    """GET /api/v1/projects/{project_id}/stamp-results should return assembled candidates."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/stamp-results")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["project_id"] == test_project.id
    # c1 and c2 have assembly+final_ranking; c3 does not
    assert data["total_count"] == 2
    assert data["returned_count"] == 2


# ============================================================================
# Test 7: stamp-results sorted by composite_score descending
# ============================================================================


@pytest.mark.asyncio
async def test_project_stamp_results_sorted(
    client, test_project, test_stamp_candidates,
):
    """STAMP results should be sorted by composite_score descending."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/stamp-results")
    assert resp.status_code == status.HTTP_200_OK
    candidates = resp.json()["data"]["candidates"]
    assert len(candidates) == 2
    scores = [c["composite_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] >= scores[1]


# ============================================================================
# Test 8: top_k parameter
# ============================================================================


@pytest.mark.asyncio
async def test_project_stamp_results_top_k(
    client, test_project, test_stamp_candidates,
):
    """top_k should limit returned candidates."""
    resp = await client.get(
        f"/api/v1/projects/{test_project.id}/stamp-results?top_k=1"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["total_count"] == 2
    assert data["returned_count"] == 1
    assert len(data["candidates"]) == 1


# ============================================================================
# Test 9: include_metrics=false
# ============================================================================


@pytest.mark.asyncio
async def test_project_stamp_results_exclude_metrics(
    client, test_project, test_stamp_candidates,
):
    """include_metrics=false should strip metrics from response."""
    resp = await client.get(
        f"/api/v1/projects/{test_project.id}/stamp-results?include_metrics=false"
    )
    assert resp.status_code == status.HTTP_200_OK
    candidates = resp.json()["data"]["candidates"]
    for c in candidates:
        assert c["metrics"] is None


# ============================================================================
# Test 10: GET /generation-runs success
# ============================================================================


@pytest.mark.asyncio
async def test_project_generation_runs_success(
    client, test_project, test_generation_run,
):
    """GET /api/v1/projects/{project_id}/generation-runs should return runs."""
    resp = await client.get(f"/api/v1/projects/{test_project.id}/generation-runs")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["project_id"] == test_project.id
    assert data["total_count"] == 1
    assert len(data["generation_runs"]) == 1
    assert data["generation_runs"][0]["id"] == test_generation_run.id


# ============================================================================
# Test 11: GET /stamp-candidates/{candidate_id} success
# ============================================================================


@pytest.mark.asyncio
async def test_stamp_candidate_detail_success(
    client, test_stamp_candidates,
):
    """GET /api/v1/stamp-candidates/{candidate_id} should return candidate details."""
    candidate_id = test_stamp_candidates[0].id
    resp = await client.get(f"/api/v1/stamp-candidates/{candidate_id}")
    assert resp.status_code == status.HTTP_200_OK
    body = resp.json()
    assert body["code"] == 200
    data = body["data"]
    assert data["id"] == candidate_id
    assert data["targeting_peptide_seq"] is not None
    assert data["full_sequence"] is not None
    assert data["composite_score"] is not None


# ============================================================================
# Test 12: stamp candidate not found returns 404
# ============================================================================


@pytest.mark.asyncio
async def test_stamp_candidate_detail_not_found(client):
    """GET with non-existent candidate_id should return 404."""
    resp = await client.get("/api/v1/stamp-candidates/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


# ============================================================================
# Test 13: validation_status remains NOT_EXPERIMENTALLY_VALIDATED
# ============================================================================


@pytest.mark.asyncio
async def test_validation_status_not_experimentally_validated(
    client, test_stamp_candidates,
):
    """All returned candidates must have NOT_EXPERIMENTALLY_VALIDATED status."""
    candidate_id = test_stamp_candidates[0].id
    resp = await client.get(f"/api/v1/stamp-candidates/{candidate_id}")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["data"]["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    # Also check stamp-results
    project_id = test_stamp_candidates[0].project_id
    resp2 = await client.get(f"/api/v1/projects/{project_id}/stamp-results")
    for c in resp2.json()["data"]["candidates"]:
        assert c["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ============================================================================
# Test 14: No fabricated experimental metrics
# ============================================================================


@pytest.mark.asyncio
async def test_no_fabricated_experimental_metrics(
    client, test_stamp_candidates,
):
    """Response must not contain fabricated experimental data."""
    candidate_id = test_stamp_candidates[0].id
    resp = await client.get(f"/api/v1/stamp-candidates/{candidate_id}")
    assert resp.status_code == status.HTTP_200_OK
    metrics = resp.json()["data"]["metrics"] or {}
    forbidden = [
        "MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent", "toxicity",
        "ipTM", "pDockQ", "docking_score", "delta_g", "ΔG",
    ]
    for key in forbidden:
        assert key not in metrics, f"Forbidden key '{key}' found in metrics"


# ============================================================================
# Test 15: v0.7 old interfaces not regressed
# ============================================================================


@pytest.mark.asyncio
async def test_old_interfaces_still_available(client):
    """v0.7 legacy endpoints must continue to respond."""
    # /health
    resp = await client.get("/health")
    assert resp.status_code == status.HTTP_200_OK

    # /api/v1/targeting-peptide/generate
    resp2 = await client.post(
        "/api/v1/targeting-peptide/generate",
        json={
            "source_epitope": {
                "candidate_id": "epi_1",
                "sequence": "MKKTAIAATAVLATA",
                "start": 1,
                "end": 15,
            }
        },
    )
    assert resp2.status_code == status.HTTP_200_OK

    # /api/v1/final-ranking/compute
    resp3 = await client.post(
        "/api/v1/final-ranking/compute",
        json={
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
        },
    )
    assert resp3.status_code == status.HTTP_200_OK
