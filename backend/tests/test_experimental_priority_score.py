"""Tests for experimental validation status state machine and priority scoring."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.crud.experimental_validation import (
    add_measurement,
    create_validation_run,
)
from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.database import Base
from app.schemas.experimental_validation import (
    ExperimentalMeasurementCreate,
    ExperimentalValidationRunCreate,
)
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate
from app.services.experimental_validation_service import (
    _compute_experimental_activity,
    _compute_safety_score,
    _normalize_computational_score,
    compute_candidate_priority,
)

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory DB session for each test."""
    # Ensure all ORM models are registered before creating tables
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="Priority Test Project"))


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
            composite_score=0.85,
        ),
    )


# ---------------------------------------------------------------------------
# 12. No data → status NOT_EXPERIMENTALLY_VALIDATED
# ---------------------------------------------------------------------------

def test_no_data_status_not_experimentally_validated(db_session, test_candidate):
    assert test_candidate.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


# ---------------------------------------------------------------------------
# 13. Planned run → status EXPERIMENT_PLANNED
# ---------------------------------------------------------------------------

def test_planned_run_status_experiment_planned(db_session, test_project, test_candidate):
    from app.services.experimental_validation_service import (
        create_experimental_validation_run,
    )

    create_experimental_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    db_session.refresh(test_candidate)
    assert test_candidate.validation_status == "EXPERIMENT_PLANNED"


# ---------------------------------------------------------------------------
# 14. Completed measurement → status PARTIALLY_VALIDATED
# ---------------------------------------------------------------------------

def test_completed_measurement_status_partially_validated(
    db_session, test_project, test_candidate
):
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
            quality_flag="PASS",
        ),
    )
    # Update run status to COMPLETED
    run.status = "COMPLETED"
    db_session.add(run)
    db_session.commit()
    db_session.refresh(test_candidate)

    # Re-evaluate
    from app.services.experimental_validation_service import (
        _update_validation_status_from_measurements,
    )

    _update_validation_status_from_measurements(db_session, test_candidate.id)
    db_session.refresh(test_candidate)
    assert test_candidate.validation_status == "PARTIALLY_VALIDATED"


# ---------------------------------------------------------------------------
# 15. Cannot jump to EXPERIMENTALLY_VALIDATED without measurements
# ---------------------------------------------------------------------------

def test_cannot_jump_to_validated_without_measurements(
    db_session, test_project, test_candidate
):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    # Even if run is marked COMPLETED without measurements
    run.status = "COMPLETED"
    db_session.add(run)
    db_session.commit()

    from app.services.experimental_validation_service import (
        _update_validation_status_from_measurements,
    )

    _update_validation_status_from_measurements(db_session, test_candidate.id)
    db_session.refresh(test_candidate)
    assert test_candidate.validation_status != "EXPERIMENTALLY_VALIDATED"


# ---------------------------------------------------------------------------
# 16. Failed quality → status VALIDATION_FAILED
# ---------------------------------------------------------------------------

def test_failed_quality_status_validation_failed(
    db_session, test_project, test_candidate
):
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
            quality_flag="FAILED",
        ),
    )
    run.status = "COMPLETED"
    db_session.add(run)
    db_session.commit()

    from app.services.experimental_validation_service import (
        _update_validation_status_from_measurements,
    )

    _update_validation_status_from_measurements(db_session, test_candidate.id)
    db_session.refresh(test_candidate)
    assert test_candidate.validation_status == "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# 17. No experimental data → priority_score is None
# ---------------------------------------------------------------------------

def test_no_data_priority_score_is_none(db_session, test_candidate):
    result = compute_candidate_priority(db_session, test_candidate.id)
    assert result.experimental_priority_score is None
    assert result.priority_status == "PENDING_EXPERIMENTAL_DATA"
    assert result.has_experimental_data is False


# ---------------------------------------------------------------------------
# 18. MIC + safety data → priority_score computed
# ---------------------------------------------------------------------------

def test_mic_plus_safety_computes_priority_score(
    db_session, test_project, test_candidate
):
    # MIC run + measurement
    mic_run = create_validation_run(
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
            validation_run_id=mic_run.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.0,
            unit="ug/ml",
            quality_flag="PASS",
        ),
    )
    mic_run.status = "COMPLETED"
    db_session.add(mic_run)

    # Hemolysis run + measurement
    hem_run = create_validation_run(
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
            validation_run_id=hem_run.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=5.0,
            unit="%",
            quality_flag="PASS",
        ),
    )
    hem_run.status = "COMPLETED"
    db_session.add(hem_run)
    db_session.commit()

    # Trigger validation status update
    from app.services.experimental_validation_service import (
        _update_validation_status_from_measurements,
    )

    _update_validation_status_from_measurements(db_session, test_candidate.id)
    db_session.refresh(test_candidate)

    result = compute_candidate_priority(db_session, test_candidate.id)
    assert result.experimental_priority_score is not None
    assert result.has_experimental_data is True
    assert result.priority_status == "READY_FOR_PRIORITIZATION"


# ---------------------------------------------------------------------------
# 19. Priority score respects weights
# ---------------------------------------------------------------------------

def test_priority_score_computation(db_session, test_project, test_candidate):
    # Setup candidate with composite_score
    test_candidate.composite_score = 0.75
    db_session.add(test_candidate)

    # MIC run + measurement
    mic_run = create_validation_run(
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
            validation_run_id=mic_run.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.0,
            unit="ug/ml",
            quality_flag="PASS",
        ),
    )
    mic_run.status = "COMPLETED"
    db_session.add(mic_run)

    # Hemolysis run + measurement
    hem_run = create_validation_run(
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
            validation_run_id=hem_run.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=5.0,
            unit="%",
            quality_flag="PASS",
        ),
    )
    hem_run.status = "COMPLETED"
    db_session.add(hem_run)
    db_session.commit()

    result = compute_candidate_priority(db_session, test_candidate.id)
    assert result.experimental_priority_score is not None
    # computational_score_contribution should be around 0.75 * 0.40 = 0.30
    assert result.computational_score_contribution is not None
    assert result.computational_score_contribution > 0
    assert result.experimental_activity_contribution is not None
    assert result.safety_contribution is not None


# ---------------------------------------------------------------------------
# Unit tests for scoring helpers
# ---------------------------------------------------------------------------

def test_normalize_computational_score():
    assert _normalize_computational_score(0.85) == 0.85
    assert _normalize_computational_score(None) is None
    assert _normalize_computational_score(1.5) == 1.0
    assert _normalize_computational_score(-0.5) == 0.0


def test_compute_experimental_activity():
    class FakeMeas:
        def __init__(self, metric_name, value):
            self.metric_name = metric_name
            self.value = value

    measurements = [FakeMeas("MIC_ug_ml", 2.0)]
    score = _compute_experimental_activity(measurements)
    assert score is not None
    assert 0 < score < 1


def test_compute_safety_score():
    class FakeMeas:
        def __init__(self, metric_name, value):
            self.metric_name = metric_name
            self.value = value

    measurements = [FakeMeas("hemolysis_percent", 5.0)]
    score = _compute_safety_score(measurements)
    assert score is not None
    assert score > 0.9  # Low hemolysis = high safety score
