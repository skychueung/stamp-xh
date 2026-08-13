"""Tests for candidate prioritization service and API."""

from __future__ import annotations

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base, get_db
from app.main import create_app
import app.models.orm  # noqa: F401
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
    return create_project(db_session, ProjectCreate(name="Prioritization Test Project"))


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
# Service-level priority_status tests
# ---------------------------------------------------------------------------

def test_no_data_needs_more_data(db_session, test_project, test_generation_run):
    from app.services.candidate_prioritization_service import compute_priority_status
    from app.crud.stamp_candidates import create_stamp_candidate
    from app.schemas.stamp import StampCandidateCreate

    c = create_stamp_candidate(
        db_session,
        StampCandidateCreate(
            project_id=test_project.id,
            generation_run_id=test_generation_run.id,
            targeting_peptide_seq="AAA",
            linker_seq="GGGGS",
            full_sequence="AAAGGGGS",
        ),
    )
    status = compute_priority_status(c, [])
    assert status == "NEEDS_MORE_DATA"


def test_mic_but_no_safety_needs_more_data(db_session, test_project, test_candidate):
    from app.services.candidate_prioritization_service import compute_priority_status
    from app.crud.experimental_validation import create_validation_run, add_measurement
    from app.schemas.experimental_validation import ExperimentalValidationRunCreate, ExperimentalMeasurementCreate

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
    db_session.refresh(test_candidate)
    from app.crud.experimental_validation import list_measurements_by_candidate
    m = list_measurements_by_candidate(db_session, test_candidate.id)
    status = compute_priority_status(test_candidate, m)
    assert status == "NEEDS_MORE_DATA"


def test_mic_and_low_hemolysis_ready_for_review(db_session, test_project, test_candidate):
    from app.services.candidate_prioritization_service import compute_priority_status
    from app.crud.experimental_validation import create_validation_run, add_measurement
    from app.schemas.experimental_validation import ExperimentalValidationRunCreate, ExperimentalMeasurementCreate

    run1 = create_validation_run(
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
            validation_run_id=run1.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.0,
            unit="ug/ml",
        ),
    )

    run2 = create_validation_run(
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
            validation_run_id=run2.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=5.0,
            unit="%",
        ),
    )

    from app.crud.experimental_validation import list_measurements_by_candidate
    m = list_measurements_by_candidate(db_session, test_candidate.id)
    status = compute_priority_status(test_candidate, m)
    assert status == "READY_FOR_REVIEW"


def test_high_hemolysis_safety_concern(db_session, test_project, test_candidate):
    from app.services.candidate_prioritization_service import compute_priority_status
    from app.crud.experimental_validation import create_validation_run, add_measurement
    from app.schemas.experimental_validation import ExperimentalValidationRunCreate, ExperimentalMeasurementCreate

    run1 = create_validation_run(
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
            validation_run_id=run1.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.0,
            unit="ug/ml",
        ),
    )

    run2 = create_validation_run(
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
            validation_run_id=run2.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=75.0,
            unit="%",
        ),
    )

    from app.crud.experimental_validation import list_measurements_by_candidate
    m = list_measurements_by_candidate(db_session, test_candidate.id)
    status = compute_priority_status(test_candidate, m)
    assert status == "SAFETY_CONCERN"


def test_validation_failed_status(db_session, test_project, test_candidate):
    from app.services.candidate_prioritization_service import compute_priority_status
    test_candidate.validation_status = "VALIDATION_FAILED"
    db_session.add(test_candidate)
    db_session.commit()

    status = compute_priority_status(test_candidate, [])
    assert status == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# API-level tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_project_prioritization_api_returns_candidates(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/candidate-prioritization"
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["project_id"] == test_project.id
    assert data["summary"]["candidate_count"] >= 1
    assert len(data["candidates"]) >= 1
    cand = next(c for c in data["candidates"] if c["candidate_id"] == test_candidate.id)
    assert cand["sequence"] == test_candidate.full_sequence
    assert "computational_summary" in cand
    assert "experimental_summary" in cand


@pytest.mark.asyncio
async def test_project_prioritization_summary_counts(async_client, test_project, test_candidate):
    resp = await async_client.get(
        f"/api/v1/experimental-validation/projects/{test_project.id}/candidate-prioritization"
    )
    assert resp.status_code == status.HTTP_200_OK
    summary = resp.json()["data"]["summary"]
    assert summary["candidate_count"] >= 1
    assert "needs_more_data" in summary
    assert "ready_for_review" in summary
    assert "safety_concern" in summary
    assert "validation_failed" in summary


@pytest.mark.asyncio
async def test_save_shortlist_decision_success(async_client, test_project, test_candidate):
    resp = await async_client.post(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority-decision",
        json={
            "decision": "SHORTLIST",
            "decision_reason": "Low MIC and acceptable hemolysis.",
            "reviewer": "test_user",
            "notes": "Prioritize for repeat assay.",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["candidate_id"] == test_candidate.id
    assert data["decision"]["decision"] == "SHORTLIST"
    assert data["decision"]["decision_reason"] == "Low MIC and acceptable hemolysis."


@pytest.mark.asyncio
async def test_save_reject_decision_success(async_client, test_project, test_candidate):
    resp = await async_client.post(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority-decision",
        json={
            "decision": "REJECT",
            "decision_reason": "High hemolysis makes this unsuitable.",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()["data"]
    assert data["decision"]["decision"] == "REJECT"


@pytest.mark.asyncio
async def test_decision_does_not_modify_composite_score(async_client, test_project, test_candidate):
    original_score = test_candidate.composite_score
    resp = await async_client.post(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority-decision",
        json={
            "decision": "SHORTLIST",
            "decision_reason": "Good candidate.",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["data"]["composite_score"] == original_score


@pytest.mark.asyncio
async def test_decision_does_not_modify_validation_status(async_client, test_project, test_candidate):
    original_status = test_candidate.validation_status
    resp = await async_client.post(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority-decision",
        json={
            "decision": "SHORTLIST",
            "decision_reason": "Good candidate.",
        },
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["data"]["validation_status"] == original_status
    assert resp.json()["data"]["validation_status"] != "EXPERIMENTALLY_VALIDATED"


@pytest.mark.asyncio
async def test_decision_empty_reason_fails(async_client, test_project, test_candidate):
    resp = await async_client.post(
        f"/api/v1/experimental-validation/candidates/{test_candidate.id}/priority-decision",
        json={
            "decision": "SHORTLIST",
            "decision_reason": "",
        },
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.asyncio
async def test_decision_unknown_candidate_404(async_client, test_project, test_candidate):
    resp = await async_client.post(
        "/api/v1/experimental-validation/candidates/nonexistent-candidate/priority-decision",
        json={
            "decision": "SHORTLIST",
            "decision_reason": "Good candidate.",
        },
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
