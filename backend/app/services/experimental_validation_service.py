"""STAMP Platform — Experimental Validation Service (v0.11-P1).

Business logic for wet-lab validation status state machine,
candidate priority scoring, and scientific-integrity enforcement.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.crud.experimental_validation import (
    add_measurement as crud_add_measurement,
    create_validation_run as crud_create_validation_run,
    list_measurements_by_candidate,
    list_validation_runs_by_candidate,
    summarize_candidate_experimental_validation,
    update_validation_run as crud_update_validation_run,
)
from app.crud.stamp_candidates import get_stamp_candidate
from app.schemas.experimental_validation import (
    CandidateExperimentalPriorityResponse,
    ExperimentalMeasurementCreate,
    ExperimentalValidationRunCreate,
    ExperimentalValidationRunUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Status state machine
# ---------------------------------------------------------------------------

REQUIRED_SAFETY_METRICS = {"hemolysis_percent", "cell_viability_percent", "HC50_ug_ml", "IC50_ug_ml"}
REQUIRED_ACTIVITY_METRICS = {"MIC_ug_ml", "MBC_ug_ml"}


def create_experimental_validation_run(
    db: Session, payload: ExperimentalValidationRunCreate
) -> Any:
    """Create a new experimental validation run.

    Defaults to PLANNED / EXPERIMENT_PLANNED. Does NOT auto-promote.
    """
    # Force safe defaults
    run_data = payload.model_dump()
    run_data["status"] = "PLANNED"

    db_obj = crud_create_validation_run(
        db, ExperimentalValidationRunCreate(**run_data)
    )
    # Set validation_status after creation (not in create schema)
    db_obj.validation_status = "EXPERIMENT_PLANNED"
    db.add(db_obj)

    # Also update candidate validation_status
    candidate = get_stamp_candidate(db, payload.candidate_id)
    if candidate is not None:
        candidate.validation_status = "EXPERIMENT_PLANNED"
        db.add(candidate)

    db.commit()
    db.refresh(db_obj)
    return db_obj


def add_experimental_measurement(
    db: Session, run_id: str, payload: ExperimentalMeasurementCreate
) -> Any:
    """Add a measurement and trigger status re-evaluation."""
    measurement = crud_add_measurement(db, payload)

    # Re-evaluate candidate validation status
    candidate_id = payload.candidate_id
    _update_validation_status_from_measurements(db, candidate_id)

    return measurement


def update_run_status(
    db: Session, run_id: str, status: str, notes: Optional[str] = None
) -> Any:
    """Update a run's execution status and re-evaluate candidate."""
    from app.crud.experimental_validation import get_validation_run

    run = get_validation_run(db, run_id)
    if run is None:
        raise ValueError(f"Run '{run_id}' not found")

    update = ExperimentalValidationRunUpdate(status=status)
    if notes:
        update.notes = notes

    run = crud_update_validation_run(db, run, update)
    _update_validation_status_from_measurements(db, run.candidate_id)
    return run


def _update_validation_status_from_measurements(
    db: Session, candidate_id: str
) -> str:
    """Recompute and update the candidate's validation_status based on runs.

    Rules:
    - No runs → NOT_EXPERIMENTALLY_VALIDATED
    - Only PLANNED runs → EXPERIMENT_PLANNED
    - Any FAILED run → VALIDATION_FAILED (most severe)
    - COMPLETED + measurements but missing key sets → PARTIALLY_VALIDATED
    - COMPLETED + activity + safety + all PASS → EXPERIMENTALLY_VALIDATED
    """
    runs = list_validation_runs_by_candidate(db, candidate_id)
    measurements = list_measurements_by_candidate(db, candidate_id)

    if not runs:
        new_status = "NOT_EXPERIMENTALLY_VALIDATED"
    elif all(r.status == "PLANNED" for r in runs):
        new_status = "EXPERIMENT_PLANNED"
    elif any(r.status == "FAILED" for r in runs):
        # If any run failed, mark as failed unless already fully validated
        new_status = "VALIDATION_FAILED"
    elif any(m.quality_flag == "FAILED" for m in measurements):
        new_status = "VALIDATION_FAILED"
    else:
        completed_runs = [r for r in runs if r.status == "COMPLETED"]
        if not completed_runs:
            new_status = "EXPERIMENT_PLANNED"
        else:
            # Check measurements from completed runs
            completed_run_ids = {r.id for r in completed_runs}
            completed_measurements = [
                m for m in measurements if m.validation_run_id in completed_run_ids
            ]

            metric_names = {m.metric_name for m in completed_measurements}
            has_activity = bool(metric_names & REQUIRED_ACTIVITY_METRICS)
            has_safety = bool(metric_names & REQUIRED_SAFETY_METRICS)
            all_pass = all(m.quality_flag == "PASS" for m in completed_measurements)

            if has_activity and has_safety and all_pass:
                new_status = "EXPERIMENTALLY_VALIDATED"
            elif completed_measurements:
                new_status = "PARTIALLY_VALIDATED"
            else:
                new_status = "EXPERIMENT_PLANNED"

    # Update candidate record
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is not None and candidate.validation_status != new_status:
        candidate.validation_status = new_status
        db.add(candidate)
        db.commit()

    return new_status


# ---------------------------------------------------------------------------
# Priority scoring
# ---------------------------------------------------------------------------

def compute_candidate_priority(
    db: Session, candidate_id: str
) -> CandidateExperimentalPriorityResponse:
    """Compute experimental priority score for a candidate.

    When no experimental data: score is None, status is PENDING_EXPERIMENTAL_DATA.
    When data exists: weighted composite of computational + structure + activity + safety.
    """
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate '{candidate_id}' not found")

    summary = summarize_candidate_experimental_validation(db, candidate_id)
    measurements = summary.get("measurements", [])

    if not measurements:
        return CandidateExperimentalPriorityResponse(
            candidate_id=candidate_id,
            composite_score=candidate.composite_score,
            experimental_priority_score=None,
            priority_status="PENDING_EXPERIMENTAL_DATA",
            computational_score_contribution=None,
            structure_support_contribution=None,
            experimental_activity_contribution=None,
            safety_contribution=None,
            validation_status=candidate.validation_status,
            has_experimental_data=False,
        )

    # Computational score contribution (40%)
    comp_score = _normalize_computational_score(candidate.composite_score)
    comp_contrib = comp_score * 0.40 if comp_score is not None else 0.0

    # Structure support contribution (20%)
    struct_score = _compute_structure_support(candidate)
    struct_contrib = struct_score * 0.20 if struct_score is not None else 0.0

    # Experimental activity contribution (25%)
    activity_score = _compute_experimental_activity(measurements)
    activity_contrib = activity_score * 0.25 if activity_score is not None else 0.0

    # Safety contribution (15%)
    safety_score = _compute_safety_score(measurements)
    safety_contrib = safety_score * 0.15 if safety_score is not None else 0.0

    total = comp_contrib + struct_contrib + activity_contrib + safety_contrib

    # Determine priority status
    if summary["overall_validation_status"] == "EXPERIMENTALLY_VALIDATED":
        priority_status = "READY_FOR_PRIORITIZATION"
    elif summary["overall_validation_status"] == "PARTIALLY_VALIDATED":
        priority_status = "PARTIALLY_PRIORITIZED"
    elif summary["overall_validation_status"] == "VALIDATION_FAILED":
        priority_status = "FAILED_SAFETY_OR_ACTIVITY"
    else:
        priority_status = "PENDING_EXPERIMENTAL_DATA"

    return CandidateExperimentalPriorityResponse(
        candidate_id=candidate_id,
        composite_score=candidate.composite_score,
        experimental_priority_score=round(total, 4) if total > 0 else None,
        priority_status=priority_status,
        computational_score_contribution=round(comp_contrib, 4) if comp_contrib > 0 else None,
        structure_support_contribution=round(struct_contrib, 4) if struct_contrib > 0 else None,
        experimental_activity_contribution=round(activity_contrib, 4) if activity_contrib > 0 else None,
        safety_contribution=round(safety_contrib, 4) if safety_contrib > 0 else None,
        validation_status=candidate.validation_status,
        has_experimental_data=True,
    )


def _normalize_computational_score(composite_score: Optional[float]) -> Optional[float]:
    """Normalize composite_score to 0-1 range (higher is better).

    Uses a sigmoid-like clamp: scores above 0.8 are excellent, below 0.2 are poor.
    """
    if composite_score is None:
        return None
    # Simple min-max normalization assuming typical range 0-1
    return max(0.0, min(1.0, composite_score))


def _compute_structure_support(candidate: Any) -> Optional[float]:
    """Compute structure support score from candidate metrics."""
    metrics = candidate.metrics or {}
    sp = metrics.get("structure_prediction") or {}
    iq = metrics.get("interface_quality") or {}
    eq = metrics.get("energy_quality") or {}

    scores = []
    if sp.get("mean_plddt"):
        scores.append(min(1.0, sp["mean_plddt"] / 100.0))
    if iq.get("pdockq"):
        scores.append(min(1.0, iq["pdockq"] / 1.0))
    if eq.get("interaction_energy_kcal_mol") is not None:
        # Negative energy is favorable; normalize roughly (-100, +100) → (0, 1)
        val = eq["interaction_energy_kcal_mol"]
        scores.append(max(0.0, min(1.0, 1.0 - (val + 50) / 100.0)))

    if not scores:
        return None
    return sum(scores) / len(scores)


def _compute_experimental_activity(measurements: list[Any]) -> Optional[float]:
    """Compute activity score from MIC/MBC measurements.

    Lower MIC = better activity. Normalize using a reference range.
    """
    mic_values = []
    mbc_values = []
    for m in measurements:
        if m.metric_name == "MIC_ug_ml" and m.value is not None:
            mic_values.append(m.value)
        elif m.metric_name == "MBC_ug_ml" and m.value is not None:
            mbc_values.append(m.value)

    if not mic_values and not mbc_values:
        return None

    # Use lowest (best) MIC; lower is better
    best_mic = min(mic_values) if mic_values else None
    best_mbc = min(mbc_values) if mbc_values else None

    # Normalize: typical MIC range 0.1–100 ug/ml
    # Score = 1 / (1 + MIC/10)  → low MIC gives high score
    scores = []
    if best_mic is not None:
        scores.append(1.0 / (1.0 + best_mic / 10.0))
    if best_mbc is not None:
        scores.append(1.0 / (1.0 + best_mbc / 10.0))

    return sum(scores) / len(scores)


def _compute_safety_score(measurements: list[Any]) -> Optional[float]:
    """Compute safety score from hemolysis / cytotoxicity measurements.

    Lower hemolysis / higher cell viability = better safety.
    """
    hemolysis_values = []
    viability_values = []
    hc50_values = []
    for m in measurements:
        if m.metric_name == "hemolysis_percent" and m.value is not None:
            hemolysis_values.append(m.value)
        elif m.metric_name == "cell_viability_percent" and m.value is not None:
            viability_values.append(m.value)
        elif m.metric_name == "HC50_ug_ml" and m.value is not None:
            hc50_values.append(m.value)

    if not hemolysis_values and not viability_values and not hc50_values:
        return None

    scores = []
    if hemolysis_values:
        # Lower hemolysis % is better; 0% → 1.0, 100% → 0.0
        scores.append(1.0 - (sum(hemolysis_values) / len(hemolysis_values)) / 100.0)
    if viability_values:
        # Higher viability % is better
        scores.append(sum(viability_values) / len(viability_values) / 100.0)
    if hc50_values:
        # Higher HC50 is better (less toxic)
        best_hc50 = max(hc50_values)
        scores.append(min(1.0, best_hc50 / 100.0))

    return sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# CSV import
# ---------------------------------------------------------------------------

import csv
import io
from app.crud.stamp_candidates import list_stamp_candidates_by_project


def import_measurements_csv(
    db: Session, project_id: str, file_content: bytes
) -> dict:
    """Import experimental measurements from a CSV file.

    Each row may create a new validation run or reuse an existing one
    (matched by candidate_id + experiment_type + protocol_name).
    Errors are collected per-row; successful rows are committed.
    """
    from app.crud.experimental_validation import (
        create_validation_run as crud_create_run,
        add_measurement as crud_add_measurement,
        list_validation_runs_by_candidate,
    )
    from app.schemas.experimental_validation import (
        ExperimentalValidationRunCreate,
        ExperimentalMeasurementCreate,
    )

    candidates = {c.id: c for c in list_stamp_candidates_by_project(db, project_id)}

    errors: list[dict] = []
    success_count = 0
    created_run_count = 0
    created_measurement_count = 0
    total_rows = 0

    text = file_content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))

    for row_idx, row in enumerate(reader, start=2):  # row 1 is header
        total_rows += 1
        candidate_id = row.get("candidate_id", "").strip()
        experiment_type = row.get("experiment_type", "").strip()
        metric_name = row.get("metric_name", "").strip()
        value_str = row.get("value", "").strip()
        unit = row.get("unit", "").strip()

        # Basic validation
        if candidate_id not in candidates:
            errors.append({
                "row": row_idx,
                "candidate_id": candidate_id,
                "reason": f"Candidate '{candidate_id}' not found in project",
            })
            continue

        if not experiment_type:
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": "experiment_type is required"})
            continue

        if not metric_name:
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": "metric_name is required"})
            continue

        if value_str == "":
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": "value is required"})
            continue

        try:
            value = float(value_str)
        except ValueError:
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": f"value '{value_str}' is not a number"})
            continue

        if not unit:
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": "unit is required"})
            continue

        # Scientific constraints
        if metric_name in ("MIC_ug_ml", "MBC_ug_ml") and value < 0:
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": f"{metric_name} must be >= 0"})
            continue

        if metric_name in ("hemolysis_percent", "cell_viability_percent", "protease_remaining_percent", "biofilm_inhibition_percent") and not (0 <= value <= 100):
            errors.append({"row": row_idx, "candidate_id": candidate_id, "reason": f"{metric_name} must be between 0 and 100"})
            continue

        # Find or create run
        existing_runs = list_validation_runs_by_candidate(db, candidate_id)
        run = None
        for r in existing_runs:
            if r.experiment_type == experiment_type:
                run = r
                break

        if run is None:
            run = crud_create_run(
                db,
                ExperimentalValidationRunCreate(
                    project_id=project_id,
                    candidate_id=candidate_id,
                    experiment_type=experiment_type,
                    organism=row.get("organism") or None,
                    strain=row.get("strain") or None,
                    protocol_name=row.get("protocol_name") or None,
                    experiment_date=row.get("experiment_date") or None,
                    notes=row.get("notes") or None,
                ),
            )
            created_run_count += 1

        # Parse condition_json
        condition_json: dict = {}
        condition_str = row.get("condition_json", "{}").strip()
        if condition_str:
            import json
            try:
                condition_json = json.loads(condition_str)
            except json.JSONDecodeError:
                pass  # ignore bad JSON, use empty dict

        # Add measurement
        crud_add_measurement(
            db,
            ExperimentalMeasurementCreate(
                validation_run_id=run.id,
                candidate_id=candidate_id,
                metric_name=metric_name,
                value=value,
                unit=unit,
                replicate_id=row.get("replicate_id") or None,
                quality_flag=row.get("quality_flag", "PASS").strip() or "PASS",
                condition_json=condition_json,
            ),
        )
        created_measurement_count += 1
        success_count += 1

        # Re-evaluate candidate status after each successful measurement
        _update_validation_status_from_measurements(db, candidate_id)

    return {
        "project_id": project_id,
        "total_rows": total_rows,
        "success_count": success_count,
        "failed_count": len(errors),
        "created_run_count": created_run_count,
        "created_measurement_count": created_measurement_count,
        "errors": errors,
    }


# ---------------------------------------------------------------------------
# Enhanced project summary
# ---------------------------------------------------------------------------

from app.crud.experimental_validation import get_project_experimental_summary as crud_get_project_summary


def get_project_experimental_validation_summary(db: Session, project_id: str) -> dict:
    """Return enriched project summary with top priority candidates."""
    summary = crud_get_project_summary(db, project_id)

    # Populate top_priority_candidates
    from app.crud.stamp_candidates import list_stamp_candidates_by_project
    candidates = list_stamp_candidates_by_project(db, project_id)

    top_candidates = []
    for c in candidates:
        if c.validation_status in ("EXPERIMENTALLY_VALIDATED", "PARTIALLY_VALIDATED"):
            try:
                priority = compute_candidate_priority(db, c.id)
                top_candidates.append({
                    "candidate_id": c.id,
                    "sequence": c.full_sequence,
                    "experimental_priority_score": priority.experimental_priority_score,
                    "priority_status": priority.priority_status,
                    "validation_status": c.validation_status,
                })
            except Exception:
                pass

    # Sort by priority score descending
    top_candidates.sort(
        key=lambda x: (x["experimental_priority_score"] or 0),
        reverse=True,
    )
    summary["top_priority_candidates"] = top_candidates[:10]

    return summary
