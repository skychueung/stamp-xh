"""P33U execution engine — process transport abstraction and execute_run().

Design (per P33U-D0):
- execute_run() is the shared engine called by each RunnerContract.execute().
- A ProcessTransport abstraction isolates subprocess spawning so zero-model
  tests inject a MockProcessRunner. NO real subprocess is spawned in tests.
- RealSubprocessTransport uses subprocess.Popen with shell=False and a list
  argv (NEVER shell=True, NEVER string-concatenated commands). It checks
  P33U_BLOCK_ALL_EXECUTION and refuses to spawn if set — defense-in-depth at
  the moment of spawn.
- Before any spawn, execute_run() enforces:
    1. manifest_sha == authorized_manifest_sha (both non-empty)  -> else refuse
    2. attempt_count(model) == 0 (retry_count = 0, fail-stop)     -> else refuse
    3. validate_input() passes                                    -> else refuse
- Gate lifecycle: open(OPEN, manifest_sha bound) -> update_pid -> on any
  terminal condition close with CLOSED/FAILED/TIMEOUT, PRESERVING the scene
  (exit_code, note, log_path). Exceptions/KeyboardInterrupt also close the
  gate FAILED and preserve the scene, then re-raise.
- retry is structurally impossible: attempt_count check + state record on
  every execute means a second call for the same model is refused.

This module imports subprocess ONLY inside RealSubprocessTransport.run, which
is never instantiated in zero-model tests (tests inject MockProcessRunner).
The module-level import surface stays clean of torch/cuda/requests.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from .config import BLOCK_ALL_EXECUTION_ENV, GPU_LOCK_PATH, VALIDATION_STATUS
from . import gate as gate_mod
from .state import P33UState


# ---------------------------------------------------------------------------
# Result / outcome types
# ---------------------------------------------------------------------------
@dataclass
class ProcessResult:
    returncode: int | None
    timed_out: bool = False
    pid: int | None = None
    note: str = ""


@dataclass
class ExecutionOutcome:
    run_id: str
    model_id: str
    state: str  # CLOSED | FAILED | TIMEOUT
    exit_code: int | None
    pid: int | None
    gate_path: str
    log_path: str
    artifacts: list[str] = field(default_factory=list)
    parsed: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    validation_status: str = VALIDATION_STATUS
    note: str = ""


class ExecutionRefused(RuntimeError):
    """Raised when auth / lock / retry / input checks refuse execution."""


class ExecutionBlocked(ExecutionRefused):
    """Raised when P33U_BLOCK_ALL_EXECUTION is set on the real spawn path."""


# ---------------------------------------------------------------------------
# Process transport abstraction
# ---------------------------------------------------------------------------
class ProcessTransport(Protocol):
    def run(self, cmd: list[str], cwd: str, env: dict[str, str],
            timeout: int, log_path: str) -> ProcessResult:
        ...


class RealSubprocessTransport:
    """Real transport. Uses Popen with shell=False and list argv. Refuses to
    spawn if P33U_BLOCK_ALL_EXECUTION is set. NEVER instantiated in tests."""

    def run(self, cmd: list[str], cwd: str, env: dict[str, str],
            timeout: int, log_path: str) -> ProcessResult:
        if os.environ.get(BLOCK_ALL_EXECUTION_ENV):
            raise ExecutionBlocked(
                "P33U real subprocess refused: %s is set. Lane D requires "
                "unsetting this env AND a matching authorized manifest SHA."
                % BLOCK_ALL_EXECUTION_ENV
            )
        if not isinstance(cmd, list) or not all(isinstance(t, str) for t in cmd):
            raise ExecutionBlocked("cmd must be a list[str]; shell=True forbidden")
        import subprocess  # local import: never on the test import path
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        log_fh = open(log_path, "w", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd, cwd=cwd, env=env, stdout=log_fh, stderr=subprocess.STDOUT,
                shell=False, start_new_session=True,
            )
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                # Kill the process group, then reap. Scene preserved by caller.
                try:
                    import os as _os
                    _os.killpg(_os.getpgid(proc.pid), 9)
                except Exception:
                    pass
                try:
                    proc.wait(timeout=10)
                except Exception:
                    pass
                return ProcessResult(returncode=None, timed_out=True, pid=proc.pid,
                                     note="subprocess timeout")
            return ProcessResult(returncode=proc.returncode, timed_out=False,
                                 pid=proc.pid)
        finally:
            log_fh.close()


class MockProcessRunner:
    """Test-only transport. Records calls; returns a configured ProcessResult.
    Never spawns anything. No subprocess / GPU / 8189 / checkpoint access."""

    def __init__(self, returncode: int = 0, timed_out: bool = False,
                 pid: int = 99999) -> None:
        self.returncode = returncode
        self.timed_out = timed_out
        self.pid = pid
        self.calls: list[dict[str, Any]] = []

    def run(self, cmd: list[str], cwd: str, env: dict[str, str],
            timeout: int, log_path: str) -> ProcessResult:
        self.calls.append({"cmd": list(cmd), "cwd": cwd, "env_keys": sorted(env),
                           "timeout": timeout, "log_path": log_path})
        # Write a minimal log so the scene is preserved exactly like real runs.
        try:
            os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
            with open(log_path, "w", encoding="utf-8") as fh:
                fh.write("[mock] cmd=%s\n" % " ".join(cmd))
        except OSError:
            pass
        return ProcessResult(returncode=self.returncode, timed_out=self.timed_out,
                             pid=self.pid)


# ---------------------------------------------------------------------------
# GPU lock (file-based, P33U-tagged)
# ---------------------------------------------------------------------------
def acquire_gpu_lock(gpu_device: str | None) -> str:
    """Create the P33U GPU lock file. Real arbitration happens at Lane D; this
    is a contract placeholder that records the device. Returns lock path."""
    os.makedirs(os.path.dirname(GPU_LOCK_PATH) or "/", exist_ok=True)
    payload = {"gpu_device": gpu_device, "acquired_at": time.time()}
    Path(GPU_LOCK_PATH).write_text(json.dumps(payload), encoding="utf-8")
    return GPU_LOCK_PATH


def release_gpu_lock() -> None:
    try:
        os.remove(GPU_LOCK_PATH)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# execute_run — shared engine
# ---------------------------------------------------------------------------
def execute_run(
    *,
    contract: Any,
    run_id: str,
    input_dir: str,
    output_dir: str,
    manifest_sha: str,
    authorized_manifest_sha: str,
    state: P33UState,
    process_transport: ProcessTransport | None = None,
    gpu_device: str | None = None,
    timeout_seconds: int | None = None,
    extra_env: dict[str, str] | None = None,
    mock_artifacts: dict[str, bytes] | None = None,
) -> ExecutionOutcome:
    """Run one model exactly once under the P33U gate.

    Parameters
    ----------
    contract : RunnerContract
        Provides model_id, validate_input, command_preview, expected_artifacts,
        and a parse_output hook (added in output_parsers).
    process_transport : ProcessTransport | None
        If None, RealSubprocessTransport is used (refuses under block env).
        Tests inject MockProcessRunner.
    mock_artifacts : dict[path_fragment -> bytes] | None
        Test-only: files to materialize in output_dir to simulate a model's
        non-empty output (for parser tests). Real runs ignore this.

    Refuses (ExecutionRefused) when:
        - authorized_manifest_sha empty / != manifest_sha
        - model already attempted (retry_count would exceed 0)
        - validate_input fails
    Refuses (ExecutionBlocked) when real transport + block env set.
    On timeout / non-zero exit / empty artifacts: closes gate FAILED/TIMEOUT,
    records failed attempt, preserves scene, returns FAILED outcome.
    """
    model_id = contract.model_id
    m = contract.meta
    timeout = int(timeout_seconds or m.get("timeout_seconds", 3600))

    # --- 1. manifest SHA authorization ---
    if not authorized_manifest_sha:
        raise ExecutionRefused("authorized_manifest_sha is empty")
    if manifest_sha != authorized_manifest_sha:
        raise ExecutionRefused(
            f"manifest SHA mismatch: gate={manifest_sha!r} "
            f"authorized={authorized_manifest_sha!r}"
        )

    # --- 2. retry guard (retry_count = 0) ---
    if state.attempt_count(model_id) > 0:
        raise ExecutionRefused(
            f"retry forbidden: model {model_id!r} already attempted under P33U "
            f"(retry_count=0 policy)"
        )

    # --- 3. input precheck ---
    v = contract.validate_input(input_dir)
    if not v.valid:
        raise ExecutionRefused(
            f"input precheck failed for {model_id!r}: {v.errors}"
        )

    os.makedirs(output_dir, exist_ok=True)
    log_path = os.path.join(output_dir, "runner.log")

    transport: ProcessTransport = process_transport or RealSubprocessTransport()

    # --- 4. open gate (manifest-SHA-bound) ---
    gate_mod.open_gate(
        model_id=model_id, run_id=run_id, manifest_sha=manifest_sha,
        ttl_seconds=timeout + 300, gpu_device=gpu_device, log_path=log_path,
    )

    pid: int | None = None
    try:
        # --- 5. build command (list argv, no shell) ---
        cmd_groups = contract.command_preview(run_id, input_dir, output_dir,
                                              gpu=gpu_device) if model_id == "pephar" \
            else contract.command_preview(run_id, input_dir, output_dir)
        # Each contract returns a list of step groups; P33U executes them in
        # sequence within one gate. A multi-step contract fails on the first
        # non-zero step.
        env = dict(os.environ)
        if extra_env:
            env.update(extra_env)
        if gpu_device is not None:
            env["CUDA_VISIBLE_DEVICES"] = gpu_device

        final_rc = 0
        for step_idx, step_cmd in enumerate(cmd_groups):
            cwd = contract.runner_cwd(step_idx)
            result = transport.run(step_cmd, cwd=cwd, env=env,
                                   timeout=timeout, log_path=log_path)
            if result.pid is not None:
                pid = result.pid
                gate_mod.update_pid(model_id, run_id, pid)
            if result.timed_out:
                gate_mod.close_gate(model_id, run_id, gate_mod.TIMEOUT,
                                    exit_code=None,
                                    note=f"timeout at step {step_idx}")
                state.record_attempt(model_id, run_id, "failed")
                release_gpu_lock()
                return ExecutionOutcome(run_id, model_id, gate_mod.TIMEOUT, None, pid,
                                        str(gate_mod._gate_path(model_id, run_id)),
                                        log_path, note=f"timeout step {step_idx}")
            if result.returncode != 0:
                gate_mod.close_gate(model_id, run_id, gate_mod.FAILED,
                                    exit_code=result.returncode,
                                    note=f"non-zero exit at step {step_idx}")
                state.record_attempt(model_id, run_id, "failed")
                release_gpu_lock()
                return ExecutionOutcome(run_id, model_id, gate_mod.FAILED,
                                        result.returncode, pid,
                                        str(gate_mod._gate_path(model_id, run_id)),
                                        log_path, note=f"non-zero step {step_idx}")
            final_rc = result.returncode

        # --- 6. optional mock artifacts (test path only) ---
        if mock_artifacts:
            for frag, data in mock_artifacts.items():
                p = os.path.join(output_dir, frag)
                os.makedirs(os.path.dirname(p) or output_dir, exist_ok=True)
                with open(p, "wb") as fh:
                    fh.write(data)

        # --- 7. output parsing + empty-artifact guard ---
        parsed = contract.parse_output(output_dir)  # type: ignore[attr-defined]
        expected = contract.expected_artifacts(output_dir)
        if parsed.get("empty", True):
            gate_mod.close_gate(model_id, run_id, gate_mod.FAILED,
                                exit_code=final_rc,
                                note="empty or missing artifacts")
            state.record_attempt(model_id, run_id, "failed")
            release_gpu_lock()
            return ExecutionOutcome(run_id, model_id, gate_mod.FAILED, final_rc, pid,
                                    str(gate_mod._gate_path(model_id, run_id)),
                                    log_path, artifacts=expected, parsed=parsed,
                                    note="empty artifacts")

        # --- 8. success ---
        prov = _write_provenance(output_dir, contract, run_id, manifest_sha,
                                 pid, final_rc, gpu_device, parsed)
        gate_mod.close_gate(model_id, run_id, gate_mod.CLOSED, exit_code=0,
                            note="ok")
        state.record_attempt(model_id, run_id, "succeeded")
        release_gpu_lock()
        return ExecutionOutcome(run_id, model_id, gate_mod.CLOSED, 0, pid,
                                str(gate_mod._gate_path(model_id, run_id)),
                                log_path, artifacts=expected, parsed=parsed,
                                provenance=prov)

    except KeyboardInterrupt:
        gate_mod.close_gate(model_id, run_id, gate_mod.FAILED, exit_code=None,
                            note="interrupted by KeyboardInterrupt; scene preserved")
        try:
            state.record_attempt(model_id, run_id, "failed")
        except Exception:
            pass
        release_gpu_lock()
        raise
    except ExecutionBlocked:
        # Real spawn refused under block env. Close gate FAILED, preserve scene.
        gate_mod.close_gate(model_id, run_id, gate_mod.FAILED, exit_code=None,
                            note="execution blocked by P33U_BLOCK_ALL_EXECUTION")
        try:
            state.record_attempt(model_id, run_id, "failed")
        except Exception:
            pass
        release_gpu_lock()
        raise
    except Exception as exc:
        gate_mod.close_gate(model_id, run_id, gate_mod.FAILED, exit_code=None,
                            note=f"exception: {type(exc).__name__}: {exc}")
        try:
            state.record_attempt(model_id, run_id, "failed")
        except Exception:
            pass
        release_gpu_lock()
        raise


def _write_provenance(output_dir: str, contract: Any, run_id: str,
                      manifest_sha: str, pid: int | None, exit_code: int,
                      gpu_device: str | None, parsed: dict[str, Any]) -> dict[str, Any]:
    m = contract.meta
    prov = {
        "run_id": run_id,
        "model_id": contract.model_id,
        "manifest_sha": manifest_sha,
        "source": m.get("source"),
        "checkpoint": m.get("checkpoint") or m.get("density_checkpoint"),
        "checkpoint_sha256": m.get("checkpoint_sha256") or m.get("density_checkpoint_sha256"),
        "env_python": m.get("env_python"),
        "gpu_device": gpu_device,
        "pid": pid,
        "exit_code": exit_code,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "validation_status": VALIDATION_STATUS,
        "prediction_tag": "COMPUTATIONAL_PREDICTION_ONLY",
        "parsed_summary": {k: (len(v) if isinstance(v, list) else v)
                           for k, v in parsed.items()},
    }
    p = os.path.join(output_dir, "provenance.json")
    try:
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(prov, fh, indent=2, sort_keys=True)
    except OSError:
        pass
    return prov
