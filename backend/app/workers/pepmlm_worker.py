#!/usr/bin/env python3
"""PepMLM real-run worker (P5C).

Single-shot / loop worker that:
  1. Polls for one pending ``pepmlm_generate`` job.
  2. Checks the real-run gate.
  3. Acquires a single-GPU lock.
  4. Runs PepMLM via the adapter and captures artifacts.
  5. Releases the lock and clears the one-time real-run token.

Safety invariants:
  - If the real-run gate is closed, jobs are marked blocked.
  - Only one real-run task executes at a time.
  - Max runtime is bounded by PEPMLM_MAX_RUNTIME_SECONDS (default 3600).
  - All artifacts are written under PEPMLM_ARTIFACT_ROOT.
  - Results are always tagged NOT_EXPERIMENTALLY_VALIDATED.
"""
from __future__ import annotations

import argparse
import datetime
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_DEV_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_DEV_BACKEND_DIR / ".env")

sys.path.insert(0, str(_DEV_BACKEND_DIR))

from sqlalchemy.orm import Session  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.models.orm import Job  # noqa: E402
from app.schemas.model_registry import ModelDryRunPayload  # noqa: E402
from app.services.audit_log_service import (  # noqa: E402
    log_job_failed,
    log_job_start,
    log_job_success,
)
from app.services.gpu_lock_service import acquire_gpu_lock, release_gpu_lock  # noqa: E402
from app.services.model_adapters.pepmlm_adapter import (  # noqa: E402
    PEPMLM_ARTIFACT_ROOT,
    _close_real_run_gate,
    _real_run_allowed,
)
from app.services.pepmlm_job_service import PEPMLM_JOB_TYPE  # noqa: E402

logger = logging.getLogger("stamp.pepmlm_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

PEPMLM_GPU_LOCK_PATH = Path("/home/xh/kxc/stampup/models_dev/pepmlm/locks/pepmlm_gpu.lock")
PEPMLM_MAX_RUNTIME_SECONDS = int(os.environ.get("PEPMLM_MAX_RUNTIME_SECONDS", "3600"))


def _ensure_dirs() -> None:
    Path(PEPMLM_ARTIFACT_ROOT).mkdir(parents=True, exist_ok=True)
    PEPMLM_GPU_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)


def _build_artifacts_json(paths: dict[str, Path]) -> dict[str, str]:
    return {
        "target.fasta": str(paths["input_dir"] / "target.fasta"),
        "candidate_sequences.csv": str(paths["output_dir"] / "candidate_sequences.csv"),
        "candidate_sequences.json": str(paths["output_dir"] / "candidate_sequences.json"),
        "run_stdout_stderr.log": str(paths["logs_dir"] / "run_stdout_stderr.log"),
        "manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
        "manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
    }


def _build_payload_from_job(job: Job) -> ModelDryRunPayload:
    inp = job.input_json or {}
    return ModelDryRunPayload(**inp)


def process_pepmlm_job(db: Session, job: Job) -> None:
    run_id = str(job.id)
    _ensure_dirs()

    if not _real_run_allowed():
        logger.warning("PepMLM job %s blocked: real-run gate is closed", run_id)
        job.status = "blocked"
        job.error_json = {"error_code": "REAL_RUN_GATE_CLOSED", "message": "Real-run gate is closed"}
        job.output_json = {
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "safety_flags": {
                "executed_model": False,
                "generated_candidates": False,
                "generated_structure": False,
                "generated_msa": False,
                "is_scientific_result": False,
                "computational_prediction_only": True,
            },
        }
        db.commit()
        return

    job.status = "running"
    job.started_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(job)
    log_job_start(db, job.id)

    lock_acquired = acquire_gpu_lock(run_id, lock_path=PEPMLM_GPU_LOCK_PATH)
    if not lock_acquired:
        logger.error("Unable to acquire GPU lock for PepMLM job %s", run_id)
        job.status = "failed"
        job.error_json = {"error_code": "GPU_LOCK_FAILED", "message": "Unable to acquire PepMLM GPU lock"}
        job.finished_at = datetime.datetime.utcnow()
        db.commit()
        return

    try:
        # Import here so gate state is evaluated at call time in this process.
        from app.services.model_adapters.pepmlm_adapter import PepMLMAdapter

        payload = _build_payload_from_job(job)
        adapter = PepMLMAdapter("pepmlm")
        result = adapter.submit(payload, run_id=run_id)

        paths = {
            "run_dir": PEPMLM_ARTIFACT_ROOT / run_id,
            "input_dir": PEPMLM_ARTIFACT_ROOT / run_id / "input",
            "output_dir": PEPMLM_ARTIFACT_ROOT / run_id / "output",
            "logs_dir": PEPMLM_ARTIFACT_ROOT / run_id / "logs",
            "manifest_dir": PEPMLM_ARTIFACT_ROOT / run_id / "manifest",
        }

        if result.status == "SUCCEEDED":
            job.status = "succeeded"
            job.message = "PepMLM real-run completed"
            job.error_message = None
            job.output_json = {
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": result.safety_flags.model_dump(),
                "run_id": run_id,
                "artifacts": result.artifacts,
            }
            job.artifacts_json = _build_artifacts_json(paths)
            log_job_success(db, job.id)
        else:
            job.status = "failed"
            job.error_json = {
                "error_code": "PEPMLM_RUN_FAILED",
                "message": result.message,
                "adapter_status": result.status,
            }
            job.error_message = result.message
            job.output_json = {
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": result.safety_flags.model_dump(),
                "run_id": run_id,
            }
            job.artifacts_json = _build_artifacts_json(paths)
            log_job_failed(db, job.id, job.error_json)
    except subprocess.TimeoutExpired:
        logger.error("PepMLM job %s timed out after %s seconds", run_id, PEPMLM_MAX_RUNTIME_SECONDS)
        job.status = "failed"
        job.error_json = {"error_code": "TIMEOUT", "message": f"Exceeded max runtime of {PEPMLM_MAX_RUNTIME_SECONDS}s"}
        job.error_message = "PepMLM run exceeded maximum allowed runtime"
        log_job_failed(db, job.id, job.error_json)
    except Exception as exc:  # noqa: BLE001
        logger.exception("PepMLM job %s failed with exception", run_id)
        job.status = "failed"
        job.error_json = {"error_code": "WORKER_EXCEPTION", "message": str(exc)}
        job.error_message = str(exc)
        log_job_failed(db, job.id, job.error_json)
    finally:
        release_gpu_lock(run_id, lock_path=PEPMLM_GPU_LOCK_PATH)
        _close_real_run_gate()
        job.finished_at = datetime.datetime.utcnow()
        if job.started_at and job.finished_at:
            runtime_seconds = int((job.finished_at - job.started_at).total_seconds())
        else:
            runtime_seconds = 0
        job.output_json = job.output_json or {}
        job.output_json["runtime_seconds"] = runtime_seconds
        db.commit()
        db.refresh(job)


def get_pending_pepmlm_job(db: Session) -> Optional[Job]:
    return (
        db.query(Job)
        .filter(Job.job_type == PEPMLM_JOB_TYPE, Job.status == "pending")
        .order_by(Job.created_at.asc())
        .with_for_update()
        .first()
    )


def run_once(db: Session) -> bool:
    job = get_pending_pepmlm_job(db)
    if job is None:
        return False
    process_pepmlm_job(db, job)
    return True


def run_loop(interval: int = 5) -> None:
    logger.info("PepMLM worker started (loop mode, interval=%ss)", interval)
    while True:
        db = SessionLocal()
        try:
            processed = run_once(db)
            if not processed:
                time.sleep(interval)
        except Exception:
            logger.exception("PepMLM worker loop error")
            time.sleep(interval)
        finally:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="PepMLM Real-Run Worker (P5C)")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    if not args.once and not args.loop:
        parser.print_help()
        sys.exit(1)

    _ensure_dirs()
    logger.info("PEPMLM real-run allowed=%s", _real_run_allowed())
    logger.info("PEPMLM_MAX_RUNTIME_SECONDS=%s", PEPMLM_MAX_RUNTIME_SECONDS)

    if args.once:
        db = SessionLocal()
        try:
            run_once(db)
        finally:
            db.close()
    elif args.loop:
        run_loop(args.interval)


if __name__ == "__main__":
    main()
