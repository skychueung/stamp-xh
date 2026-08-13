"""STAMP Platform — Experimental Validation CRUD (v0.11-P1).

Plain-function CRUD for experimental validation runs and measurements.
"""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.orm import (
    ExperimentalMeasurement,
    ExperimentalValidationRun,
    StampCandidate,
)
from app.schemas.experimental_validation import (
    ExperimentalMeasurementCreate,
    ExperimentalValidationRunCreate,
    ExperimentalValidationRunUpdate,
)


# ---------------------------------------------------------------------------
# Validation Runs
# ---------------------------------------------------------------------------

def create_validation_run(
    db: Session, obj_in: ExperimentalValidationRunCreate
) -> ExperimentalValidationRun:
    """Create a new experimental validation run."""
    db_obj = ExperimentalValidationRun(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_validation_run(
    db: Session, run_id: str
) -> Optional[ExperimentalValidationRun]:
    """Get a validation run by ID."""
    return db.query(ExperimentalValidationRun).filter(
        ExperimentalValidationRun.id == run_id
    ).first()


def list_validation_runs_by_candidate(
    db: Session, candidate_id: str
) -> List[ExperimentalValidationRun]:
    """List all validation runs for a candidate."""
    return (
        db.query(ExperimentalValidationRun)
        .filter(ExperimentalValidationRun.candidate_id == candidate_id)
        .order_by(ExperimentalValidationRun.created_at.desc())
        .all()
    )


def list_validation_runs_by_project(
    db: Session, project_id: str
) -> List[ExperimentalValidationRun]:
    """List all validation runs for a project."""
    return (
        db.query(ExperimentalValidationRun)
        .filter(ExperimentalValidationRun.project_id == project_id)
        .order_by(ExperimentalValidationRun.created_at.desc())
        .all()
    )


def update_validation_run(
    db: Session,
    db_obj: ExperimentalValidationRun,
    obj_in: ExperimentalValidationRunUpdate,
) -> ExperimentalValidationRun:
    """Update a validation run (partial)."""
    update_data = obj_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_obj, field, value)
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


# ---------------------------------------------------------------------------
# Measurements
# ---------------------------------------------------------------------------

def add_measurement(
    db: Session, obj_in: ExperimentalMeasurementCreate
) -> ExperimentalMeasurement:
    """Add a new experimental measurement."""
    db_obj = ExperimentalMeasurement(**obj_in.model_dump())
    db.add(db_obj)
    db.commit()
    db.refresh(db_obj)
    return db_obj


def get_measurement(
    db: Session, measurement_id: str
) -> Optional[ExperimentalMeasurement]:
    """Get a measurement by ID."""
    return db.query(ExperimentalMeasurement).filter(
        ExperimentalMeasurement.id == measurement_id
    ).first()


def list_measurements_by_run(
    db: Session, run_id: str
) -> List[ExperimentalMeasurement]:
    """List all measurements for a validation run."""
    return (
        db.query(ExperimentalMeasurement)
        .filter(ExperimentalMeasurement.validation_run_id == run_id)
        .order_by(ExperimentalMeasurement.created_at.desc())
        .all()
    )


def list_measurements_by_candidate(
    db: Session, candidate_id: str
) -> List[ExperimentalMeasurement]:
    """List all measurements for a candidate across all runs."""
    return (
        db.query(ExperimentalMeasurement)
        .filter(ExperimentalMeasurement.candidate_id == candidate_id)
        .order_by(ExperimentalMeasurement.created_at.desc())
        .all()
    )


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def summarize_candidate_experimental_validation(
    db: Session, candidate_id: str
) -> dict:
    """Return a summary dict of experimental validation for a candidate."""
    from app.crud.stamp_candidates import get_stamp_candidate

    runs = list_validation_runs_by_candidate(db, candidate_id)
    measurements = list_measurements_by_candidate(db, candidate_id)

    completed_runs = [r for r in runs if r.status == "COMPLETED"]
    failed_runs = [r for r in runs if r.status == "FAILED"]

    # Determine overall status from candidate first, then fall back to runs
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is not None and candidate.validation_status != "NOT_EXPERIMENTALLY_VALIDATED":
        overall_status = candidate.validation_status
    elif runs:
        status_priority = {
            "VALIDATION_FAILED": 5,
            "EXPERIMENTALLY_VALIDATED": 4,
            "PARTIALLY_VALIDATED": 3,
            "EXPERIMENT_PLANNED": 2,
            "NOT_EXPERIMENTALLY_VALIDATED": 1,
        }
        best_run = max(
            runs,
            key=lambda r: status_priority.get(r.validation_status, 0),
        )
        overall_status = best_run.validation_status
    else:
        overall_status = "NOT_EXPERIMENTALLY_VALIDATED"

    return {
        "candidate_id": candidate_id,
        "overall_validation_status": overall_status,
        "run_count": len(runs),
        "completed_run_count": len(completed_runs),
        "failed_run_count": len(failed_runs),
        "measurement_count": len(measurements),
        "runs": runs,
        "measurements": measurements,
    }


def get_project_experimental_summary(db: Session, project_id: str) -> dict:
    """Return project-level experimental validation summary."""
    runs = list_validation_runs_by_project(db, project_id)
    candidates = (
        db.query(StampCandidate)
        .filter(StampCandidate.project_id == project_id)
        .all()
    )

    total_candidates = len(candidates)
    candidate_ids_with_data = {r.candidate_id for r in runs}
    candidates_with_data = len(candidate_ids_with_data)

    # Validation status counts (from candidates, not runs)
    validation_status_counts: dict[str, int] = {}
    for c in candidates:
        validation_status_counts[c.validation_status] = (
            validation_status_counts.get(c.validation_status, 0) + 1
        )

    # Measurement counts by metric_name
    from app.models.orm import ExperimentalMeasurement
    measurements = (
        db.query(ExperimentalMeasurement)
        .filter(ExperimentalMeasurement.candidate_id.in_([c.id for c in candidates]))
        .all()
    )
    measurement_counts: dict[str, int] = {}
    for m in measurements:
        measurement_counts[m.metric_name] = (
            measurement_counts.get(m.metric_name, 0) + 1
        )

    # Coverage metrics
    candidate_ids_with_measurement = {m.candidate_id for m in measurements}
    candidate_ids_with_mic = {
        m.candidate_id for m in measurements
        if m.metric_name in ("MIC_ug_ml", "MBC_ug_ml")
    }
    candidate_ids_with_safety = {
        m.candidate_id for m in measurements
        if m.metric_name in ("hemolysis_percent", "cell_viability_percent", "HC50_ug_ml", "IC50_ug_ml")
    }
    coverage_percent = (
        round(len(candidate_ids_with_measurement) / total_candidates * 100, 1)
        if total_candidates > 0 else 0.0
    )

    return {
        "project_id": project_id,
        "total_candidates": total_candidates,
        "candidates_with_experimental_data": candidates_with_data,
        "candidates_fully_validated": validation_status_counts.get("EXPERIMENTALLY_VALIDATED", 0),
        "candidates_failed_validation": validation_status_counts.get("VALIDATION_FAILED", 0),
        "candidates_pending": validation_status_counts.get("NOT_EXPERIMENTALLY_VALIDATED", 0),
        "experiment_type_counts": {r.experiment_type: sum(1 for x in runs if x.experiment_type == r.experiment_type) for r in runs},
        "validation_status_counts": validation_status_counts,
        "measurement_counts": measurement_counts,
        "coverage": {
            "candidates_with_any_measurement": len(candidate_ids_with_measurement),
            "candidates_with_mic": len(candidate_ids_with_mic),
            "candidates_with_safety": len(candidate_ids_with_safety),
            "experimental_coverage_percent": coverage_percent,
        },
        "top_priority_candidates": [],  # Populated by service layer
    }
