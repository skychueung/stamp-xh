"""STAMP Platform — Structure Prediction Result Persistence (v0.10-P6d).

Writes real LocalColabFold structure metrics from a succeeded job into the
corresponding stamp_candidate.metrics['structure_prediction'].

Enforces the scientific-integrity boundary: no fabricated wet-lab metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.crud.jobs import get_job
from app.crud.stamp_candidates import get_stamp_candidate, update_stamp_candidate
from app.schemas import StampCandidateUpdate

logger = logging.getLogger(__name__)

FORBIDDEN_METRIC_KEYS = ("pDockQ", "delta_G", "docking_score")
REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"


def _validate_output_json_has_no_fabricated_metrics(output_json: dict[str, Any]) -> None:
    """Reject any non-null forbidden metrics or wet-lab validation claims."""
    # Check top-level forbidden metrics
    for key in FORBIDDEN_METRIC_KEYS:
        value = output_json.get(key)
        if value is not None:
            raise ValueError(f"Forbidden metric '{key}' must be null, got {value!r}")

    # Check nested forbidden_metrics
    nested = output_json.get("forbidden_metrics", {})
    for key in FORBIDDEN_METRIC_KEYS:
        value = nested.get(key)
        if value is not None:
            raise ValueError(
                f"Forbidden metric '{key}' in forbidden_metrics must be null, got {value!r}"
            )

    # Wet-lab validation claims
    vs = output_json.get("validation_status", "")
    if vs != REQUIRED_VALIDATION_STATUS and "experimentally_validated" in str(vs).lower():
        raise ValueError(f"validation_status claims experimental validation: {vs!r}")

    ps = output_json.get("prediction_status", "")
    if "wet_lab" in str(ps).lower() or "experimentally_confirmed" in str(ps).lower():
        raise ValueError(f"prediction_status claims wet-lab confirmation: {ps!r}")


def persist_structure_prediction_to_candidate(db: Session, job_id: str) -> dict[str, Any]:
    """Persist a succeeded structure_prediction job into stamp_candidate.metrics.

    Returns a summary dict for the router response.

    Raises:
        ValueError: if job/candidate not found, job not succeeded,
                    candidate_id missing, or integrity checks fail.
    """
    job = get_job(db, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found")

    if job.job_type != "structure_prediction":
        raise ValueError(
            f"Job '{job_id}' is job_type='{job.job_type}', expected 'structure_prediction'"
        )

    if job.status != "succeeded":
        raise ValueError(
            f"Job '{job_id}' status='{job.status}', must be 'succeeded' to persist"
        )

    output_json = job.output_json
    if not output_json:
        raise ValueError(f"Job '{job_id}' has no output_json")

    # Integrity boundary check
    _validate_output_json_has_no_fabricated_metrics(output_json)

    # Validate mean_plddt is real numeric
    mean_plddt = output_json.get("mean_plddt")
    if mean_plddt is None or not isinstance(mean_plddt, (int, float)):
        raise ValueError(f"mean_plddt must be a real numeric value, got {mean_plddt!r}")

    # Resolve candidate_id
    candidate_id = (
        output_json.get("candidate_id")
        or (job.input_json or {}).get("candidate_id")
    )
    if not candidate_id:
        raise ValueError(f"candidate_id missing in job '{job_id}' input_json/output_json")

    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise ValueError(f"StampCandidate '{candidate_id}' not found")

    # Build structure_prediction metrics block
    structure_metrics: dict[str, Any] = {
        "mode": output_json.get("mode", "LOCALCOLABFOLD_IMPORTED_RESULT"),
        "model_source": output_json.get("model_source", "LocalColabFold"),
        "validation_status": output_json.get("validation_status", REQUIRED_VALIDATION_STATUS),
        "prediction_status": output_json.get("prediction_status", REQUIRED_PREDICTION_STATUS),
        "metrics_are_real": output_json.get("metrics_are_real", True),
        "mean_plddt": output_json.get("mean_plddt"),
        "ptm": output_json.get("ptm"),
        "iptm": output_json.get("iptm"),
        "structure_file": output_json.get("structure_file"),
        "pae_file": output_json.get("pae_file"),
        "raw_score_json": output_json.get("raw_score_json"),
        "plddt_per_residue": output_json.get("plddt_per_residue"),
        "coverage_plot": output_json.get("coverage_plot"),
        "source_job_id": job_id,
        "source_result_dir": output_json.get("source_result_dir"),
        "forbidden_metrics": output_json.get("forbidden_metrics", {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        }),
    }

    # Merge into existing metrics without overwriting other keys
    existing_metrics = candidate.metrics or {}
    updated_metrics = {**existing_metrics, "structure_prediction": structure_metrics}

    update_stamp_candidate(
        db,
        candidate,
        StampCandidateUpdate(metrics=updated_metrics),
    )

    logger.info(
        "Persisted structure_prediction metrics for candidate %s from job %s (mean_plddt=%s)",
        candidate_id,
        job_id,
        structure_metrics.get("mean_plddt"),
    )

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "status": "COMPLETED",
        "validation_status": structure_metrics["validation_status"],
        "prediction_status": structure_metrics["prediction_status"],
        "mean_plddt": structure_metrics["mean_plddt"],
        "ptm": structure_metrics["ptm"],
        "iptm": structure_metrics["iptm"],
        "metrics_are_real": structure_metrics["metrics_are_real"],
    }
