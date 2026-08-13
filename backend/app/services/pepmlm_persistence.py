"""STAMP Platform — PepMLM Result Persistence Service (v0.10-P3a).

Persists a succeeded pepmlm_generation job into stamp_generation_runs + stamp_candidates.
All results remain NOT_EXPERIMENTALLY_VALIDATED.
No fabricated experimental or structural metrics are written.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from sqlalchemy.orm import Session

from app.crud.jobs import get_job
from app.crud.stamp_candidates import (
    create_stamp_candidates_bulk,
    create_stamp_generation_run,
    mark_stamp_generation_run_completed,
)
from app.models.orm import Job
from app.schemas import StampCandidateCreate, StampGenerationRunCreate

logger = logging.getLogger(__name__)

# Forbidden keys that must never be written to candidate metrics.
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
    k_lower = key.lower()
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        if forbidden in k_lower:
            return True
    return False


def _filter_metrics(raw_metrics: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in raw_metrics.items() if not _is_forbidden_key(k)}


def persist_pepmlm_results(db: Session, job_id: str) -> dict[str, Any]:
    """Persist a succeeded pepmlm_generation job to stamp_generation_runs + stamp_candidates.

    Returns:
        dict with keys: job_id, generation_run_id, candidate_count,
        created_candidate_ids, status, validation_status.

    Raises:
        ValueError: for validation errors (job not found, wrong type, etc.)
    """
    job = get_job(db, job_id)
    if job is None:
        raise ValueError(f"Job '{job_id}' not found")

    if job.job_type != "pepmlm_generation":
        raise ValueError(
            f"Job '{job_id}' is not a pepmlm_generation (got '{job.job_type}')"
        )

    if job.status != "succeeded":
        raise ValueError(
            f"Job '{job_id}' status is '{job.status}', expected 'succeeded'"
        )

    output_json = job.output_json or {}
    input_json = job.input_json or {}
    project_id = input_json.get("project_id") or job.project_id
    epitope_id = input_json.get("epitope_id")
    linker_seq = input_json.get("linker_seq", "GGGGS")

    # Determine mode from output_json
    real_model_loaded = output_json.get("real_model_loaded", False)
    mode = output_json.get("mode", "PEPMLM_HTTP_SIDECAR_STUB")

    if real_model_loaded and mode == "PEPMLM_HTTP_SIDECAR_REAL":
        generator_name = "pepmlm_650m_real"
        generator_version = "v0.10-p3c"
        generation_status = "COMPUTATIONAL_GENERATION_ONLY"
    else:
        generator_name = "pepmlm_stub"
        generator_version = "v0.10-p3a-stub"
        generation_status = "COMPUTATIONAL_GENERATION_STUB_ONLY"

    raw_summary = output_json.get("raw_result_summary", {})

    # ------------------------------------------------------------------
    # 1. Create stamp_generation_runs record
    # ------------------------------------------------------------------
    run_in = StampGenerationRunCreate(
        project_id=project_id,
        epitope_id=epitope_id,
        generator_name=generator_name,
        generator_version=generator_version,
        parameters={
            **(input_json.get("parameters") or {}),
            "sidecar_url": output_json.get("sidecar_url", "http://127.0.0.1:5011"),
            "job_id": job_id,
            "mode": mode,
            "model_name": raw_summary.get("model_name"),
            "real_model_loaded": real_model_loaded,
        },
        status="PENDING",
    )
    run = create_stamp_generation_run(db, run_in)
    run_id = run.id

    # ------------------------------------------------------------------
    # 2. Map generated peptides to stamp_candidates
    # ------------------------------------------------------------------
    preview = output_json.get("generated_peptides_preview", [])
    created_candidates: List[StampCandidateCreate] = []

    for idx, peptide in enumerate(preview):
        seq = peptide.get("sequence")
        if not seq:
            logger.warning("Skipping peptide %d missing sequence", idx)
            continue

        seq_str = str(seq).upper().strip()
        full_seq = seq_str + linker_seq
        score = peptide.get("score")
        try:
            score = float(score) if score is not None else None
        except (ValueError, TypeError):
            score = None

        # Build metrics with provenance markers
        if real_model_loaded and mode == "PEPMLM_HTTP_SIDECAR_REAL":
            metrics = {
                "source": "pepmlm_650m_real",
                "is_stub": False,
                "real_model_loaded": True,
                "rank": peptide.get("rank"),
                "original_score": peptide.get("score"),
                "ppl": peptide.get("ppl"),
                "charge": peptide.get("charge"),
                "pi": peptide.get("pi"),
                "gravy": peptide.get("gravy"),
                "hydrophobicity": peptide.get("hydrophobicity"),
                "warnings": peptide.get("warnings"),
            }
        else:
            metrics = {
                "source": "pepmlm_stub",
                "is_stub": True,
                "real_model_loaded": False,
                "rank": peptide.get("rank"),
                "original_score": peptide.get("score"),
            }
        metrics = _filter_metrics(metrics)

        created_candidates.append(
            StampCandidateCreate(
                project_id=project_id,
                epitope_id=epitope_id,
                generation_run_id=run_id,
                targeting_peptide_seq=seq_str,
                linker_seq=linker_seq,
                full_sequence=full_seq,
                composite_score=score,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                metrics=metrics,
            )
        )

    created_candidate_ids: List[str] = []
    if created_candidates:
        db_objs = create_stamp_candidates_bulk(db, created_candidates)
        created_candidate_ids = [c.id for c in db_objs]

    mark_stamp_generation_run_completed(db, run_id)

    return {
        "job_id": job_id,
        "generation_run_id": run_id,
        "candidate_count": len(created_candidate_ids),
        "created_candidate_ids": created_candidate_ids,
        "status": "COMPLETED",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "generation_status": generation_status,
        "real_model_loaded": real_model_loaded,
    }
