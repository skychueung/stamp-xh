"""EvoBind2 Job Service — Queue skeleton (v0.4-p3c-artifacts).

Provides job submit, query, artifacts, and cancel logic.
Real execution is BLOCKED; dry-run / probe readiness are READY.
Reuses the existing STAMP Job ORM (job_type=\"evobind2_predict\").
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session

from app.crud.jobs import create_job, get_job, update_job_status
from app.models.orm import Job
from app.schemas import JobCreate
from app.schemas.evobind2 import (
    ALLOWED_MODEL_NAMES,
    BLOCKED_MODEL_NAMES,
    DEFAULT_MODEL_NAME,
    EvoBind2JobSubmitRequest,
    _default_safety_flags,
)
from app.services.audit_log_service import log_job_cancel, log_job_submit
from app.services.compute_wrappers.evobind2_wrapper import (
    EVOBIND2_ARTIFACT_ROOT,
    EVOBIND2_REAL_RUN_ENABLED,
    probe_readiness,
)

logger = logging.getLogger(__name__)

EVOBIND2_JOB_TYPE = "evobind2_predict"

# Well-known artifact layout for an EvoBind2 run.  Paths are relative to
# EVOBIND2_ARTIFACT_ROOT/{run_id}.  This avoids exposing absolute server paths
# and makes path-traversal checks straightforward.
_KNOWN_ARTIFACTS: list[dict[str, str]] = [
    {"name": "metrics_csv", "path": "output/metrics.csv", "type": "metrics"},
    {"name": "pdb", "path": "output/unrelaxed_true.pdb", "type": "pdb"},
    {"name": "run_log", "path": "logs/run_stdout_stderr.log", "type": "log"},
    {"name": "gpu_sample_csv", "path": "logs/gpu_sample.csv", "type": "log"},
    {"name": "jax_precheck_log", "path": "logs/jax_gpu_precheck.log", "type": "log"},
    {"name": "manifest_pre", "path": "manifest/manifest_pre.json", "type": "manifest"},
    {"name": "manifest_post", "path": "manifest/manifest_post.json", "type": "manifest"},
    {"name": "receptor_fasta", "path": "input/receptor.fasta", "type": "input"},
    {"name": "receptor_msa_a3m", "path": "input/receptor_msa.a3m", "type": "input"},
]

_KNOWN_ARTIFACT_PATHS: dict[str, str] = {
    a["name"]: a["path"] for a in _KNOWN_ARTIFACTS
}

# ---------------------------------------------------------------------------
# Safety flags builder
# ---------------------------------------------------------------------------


def _build_safety_flags(mode: str, model_name: str, msa_mode: str) -> dict[str, bool]:
    """Build safety flags for an EvoBind2 job based on its parameters."""
    flags = _default_safety_flags()
    flags["is_candidate_generation"] = mode == "design"
    flags["uses_uniref30"] = msa_mode in ("hhblits", "uniref30")
    flags["requires_manual_review"] = True
    flags["requires_real_validation"] = True
    return flags


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _validate_submit(request: EvoBind2JobSubmitRequest) -> tuple[bool, Optional[str]]:
    """Validate an EvoBind2 job submit request.

    Returns (is_valid, error_message).
    """
    if request.model_name in BLOCKED_MODEL_NAMES:
        return False, (
            f"{request.model_name} parameter exists but current EvoBind2 "
            "mc_design.py/config.py path does not support it."
        )
    if request.model_name not in ALLOWED_MODEL_NAMES:
        return False, f"Invalid model name: {request.model_name}. Allowed: {ALLOWED_MODEL_NAMES}"
    if request.mode != "predict_only":
        return False, "Only 'predict_only' mode is supported in this skeleton phase."
    if request.msa_mode not in {"single_sequence", "precomputed_a3m"}:
        return False, (
            f"MSA mode '{request.msa_mode}' is not supported. "
            "Allowed: single_sequence, precomputed_a3m"
        )
    return True, None


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------


def submit_evobind2_job(db: Session, request: EvoBind2JobSubmitRequest) -> Job:
    """Submit a new EvoBind2 job.

    Steps:
      1. Validate input parameters.
      2. Create a Job record (status=pending).
      3. Write audit log (SUBMIT).
      4. If dry_run -> READY_FOR_DRY_RUN (no real execution).
      5. If real_run and EVOBIND2_REAL_RUN_ENABLED -> PENDING (future).
      6. If real_run and not enabled -> BLOCKED.
    """
    valid, error = _validate_submit(request)
    if not valid:
        logger.warning("EvoBind2 job submit validation failed: %s", error)
        raise ValueError(error)

    # Create job record
    job = create_job(
        db,
        JobCreate(
            project_id=request.project_id,
            job_type=EVOBIND2_JOB_TYPE,
            input_json=request.model_dump(),
        ),
    )
    logger.info("EvoBind2 job created: %s (project=%s)", job.id, request.project_id)

    # Audit log: submitted
    log_job_submit(db, job.id)

    safety_flags = _build_safety_flags(
        request.mode, request.model_name, request.msa_mode
    )

    # Run readiness probe to include in output
    readiness = probe_readiness()

    if request.dry_run:
        # Dry-run / probe readiness: mark as READY or COMPLETED
        job = update_job_status(
            db,
            job.id,
            status="ready_for_dry_run",
            progress=100,
            message="Dry-run readiness check passed. Real execution is still disabled.",
            error_message=None,
            output_json={
                "safety_flags": safety_flags,
                "model_name": request.model_name,
                "mode": request.mode,
                "msa_mode": request.msa_mode,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "readiness": readiness,
                "dry_run": True,
            },
        )
        logger.info(
            "EvoBind2 job %s ready for dry-run (real_run_enabled=%s)",
            job.id,
            EVOBIND2_REAL_RUN_ENABLED,
        )
    elif EVOBIND2_REAL_RUN_ENABLED:
        # Real run is enabled (future gate-open phase)
        job = update_job_status(
            db,
            job.id,
            status="pending",
            progress=0,
            message="EvoBind2 job queued for real execution",
            error_message=None,
            output_json={
                "safety_flags": safety_flags,
                "model_name": request.model_name,
                "mode": request.mode,
                "msa_mode": request.msa_mode,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "readiness": readiness,
            },
        )
        logger.info("EvoBind2 job %s queued for real execution", job.id)
    else:
        # Real run blocked in this phase
        job = update_job_status(
            db,
            job.id,
            status="blocked",
            progress=0,
            message="Job blocked — real execution is not enabled (real_run_enabled=false).",
            error_message="EvoBind2 real execution is not enabled in this skeleton phase.",
            output_json={
                "safety_flags": safety_flags,
                "model_name": request.model_name,
                "mode": request.mode,
                "msa_mode": request.msa_mode,
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "readiness": readiness,
            },
        )
        logger.info(
            "EvoBind2 job %s blocked: real execution is not enabled",
            job.id,
        )

    if job is None:
        raise RuntimeError("Failed to update job status after submit")

    return job


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


def get_evobind2_job(db: Session, job_id: str) -> Optional[Job]:
    """Get an EvoBind2 job by ID.

    Returns None if the job does not exist or is not an evobind2_predict job.
    """
    job = get_job(db, job_id)
    if job is None or job.job_type != EVOBIND2_JOB_TYPE:
        return None
    return job


def get_evobind2_job_safety_flags(job: Job) -> dict[str, bool]:
    """Extract and return safety flags for a job from its input_json."""
    input_json = job.input_json or {}
    mode = input_json.get("mode", "predict_only")
    model_name = input_json.get("model_name", DEFAULT_MODEL_NAME)
    msa_mode = input_json.get("msa_mode", "single_sequence")
    return _build_safety_flags(mode, model_name, msa_mode)


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def _run_dir_for_job(job: Job) -> Optional[Path]:
    """Return the absolute run directory for a job if it is under the artifact root.

    Performs path-traversal hardening: the resolved path must be inside
    EVOBIND2_ARTIFACT_ROOT.
    """
    root = Path(EVOBIND2_ARTIFACT_ROOT).resolve()
    run_dir = (root / str(job.id)).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError:
        logger.warning("Run dir for job %s escapes artifact root", job.id)
        return None
    return run_dir


def _list_known_run_artifacts(run_dir: Path) -> list[dict]:
    """List well-known artifact metadata for a run directory.

    All returned paths are relative to the run directory.  Non-existent files
    are reported with exists=False and size_bytes=0.
    """
    result: list[dict] = []
    for definition in _KNOWN_ARTIFACTS:
        rel_path = definition["path"]
        full_path = run_dir / rel_path
        # Defensive: the constructed path must still be inside run_dir.
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


def get_evobind2_job_artifacts(db: Session, job_id: str) -> list[dict]:
    """List artifact metadata for a job, verifying file existence on disk.

    Returns a list of dicts with keys: name, path, artifact_type, exists,
    size_bytes.  Paths are relative to the EvoBind2 artifact root and never
    expose the server absolute path.  Non-existent files are never reported
    as existing.
    """
    job = get_evobind2_job(db, job_id)
    if job is None:
        return []

    run_dir = _run_dir_for_job(job)
    if run_dir is not None and run_dir.exists():
        return _list_known_run_artifacts(run_dir)

    # Fallback for older jobs that only stored artifacts_json: map absolute
    # paths to internal relative paths when they are inside the artifact root.
    artifacts_json = job.artifacts_json or {}
    result: list[dict] = []
    root_abs = Path(EVOBIND2_ARTIFACT_ROOT).resolve()
    for name, raw_path in artifacts_json.items():
        if not raw_path or not isinstance(raw_path, str):
            continue
        path_obj = Path(raw_path).resolve()
        try:
            rel_path = path_obj.relative_to(root_abs)
        except ValueError:
            # Path is outside the allowed artifact root; skip it.
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


def resolve_evobind2_artifact_path(job: Job, artifact_name: str) -> Optional[Path]:
    """Resolve an artifact name to an absolute, sanitized file path.

    Returns None if the artifact is unknown or would resolve outside the
    EvoBind2 artifact root.  This is the only function that should produce
    absolute paths for artifact downloads.
    """
    rel_path = _KNOWN_ARTIFACT_PATHS.get(artifact_name)
    if rel_path is None:
        return None

    run_dir = _run_dir_for_job(job)
    if run_dir is None:
        return None

    full_path = (run_dir / rel_path).resolve()
    try:
        full_path.relative_to(run_dir.resolve())
    except ValueError:
        return None
    return full_path


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------


def cancel_evobind2_job(db: Session, job_id: str) -> Optional[Job]:
    """Cancel an EvoBind2 job if it is pending, running, or blocked.

    Rules:
      - pending / running / blocked / ready_for_dry_run -> cancelled
      - cancelled                   -> idempotent, return as-is
      - succeeded / failed          -> return as-is (no state change)
    """
    job = get_evobind2_job(db, job_id)
    if job is None:
        return None

    if job.status == "cancelled":
        return job

    if job.status not in ("pending", "running", "blocked", "ready_for_dry_run"):
        logger.warning(
            "EvoBind2 job %s cannot be cancelled from status %s",
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
        logger.info("EvoBind2 job %s cancelled (was %s)", job_id, job.status)

    return updated
