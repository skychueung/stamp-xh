"""Tests for experimental validation ORM models and basic CRUD."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models.orm  # Ensure all ORM tables are registered in Base.metadata
from app.crud.experimental_validation import (
    add_measurement,
    create_validation_run,
    get_measurement,
    get_validation_run,
    list_measurements_by_candidate,
    list_measurements_by_run,
    list_validation_runs_by_candidate,
    summarize_candidate_experimental_validation,
)
from app.services.experimental_validation_service import (
    create_experimental_validation_run as svc_create_validation_run,
)
from app.crud.projects import create_project
from app.crud.stamp_candidates import create_stamp_candidate, create_stamp_generation_run
from app.models.orm import ExperimentalMeasurement, ExperimentalValidationRun
from app.schemas.experimental_validation import (
    ExperimentalMeasurementCreate,
    ExperimentalValidationRunCreate,
)
from app.schemas.project import ProjectCreate
from app.schemas.stamp import StampCandidateCreate, StampGenerationRunCreate

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh in-memory DB session for each test."""
    # Ensure all ORM models are registered before creating tables
    import app.models.orm  # noqa: F401
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_project(db_session):
    return create_project(db_session, ProjectCreate(name="Test Project"))


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


# ---------------------------------------------------------------------------
# 1. Create validation run
# ---------------------------------------------------------------------------

def test_create_validation_run(db_session, test_project, test_candidate):
    run = svc_create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
            organism="Staphylococcus aureus",
            protocol_name="broth microdilution",
        ),
    )
    assert run.id is not None
    assert run.experiment_type == "MIC"
    assert run.status == "PLANNED"
    assert run.validation_status == "EXPERIMENT_PLANNED"


# ---------------------------------------------------------------------------
# 2. Add MIC measurement
# ---------------------------------------------------------------------------

def test_add_mic_measurement(db_session, test_project, test_candidate):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    m = add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="MIC_ug_ml",
            value=2.5,
            unit="ug/ml",
            quality_flag="PASS",
        ),
    )
    assert m.metric_name == "MIC_ug_ml"
    assert m.value == 2.5
    assert m.quality_flag == "PASS"


# ---------------------------------------------------------------------------
# 3. Add MBC measurement
# ---------------------------------------------------------------------------

def test_add_mbc_measurement(db_session, test_project, test_candidate):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MBC",
        ),
    )
    m = add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="MBC_ug_ml",
            value=5.0,
            unit="ug/ml",
            quality_flag="PASS",
        ),
    )
    assert m.metric_name == "MBC_ug_ml"
    assert m.value == 5.0


# ---------------------------------------------------------------------------
# 4. Add hemolysis measurement
# ---------------------------------------------------------------------------

def test_add_hemolysis_measurement(db_session, test_project, test_candidate):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="HEMOLYSIS",
        ),
    )
    m = add_measurement(
        db_session,
        ExperimentalMeasurementCreate(
            validation_run_id=run.id,
            candidate_id=test_candidate.id,
            metric_name="hemolysis_percent",
            value=5.0,
            unit="%",
            quality_flag="PASS",
        ),
    )
    assert m.metric_name == "hemolysis_percent"
    assert m.value == 5.0


# ---------------------------------------------------------------------------
# 5. MIC cannot be negative
# ---------------------------------------------------------------------------

def test_mic_cannot_be_negative(db_session, test_project, test_candidate):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    with pytest.raises(ValueError, match="must be >= 0"):
        add_measurement(
            db_session,
            ExperimentalMeasurementCreate(
                validation_run_id=run.id,
                candidate_id=test_candidate.id,
                metric_name="MIC_ug_ml",
                value=-1.0,
                unit="ug/ml",
                quality_flag="PASS",
            ),
        )


# ---------------------------------------------------------------------------
# 6. hemolysis_percent cannot exceed 100
# ---------------------------------------------------------------------------

def test_hemolysis_percent_cannot_exceed_100(db_session, test_project, test_candidate):
    run = create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="HEMOLYSIS",
        ),
    )
    with pytest.raises(ValueError, match="must be between 0 and 100"):
        add_measurement(
            db_session,
            ExperimentalMeasurementCreate(
                validation_run_id=run.id,
                candidate_id=test_candidate.id,
                metric_name="hemolysis_percent",
                value=105.0,
                unit="%",
                quality_flag="PASS",
            ),
        )


# ---------------------------------------------------------------------------
# Additional: list and summary helpers
# ---------------------------------------------------------------------------

def test_list_validation_runs_by_candidate(db_session, test_project, test_candidate):
    create_validation_run(
        db_session,
        ExperimentalValidationRunCreate(
            project_id=test_project.id,
            candidate_id=test_candidate.id,
            experiment_type="MIC",
        ),
    )
    runs = list_validation_runs_by_candidate(db_session, test_candidate.id)
    assert len(runs) == 1


def test_summarize_candidate_experimental_validation_no_data(
    db_session, test_candidate
):
    summary = summarize_candidate_experimental_validation(db_session, test_candidate.id)
    assert summary["overall_validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert summary["measurement_count"] == 0
