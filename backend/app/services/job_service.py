"""STAMP Platform — Job Service (v0.9-P6 + P2).

Provides mock run, real P5-lite workflow dispatch, and cancel logic.
All outputs are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
No real ML models, no structural predictions, no fabricated metrics.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from fastapi import BackgroundTasks
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crud.jobs import create_job, get_job, update_job_status
from app.database import SessionLocal
from app.models.orm import Job
from app.schemas import (
    BepiPred3JobInput,
    EpitopeScanRunRequest,
    JobCreate,
    PeptideGenerationRunRequest,
    StampAssemblyRunRequest,
)
from app.services.bepipred3_adapter import (
    BepiPred3SidecarError,
    call_bepipred3_sidecar,
    normalize_bepipred3_response,
    resolve_sequence,
)
from app.services.epitope_scan_persistence import run_epitope_scan_and_persist
from app.services.peptide_generation_persistence import run_peptide_generation_and_persist
from app.services.stamp_assembly_persistence import run_stamp_assembly_and_persist
from app.services.pepmlm_adapter import (
    PepMLMSidecarError,
    call_pepmlm_sidecar,
    normalize_pepmlm_response,
)
from app.services.complex_prediction_input import build_complex_prediction_manifest
from app.services.structure_prediction_import import (
    load_localcolabfold_metrics,
    normalize_localcolabfold_metrics,
    validate_no_fabricated_structure_metrics,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Supported job types
# ---------------------------------------------------------------------------

SUPPORTED_JOB_TYPES = {
    "epitope_scan",
    "peptide_generation",
    "stamp_assembly",
    "bepipred3_scan",
    "pepmlm_generation",
    "structure_prediction",
    "complex_structure_prediction",
}

# ---------------------------------------------------------------------------
# Async job dispatch (v0.10-P2b)
# ---------------------------------------------------------------------------


def _is_cancelled(db: Session, job_id: str) -> bool:
    """Check whether a job has been cancelled by the user.

    Used inside background threads for cooperative cancellation.
    """
    job = get_job(db, job_id)
    return job is not None and job.status == "cancelled"


def run_job_background(job_id: str) -> None:
    """Run a real job in a background thread with its own DB session.

    This is used by FastAPI BackgroundTasks. It creates a fresh SessionLocal
    because the request-scoped session cannot be shared across threads.

    Cooperative cancellation: checks job.status before and after sidecar call.
    """
    db = SessionLocal()
    try:
        # Cooperative cancellation check #1: before any work
        if _is_cancelled(db, job_id):
            logger.info("Job %s was cancelled before background work started", job_id)
            return

        run_real_job(db, job_id=job_id)
    finally:
        db.close()


def start_job_async(
    db: Session,
    job_id: str,
    background_tasks: BackgroundTasks,
) -> Optional[Job]:
    """Start a job asynchronously via FastAPI BackgroundTasks.

    Rules:
      - pending  → enqueue background task, status=running, progress=5
      - running  → return as-is (idempotent, no duplicate start)
      - succeeded/failed/cancelled → return as-is (terminal state, no restart)
    """
    job = get_job(db, job_id)
    if job is None:
        return None

    if job.status == "running":
        return job

    if job.status in ("succeeded", "failed", "cancelled"):
        return job

    job = update_job_status(
        db,
        job_id,
        status="running",
        progress=5,
        message="Async execution queued",
    )
    if job is None:
        return None

    background_tasks.add_task(run_job_background, job_id)
    return job


# ---------------------------------------------------------------------------
# Real job dispatch (v0.9-P2)
# ---------------------------------------------------------------------------


def run_real_job(db: Session, job_id: str) -> Optional[Job]:
    """Dispatch a real P5-lite job based on job_type.

    Workflow:
      1. Validate job exists and is runnable.
      2. Validate input_json with Pydantic model_validate.
      3. Call the appropriate persistence service.
      4. On success: status=succeeded, progress=100, output_json=summary.
      5. On failure: status=failed, error_message=exception summary.

    Returns the updated Job ORM object, or None if job not found.
    """
    job = get_job(db, job_id)
    if job is None:
        return None

    # Terminal-state guard
    if job.status in ("succeeded", "failed", "cancelled"):
        logger.warning("Job %s is already in terminal state %s", job_id, job.status)
        return job

    if job.job_type not in SUPPORTED_JOB_TYPES:
        logger.error("Unsupported job_type '%s' for job %s", job.job_type, job_id)
        return update_job_status(
            db,
            job_id,
            status="failed",
            progress=0,
            message="Job failed",
            error_message=f"Unsupported job_type: {job.job_type}",
        )

    # Transition to running
    job = update_job_status(
        db, job_id, status="running", progress=10, message="Real execution started"
    )
    if job is None:
        return None

    try:
        # Validate input_json with Pydantic
        if job.job_type == "epitope_scan":
            request = EpitopeScanRunRequest.model_validate(job.input_json or {})
            result = run_epitope_scan_and_persist(db, request)
            output_json = {
                "scan_id": result.scan_id,
                "status": result.status,
                "candidate_count": result.candidate_count,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            }

        elif job.job_type == "peptide_generation":
            request = PeptideGenerationRunRequest.model_validate(job.input_json or {})
            result = run_peptide_generation_and_persist(db, request)
            output_json = {
                "generation_run_id": result.generation_run_id,
                "status": result.status,
                "candidate_count": result.candidate_count,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            }

        elif job.job_type == "stamp_assembly":
            request = StampAssemblyRunRequest.model_validate(job.input_json or {})
            result = run_stamp_assembly_and_persist(db, request)
            output_json = {
                "generation_run_id": result.generation_run_id,
                "status": result.status,
                "processed_count": result.processed_count,
                "skipped_count": result.skipped_count,
                "failed_count": result.failed_count,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            }

        elif job.job_type == "bepipred3_scan":
            input_data = BepiPred3JobInput.model_validate(job.input_json or {})
            sequence = resolve_sequence(db, input_data)

            # Cooperative cancellation check #2: before sidecar call
            if _is_cancelled(db, job_id):
                logger.info("Job %s cancelled before sidecar call", job_id)
                return job

            raw_result = call_bepipred3_sidecar(
                sequence=sequence,
                base_url=input_data.sidecar_url,
                timeout=None,
                parameters=input_data.parameters,
            )

            # Cooperative cancellation check #3: after sidecar call, before writing results
            if _is_cancelled(db, job_id):
                logger.info("Job %s cancelled after sidecar call; discarding results", job_id)
                return job

            output_json = normalize_bepipred3_response(
                raw_result,
                target_protein_id=input_data.target_protein_id,
                sidecar_url=input_data.sidecar_url,
            )

        elif job.job_type == "pepmlm_generation":
            from app.schemas.pepmlm import PepMLMJobInput

            input_data = PepMLMJobInput.model_validate(job.input_json or {})
            epitope_sequence = input_data.epitope_sequence

            # If epitope_sequence not provided directly, try to resolve from epitope_id
            if not epitope_sequence and input_data.epitope_id:
                from app.models.orm import EpitopeCandidate
                epitope = db.query(EpitopeCandidate).filter(EpitopeCandidate.id == input_data.epitope_id).first()
                if epitope:
                    epitope_sequence = epitope.sequence

            if not epitope_sequence:
                raise ValueError("epitope_sequence or epitope_id required for pepmlm_generation")

            # Cooperative cancellation check #2: before sidecar call
            if _is_cancelled(db, job_id):
                logger.info("Job %s cancelled before PepMLM sidecar call", job_id)
                return job

            raw_result = call_pepmlm_sidecar(
                epitope_sequence=epitope_sequence,
                base_url=input_data.sidecar_url,
                top_k=input_data.top_k,
                linker_seq=input_data.linker_seq,
                parameters=input_data.parameters,
            )

            # Cooperative cancellation check #3: after sidecar call
            if _is_cancelled(db, job_id):
                logger.info("Job %s cancelled after PepMLM sidecar call; discarding results", job_id)
                return job

            output_json = normalize_pepmlm_response(
                raw_result,
                sidecar_url=input_data.sidecar_url,
            )

        elif job.job_type == "structure_prediction":
            input_data = job.input_json or {}
            result_dir = input_data.get("result_dir")
            if not result_dir:
                raise ValueError("result_dir required in input_json for structure_prediction")

            raw_metrics = load_localcolabfold_metrics(result_dir)
            output_json = normalize_localcolabfold_metrics(raw_metrics)
            validate_no_fabricated_structure_metrics(output_json)

        elif job.job_type == "complex_structure_prediction":
            input_data = job.input_json or {}
            target_sequence = input_data.get("target_sequence")
            peptide_sequence = input_data.get("peptide_sequence")
            if not target_sequence or not peptide_sequence:
                raise ValueError(
                    "target_sequence and peptide_sequence required in input_json for complex_structure_prediction"
                )

            output_json = build_complex_prediction_manifest(
                target_sequence=target_sequence,
                peptide_sequence=peptide_sequence,
                target_chain_id=input_data.get("target_chain_id", "A"),
                peptide_chain_id=input_data.get("peptide_chain_id", "B"),
                target_name=input_data.get("target_name", "target"),
                peptide_name=input_data.get("peptide_name", "candidate_peptide"),
                candidate_id=input_data.get("candidate_id"),
                job_id=job.id,
            )

        else:
            # Defensive — should never reach here due to SUPPORTED_JOB_TYPES check
            raise ValueError(f"Unhandled job_type: {job.job_type}")

        return update_job_status(
            db,
            job_id,
            status="succeeded",
            progress=100,
            message="Execution completed successfully",
            output_json=output_json,
        )

    except ValidationError as exc:
        error_msg = f"Input validation failed: {exc.errors()[0]['msg'] if exc.errors() else str(exc)}"
        logger.error("Job %s input validation failed: %s", job_id, error_msg)
        return update_job_status(
            db,
            job_id,
            status="failed",
            progress=10,
            message="Execution failed",
            error_message=error_msg,
        )

    except BepiPred3SidecarError as exc:
        error_msg = _format_sidecar_error(exc)
        logger.error("Job %s BepiPred3 sidecar error: %s", job_id, error_msg)
        return update_job_status(
            db,
            job_id,
            status="failed",
            progress=10,
            message="Execution failed",
            error_message=error_msg,
        )

    except PepMLMSidecarError as exc:
        error_msg = _format_pepmlm_sidecar_error(exc)
        logger.error("Job %s PepMLM sidecar error: %s", job_id, error_msg)
        return update_job_status(
            db,
            job_id,
            status="failed",
            progress=10,
            message="Execution failed",
            error_message=error_msg,
        )

    except Exception as exc:
        error_msg = f"[INTERNAL_ERROR] {type(exc).__name__}: {str(exc)}"
        logger.error("Job %s execution failed: %s", job_id, error_msg)
        return update_job_status(
            db,
            job_id,
            status="failed",
            progress=10,
            message="Execution failed",
            error_message=error_msg,
        )


# ---------------------------------------------------------------------------
# Mock run (for testing the job lifecycle without real compute)
# ---------------------------------------------------------------------------


def run_mock_job(
    db: Session,
    job_id: str,
    sleep_seconds: float = 0.5,
    should_fail: bool = False,
    fail_message: str = "Mock failure for testing.",
) -> Optional[Job]:
    """Execute a mock job run: pending -> running -> succeeded/failed.

    This is a SYNCHRONOUS mock for pytest and integration testing only.
    In production, real jobs should be handled by a background worker
    (e.g. Celery, RQ, or asyncio task queue).
    """
    job = get_job(db, job_id)
    if job is None:
        return None

    if job.status not in ("pending", "running"):
        logger.warning("Job %s cannot be started from status %s", job_id, job.status)
        return job

    # Transition to running
    job = update_job_status(
        db, job_id, status="running", progress=10, message="Mock execution started"
    )
    if job is None:
        return None

    # Simulate work
    time.sleep(sleep_seconds)

    if should_fail:
        job = update_job_status(
            db,
            job_id,
            status="failed",
            progress=0,
            message="Execution failed",
            error_message=fail_message,
            output_json={
                "mode": "MOCK_JOB_V0_9",
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "error": fail_message,
            },
        )
    else:
        job = update_job_status(
            db,
            job_id,
            status="succeeded",
            progress=100,
            message="Mock execution completed successfully",
            output_json={
                "mode": "MOCK_JOB_V0_9",
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "result": "This is mock output for job system testing only.",
                "metrics": {},
            },
        )

    return job


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def cancel_job(db: Session, job_id: str) -> Optional[Job]:
    """Cancel a job if it is pending or running."""
    job = get_job(db, job_id)
    if job is None:
        return None

    if job.status not in ("pending", "running"):
        logger.warning("Job %s cannot be cancelled from status %s", job_id, job.status)
        return job

    return update_job_status(
        db,
        job_id,
        status="cancelled",
        progress=job.progress,
        message="Job cancelled by user",
        error_message="[USER_CANCELLED] Job was cancelled by user",
        output_json={
            "mode": "MOCK_JOB_V0_9",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "cancelled": True,
            "previous_status": job.status,
        },
    )


# ---------------------------------------------------------------------------
# Retry (v0.10-P2d)
# ---------------------------------------------------------------------------


def retry_job(db: Session, job_id: str) -> Optional[Job]:
    """Create a new pending job by copying an existing failed or cancelled job.

    The original job is preserved for audit history.
    Returns the new Job ORM object, or None if original not found.
    """
    job = get_job(db, job_id)
    if job is None:
        return None

    new_job = create_job(
        db,
        JobCreate(
            project_id=job.project_id,
            job_type=job.job_type,
            input_json=job.input_json or {},
        ),
    )
    return new_job


# ---------------------------------------------------------------------------
# Structured error formatting (v0.10-P2d)
# ---------------------------------------------------------------------------


def _format_sidecar_error(exc: BepiPred3SidecarError) -> str:
    """Map BepiPred3SidecarError to a structured error string with prefix."""
    msg = str(exc).lower()
    if "timeout" in msg:
        return f"[SIDECAR_TIMEOUT] {exc}"
    elif "connection refused" in msg or "connect" in msg:
        return f"[SIDECAR_UNAVAILABLE] {exc}"
    elif "http" in msg:
        return f"[SIDECAR_HTTP_ERROR] {exc}"
    elif "invalid" in msg:
        return f"[INVALID_INPUT] {exc}"
    else:
        return f"[SIDECAR_ERROR] {exc}"


def _format_pepmlm_sidecar_error(exc: PepMLMSidecarError) -> str:
    """Map PepMLMSidecarError to a structured error string with prefix."""
    msg = str(exc).lower()
    if "timeout" in msg:
        return f"[SIDECAR_TIMEOUT] {exc}"
    elif "connection refused" in msg or "connect" in msg:
        return f"[SIDECAR_UNAVAILABLE] {exc}"
    elif "http" in msg:
        return f"[SIDECAR_HTTP_ERROR] {exc}"
    elif "invalid" in msg:
        return f"[INVALID_INPUT] {exc}"
    else:
        return f"[SIDECAR_ERROR] {exc}"
