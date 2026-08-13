"""P33S gate — per-job JSON gate with precise PID cleanup.

Rules (per goal):
- One gate file per (task, model, job). No cross-task sharing.
- Gate is JSON: job_id, model_id, pid, started_at, ttl_seconds, state, gpu_device.
- States: OPEN (running), CLOSED (clean exit), CANCELLED, FAILED, STALE.
- Cleanup kills the exact recorded PID via os.kill(pid, SIGTERM) with a short
  grace window, then SIGKILL. NEVER pkill / NEVER kill by name pattern.
- Stale gates (past TTL) are marked STALE but NOT auto-killed; the owning job's
  PID is reaped only on explicit cancel().
"""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass
from pathlib import Path

GATE_ROOT = Path("/home/xh/kxc/stampup/run_gates/p33s")
DEFAULT_TTL = 3600


@dataclass
class GateState:
    job_id: str
    model_id: str
    stage: str
    pid: int | None
    started_at: str
    ttl_seconds: int
    state: str  # OPEN | CLOSED | CANCELLED | FAILED | STALE
    gpu_device: str | None = None
    ended_at: str = ""
    exit_code: int | None = None
    note: str = ""


def _gate_dir(task: str, model_id: str) -> Path:
    d = GATE_ROOT / task / model_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gate_path(task: str, model_id: str, job_id: str) -> Path:
    return _gate_dir(task, model_id) / f"{job_id}.gate.json"


def open_gate(
    task: str,
    model_id: str,
    job_id: str,
    stage: str,
    pid: int | None,
    ttl_seconds: int = DEFAULT_TTL,
    gpu_device: str | None = None,
) -> GateState:
    gs = GateState(
        job_id=job_id,
        model_id=model_id,
        stage=stage,
        pid=pid,
        started_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ttl_seconds=ttl_seconds,
        state="OPEN",
        gpu_device=gpu_device,
    )
    _write(task, model_id, gs)
    return gs


def close_gate(task: str, model_id: str, job_id: str, exit_code: int, note: str = "") -> GateState:
    gs = _read(task, model_id, job_id)
    if gs is None:
        gs = GateState(job_id, model_id, "unknown", None,
                       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), DEFAULT_TTL, "CLOSED")
    gs.state = "CLOSED" if exit_code == 0 else "FAILED"
    gs.exit_code = exit_code
    gs.ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gs.note = note
    _write(task, model_id, gs)
    return gs


def cancel_gate(task: str, model_id: str, job_id: str, grace_seconds: float = 5.0) -> GateState:
    """Cancel a job: SIGTERM the exact recorded PID, wait, SIGKILL if alive."""
    gs = _read(task, model_id, job_id)
    if gs is None:
        gs = GateState(job_id, model_id, "unknown", None,
                       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), DEFAULT_TTL, "CANCELLED",
                       note="gate not found at cancel time")
        _write(task, model_id, gs)
        return gs
    pid = gs.pid
    killed = False
    if pid and _pid_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            gs.note = f"permission denied signaling pid {pid}"
        # grace window
        deadline = time.time() + grace_seconds
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(0.2)
        if _pid_alive(pid):
            try:
                os.kill(pid, signal.SIGKILL)
                killed = True
            except ProcessLookupError:
                pass
            except PermissionError:
                gs.note = f"permission denied SIGKILL pid {pid}"
    gs.state = "CANCELLED"
    gs.ended_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    gs.note = gs.note or f"cancelled; pid={pid} killed={killed}"
    _write(task, model_id, gs)
    return gs


def mark_stale(task: str, model_id: str, job_id: str) -> GateState | None:
    """Mark a gate STALE if past TTL. Does NOT kill — only the owner cancels."""
    gs = _read(task, model_id, job_id)
    if gs is None or gs.state != "OPEN":
        return gs
    started = time.mktime(time.strptime(gs.started_at, "%Y-%m-%dT%H:%M:%SZ"))
    if time.time() - started > gs.ttl_seconds:
        gs.state = "STALE"
        _write(task, model_id, gs)
    return gs


def list_open_gates(task: str) -> list[GateState]:
    out: list[GateState] = []
    base = GATE_ROOT / task
    if not base.is_dir():
        return out
    for f in base.rglob("*.gate.json"):
        try:
            gs = GateState(**json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
        if gs.state == "OPEN":
            out.append(gs)
    return out


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write(task: str, model_id: str, gs: GateState) -> None:
    p = _gate_path(task, model_id, gs.job_id)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(gs), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def _read(task: str, model_id: str, job_id: str) -> GateState | None:
    p = _gate_path(task, model_id, job_id)
    if not p.is_file():
        return None
    try:
        return GateState(**json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return None
