"""P33L job orchestrator: fixed order, one attempt per model, fail-stop.

The orchestrator is the single backend component that may:
  - authorize a P33L real-run request
  - create a file-based execution gate
  - acquire the GPU lock
  - spawn the model wrapper subprocess
  - enforce hard timeout, disk quota, and output file limits
  - write the uniform run manifest
  - cancel a running job
  - clean up the gate, lock, and subprocess tree by PID

It never uses broad pkill/rm.  All cleanup is scoped to the exact job PID,
gate directory, and run directory created for that job.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import subprocess
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.gpu_lock_service import acquire_gpu_lock, release_gpu_lock

from .config import get_model_config, ordered_model_ids, validate_job_id
from .gate import P33LGate
from .manifest import write_manifest
from .security import compute_file_sha256, safe_relative_path, validate_run_dir
from .state import P33LState
from .wrapper import ModelRealRunWrapper

logger = logging.getLogger("stamp")


@dataclass
class P33LJob:
    job_id: str
    model_id: str
    attempt_number: int = 1
    status: str = "queued"  # queued|running|succeeded|failed|timeout|cancelled|blocked
    manifest_sha: str = ""
    run_dir: str = ""
    gate_path: str = ""
    pid: Optional[int] = None
    result: dict = field(default_factory=dict)
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "model_id": self.model_id,
            "attempt_number": self.attempt_number,
            "status": self.status,
            "manifest_sha": self.manifest_sha,
            "run_dir": self.run_dir,
            "gate_path": self.gate_path,
            "pid": self.pid,
            "result": self.result,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


class P33LOrchestrator:
    """Persistent, fail-stop orchestrator for the six-model P33L sequence."""

    ARTIFACT_ROOT = "/mnt/sdb/kxc/stamp_models/artifacts/p33l"

    def __init__(self, manifest_sha: str, state_path: str = ""):
        self.manifest_sha = manifest_sha
        self.state = P33LState(state_path) if state_path else P33LState()
        self.jobs: Dict[str, P33LJob] = {}
        self._load_attempts_into_memory()
        os.makedirs(self.ARTIFACT_ROOT, exist_ok=True)

    def _load_attempts_into_memory(self) -> None:
        """Rebuild in-memory job list from persistent attempt records."""
        for model_id in ordered_model_ids():
            for attempt in self.state.get_attempts(model_id):
                job_id = attempt.get("job_id", "")
                if job_id and job_id not in self.jobs:
                    self.jobs[job_id] = P33LJob(
                        job_id=job_id,
                        model_id=model_id,
                        status=attempt.get("status", "unknown"),
                        manifest_sha=self.manifest_sha,
                    )

    def _next_allowed_model(self) -> Optional[str]:
        for model_id in ordered_model_ids():
            if not self.state.is_model_attempted(model_id):
                return model_id
        return None

    def _prior_failed_model(self) -> Optional[str]:
        for model_id in ordered_model_ids():
            attempts = self.state.get_attempts(model_id)
            if any(a.get("status") != "succeeded" for a in attempts):
                return model_id
        return None

    def _validate_input(self, model_id: str, input_payload: dict) -> tuple[bool, str]:
        cfg = get_model_config(model_id)
        allowed = {
            "pepmlm": {"target_sequence", "peptide_length", "num_candidates", "seed", "top_k", "device"},
            "evobind2": {"receptor_fasta_path", "receptor_sequence", "peptide_length", "peptide_sequence", "max_recycles", "num_iterations", "device", "seed"},
            "diffpepbuilder": {"target_pdb_path", "num_candidates", "seed", "device"},
            "pepflow": {"receptor_pdb_path", "num_samples", "num_steps", "seed", "device"},
            "pephar": {"input_pdb_path", "model_variant", "seed", "device"},
            "ppflow": {"target_pdb_path", "batch_size", "tag", "seed", "device", "checkpoint", "config"},
        }
        allowed_keys = allowed.get(model_id, set())
        for key in input_payload:
            if key not in allowed_keys:
                return False, f"unexpected key '{key}' for {model_id}"
        return True, ""

    def create_job(self, model_id: str, input_payload: dict) -> P33LJob:
        """Create a new P33L job if and only if it is the next allowed model."""
        model_id = model_id.lower().strip()
        cfg = get_model_config(model_id)

        # 1. Idempotency / one attempt per model
        if self.state.is_model_attempted(model_id):
            raise ValueError(f"Model {model_id} already attempted in this P33L session")

        # 2. Model scope and order
        if model_id != self._next_allowed_model():
            raise ValueError(f"Model {model_id} is not next in fixed order")

        # 3. Fail-stop: if any prior model failed, refuse all subsequent models
        failed = self._prior_failed_model()
        if failed and failed != model_id:
            raise ValueError(f"Prior model {failed} failed; P33L stopped")

        # 4. Input schema validation
        ok, error = self._validate_input(model_id, input_payload)
        if not ok:
            raise ValueError(f"Input validation failed: {error}")

        # 5. Build job
        job_id = f"p33l_{model_id}_{uuid.uuid4().hex[:16]}"
        validate_job_id(job_id)
        run_dir = os.path.join(self.ARTIFACT_ROOT, job_id)
        validate_run_dir(run_dir)

        job = P33LJob(
            job_id=job_id,
            model_id=model_id,
            attempt_number=1,
            status="queued",
            manifest_sha=self.manifest_sha,
            run_dir=run_dir,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self.jobs[job_id] = job
        return job

    def run_job(self, job: P33LJob, input_payload: dict) -> P33LJob:
        """Execute the job under a fresh gate, GPU lock, timeout, and quota."""
        cfg = get_model_config(job.model_id)
        gate = P33LGate(
            model_id=job.model_id,
            job_id=job.job_id,
            manifest_sha=self.manifest_sha,
            ttl_seconds=cfg.timeout_seconds + 300,
        )

        proc: Optional[subprocess.Popen] = None
        try:
            # Create run directory
            os.makedirs(job.run_dir, exist_ok=True)

            # Create gate
            gate_doc = gate.create()
            job.gate_path = gate.gate_path

            # Acquire GPU lock
            lock_acquired = acquire_gpu_lock(
                job_id=job.job_id,
                timeout_seconds=cfg.timeout_seconds + 300,
            )
            if not lock_acquired:
                raise RuntimeError("GPU lock unavailable")

            job.status = "running"
            job.started_at = datetime.now(timezone.utc).isoformat()

            # Start model wrapper subprocess
            proc = ModelRealRunWrapper.start(
                model_id=job.model_id,
                job_id=job.job_id,
                input_payload=input_payload,
                run_dir=job.run_dir,
                gate_path=job.gate_path,
                manifest_sha=self.manifest_sha,
            )
            job.pid = proc.pid
            self.state.record_attempt(job.model_id, job.job_id, "running")

            # Wait with hard timeout
            try:
                exit_code = proc.wait(timeout=cfg.timeout_seconds)
            except subprocess.TimeoutExpired:
                self._kill_process_tree(job.pid)
                exit_code = -signal.SIGTERM
                job.status = "timeout"

            # Determine status and load structured result from wrapper
            if job.status != "timeout":
                job.status = "succeeded" if exit_code == 0 else "failed"
            job.result = self._load_wrapper_result(job.run_dir) or {"exit_code": exit_code}

        except Exception as exc:
            logger.exception("P33L job %s failed", job.job_id)
            job.status = "failed"
            job.result = {"error": str(exc), "error_type": exc.__class__.__name__}
        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()
            # Ensure subprocess is gone
            if proc is not None and proc.poll() is None and job.pid:
                self._kill_process_tree(job.pid)
            # Release GPU lock
            release_gpu_lock(job.job_id)
            # Close gate
            gate.close()
            # Enforce quota and write manifest
            self._finalize_job(job, input_payload)
            # Persist final outcome
            self.state.record_attempt(job.model_id, job.job_id, job.status)

        return job

    def cancel_job(self, job_id: str) -> P33LJob:
        """Cancel a running or queued job using its recorded PID."""
        job = self.jobs.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")

        if job.status not in ("queued", "running"):
            return job

        if job.pid:
            self._kill_process_tree(job.pid)

        # Close the gate if it exists
        if job.gate_path and os.path.exists(job.gate_path):
            gate = P33LGate(job.model_id, job.job_id, manifest_sha=self.manifest_sha)
            gate.gate_path = job.gate_path
            gate.close()

        release_gpu_lock(job_id)
        job.status = "cancelled"
        job.finished_at = datetime.now(timezone.utc).isoformat()
        self.state.record_attempt(job.model_id, job.job_id, "cancelled")
        return job

    def get_job(self, job_id: str) -> Optional[P33LJob]:
        return self.jobs.get(job_id)

    def _finalize_job(self, job: P33LJob, input_payload: dict) -> None:
        """Enforce disk quota, count output files, and write the manifest."""
        cfg = get_model_config(job.model_id)
        quota_error = None
        file_count = 0
        total_size = 0

        if os.path.isdir(job.run_dir):
            for root, _, files in os.walk(job.run_dir):
                for f in files:
                    fp = os.path.join(root, f)
                    try:
                        total_size += os.path.getsize(fp)
                        file_count += 1
                    except OSError:
                        pass

            if total_size > cfg.disk_quota_bytes:
                quota_error = f"disk quota exceeded: {total_size} > {cfg.disk_quota_bytes}"
                job.status = "failed"
            if file_count > cfg.max_output_files:
                quota_error = f"max output files exceeded: {file_count} > {cfg.max_output_files}"
                job.status = "failed"

        input_provenance = self._build_input_provenance(job, input_payload)
        result = {
            "status": job.status,
            "exit_code": job.result.get("exit_code") if job.result else None,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "disk_used_bytes": total_size,
            "file_count": file_count,
            "quota_error": quota_error,
            **(job.result or {}),
        }
        try:
            write_manifest(job.run_dir, job, result, input_provenance)
        except Exception as exc:
            logger.exception("Failed to write manifest for %s", job.job_id)
            job.status = "failed"
            result["manifest_error"] = str(exc)
            job.result = result

    @staticmethod
    def _load_wrapper_result(run_dir: str) -> Optional[dict]:
        """Load the wrapper result written by the driver subprocess."""
        result_path = os.path.join(run_dir, "manifest", "wrapper_result.json")
        if not os.path.exists(result_path):
            return None
        try:
            with open(result_path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def _build_input_provenance(self, job: P33LJob, input_payload: dict) -> dict:
        cfg = get_model_config(job.model_id)
        input_dir = os.path.join(job.run_dir, "input")
        files = []
        if os.path.isdir(input_dir):
            for f in sorted(os.listdir(input_dir)):
                fp = os.path.join(input_dir, f)
                if os.path.isfile(fp):
                    try:
                        files.append({"path": f"input/{f}", "sha256": compute_file_sha256(fp)})
                    except OSError:
                        files.append({"path": f"input/{f}", "sha256": "ERROR"})
        return {
            "source": "acceptance_fixture",
            "fixture_path": cfg.fixture_path,
            "fixture_sha256": cfg.fixture_sha256,
            "user_input": input_payload,
            "files": files,
            "schema_valid": True,
        }

    @staticmethod
    def _kill_process_tree(pid: Optional[int]) -> None:
        """Kill a process and its children by PID, never pkill."""
        if not pid:
            return
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, OSError):
            pass

        # Wait up to 30 seconds
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            time.sleep(0.2)

        try:
            os.killpg(os.getpgid(pid), signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    def reset_session(self) -> None:
        """Reset persistent state.  Use only in tests with isolated state paths."""
        self.state.reset()
        self.jobs.clear()
