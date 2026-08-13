#!/usr/bin/env python3
"""Continuous worker for all five production model queues."""

from __future__ import annotations

import argparse
import logging
import time

from app.database import SessionLocal
from app.services.unified_model_runtime import get_next_queued_model_job, process_model_job, recover_interrupted_model_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stamp.model_worker")


def run_once() -> bool:
    db = SessionLocal()
    try:
        job = get_next_queued_model_job(db)
        if job is None:
            return False
        process_model_job(db, job)
        return True
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    db = SessionLocal()
    try:
        recovered = recover_interrupted_model_jobs(db)
        logger.info("Recovered %d interrupted model jobs", len(recovered))
    finally:
        db.close()
    if args.once:
        run_once()
        return
    while True:
        if not run_once():
            time.sleep(args.interval)


if __name__ == "__main__":
    main()
