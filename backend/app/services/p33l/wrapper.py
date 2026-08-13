"""Thin per-model wrapper that routes P33L orchestrator calls to real runners.

The wrapper is responsible for:
  - building the exact CLI command for each of the six models
  - copying the acceptance fixture into the run input directory
  - creating any per-model gate files required by legacy runners
  - spawning the model subprocess in the same process group as the driver
  - capturing exit code, stdout/stderr, and a structured result dict

When the P33L gate is CLOSED (Phase 2/3 and any unauthorized request), the
wrapper returns immediately with status BLOCKED and does not spawn any model
subprocess, import any model code, or load any checkpoint.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict

from .config import copy_fixture_to_run_dir, get_model_config
from .gate import P33LGate
from .security import compute_file_sha256, validate_run_dir

logger = logging.getLogger("stamp")


class ModelBlockedError(Exception):
    """Raised when the P33L gate is closed and the model must not run."""


class ModelRealRunWrapper:
    """Unified entry point for the six P33L model real runners."""

    @classmethod
    def start(
        cls,
        model_id: str,
        job_id: str,
        input_payload: dict,
        run_dir: str,
        gate_path: str,
        manifest_sha: str,
    ) -> subprocess.Popen:
        """Spawn a driver subprocess that will run the model.

        The driver runs in a new session so the orchestrator can cancel the
        entire process tree by process group.
        """
        validate_run_dir(run_dir)
        # Serialize the call arguments for the driver entry point.
        payload = {
            "model_id": model_id,
            "job_id": job_id,
            "input_payload": input_payload,
            "run_dir": run_dir,
            "gate_path": gate_path,
            "manifest_sha": manifest_sha,
        }
        env = {**os.environ, "P33L_DRIVER_PAYLOAD": json.dumps(payload)}
        log_path = os.path.join(run_dir, "logs", "run_stdout_stderr.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        log_fh = open(log_path, "w", encoding="utf-8")

        proc = subprocess.Popen(
            [sys.executable, "-m", "app.services.p33l.wrapper", "_driver"],
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
            pass_fds=(),
        )
        # Detach the file handle from this process; the driver owns it now.
        log_fh.detach()
        return proc

    @classmethod
    def _driver_entry(cls) -> int:
        """Entry point executed inside the driver subprocess."""
        payload_str = os.environ.get("P33L_DRIVER_PAYLOAD")
        if not payload_str:
            print("P33L_DRIVER_PAYLOAD missing", file=sys.stderr)
            return 1
        payload = json.loads(payload_str)
        result = cls.submit(
            model_id=payload["model_id"],
            job_id=payload["job_id"],
            input_payload=payload["input_payload"],
            run_dir=payload["run_dir"],
            gate_path=payload["gate_path"],
            manifest_sha=payload["manifest_sha"],
        )
        result_path = os.path.join(payload["run_dir"], "manifest", "wrapper_result.json")
        os.makedirs(os.path.dirname(result_path), exist_ok=True)
        with open(result_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        return result.get("exit_code", 1)

    @classmethod
    def submit(
        cls,
        model_id: str,
        job_id: str,
        input_payload: dict,
        run_dir: str,
        gate_path: str,
        manifest_sha: str,
    ) -> dict:
        """Run one model if the P33L gate is open; otherwise return BLOCKED."""
        cfg = get_model_config(model_id)

        # 0. Test-mode hard block: never run models when this env var is set.
        if os.environ.get("P33L_BLOCK_ALL_WRAPPER_EXECUTION", "").lower() in ("1", "true", "yes"):
            return {
                "model_id": model_id,
                "job_id": job_id,
                "status": "blocked",
                "exit_code": 1,
                "error": "P33L wrapper execution is blocked by test configuration",
            }

        # 1. Validate P33L gate is open
        gate = P33LGate(model_id=model_id, job_id=job_id, manifest_sha=manifest_sha)
        gate.gate_path = gate_path
        if not gate.validate():
            return {
                "model_id": model_id,
                "job_id": job_id,
                "status": "blocked",
                "exit_code": 1,
                "error": "P33L gate is closed, expired, or unauthorized",
            }

        # 2. Prepare run directory and input fixture
        os.makedirs(run_dir, exist_ok=True)
        try:
            input_path = copy_fixture_to_run_dir(cfg.fixture_path, run_dir, model_id)
        except Exception as exc:
            return {
                "model_id": model_id,
                "job_id": job_id,
                "status": "failed",
                "exit_code": 1,
                "error": f"Failed to copy fixture: {exc}",
            }

        # Allow user input to override the fixture path for models that accept structure input
        input_path = cls._resolve_input_path(model_id, input_payload, input_path)

        # 3. Create per-model gate/authorization artifacts as needed
        cls._prepare_model_specific_gate(model_id, run_dir, gate_path)

        # 4. Build command
        ctx = {
            "run_dir": run_dir,
            "gate_path": gate_path,
            "config": cfg,
            "fixture_path": input_path,
            "model_variant": input_payload.get("model_variant", "prediction"),
        }
        try:
            command = cfg.command_args(ctx)
        except Exception as exc:
            return {
                "model_id": model_id,
                "job_id": job_id,
                "status": "failed",
                "exit_code": 1,
                "error": f"Failed to build command: {exc}",
            }

        # 5. Run subprocess with hard timeout
        log_path = os.path.join(run_dir, "logs", "run_stdout_stderr.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        started_at = _now_iso()
        try:
            env = cls._build_env(model_id)
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=cfg.timeout_seconds,
                check=False,
                cwd=run_dir,
            )
            with open(log_path, "wb") as fh:
                fh.write(proc.stdout)
            exit_code = proc.returncode
            status = "succeeded" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            status = "timeout"
            exit_code = -15
        except Exception as exc:
            status = "failed"
            exit_code = 1
            with open(log_path, "a", encoding="utf-8") as fh:
                fh.write(f"\nWrapper exception: {exc}\n")

        return {
            "model_id": model_id,
            "job_id": job_id,
            "status": status,
            "exit_code": exit_code,
            "command": command,
            "started_at": started_at,
            "finished_at": _now_iso(),
            "log_path": log_path,
            "input_path": input_path,
            "input_sha256": compute_file_sha256(input_path) if os.path.exists(input_path) else None,
        }

    @classmethod
    def _resolve_input_path(cls, model_id: str, input_payload: dict, fixture_path: str) -> str:
        """Return the user-provided input path if it is under an allowed root."""
        user_path = None
        if model_id in ("diffpepbuilder", "ppflow"):
            user_path = input_payload.get("target_pdb_path")
        elif model_id in ("pepflow", "pephar"):
            user_path = input_payload.get("receptor_pdb_path") or input_payload.get("input_pdb_path")
        elif model_id == "evobind2":
            user_path = input_payload.get("receptor_fasta_path")

        if not user_path:
            return fixture_path

        # Allow only absolute paths under /mnt/sdb/kxc/stamp_models or /home/xh/kxc/stampup
        real_user = os.path.realpath(user_path)
        allowed_roots = [
            "/mnt/sdb/kxc/stamp_models",
            "/home/xh/kxc/stampup",
        ]
        for root in allowed_roots:
            if real_user == root or real_user.startswith(root + os.sep):
                return real_user
        return fixture_path

    @classmethod
    def _prepare_model_specific_gate(cls, model_id: str, run_dir: str, gate_path: str) -> None:
        """Create the per-model gate files expected by legacy runners."""
        if model_id in ("diffpepbuilder", "pephar"):
            # Legacy runners expect a gate file containing the literal string 'true'
            gate_file = Path(gate_path)
            gate_file.parent.mkdir(parents=True, exist_ok=True)
            gate_file.write_text("true", encoding="utf-8")
            os.chmod(gate_file, 0o600)
        elif model_id == "evobind2":
            # EvoBind2 runner expects a gate file named after run_id under its gate root
            evobind2_gate_root = Path("/home/xh/kxc/stampup/run_gates/evobind2")
            evobind2_gate_root.mkdir(parents=True, exist_ok=True)
            job_id = os.path.basename(run_dir)
            gate_file = evobind2_gate_root / job_id
            gate_file.write_text("true", encoding="utf-8")
            os.chmod(gate_file, 0o600)
        elif model_id == "pepmlm":
            # PepMLM adapter checks for a gate file or env var
            pepmlm_gate = Path("/home/xh/kxc/stampup/models_dev/pepmlm/.real_run_enabled")
            pepmlm_gate.touch(mode=0o600, exist_ok=True)

    @classmethod
    def _build_env(cls, model_id: str) -> Dict[str, str]:
        """Return environment overrides for the model subprocess."""
        env = {**os.environ}
        if model_id == "pepmlm":
            env["PEPMLM_REAL_RUN_ENABLED"] = "true"
        return env


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


if __name__ == "__main__" and len(sys.argv) >= 2 and sys.argv[1] == "_driver":
    sys.exit(ModelRealRunWrapper._driver_entry())
