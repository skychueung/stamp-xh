"""Tests for wet-lab validation report export service and API."""

from __future__ import annotations


import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.experimental_validation import create_validation_run, add_measurement
from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base, get_db
from app.main import create_app
import app.models.orm  # noqa: F401
from app.schemas.experimental_validation import ExperimentalValidationRunCreate, ExperimentalMeasurementCreate
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
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
    return create_project(db_session, ProjectCreate(name="Report Export Test Project"))


@pytest.fixture
def test_generation_run(db_session, test_project):
    return create_stamp_generation_run(
        db_session, StampGenerationRunCreate(project_id=test_project.id)
    )


@pytest.fixture
def test_candidate(db_session, test_project, test_generation_run):
    return create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="MKWVTFISLL",
            linker_seq="GGGGS",
            full_sequence="MKWVTFISLLGGGGS",
        ),
    )


@pytest.fixture
def test_app(db_session):
    Base.metadata.create_all(bind=db_session.bind)
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


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------

def test_json_report_no_data(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    assert report["project_id"] == test_project.id
    assert report["report_type"] == "STAMP_WETLAB_VALIDATION_REPORT"
    assert "generated_at" in report
    assert report["scientific_boundary"]["experimental_data_user_provided_only"] is True
    assert report["summary"]["candidate_count"] >= 1
    assert report["summary"]["candidates_with_measurements"] == 0
    assert report["summary"]["experimental_coverage_percent"] == 0.0

    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["sequence"] == test_candidate.full_sequence
    assert cand["experimental_measurements"] == []
    assert cand["measurement_count"] == 0


def test_json_report_with_mic_measurement(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data

    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.0,
            unit="ug/ml",
        ),
    )

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    assert report["summary"]["candidates_with_measurements"] >= 1

    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    assert len(cand["experimental_measurements"]) >= 1
    mic_measurement = next(m for m in cand["experimental_measurements"] if m["metric_name"] == "MIC_ug_ml")
    assert mic_measurement["value"] == 2.0
    assert mic_measurement["unit"] == "ug/ml"


def test_json_report_with_hemolysis_measurement(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data

    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="HEMOLYSIS",
        ),
    )
    add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=5.0,
            unit="%",
        ),
    )

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    hem_measurement = next(m for m in cand["experimental_measurements"] if m["metric_name"] == "hemolysis_percent")
    assert hem_measurement["value"] == 5.0


def test_report_computational_metrics_in_reference_only(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data

    # Set some computational metrics on candidate
    test_candidate.metrics = {
        "structure_prediction": {"mean_plddt": 75.5},
        "interface_quality": {"pdockq": 0.65},
        "energy_quality": {"interaction_energy_kcal_mol": 86.3},
    }
    db_session.add(test_candidate)
    db_session.commit()

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)

    assert "computational_reference" in cand
    assert cand["computational_reference"]["mean_plddt"] == 75.5
    assert cand["computational_reference"]["pdockq"] == 0.65
    assert cand["computational_reference"]["interaction_energy_kcal_mol"] == 86.3
    # No computational metrics in experimental_measurements
    for m in cand["experimental_measurements"]:
        assert m["metric_name"] not in ("mean_plddt", "pdockq", "interaction_energy_kcal_mol")


def test_report_manual_shortlist_appears(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data
    from app.services.candidate_prioritization_service import save_candidate_priority_decision

    save_candidate_priority_decision(
        db_session, test_candidate.id,
        {"decision": "SHORTLIST", "decision_reason": "Low MIC and acceptable hemolysis.", "reviewer": "Dr. X"}
    )

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["manual_decision"] is not None
    assert cand["manual_decision"]["decision"] == "SHORTLIST"
    assert cand["manual_decision"]["decision_reason"] == "Low MIC and acceptable hemolysis."


def test_report_shortlist_does_not_change_validation_status(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data
    from app.services.candidate_prioritization_service import save_candidate_priority_decision

    original_status = test_candidate.validation_status
    save_candidate_priority_decision(
        db_session, test_candidate.id,
        {"decision": "SHORTLIST", "decision_reason": "Good candidate.", "reviewer": "Dr. X"}
    )

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["validation_status"] == original_status
    assert cand["validation_status"] != "EXPERIMENTALLY_VALIDATED"


def test_report_no_fabrication_without_measurements(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    cand = next(c for c in report["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["measurement_count"] == 0
    assert cand["experimental_measurements"] == []
    # No MIC/MBC/hemolysis should appear
    for m in cand["experimental_measurements"]:
        assert m["metric_name"] not in ("MIC_ug_ml", "MBC_ug_ml", "hemolysis_percent")


def test_markdown_report_renders(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data, render_wetlab_report_markdown

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    md = render_wetlab_report_markdown(report)
    assert "# STAMP Wet-lab Validation Report" in md
    assert "Scientific Boundary" in md
    assert "Project Summary" in md
    assert test_project.id in md


def test_csv_report_renders(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data, render_wetlab_report_csv

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    csv_content = render_wetlab_report_csv(report)
    assert "candidate_id,sequence,validation_status" in csv_content
    assert test_candidate.id in csv_content


def test_integrity_validator_passes_clean_report(db_session, test_project, test_candidate):
    from app.services.wetlab_report_export import build_wetlab_validation_report_data, validate_wetlab_report_integrity

    report = build_wetlab_validation_report_data(db_session, test_project.id, top_k=50)
    errors = validate_wetlab_report_integrity(report)
    assert errors == []


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_api_json_report(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=json"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["project_id"] == test_project.id
    assert data["report_type"] == "STAMP_WETLAB_VALIDATION_REPORT"
    assert "candidates" in data


@pytest.mark.asyncio
async def test_api_markdown_report(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=markdown"
    )
    assert resp.status_code == status.HTTP_200_OK
    text = resp.text
    assert "# STAMP Wet-lab Validation Report" in text
    assert "Experimental measurements in this report are user-entered" in text


@pytest.mark.asyncio
async def test_api_csv_report(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=csv"
    )
    assert resp.status_code == status.HTTP_200_OK
    text = resp.text
    assert "candidate_id,sequence,validation_status" in text


@pytest.mark.asyncio
async def test_api_invalid_format_returns_400(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=xml"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "format must be one of" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_project_not_found(async_client, test_project, test_candidate):
    resp = await async_client.get(
        "/api/v1/experimental-validation/projects/nonexistent-project/wetlab-validation-report?format=json"
    )
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.asyncio
async def test_api_report_with_measurements(async_client, test_project, test_candidate, db_session):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.5,
            unit="ug/ml",
        ),
    )

    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=json"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    cand = next(c for c in data["candidates"] if c["candidate_id"] == test_candidate.id)
    assert len(cand["experimental_measurements"]) >= 1
    mic = next(m for m in cand["experimental_measurements"] if m["metric_name"] == "MIC_ug_ml")
    assert mic["value"] == 2.5


@pytest.mark.asyncio
async def test_api_report_shortlist_in_json(async_client, test_project, test_candidate, db_session):
    from app.services.candidate_prioritization_service import save_candidate_priority_decision

    save_candidate_priority_decision(
        db_session, test_candidate.id,
        {"decision": "SHORTLIST", "decision_reason": "Good candidate.", "reviewer": "Dr. X"}
    )

    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/wetlab-validation-report?format=json"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    cand = next(c for c in data["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["manual_decision"] is not None
    assert cand["manual_decision"]["decision"] == "SHORTLIST"
    assert cand["validation_status"] != "EXPERIMENTALLY_VALIDATED"
