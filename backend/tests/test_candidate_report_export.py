"""Tests for candidate report export (v0.10-P7).

Validates JSON/Markdown/CSV report generation, scientific boundary
enforcement, and API endpoint behavior.
"""

from __future__ import annotations

import json

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate
from app.database import Base, get_db
from app.main import create_app
from app.schemas import ProjectCreate, StampCandidateCreate
from app.services.candidate_report_export import (
    build_candidate_report_data,
    render_candidate_report_csv,
    render_candidate_report_markdown,
    validate_report_no_fabricated_metrics,
)

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
    proj = create_project(db_session, ProjectCreate(name="Report Export Test Project"))
    return proj


@pytest.fixture
def test_candidates(db_session, test_project):
    """Create stamp candidates with full metrics."""
    cands = []
    for i in range(3):
        cand = create_stamp_candidate(
            db_session,
            StampCandidateCreate(
                project_id=test_project.id,
                targeting_peptide_seq=f"ACDEFGHIKLMNPQR{i}",
                linker_seq="EAAAK",
                full_sequence=f"ACDEFGHIKLMNPQR{i}EAAAKFSRFLRRVRRYRPKISFNLEPFFKF",
                composite_score=float(90 - i * 10),
                metrics={
                    "source": "pepmlm_650m_real",
                    "ppl": 10.73 + i,
                    "charge": 1.0 + i,
                    "pi": 7.4 + i,
                    "structure_prediction": {
                        "mean_plddt": 65.23,
                        "ptm": 0.28,
                        "iptm": None,
                        "prediction_status": "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY",
                        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                    },
                    "interface_quality": {
                        "pdockq": 0.644,
                        "input_features": {
                            "interface_contact_count": 149,
                            "interface_residue_plddt_mean": 37.62,
                        },
                        "prediction_status": "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY",
                        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                    },
                    "energy_quality": {
                        "source": "foldx_analysecomplex",
                        "interaction_energy_kcal_mol": 86.3008,
                        "energy_terms": {
                            "backbone_hbond": -4.29,
                            "sidechain_hbond": -8.36,
                            "van_der_waals": -17.56,
                            "electrostatics": -1.67,
                            "vdw_clashes": 89.04,
                        },
                        "quality_flags": {
                            "unfavorable_interaction_energy": True,
                            "high_vdw_clashes": True,
                            "interpretation": "Positive interaction energy suggests unfavorable model.",
                        },
                        "prediction_status": "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY",
                        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                    },
                },
            ),
        )
        cands.append(cand)
    return cands


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
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Service tests
# ---------------------------------------------------------------------------


def test_build_report_data_structure(db_session, test_project, test_candidates):
    """Report data must have correct top-level structure."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    assert data["project_id"] == test_project.id
    assert data["report_type"] == "STAMP_CANDIDATE_REPORT"
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert "generated_at" in data
    assert "summary" in data
    assert "scientific_boundary" in data
    assert "candidates" in data


def test_build_report_summary(db_session, test_project, test_candidates):
    """Summary must reflect available metrics."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    summary = data["summary"]
    assert summary["candidate_count"] == 3
    assert summary["has_structure_prediction"] is True
    assert summary["has_interface_quality"] is True
    assert summary["has_energy_quality"] is True


def test_build_report_candidates_count(db_session, test_project, test_candidates):
    """Report must include correct number of candidates."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    assert len(data["candidates"]) == 3


def test_build_report_candidate_fields(db_session, test_project, test_candidates):
    """Each candidate must have required fields."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    c = data["candidates"][0]
    assert c["rank"] == 1
    assert c["candidate_id"] == test_candidates[0].id
    assert c["composite_score"] == 90.0
    assert c["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert "generation" in c
    assert "structure_prediction" in c
    assert "interface_quality" in c
    assert "energy_quality" in c


def test_build_report_structure_prediction(db_session, test_project, test_candidates):
    """Structure prediction fields must be present."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    sp = data["candidates"][0]["structure_prediction"]
    assert sp["mean_plddt"] == 65.23
    assert sp["ptm"] == 0.28
    assert sp["iptm"] is None
    assert sp["prediction_status"] == "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"


def test_build_report_interface_quality(db_session, test_project, test_candidates):
    """Interface quality fields must be present."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    iq = data["candidates"][0]["interface_quality"]
    assert iq["pdockq"] == 0.644
    assert iq["interface_contacts"] == 149
    assert iq["prediction_status"] == "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"


def test_build_report_energy_quality(db_session, test_project, test_candidates):
    """Energy quality fields must be present."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    eq = data["candidates"][0]["energy_quality"]
    assert eq["interaction_energy_kcal_mol"] == 86.3008
    assert eq["vdw_clashes"] == 89.04
    assert eq["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"
    assert eq["not_docking_score"] is True
    assert eq["not_mmgbsa_delta_g"] is True


def test_build_report_top_k(db_session, test_project, test_candidates):
    """top_k must limit candidate count."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=2)
    assert len(data["candidates"]) == 2
    assert data["candidates"][0]["composite_score"] == 90.0
    assert data["candidates"][1]["composite_score"] == 80.0


def test_build_report_no_candidates_empty(db_session, test_project):
    """Project with no candidates must return empty report."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    assert data["summary"]["candidate_count"] == 0
    assert data["candidates"] == []


def test_build_report_missing_project_raises(db_session):
    """Missing project must raise ValueError."""
    with pytest.raises(ValueError, match="not found"):
        build_candidate_report_data(db_session, "nonexistent-project", top_k=10)


# ---------------------------------------------------------------------------
# Markdown tests
# ---------------------------------------------------------------------------


def test_markdown_contains_title(db_session, test_project, test_candidates):
    """Markdown must contain STAMP Candidate Report title."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    md = render_candidate_report_markdown(data)
    assert "# STAMP Candidate Report" in md


def test_markdown_contains_scientific_boundary(db_session, test_project, test_candidates):
    """Markdown must contain scientific boundary section."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    md = render_candidate_report_markdown(data)
    assert "Scientific Boundary" in md
    assert "NOT experimentally validated" in md
    assert "MIC" in md
    assert "docking_score" in md
    assert "MM-GBSA" in md


def test_markdown_contains_candidate_details(db_session, test_project, test_candidates):
    """Markdown must contain candidate details."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    md = render_candidate_report_markdown(data)
    assert "Rank 1" in md
    assert "86.3008" in md
    assert "0.644" in md


def test_markdown_contains_structure_validation_section(db_session, test_project, test_candidates):
    """Markdown must contain Computational Structure Validation section."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    md = render_candidate_report_markdown(data)
    assert "Computational Structure Validation" in md
    assert "Structure Prediction" in md
    assert "Interface Quality" in md
    assert "FoldX Energy Quality" in md


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------


def test_csv_contains_header(db_session, test_project, test_candidates):
    """CSV must contain expected header columns."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    csv_text = render_candidate_report_csv(data)
    assert "rank,candidate_id" in csv_text
    assert "interaction_energy_kcal_mol" in csv_text
    assert "vdw_clashes" in csv_text
    assert "energy_interpretation" in csv_text


def test_csv_contains_candidate_data(db_session, test_project, test_candidates):
    """CSV must contain candidate data rows."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    csv_text = render_candidate_report_csv(data)
    lines = csv_text.strip().split("\n")
    assert len(lines) == 4  # header + 3 candidates
    assert "86.3008" in csv_text
    assert "0.644" in csv_text
    assert "149" in csv_text


def test_csv_empty_candidates(db_session, test_project):
    """CSV with no candidates must have only header."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    csv_text = render_candidate_report_csv(data)
    lines = csv_text.strip().split("\n")
    assert len(lines) == 1


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


def test_validate_report_passes_clean(db_session, test_project, test_candidates):
    """Clean report must pass validation."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    validate_report_no_fabricated_metrics(data)  # should not raise


def test_validate_report_rejects_mic(db_session, test_project, test_candidates):
    """Report containing MIC must fail validation."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    data["MIC"] = 0.5
    with pytest.raises(ValueError, match="Forbidden"):
        validate_report_no_fabricated_metrics(data)


def test_validate_report_rejects_docking_score(db_session, test_project, test_candidates):
    """Candidate with non-null docking_score must fail validation."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    data["candidates"][0]["energy_quality"]["docking_score"] = -5.2
    with pytest.raises(ValueError, match="docking_score"):
        validate_report_no_fabricated_metrics(data)


def test_validate_report_rejects_mmgbsa(db_session, test_project, test_candidates):
    """Candidate with non-null mmgbsa_delta_G must fail validation."""
    data = build_candidate_report_data(db_session, test_project.id, top_k=10)
    data["candidates"][0]["energy_quality"]["mmgbsa_delta_G"] = -15.3
    with pytest.raises(ValueError, match="mmgbsa_delta_G"):
        validate_report_no_fabricated_metrics(data)


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_json_report(async_client, db_session, test_project, test_candidates):
    """GET /projects/{id}/candidate-report?format=json must return report data."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=json&top_k=10"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["report_type"] == "STAMP_CANDIDATE_REPORT"
    assert len(data["candidates"]) == 3


@pytest.mark.asyncio
async def test_api_markdown_report(async_client, db_session, test_project, test_candidates):
    """GET /projects/{id}/candidate-report?format=markdown must return markdown."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=markdown&top_k=10"
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers["content-type"].startswith("text/markdown")
    assert "# STAMP Candidate Report" in resp.text


@pytest.mark.asyncio
async def test_api_csv_report(async_client, db_session, test_project, test_candidates):
    """GET /projects/{id}/candidate-report?format=csv must return csv."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=csv&top_k=10"
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.headers["content-type"].startswith("text/csv")
    assert "rank,candidate_id" in resp.text


@pytest.mark.asyncio
async def test_api_invalid_format(async_client, db_session, test_project, test_candidates):
    """Invalid format must return 422."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=xml&top_k=10"
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_api_project_not_found(async_client, db_session):
    """Non-existent project must return 404."""
    resp = await async_client.get(
        "/api/v1/projects/nonexistent-project/candidate-report?format=json"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_api_no_candidates(async_client, db_session, test_project):
    """Project with no candidates must return empty report (200, not error)."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=json"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["summary"]["candidate_count"] == 0
    assert data["candidates"] == []


@pytest.mark.asyncio
async def test_api_validation_status_all_not_experimentally_validated(
    async_client, db_session, test_project, test_candidates
):
    """All candidates in report must have NOT_EXPERIMENTALLY_VALIDATED."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=json"
    )
    data = resp.json()["data"]
    for c in data["candidates"]:
        assert c["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
async def test_api_computational_status_preserved(
    async_client, db_session, test_project, test_candidates
):
    """All computational statuses must be preserved in API response."""
    resp = await async_client.get(
        f"/api/v1/projects/{test_project.id}/candidate-report?format=json"
    )
    data = resp.json()["data"]
    c = data["candidates"][0]
    assert c["structure_prediction"]["prediction_status"] == "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"
    assert c["interface_quality"]["prediction_status"] == "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"
    assert c["energy_quality"]["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"
