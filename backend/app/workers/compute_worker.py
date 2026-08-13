"""Compute Worker for STAMP v1.2-lab-production-fast.

Polls SQLite for PENDING jobs and processes them.
Usage:
    python -m app.workers.compute_worker --once
    python -m app.workers.compute_worker --loop --interval 5
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from typing import Optional

sys.path.insert(0, "D:\\Desktop\\靶向肽\\github\\前端\\backend")

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.orm import Job
from app.services.audit_log_service import log_job_failed, log_job_start, log_job_success
from app.services.server_compute_runner import ServerComputeRunner

logger = logging.getLogger("stamp.worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# Job types that can run locally without heavy compute
LOCAL_JOB_TYPES = {
    "report_export",
    "lims_export",
    "audit_log_cleanup",
}


def get_pending_job(db: Session) -> Optional[Job]:
    """Fetch the oldest PENDING job ordered by priority desc, created_at asc."""
    return db.query(Job).filter(Job.status == "PENDING").order_by(
        Job.priority.desc(), Job.created_at.asc()
    ).with_for_update().first()


def process_job(db: Session, job: Job) -> None:
    """Process a single job."""
    job.status = "RUNNING"
    job.started_at = time.time()
    db.commit()
    db.refresh(job)
    log_job_start(db, job.id)

    try:
        if job.job_type in LOCAL_JOB_TYPES:
            # Local execution: immediately succeed for MVP
            job.status = "SUCCEEDED"
            job.output_json = {"message": f"Local job {job.job_type} completed (MVP)."}
            log_job_success(db, job.id)
        else:
            # Heavy compute: try server dispatch
            runner = ServerComputeRunner(host=job.server_host or "192.168.31.218")
            result = runner.dispatch(job.job_type, job.input_json or {})
            status = result.get("status", "BLOCKED")
            job.status = status
            if status == "BLOCKED":
                job.error_json = result
            elif status == "SUCCEEDED":
                job.output_json = result
                log_job_success(db, job.id)
            else:
                job.error_json = result
                log_job_failed(db, job.id, result)
    except Exception as exc:
        logger.exception(f"Job {job.id} failed with exception")
        job.status = "FAILED"
        job.error_json = {
            "error_code": "WORKER_EXCEPTION",
            "message": str(exc),
        }
        log_job_failed(db, job.id, job.error_json)
    finally:
        job.finished_at = time.time()
        db.commit()
        db.refresh(job)


def run_once(db: Session) -> bool:
    """Process one pending job. Returns True if a job was processed."""
    job = get_pending_job(db)
    if job is None:
        return False
    process_job(db, job)
    return True


def run_loop(interval: int = 5) -> None:
    """Continuously poll for jobs."""
    logger.info(f"Worker started (loop mode, interval={interval}s)")
    while True:
        db = SessionLocal()
        try:
            processed = run_once(db)
            if not processed:
                time.sleep(interval)
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(interval)
        finally:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="STAMP Compute Worker")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.once:
        db = SessionLocal()
        try:
            processed = run_once(db)
            if processed:
                logger.info("Processed one job.")
            else:
                logger.info("No pending jobs.")
        finally:
            db.close()
    elif args.loop:
        run_loop(interval=args.interval)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
