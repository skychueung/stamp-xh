"""PepMLM Job Service — minimal real-run job queue for the Model Registry.

Provides submit, query, artifact listing, and cancel logic.  Real execution is
blocked unless the PepMLM real-run gate is open (env var PEPMLM_REAL_RUN_ENABLED
or one-time token PEPMLM_REAL_RUN_TOKEN).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.crud.jobs import create_job, get_job, update_job_status
from app.models.orm import Job
from app.schemas import JobCreate
from app.schemas.model_registry import ModelDryRunPayload
from app.services.audit_log_service import log_job_cancel, log_job_submit
from app.services.model_adapters.pepmlm_adapter import (
    PEPMLM_ARTIFACT_ROOT,
    _real_run_allowed,
)

logger = logging.getLogger(__name__)

PEPMLM_JOB_TYPE = "pepmlm_generate"

_KNOWN_ARTIFACTS: list[dict[str, str]] = [
    {"name": "target.fasta", "path": "input/target.fasta", "type": "input"},
    {"name": "candidate_sequences.csv", "path": "output/candidate_sequences.csv", "type": "sequence_csv"},
    {"name": "candidate_sequences.json", "path": "output/candidate_sequences.json", "type": "sequence_json"},
    {"name": "run_stdout_stderr.log", "path": "logs/run_stdout_stderr.log", "type": "log"},
    {"name": "manifest_pre.json", "path": "manifest/manifest_pre.json", "type": "manifest"},
    {"name": "manifest_post.json", "path": "manifest/manifest_post.json", "type": "manifest"},
]

_KNOWN_ARTIFACT_PATHS: dict[str, str] = {
    a["name"]: a["path"] for a in _KNOWN_ARTIFACTS
}


def _validate_submit(payload: ModelDryRunPayload) -> tuple[bool, Optional[str]]:
    """Validate a PepMLM job submit request."""
    seq = payload.target_sequence or ""
    if not seq.strip():
        return False, "target_sequence is required"
    if payload.peptide_length is not None and not (1 <= payload.peptide_length <= 100):
        return False, "peptide_length must be between 1 and 100"
    if payload.num_candidates is not None and not (1 <= payload.num_candidates <= 100):
        return False, "num_candidates must be between 1 and 100"
    return True, None


def submit_pepmlm_job(
    db: Session,
    payload: ModelDryRunPayload,
    project_id: str,
) -> Job:
    """Submit a new PepMLM job record.

    The job is created as ``pending`` when the real-run gate is open, otherwise
    ``blocked``.  Actual model execution is performed by the PepMLM worker.
    """
    valid, error = _validate_submit(payload)
    if not valid:
        logger.warning("PepMLM job submit validation failed: %s", error)
        raise ValueError(error)

    job = create_job(
        db,
        JobCreate(
            project_id=project_id,
            job_type=PEPMLM_JOB_TYPE,
            input_json=payload.model_dump(),
        ),
    )
    logger.info("PepMLM job created: %s (project=%s)", job.id, project_id)
    log_job_submit(db, job.id)

    if _real_run_allowed():
        job = update_job_status(
            db,
            job.id,
            status="pending",
            progress=0,
            message="PepMLM job queued for real execution",
            error_message=None,
            output_json={
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": {
                    "executed_model": False,
                    "generated_candidates": False,
                    "generated_structure": False,
                    "generated_msa": False,
                    "is_scientific_result": False,
                    "computational_prediction_only": True,
                },
            },
        )
    else:
        job = update_job_status(
            db,
            job.id,
            status="blocked",
            progress=0,
            message="PepMLM real execution is disabled (gate closed).",
            error_message="Real-run gate is closed.",
            output_json={
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": {
                    "executed_model": False,
                    "generated_candidates": False,
                    "generated_structure": False,
                    "generated_msa": False,
                    "is_scientific_result": False,
                    "computational_prediction_only": True,
                },
            },
        )

    if job is None:
        raise RuntimeError("Failed to update PepMLM job status after submit")
    return job


def get_pepmlm_job(db: Session, job_id: str) -> Optional[Job]:
    """Get a PepMLM job by ID."""
    job = get_job(db, job_id)
    if job is None or job.job_type != PEPMLM_JOB_TYPE:
        return None
    return job


def _run_dir_for_job(job: Job) -> Optional[Path]:
    """Return the absolute run directory for a job, hardened against traversal."""
    root = Path(PEPMLM_ARTIFACT_ROOT).resolve()
    run_dir = (root / str(job.id)).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError:
        logger.warning("Run dir for job %s escapes artifact root", job.id)
        return None
    return run_dir


def get_pepmlm_job_artifacts(db: Session, job_id: str) -> list[dict]:
    """List artifact metadata for a PepMLM job, verifying disk existence.

    Returns relative paths and never exposes absolute server paths.
    """
    job = get_pepmlm_job(db, job_id)
    if job is None:
        return []

    run_dir = _run_dir_for_job(job)
    if run_dir is not None and run_dir.exists():
        result: list[dict] = []
        for definition in _KNOWN_ARTIFACTS:
            rel_path = definition["path"]
            full_path = run_dir / rel_path
            try:
                full_path.resolve().relative_to(run_dir.resolve())
            except ValueError:
                continue
            exists = full_path.exists()
            result.append(
                {
                    "name": definition["name"],
                    "path": rel_path,
                    "artifact_type": definition["type"],
                    "exists": exists,
                    "size_bytes": full_path.stat().st_size if exists else 0,
                }
            )
        return result

    artifacts_json = job.artifacts_json or {}
    result = []
    root_abs = Path(PEPMLM_ARTIFACT_ROOT).resolve()
    for name, raw_path in artifacts_json.items():
        if not raw_path or not isinstance(raw_path, str):
            continue
        path_obj = Path(raw_path).resolve()
        try:
            rel_path = path_obj.relative_to(root_abs)
        except ValueError:
            logger.warning("Ignoring artifact path outside root for job %s: %s", job_id, raw_path)
            continue
        known = _KNOWN_ARTIFACT_PATHS.get(name)
        artifact_type = "other"
        if known:
            for definition in _KNOWN_ARTIFACTS:
                if definition["path"] == str(rel_path) or definition["name"] == name:
                    artifact_type = definition["type"]
                    break
        exists = path_obj.exists()
        result.append(
            {
                "name": name,
                "path": str(rel_path),
                "artifact_type": artifact_type,
                "exists": exists,
                "size_bytes": path_obj.stat().st_size if exists else 0,
            }
        )
    return result


def cancel_pepmlm_job(db: Session, job_id: str) -> Optional[Job]:
    """Cancel a PepMLM job if it is pending, running, or blocked."""
    job = get_pepmlm_job(db, job_id)
    if job is None:
        return None

    if job.status == "cancelled":
        return job

    if job.status not in ("pending", "running", "blocked"):
        logger.warning(
            "PepMLM job %s cannot be cancelled from status %s",
            job_id,
            job.status,
        )
        return job

    updated = update_job_status(
        db,
        job_id,
        status="cancelled",
        progress=job.progress,
        message="Job cancelled by user",
        error_message="[USER_CANCELLED] Job was cancelled by user",
        output_json={
            **(job.output_json or {}),
            "cancelled": True,
            "previous_status": job.status,
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        },
    )

    if updated is not None:
        log_job_cancel(db, job_id)
        logger.info("PepMLM job %s cancelled (was %s)", job_id, job.status)

    return updated
