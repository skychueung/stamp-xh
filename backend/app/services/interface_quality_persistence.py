"""STAMP Platform — Interface Quality Persistence (v0.10-P6j).

Writes real pDockQ interface-quality metrics from a succeeded
complex_structure_prediction job into
stamp_candidate.metrics['interface_quality'].

Enforces the scientific-integrity boundary: no fabricated wet-lab metrics,
no delta_G, no docking_score.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.crud.jobs import get_job
from app.crud.stamp_candidates import get_stamp_candidate, update_stamp_candidate
from app.schemas import StampCandidateUpdate
from app.services.complex_interface_parser import parse_complex_interface
from app.services.pdockq_calculator import PDockQError, build_interface_quality

logger = logging.getLogger(__name__)

FORBIDDEN_METRIC_KEYS = ("delta_G", "docking_score")
REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"


def _validate_interface_quality_no_forbidden_metrics(
    interface_quality: dict[str, Any],
) -> None:
    """Reject any non-null forbidden metrics in interface_quality output."""
    forbidden = interface_quality.get("forbidden_metrics", {})
    for key in FORBIDDEN_METRIC_KEYS:
        value = forbidden.get(key)
        if value is not None:
            raise ValueError(
                f"Forbidden metric '{key}' in forbidden_metrics must be null, got {value!r}"
            )

    # Also check top-level (should not exist there either)
    for key in FORBIDDEN_METRIC_KEYS:
        if key in interface_quality and interface_quality[key] is not None:
            raise ValueError(
                f"Forbidden metric '{key}' at top level must be null, got {interface_quality[key]!r}"
            )


def persist_interface_quality_to_candidate(
    db: Session,
    job_id: str,
) -> dict[str, Any]:
    """Persist a succeeded complex_structure_prediction job's interface quality to candidate metrics.

    The workflow:
      1. Verify job exists, is 'complex_structure_prediction', and succeeded.
      2. Locate the complex PDB from output_json or input_json.
      3. Run complex_interface_parser (P6i) on the PDB.
      4. Run pdockq_calculator (P6j) on the parsed features.
      5. Write result to candidate.metrics['interface_quality'] without
         overwriting other metric keys (e.g. structure_prediction).

    Returns:
        Summary dict for the router response.

    Raises:
        ValueError: if job/candidate not found, job not succeeded,
                    PDB path missing, parsing fails, or integrity checks fail.
    """
    job = get_job(db, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found")

    if job.job_type != "complex_structure_prediction":
        raise ValueError(
            f"Job '{job_id}' is job_type='{job.job_type}', expected 'complex_structure_prediction'"
        )

    if job.status != "succeeded":
        raise ValueError(
            f"Job '{job_id}' status='{job.status}', must be 'succeeded' to persist"
        )

    output_json = job.output_json or {}
    input_json = job.input_json or {}

    # Resolve candidate_id
    candidate_id = output_json.get("candidate_id") or input_json.get("candidate_id")
    if not candidate_id:
        raise ValueError(f"candidate_id missing in job '{job_id}' input_json/output_json")

    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise ValueError(f"StampCandidate '{candidate_id}' not found")

    # Resolve complex PDB path
    pdb_path = output_json.get("complex_structure_file") or output_json.get("structure_file")
    if not pdb_path:
        raise ValueError(f"complex_structure_file missing in job '{job_id}' output_json")

    # Parse interface features (P6i)
    try:
        parser_result = parse_complex_interface(
            pdb_path,
            pae_json_path=output_json.get("pae_json_path") or output_json.get("pae_file"),
            chain_mapping=output_json.get("chain_mapping"),
        )
    except Exception as exc:
        raise ValueError(f"Interface parsing failed for job '{job_id}': {exc}") from exc

    # Compute interface quality with pDockQ (P6j)
    try:
        interface_quality = build_interface_quality(
            parser_result,
            input_complex_structure_file=pdb_path,
        )
    except PDockQError as exc:
        raise ValueError(f"pDockQ calculation failed for job '{job_id}': {exc}") from exc

    # Integrity boundary check
    _validate_interface_quality_no_forbidden_metrics(interface_quality)

    # Ensure pDockQ is not written into structure_prediction
    existing_metrics = candidate.metrics or {}
    if "structure_prediction" in existing_metrics:
        sp = existing_metrics["structure_prediction"]
        if isinstance(sp, dict) and sp.get("pDockQ") is not None:
            raise ValueError(
                "structure_prediction already contains non-null pDockQ; "
                "pDockQ must live only in interface_quality"
            )

    # Merge into existing metrics without overwriting other keys
    updated_metrics = {**existing_metrics, "interface_quality": interface_quality}

    update_stamp_candidate(
        db,
        candidate,
        StampCandidateUpdate(metrics=updated_metrics),
    )

    logger.info(
        "Persisted interface_quality metrics for candidate %s from job %s (pdockq=%s)",
        candidate_id,
        job_id,
        interface_quality.get("pdockq"),
    )

    return {
        "job_id": job_id,
        "candidate_id": candidate_id,
        "status": "COMPLETED",
        "validation_status": interface_quality["validation_status"],
        "prediction_status": interface_quality["prediction_status"],
        "pdockq": interface_quality["pdockq"],
        "interface_contact_count": interface_quality["input_features"]["interface_contact_count"],
        "interface_residue_plddt_mean": interface_quality["input_features"]["interface_residue_plddt_mean"],
        "metrics_are_real": interface_quality["metrics_are_real"],
    }
