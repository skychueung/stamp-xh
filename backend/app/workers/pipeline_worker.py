"""Durable database-backed worker for long-running pipeline executions."""

from __future__ import annotations

import argparse
import logging
import os
import socket
import threading
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.orm import PipelineRun
from app.services.pipeline_artifacts import atomic_write_json, mark_manifest_status, run_root
from app.services.pipeline_orchestrator import run_pipeline_once

logger = logging.getLogger("stamp.pipeline_worker")
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
POLL_SECONDS = float(os.environ.get("STAMP_PIPELINE_WORKER_POLL_SECONDS", "2"))
LEASE_SECONDS = int(os.environ.get("STAMP_PIPELINE_WORKER_LEASE_SECONDS", "120"))
MAX_RETRIES = int(os.environ.get("STAMP_PIPELINE_MAX_RETRIES", "3"))


def _metadata(run: PipelineRun) -> dict:
    return dict(run.output_json or {})


def _store_metadata(run: PipelineRun, metadata: dict) -> None:
    run.output_json = metadata
    run.updated_at = datetime.now(timezone.utc)


def enqueue_pipeline(
    db: Session,
    run: PipelineRun,
    *,
    top_epitopes: int,
    peptides_per_epitope: int,
    top_stamp_candidates: int,
) -> PipelineRun:
    metadata = _metadata(run)
    queue = dict(metadata.get("queue") or {})
    if run.status in {"QUEUED", "RUNNING"} and queue.get("state") in {"queued", "claimed"}:
        return run
    queue.update(
        {
            "state": "queued",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "worker_id": None,
            "heartbeat_at": None,
            "lease_expires_at": None,
            "retry_count": int(queue.get("retry_count", 0)),
            "max_retries": MAX_RETRIES,
            "parameters": {
                "top_epitopes": top_epitopes,
                "peptides_per_epitope": peptides_per_epitope,
                "top_stamp_candidates": top_stamp_candidates,
            },
        }
    )
    metadata["queue"] = queue
    _store_metadata(run, metadata)
    run.status = "QUEUED"
    db.commit()
    db.refresh(run)
    mark_manifest_status(run.id, "QUEUED")
    return run


def recover_stale_runs(db: Session) -> int:
    now = datetime.now(timezone.utc)
    recovered = 0
    for run in db.query(PipelineRun).filter(PipelineRun.status == "RUNNING").all():
        metadata = _metadata(run)
        queue = dict(metadata.get("queue") or {})
        lease_raw = queue.get("lease_expires_at")
        if not lease_raw:
            continue
        lease = datetime.fromisoformat(lease_raw)
        if lease.tzinfo is None:
            lease = lease.replace(tzinfo=timezone.utc)
        if lease >= now:
            continue
        queue.update({"state": "queued", "worker_id": None, "heartbeat_at": None, "lease_expires_at": None})
        metadata["queue"] = queue
        _store_metadata(run, metadata)
        run.status = "INTERRUPTED"
        db.commit()
        mark_manifest_status(run.id, "INTERRUPTED")
        run.status = "QUEUED"
        db.commit()
        mark_manifest_status(run.id, "QUEUED")
        recovered += 1
    return recovered


def claim_next(db: Session) -> PipelineRun | None:
    run = (
        db.query(PipelineRun)
        .filter(PipelineRun.status == "QUEUED")
        .order_by(PipelineRun.created_at.asc())
        .with_for_update()
        .first()
    )
    if run is None:
        return None
    now = datetime.now(timezone.utc)
    metadata = _metadata(run)
    queue = dict(metadata.get("queue") or {})
    queue.update(
        {
            "state": "claimed",
            "worker_id": WORKER_ID,
            "heartbeat_at": now.isoformat(),
            "lease_expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat(),
        }
    )
    metadata["queue"] = queue
    _store_metadata(run, metadata)
    run.status = "RUNNING"
    db.commit()
    db.refresh(run)
    _write_heartbeat(run.id, queue)
    return run


def _write_heartbeat(run_id: str, queue: dict) -> None:
    atomic_write_json(run_root(run_id) / "worker.json", queue)


def _heartbeat_loop(run_id: str, stop: threading.Event) -> None:
    interval = max(1.0, LEASE_SECONDS / 3)
    while not stop.wait(interval):
        with SessionLocal() as heartbeat_db:
            run = heartbeat_db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
            if run is None or run.status != "RUNNING":
                return
            now = datetime.now(timezone.utc)
            metadata = _metadata(run)
            queue = dict(metadata.get("queue") or {})
            if queue.get("worker_id") != WORKER_ID:
                return
            queue.update(
                {
                    "heartbeat_at": now.isoformat(),
                    "lease_expires_at": (now + timedelta(seconds=LEASE_SECONDS)).isoformat(),
                }
            )
            metadata["queue"] = queue
            _store_metadata(run, metadata)
            heartbeat_db.commit()
            _write_heartbeat(run_id, queue)


def process_run(db: Session, run: PipelineRun) -> None:
    metadata = _metadata(run)
    queue = dict(metadata.get("queue") or {})
    params = dict(queue.get("parameters") or {})
    heartbeat_stop = threading.Event()
    heartbeat_thread = threading.Thread(
        target=_heartbeat_loop, args=(run.id, heartbeat_stop), daemon=True
    )
    heartbeat_thread.start()
    try:
        result = run_pipeline_once(
            db,
            run.id,
            top_epitopes=int(params.get("top_epitopes", 20)),
            peptides_per_epitope=int(params.get("peptides_per_epitope", 5)),
            top_stamp_candidates=int(params.get("top_stamp_candidates", 100)),
        )
        metadata = _metadata(result)
        queue = dict(metadata.get("queue") or queue)
        queue.update({"state": "completed", "finished_at": datetime.now(timezone.utc).isoformat()})
        metadata["queue"] = queue
        _store_metadata(result, metadata)
        db.commit()
        _write_heartbeat(result.id, queue)
    except Exception as exc:
        db.rollback()
        run = db.query(PipelineRun).filter(PipelineRun.id == run.id).first()
        if run is None:
            raise
        metadata = _metadata(run)
        queue = dict(metadata.get("queue") or queue)
        retry_count = int(queue.get("retry_count", 0)) + 1
        queue.update({"retry_count": retry_count, "last_error": str(exc), "worker_id": None})
        if retry_count <= int(queue.get("max_retries", MAX_RETRIES)):
            queue["state"] = "queued"
            run.status = "QUEUED"
        else:
            queue["state"] = "dead_letter"
            run.status = "FAILED"
        metadata["queue"] = queue
        _store_metadata(run, metadata)
        db.commit()
        mark_manifest_status(run.id, run.status)
        logger.exception("Pipeline run %s failed", run.id)
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=2)


def run_once(db: Session) -> bool:
    recover_stale_runs(db)
    run = claim_next(db)
    if run is None:
        return False
    process_run(db, run)
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if args.once:
        with SessionLocal() as db:
            run_once(db)
        return
    if not args.loop:
        parser.error("choose --once or --loop")
    while True:
        with SessionLocal() as db:
            processed = run_once(db)
        if not processed:
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
