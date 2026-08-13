#!/usr/bin/env python3
"""EvoBind2 real-run worker (P3B/P3C hardened).

Single-shot / loop worker that:
  1. Polls for one pending ``evobind2_predict`` job.
  2. Enforces the final real-run gate (EVOBIND2_REAL_RUN_ENABLED,
     probe readiness, manual approval token).
  3. Acquires a single-GPU lock.
  4. Writes receptor.fasta and runs mc_design.py once.
  5. Captures stdout/stderr, metrics.csv / PDB, and a manifest.
  6. Releases the lock and closes the real-run gate.

Safety invariants:
  - If EVOBIND2_REAL_RUN_ENABLED is False, jobs are marked blocked.
  - Only one real-run task executes at a time.
  - Max runtime is bounded by EVOBIND2_MAX_RUNTIME_SECONDS.
  - All artifacts are written under EVOBIND2_ARTIFACT_ROOT.
  - Results are always tagged NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Load backend/.env so that EVOBIND2_REAL_RUN_APPROVAL and gate env vars are available.
from dotenv import load_dotenv

_DEV_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_DEV_BACKEND_DIR / ".env")

sys.path.insert(0, str(_DEV_BACKEND_DIR))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.orm import Job
from app.services.audit_log_service import (
    log_job_failed,
    log_job_start,
    log_job_success,
)
from app.services.compute_wrappers.evobind2_wrapper import (
    CONDA_ENV_PATH,
    EVOBIND2_ARTIFACT_ROOT,
    EVOBIND2_LOG_ROOT,
    EVOBIND2_REAL_RUN_ENABLED,
    EVOBIND2_ROOT,
    EvoBind2Input,
    build_environment,
    build_mc_design_command,
    build_run_paths,
    probe_readiness,
)
from app.services.evobind2_job_service import EVOBIND2_JOB_TYPE
from app.services.gpu_lock_service import (
    acquire_gpu_lock,
    release_gpu_lock,
)

logger = logging.getLogger("stamp.evobind2_worker")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

EVOBIND2_GPU_LOCK_PATH = Path("/home/xh/kxc/stampup/models_dev/evobind2/locks/evobind2_gpu.lock")
ARTIFACT_RETENTION_SECONDS = int(os.environ.get("EVOBIND2_ARTIFACT_RETENTION_SECONDS", "604800"))
EVOBIND2_MAX_RUNTIME_SECONDS = int(os.environ.get("EVOBIND2_MAX_RUNTIME_SECONDS", "14400"))


def _ensure_dirs() -> None:
    Path(EVOBIND2_LOG_ROOT).mkdir(parents=True, exist_ok=True)
    EVOBIND2_GPU_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    Path(EVOBIND2_ARTIFACT_ROOT).mkdir(parents=True, exist_ok=True)


def _final_gate_check() -> tuple[bool, Optional[str]]:
    if not EVOBIND2_REAL_RUN_ENABLED:
        return False, "EVOBIND2_REAL_RUN_ENABLED=false"

    readiness = probe_readiness()
    overall = readiness.get("overall_status")
    if overall not in {"READY_FOR_REAL_RUN", "READY_FOR_PROBE"}:
        return False, f"Readiness gate not open: {overall}"

    if not os.environ.get("EVOBIND2_REAL_RUN_APPROVAL"):
        return False, "EVOBIND2_REAL_RUN_APPROVAL token missing"

    return True, None


def _manifest_for_run(run_id: str, paths: dict[str, str]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "artifacts": [
            {"name": "metrics_csv", "path": paths["metrics_csv"], "exists": False, "size_bytes": 0},
            {"name": "pdb", "path": paths["pdb"], "exists": False, "size_bytes": 0},
            {"name": "gpu_sample_csv", "path": paths["gpu_sample_csv"], "exists": False, "size_bytes": 0},
            {"name": "run_log", "path": paths["run_log"], "exists": False, "size_bytes": 0},
            {"name": "jax_precheck_log", "path": paths["jax_precheck_log"], "exists": False, "size_bytes": 0},
        ],
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "safety_flags": {
            "is_candidate_generation": False,
            "is_scientific_result": False,
        },
    }


def _close_gate_after_run() -> None:
    """Disable real-run in wrapper.py so the gate cannot be left open."""
    wrapper_path = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend/app/services/compute_wrappers/evobind2_wrapper.py")
    try:
        text = wrapper_path.read_text(encoding="utf-8")
        text = text.replace("EVOBIND2_REAL_RUN_ENABLED = True", "EVOBIND2_REAL_RUN_ENABLED = False")
        wrapper_path.write_text(text, encoding="utf-8")
        logger.info("Real-run gate closed in wrapper.py")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to close real-run gate in wrapper.py: %s", exc)


def _write_receptor_fasta(target_sequence: str, path: str) -> str:
    """Write receptor.fasta and return the cleaned sequence."""
    lines = [line.strip() for line in target_sequence.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty target_sequence")

    if lines[0].startswith(>"):
        header = lines[0]
        seq_lines = lines[1:]
    else:
        header = ">receptor"
        seq_lines = lines

    sequence = "".join(seq_lines).replace(" ", "")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(f"{header}\n{sequence}\n")
    return sequence


def _write_single_sequence_a3m(fasta_path: str, a3m_path: str) -> None:
    """Create a minimal single-sequence a3m MSA from the receptor FASTA."""
    Path(a3m_path).parent.mkdir(parents=True, exist_ok=True)
    with open(fasta_path, "r", encoding="utf-8") as fh:
        content = fh.read()
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Empty FASTA for a3m generation")
    header = lines[0] if lines[0].startswith(">") else ">receptor"
    sequence = "".join(lines[1:]) if lines[0].startswith(">") else "".join(lines)
    with open(a3m_path, "w", encoding="utf-8") as fh:
        fh.write(f"{header}\n{sequence}\n")


def _build_input_from_job(job: Job) -> EvoBind2Input:
    inp = job.input_json or {}
    return EvoBind2Input(
        run_id=str(job.id),
        receptor_fasta=inp.get("target_sequence", ""),
        peptide_length=inp.get("peptide_length", 8),
        mode=inp.get("mode", "predict_only"),
        peptide_sequence=inp.get("peptide_sequence"),
        model_name=inp.get("model_name", "model_1_ptm"),
        max_recycles=inp.get("max_recycles", 1),
        num_iterations=inp.get("num_iterations", 1),
        use_gpu=inp.get("use_gpu", True),
        selected_gpu=inp.get("selected_gpu", "auto"),
        msa_mode=inp.get("msa_mode", "single_sequence"),
        receptor_msa_a3m=inp.get("receptor_msa_a3m"),
    )


def _update_manifest_from_disk(manifest: dict[str, Any]) -> None:
    for artifact in manifest["artifacts"]:
        path = artifact["path"]
        exists = os.path.exists(path)
        artifact["exists"] = exists
        artifact["size_bytes"] = os.path.getsize(path) if exists else 0


def _write_manifest(manifest: dict[str, Any], paths: dict[str, str]) -> None:
    manifest_dir = Path(paths["run_dir"]) / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    pre_path = manifest_dir / "manifest_pre.json"
    post_path = manifest_dir / "manifest_post.json"
    if not pre_path.exists():
        pre_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    post_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _build_artifacts_json(paths: dict[str, str], manifest: dict[str, Any]) -> dict[str, str]:
    """Build the artifacts_json mapping stored on the Job record.

    Includes the core manifest artifacts plus input files and manifest JSON.
    Paths are absolute; the API layer normalizes them to internal relative paths
    before exposing them to clients.
    """
    artifacts: dict[str, str] = {
        a["name"]: a["path"] for a in manifest["artifacts"]
    }
    artifacts["receptor_fasta"] = paths["receptor_fasta_path"]
    artifacts["receptor_msa_a3m"] = paths["receptor_msa_path"]
    artifacts["manifest_pre"] = str(Path(paths["run_dir"]) / "manifest" / "manifest_pre.json")
    artifacts["manifest_post"] = str(Path(paths["run_dir"]) / "manifest" / "manifest_post.json")
    return artifacts


def _run_mc_design(
    job: Job,
    paths: dict[str, str],
    manifest: dict[str, Any],
    selected_gpu: int,
) -> int:
    inp = _build_input_from_job(job)
    sequence = _write_receptor_fasta(inp.receptor_fasta, paths["receptor_fasta_path"])

    # EvoBind2 foldonly.py requires at least one MSA even in single_sequence mode.
    # Generate a single-sequence a3m from the receptor FASTA when none is supplied.
    if inp.msa_mode == "single_sequence" and not inp.receptor_msa_a3m:
        _write_single_sequence_a3m(paths["receptor_fasta_path"], paths["receptor_msa_path"])
        inp.receptor_msa_a3m = paths["receptor_msa_path"]

    # Pre-run manifest
    _write_manifest(manifest, paths)

    env = build_environment(selected_gpu)
    # Ensure the host conda executable is discoverable for subprocess.run.
    env["PATH"] = f"/home/xh/miniconda3/bin:{env['PATH']}"
    # Conda run requires a SHELL env var when invoked without an interactive shell.
    env["SHELL"] = "/bin/bash"
    cmd = build_mc_design_command(paths, inp)
    # Bypass 'conda run' which fails in non-interactive subprocesses; invoke the env python directly.
    if len(cmd) >= 5 and cmd[0] == "conda" and cmd[1] == "run" and cmd[2] == "-p":
        cmd = [f"{CONDA_ENV_PATH}/bin/python"] + cmd[5:]

    logger.info("Running mc_design.py for job %s on GPU %s", job.id, selected_gpu)
    logger.info("Command: %s", " ".join(cmd))

    Path(paths["logs_dir"]).mkdir(parents=True, exist_ok=True)
    Path(paths["output_dir"]).mkdir(parents=True, exist_ok=True)
    with open(paths["run_log"], "w", encoding="utf-8") as log_fh:
        proc = subprocess.run(
            cmd,
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env={**os.environ, **env},
            cwd=EVOBIND2_ROOT,
            timeout=EVOBIND2_MAX_RUNTIME_SECONDS,
        )

    return proc.returncode


def process_evobind2_job(db: Session, job: Job) -> None:
    run_id = str(job.id)
    _ensure_dirs()

    ok, reason = _final_gate_check()
    if not ok:
        logger.warning("EvoBind2 job %s blocked by final gate: %s", run_id, reason)
        job.status = "blocked"
        job.error_json = {"error_code": "REAL_RUN_GATE_CLOSED", "message": reason}
        job.output_json = {
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "safety_flags": {
                "is_candidate_generation": False,
                "is_scientific_result": False,
                "executed_model": False,
                "generated_candidates": False,
                "generated_pdb": False,
                "generated_msa": False,
            },
        }
        db.commit()
        return

    job.status = "running"
    job.started_at = datetime.datetime.utcnow()
    db.commit()
    db.refresh(job)
    log_job_start(db, job.id)

    selected_gpu = 0
    paths = build_run_paths(run_id)
    manifest = _manifest_for_run(run_id, paths)

    # Write pre-run manifest before lock/execution
    _write_manifest(manifest, paths)

    lock_acquired = acquire_gpu_lock(run_id, lock_path=EVOBIND2_GPU_LOCK_PATH)
    if not lock_acquired:
        logger.error("Unable to acquire GPU lock for job %s", run_id)
        job.status = "failed"
        job.error_json = {"error_code": "GPU_LOCK_FAILED", "message": "Unable to acquire EvoBind2 GPU lock"}
        db.commit()
        return

    returncode = -1
    try:
        returncode = _run_mc_design(job, paths, manifest, selected_gpu)
        _update_manifest_from_disk(manifest)
        _write_manifest(manifest, paths)

        if returncode == 0:
            job.status = "succeeded"
            job.message = "EvoBind2 real-run completed"
            job.error_message = None
            job.output_json = {
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "safety_flags": {
                    "is_candidate_generation": False,
                    "is_scientific_result": False,
                    "executed_model": True,
                    "generated_candidates": False,
                    "generated_pdb": manifest["artifacts"][1]["exists"],
                    "generated_msa": False,
                },
                "manifest": manifest,
            }
            log_job_success(db, job.id)
        else:
            job.status = "failed"
            job.error_json = {"error_code": "MC_DESIGN_NONZERO_EXIT", "message": f"mc_design.py exited with code {returncode}"}
            job.error_message = f"mc_design.py exited with code {returncode}"
            job.output_json = {"manifest": manifest, "validation_status": "NOT_EXPERIMENTALLY_VALIDATED"}
            log_job_failed(db, job.id, f"mc_design.py exited with code {returncode}")
    except subprocess.TimeoutExpired:
        logger.error("EvoBind2 job %s timed out after %s seconds", run_id, EVOBIND2_MAX_RUNTIME_SECONDS)
        job.status = "failed"
        job.error_json = {"error_code": "TIMEOUT", "message": f"Exceeded max runtime of {EVOBIND2_MAX_RUNTIME_SECONDS}s"}
        job.error_message = "EvoBind2 run exceeded maximum allowed runtime"
        _update_manifest_from_disk(manifest)
        _write_manifest(manifest, paths)
        job.output_json = {"manifest": manifest, "validation_status": "NOT_EXPERIMENTALLY_VALIDATED"}
        log_job_failed(db, job.id, "EvoBind2 run exceeded maximum allowed runtime")
    except Exception as exc:  # noqa: BLE001
        logger.exception("EvoBind2 job %s failed with exception", run_id)
        job.status = "failed"
        job.error_json = {"error_code": "WORKER_EXCEPTION", "message": str(exc)}
        job.error_message = str(exc)
        _update_manifest_from_disk(manifest)
        _write_manifest(manifest, paths)
        job.output_json = {"manifest": manifest, "validation_status": "NOT_EXPERIMENTALLY_VALIDATED"}
        log_job_failed(db, job.id, str(exc))
    finally:
        release_gpu_lock(run_id, lock_path=EVOBIND2_GPU_LOCK_PATH)
        job.finished_at = datetime.datetime.utcnow()
        if job.started_at and job.finished_at:
            runtime_seconds = int((job.finished_at - job.started_at).total_seconds())
        else:
            runtime_seconds = 0
        job.output_json = job.output_json or {}
        job.output_json["runtime_seconds"] = runtime_seconds
        job.artifacts_json = _build_artifacts_json(paths, manifest)
        db.commit()
        db.refresh(job)
        _close_gate_after_run()


def get_pending_evobind2_job(db: Session) -> Optional[Job]:
    return (
        db.query(Job)
        .filter(Job.job_type == EVOBIND2_JOB_TYPE, Job.status == "pending")
        .order_by(Job.created_at.asc())
        .with_for_update()
        .first()
    )


def run_once(db: Session) -> bool:
    job = get_pending_evobind2_job(db)
    if job is None:
        return False
    process_evobind2_job(db, job)
    return True


def run_loop(interval: int = 5) -> None:
    logger.info("EvoBind2 worker started (loop mode, interval=%ss)", interval)
    while True:
        db = SessionLocal()
        try:
            processed = run_once(db)
            if not processed:
                time.sleep(interval)
        except Exception:
            logger.exception("EvoBind2 worker loop error")
            time.sleep(interval)
        finally:
            db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="EvoBind2 Real-Run Worker (P3C hardened)")
    parser.add_argument("--once", action="store_true", help="Process one job and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument("--interval", type=int, default=5, help="Polling interval in seconds")
    args = parser.parse_args()

    if not args.once and not args.loop:
        parser.print_help()
        sys.exit(1)

    _ensure_dirs()
    logger.info("EVOBIND2_REAL_RUN_ENABLED=%s", EVOBIND2_REAL_RUN_ENABLED)
    logger.info("EVOBIND2_MAX_RUNTIME_SECONDS=%s", EVOBIND2_MAX_RUNTIME_SECONDS)

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
