"""STAMP Platform — BepiPred3 Result Persistence Service (v0.10-P1c).

Persists a succeeded bepipred3_scan job into epitope_scans + epitope_candidates.
All predictions remain NOT_EXPERIMENTALLY_VALIDATED.
No fabricated experimental or structural metrics are written.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.crud.epitopes import (
    create_epitope_candidates_bulk,
    create_epitope_scan,
    update_epitope_scan_status,
)
from app.crud.jobs import get_job
from app.models.orm import Job
from app.schemas import EpitopeCandidateCreate, EpitopeScanCreate
from app.services.biophys import (
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
)

logger = logging.getLogger(__name__)

# Forbidden keys that must never be written to candidate metrics.
# Checked case-insensitively and as substrings.
_FORBIDDEN_SUBSTRINGS = {
    "mic",
    "mbc",
    "hemolysis",
    "toxicity",
    "iptm",
    "pdockq",
    "docking_score",
    "delta_g",
    "experimentally_validated",
    "wet_lab_confirmed",
    "wet-lab",
    "experimentally validated",
}


def _is_forbidden_key(key: str) -> bool:
    """Return True if a metric key contains forbidden scientific terms."""
    k_lower = key.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        if forbidden in k_lower:
            return True
    return False


def _filter_metrics(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    """Remove forbidden keys from metrics dict."""
    return {k: v for k, v in raw_metrics.items() if not _is_forbidden_key(k)}


def _resolve_ranked_peptides(output_json: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract ranked peptide list from job output_json.

    Prefers the full ``ranked_peptides`` list if present,
    otherwise falls back to ``ranked_peptides_preview``.
    """
    peptides = output_json.get("ranked_peptides")
    if peptides is None:
        peptides = output_json.get("ranked_peptides_preview", [])
    if not isinstance(peptides, list):
        return []
    return [p for p in peptides if isinstance(p, dict)]


def _map_peptide_to_candidate(
    peptide: dict[str, Any],
    scan_id: str,
) -> Optional[EpitopeCandidateCreate]:
    """Map a single BepiPred3 ranked peptide to an EpitopeCandidateCreate.

    Fields resolved:
      - sequence / peptide / fragment  → sequence
      - start / Start_Position         → start
      - end / End_Position             → end
      - score / Score / ranking_score  → ranking_score
    """
    seq = peptide.get("sequence") or peptide.get("peptide") or peptide.get("fragment")
    start = peptide.get("start") or peptide.get("Start_Position")
    end = peptide.get("end") or peptide.get("End_Position")
    score = peptide.get("score") or peptide.get("Score") or peptide.get("ranking_score")

    if not seq or start is None or end is None:
        logger.warning("Skipping peptide missing required fields: %s", peptide)
        return None

    try:
        start = int(start)
        end = int(end)
    except (ValueError, TypeError):
        logger.warning("Skipping peptide with invalid start/end: %s", peptide)
        return None

    if isinstance(score, str):
        try:
            score = float(score)
        except (ValueError, TypeError):
            score = None

    # Preserve original peptide dict in metrics, add source provenance
    raw_metrics = dict(peptide)
    raw_metrics["source"] = "bepipred3_sidecar"
    metrics = _filter_metrics(raw_metrics)

    sequence_str = str(seq).upper().strip()

    # Compute biophysical properties where possible
    net_charge: Optional[float] = None
    hydrophobicity: Optional[float] = None
    pi: Optional[float] = None
    cys_count: Optional[int] = None

    try:
        net_charge = calculate_net_charge(sequence_str)
    except Exception as exc:
        logger.debug("Failed to calculate net_charge for %s: %s", sequence_str, exc)

    try:
        hydrophobicity = calculate_gravy(sequence_str)
    except Exception as exc:
        logger.debug("Failed to calculate hydrophobicity for %s: %s", sequence_str, exc)

    try:
        pi = calculate_pi(sequence_str)
    except Exception as exc:
        logger.debug("Failed to calculate pI for %s: %s", sequence_str, exc)

    try:
        cys_count = count_cys(sequence_str)
    except Exception as exc:
        logger.debug("Failed to count Cys for %s: %s", sequence_str, exc)

    # Flag missing computed properties in metrics for traceability
    missing = []
    if net_charge is None:
        missing.append("net_charge")
    if hydrophobicity is None:
        missing.append("hydrophobicity")
    if pi is None:
        missing.append("pi")
    if cys_count is None:
        missing.append("cys_count")
    if missing:
        metrics["missing_computed_properties"] = missing

    return EpitopeCandidateCreate(
        scan_id=scan_id,
        start=start,
        end=end,
        sequence=sequence_str,
        net_charge=net_charge,
        hydrophobicity=hydrophobicity,
        pi=pi,
        cys_count=cys_count,
        surface_exposure_score=None,
        metrics=metrics,
        ranking_score=score,
        filter_status="PASS",
    )


def persist_bepipred3_results(db: Session, job_id: str) -> dict[str, Any]:
    """Persist a succeeded bepipred3_scan job to epitope_scans + epitope_candidates.

    Returns:
        dict with keys: job_id, scan_id, candidate_count, created_candidate_ids,
        status, validation_status, prediction_status, skipped_count.

    Raises:
        ValueError: with descriptive message for all validation errors.
    """
    job = get_job(db, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found")

    if job.job_type != "bepipred3_scan":
        raise ValueError(
            f"Job '{job_id}' is not a bepipred3_scan (got '{job.job_type}')"
        )

    if job.status != "succeeded":
        raise ValueError(
            f"Job '{job_id}' status is '{job.status}', expected 'succeeded'"
        )

    output_json = job.output_json
    if not output_json:
        raise ValueError(f"Job '{job_id}' has no output_json")

    input_json = job.input_json or {}
    project_id = input_json.get("project_id") or job.project_id
    target_protein_id = input_json.get("target_protein_id")

    if not target_protein_id:
        raise ValueError(
            f"Job '{job_id}' input_json missing required 'target_protein_id'"
        )

    # ------------------------------------------------------------------
    # 1. Create epitope_scan record
    # ------------------------------------------------------------------
    parameters = {
        **(input_json.get("parameters") or {}),
        "sidecar_url": output_json.get("sidecar_url")
        or input_json.get("sidecar_url")
        or "http://127.0.0.1:5001/api/predict",
        "job_id": job_id,
        "mode": "BEPIPRED3_HTTP_SIDECAR",
    }

    scan_in = EpitopeScanCreate(
        project_id=project_id,
        target_protein_id=target_protein_id,
        parameters=parameters,
        algorithm="bepipred3_sidecar",
        algorithm_version="v0.10-p1c",
    )
    scan = create_epitope_scan(db, scan_in)
    update_epitope_scan_status(db, scan.id, "COMPLETED")

    # ------------------------------------------------------------------
    # 2. Map ranked peptides to epitope_candidates
    # ------------------------------------------------------------------
    ranked_peptides = _resolve_ranked_peptides(output_json)

    created_candidates: List[EpitopeCandidateCreate] = []
    skipped_count = 0
    for peptide in ranked_peptides:
        candidate = _map_peptide_to_candidate(peptide, scan.id)
        if candidate is None:
            skipped_count += 1
            continue
        created_candidates.append(candidate)

    created_candidate_ids: List[str] = []
    if created_candidates:
        db_objs = create_epitope_candidates_bulk(db, created_candidates)
        created_candidate_ids = [c.id for c in db_objs]

    return {
        "job_id": job_id,
        "scan_id": scan.id,
        "candidate_count": len(created_candidate_ids),
        "created_candidate_ids": created_candidate_ids,
        "status": "COMPLETED",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_PREDICTION_ONLY",
        "skipped_count": skipped_count,
    }
