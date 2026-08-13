"""STAMP Platform — Energy Quality Persistence (v0.10-P6m).

Writes real FoldX AnalyseComplex interaction-energy metrics from a
succeeded energy_estimation or complex_structure_prediction job into
stamp_candidate.metrics['energy_quality'].

Enforces the scientific-integrity boundary:
  - energy_quality is a SEPARATE metrics namespace from interface_quality
    and structure_prediction.
  - docking_score, mmgbsa_delta_G, experimental_delta_G remain null.
  - All metrics are NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.crud.jobs import get_job
from app.crud.stamp_candidates import get_stamp_candidate, update_stamp_candidate
from app.schemas import StampCandidateUpdate
from app.services.foldx_output_parser import FoldXParserError, parse_foldx_interaction_fxout

logger = logging.getLogger(__name__)

FORBIDDEN_METRIC_KEYS = ("docking_score", "mmgbsa_delta_G", "experimental_delta_G")
REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"


class EnergyQualityError(ValueError):
    """Raised when energy quality persistence fails."""

    pass


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_energy_quality_no_forbidden_metrics(
    energy_quality: dict[str, Any],
) -> None:
    """Reject any non-null forbidden metrics in energy_quality output."""
    forbidden = energy_quality.get("forbidden_metrics", {})
    for key in FORBIDDEN_METRIC_KEYS:
        value = forbidden.get(key)
        if value is not None:
            raise EnergyQualityError(
                f"Forbidden metric '{key}' in forbidden_metrics must be null, got {value!r}"
            )

    # Also check top-level (should not exist there either)
    for key in FORBIDDEN_METRIC_KEYS:
        if key in energy_quality and energy_quality[key] is not None:
            raise EnergyQualityError(
                f"Forbidden metric '{key}' at top level must be null, got {energy_quality[key]!r}"
            )


def _validate_energy_quality_does_not_pollute_other_namespaces(
    candidate_metrics: dict[str, Any],
) -> None:
    """Ensure energy_quality fields are not already present in other namespaces."""
    # Check interface_quality
    iq = candidate_metrics.get("interface_quality")
    if isinstance(iq, dict):
        for key in ("interaction_energy_kcal_mol", "energy_terms"):
            if key in iq and iq[key] is not None:
                raise EnergyQualityError(
                    f"Field '{key}' already present in interface_quality; "
                    f"energy_quality must be a separate namespace"
                )

    # Check structure_prediction
    sp = candidate_metrics.get("structure_prediction")
    if isinstance(sp, dict):
        for key in ("interaction_energy_kcal_mol", "energy_terms"):
            if key in sp and sp[key] is not None:
                raise EnergyQualityError(
                    f"Field '{key}' already present in structure_prediction; "
                    f"energy_quality must be a separate namespace"
                )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


def persist_energy_quality_to_candidate(
    db: Session,
    job_id: str,
    *,
    interaction_fxout_path: str | None = None,
) -> dict[str, Any]:
    """Persist FoldX energy quality metrics to a stamp candidate.

    Workflow:
      1. Verify job exists and succeeded.
      2. Resolve candidate_id from job input/output.
      3. Parse FoldX Interaction_*.fxout (or use provided path).
      4. Build energy_quality dict with quality flags.
      5. Write to candidate.metrics['energy_quality'] without overwriting
         other metric keys (interface_quality, structure_prediction, etc.).

    Args:
        db: Database session.
        job_id: Job ID.
        interaction_fxout_path: Optional explicit path to FoldX Interaction fxout.
            If not provided, resolved from job.output_json['interaction_fxout'].

    Returns:
        Summary dict for the router response.

    Raises:
        EnergyQualityError: if job/candidate not found, job not succeeded,
            fxout missing, parsing fails, or integrity checks fail.
    """
    job = get_job(db, job_id)
    if job is None:
        raise EnergyQualityError(f"Job '{job_id}' not found")

    if job.status != "succeeded":
        raise EnergyQualityError(
            f"Job '{job_id}' status='{job.status}', must be 'succeeded' to persist"
        )

    output_json = job.output_json or {}
    input_json = job.input_json or {}

    # Resolve candidate_id
    candidate_id = output_json.get("candidate_id") or input_json.get("candidate_id")
    if not candidate_id:
        raise EnergyQualityError(f"candidate_id missing in job '{job_id}' input_json/output_json")

    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise EnergyQualityError(f"StampCandidate '{candidate_id}' not found")

    # Resolve interaction fxout path
    fxout_path = interaction_fxout_path
    if not fxout_path:
        fxout_path = output_json.get("interaction_fxout") or output_json.get("foldx_interaction_fxout")
    if not fxout_path:
        raise EnergyQualityError(
            f"interaction_fxout path missing in job '{job_id}' output_json "
            f"and not provided as argument"
        )

    # Parse FoldX output (P6m)
    try:
        energy_quality = parse_foldx_interaction_fxout(fxout_path)
    except FoldXParserError as exc:
        raise EnergyQualityError(
            f"FoldX output parsing failed for job '{job_id}': {exc}"
        ) from exc

    # Integrity boundary checks
    _validate_energy_quality_no_forbidden_metrics(energy_quality)
    _validate_energy_quality_does_not_pollute_other_namespaces(candidate.metrics or {})

    # Merge into existing metrics without overwriting other keys
    existing_metrics = candidate.metrics or {}
    updated_metrics = {**existing_metrics, "energy_quality": energy_quality}

    update_stamp_candidate(
        db,
        candidate,
        StampCandidateUpdate(metrics=updated_metrics),
    )

    logger.info(
        "Persisted energy_quality metrics for candidate %s from job %s (interaction_energy=%s)",
        candidate_id,
        job_id,
        energy_quality.get("interaction_energy_kcal_mol"),
    )

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "status": "COMPLETED",
        "validation_status": energy_quality["validation_status"],
        "prediction_status": energy_quality["prediction_status"],
        "interaction_energy_kcal_mol": energy_quality["interaction_energy_kcal_mol"],
        "energy_terms": energy_quality["energy_terms"],
        "quality_flags": energy_quality["quality_flags"],
        "metrics_are_real": energy_quality["metrics_are_real"],
    }


def persist_energy_quality_to_candidate_by_fxout(
    db: Session,
    candidate_id: str,
    fxout_path: str,
    *,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Persist FoldX energy quality directly by candidate_id + fxout path.

    This bypasses the job lookup and is useful for batch import scenarios.

    Args:
        db: Database session.
        candidate_id: Candidate ID.
        fxout_path: Path to FoldX Interaction_*.fxout file.
        overwrite: If True, overwrite existing energy_quality; if False, skip.

    Returns:
        Summary dict.

    Raises:
        EnergyQualityError: if candidate not found, fxout missing, or integrity checks fail.
    """
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise EnergyQualityError(f"StampCandidate '{candidate_id}' not found")

    existing_metrics = candidate.metrics or {}
    if not overwrite and "energy_quality" in existing_metrics:
        logger.info("Candidate '%s' already has energy_quality, skipping", candidate_id)
        return {
            "candidate_id": candidate_id,
            "status": "SKIPPED",
            "reason": "energy_quality already exists",
        }

    # Parse FoldX output
    try:
        energy_quality = parse_foldx_interaction_fxout(fxout_path)
    except FoldXParserError as exc:
        raise EnergyQualityError(
            f"FoldX output parsing failed for candidate '{candidate_id}': {exc}"
        ) from exc

    # Integrity boundary checks
    _validate_energy_quality_no_forbidden_metrics(energy_quality)
    _validate_energy_quality_does_not_pollute_other_namespaces(existing_metrics)

    # Merge into existing metrics
    updated_metrics = {**existing_metrics, "energy_quality": energy_quality}

    update_stamp_candidate(
        db,
        candidate,
        StampCandidateUpdate(metrics=updated_metrics),
    )

    logger.info(
        "Persisted energy_quality metrics for candidate %s (interaction_energy=%s)",
        candidate_id,
        energy_quality.get("interaction_energy_kcal_mol"),
    )

    return {
        "candidate_id": candidate_id,
        "status": "COMPLETED",
        "validation_status": energy_quality["validation_status"],
        "prediction_status": energy_quality["prediction_status"],
        "interaction_energy_kcal_mol": energy_quality["interaction_energy_kcal_mol"],
        "energy_terms": energy_quality["energy_terms"],
        "quality_flags": energy_quality["quality_flags"],
        "metrics_are_real": energy_quality["metrics_are_real"],
    }
