"""P33U per-run execution gate with manifest-SHA binding.

Independent of P33L and P33S gates. Gate root:
    /home/xh/kxc/stampup/run_gates/p33u_lane_d/<model_id>/<run_id>.gate.json

A gate JSON binds EXACTLY:
    run_id, model_id, pid, manifest_sha, started_at, ttl_seconds,
    state, ended_at, exit_code, gpu_device, log_path, note

States: OPEN | CLOSED | FAILED | CANCELLED | TIMEOUT | STALE

On exception / timeout / interrupt: the gate is closed with FAILED or TIMEOUT
state and the failure scene (exit_code, note, log_path) is PRESERVED — the
gate file is NEVER silently deleted. Cleanup kills the exact recorded PID via
SIGTERM (grace) then SIGKILL, scoped to the recorded PID's process group.
NEVER pkill. NEVER kill by name pattern.

This module does NOT spawn processes and does NOT import subprocess. It only
manages gate JSON state. Process spawning lives in runner.py.
"""

from __future__ import annotations

import json
import os
import signal
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .config import GATE_ROOT

DEFAULT_TTL = 3600

# Gate states.
OPEN = "OPEN"
CLOSED = "CLOSED"        # clean exit, exit_code 0, artifacts verified
FAILED = "FAILED"        # non-zero exit, empty artifacts, or exception
CANCELLED = "CANCELLED"  # explicit cancel via cancel_gate
TIMEOUT = "TIMEOUT"      # exceeded ttl / subprocess timeout
STALE = "STALE"          # open past ttl, not yet reaped


@dataclass
class P33UGate:
    run_id: str
    model_id: str
    pid: int | None
    manifest_sha: str
    started_at: str
    ttl_seconds: int
    state: str
    gpu_device: str | None = None
    ended_at: str = ""
    exit_code: int | None = None
    log_path: str = ""
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _gate_dir(model_id: str) -> Path:
    d = Path(GATE_ROOT) / model_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _gate_path(model_id: str, run_id: str) -> Path:
    return _gate_dir(model_id) / f"{run_id}.gate.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def open_gate(
    model_id: str,
    run_id: str,
    manifest_sha: str,
    ttl_seconds: int = DEFAULT_TTL,
    gpu_device: str | None = None,
    log_path: str = "",
) -> P33UGate:
    """Open a gate bound to (run_id, model_id, manifest_sha). PID is set later
    via update_pid once the subprocess has spawned."""
    if not manifest_sha:
        raise ValueError("manifest_sha is required to open a P33U gate")
    gs = P33UGate(
        run_id=run_id,
        model_id=model_id,
        pid=None,
        manifest_sha=manifest_sha,
        started_at=_now(),
        ttl_seconds=ttl_seconds,
        state=OPEN,
        gpu_device=gpu_device,
        log_path=log_path,
    )
    _write(gs)
    return gs


def update_pid(model_id: str, run_id: str, pid: int) -> P33UGate:
    """Record the spawned subprocess PID so cleanup can target it exactly."""
    gs = _read(model_id, run_id)
    if gs is None:
        raise FileNotFoundError(f"gate not found: {model_id}/{run_id}")
    gs.pid = pid
    _write(gs)
    return gs


def close_gate(
    model_id: str,
    run_id: str,
    state: str,
    exit_code: int | None = None,
    note: str = "",
) -> P33UGate:
    """Close a gate with the given terminal state. Preserves the failure scene
    (exit_code, note, log_path) — never deletes the gate file."""
    gs = _read(model_id, run_id)
    if gs is None:
        # Gate missing at close time: synthesize a minimal CLOSED/FAILED record
        # so the failure is still auditable rather than silently lost.
        gs = P33UGate(
            run_id=run_id, model_id=model_id, pid=None, manifest_sha="",
            started_at=_now(), ttl_seconds=DEFAULT_TTL, state=state,
            exit_code=exit_code, ended_at=_now(), note=f"gate missing at close; {note}",
        )
        _write(gs)
        return gs
    gs.state = state
    gs.exit_code = exit_code
    gs.ended_at = _now()
    if note:
        gs.note = note if not gs.note else f"{gs.note}; {note}"
    _write(gs)
    return gs


def cancel_gate(model_id: str, run_id: str, grace_seconds: float = 5.0) -> P33UGate:
    """Cancel a run: SIGTERM the exact recorded PID's process group, wait the
    grace window, SIGKILL if still alive. Then mark CANCELLED. Preserves scene."""
    gs = _read(model_id, run_id)
    if gs is None:
        gs = P33UGate(run_id=run_id, model_id=model_id, pid=None, manifest_sha="",
                      started_at=_now(), ttl_seconds=DEFAULT_TTL, state=CANCELLED,
                      ended_at=_now(), note="gate not found at cancel time")
        _write(gs)
        return gs
    killed = False
    pid = gs.pid
    if pid and _pid_alive(pid):
        try:
            # Scope to the PID's process group so child model processes die too,
            # but never broaden to a name-based pkill.
            pgid = os.getpgid(pid)
            os.killpg(pgid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
        deadline = time.time() + grace_seconds
        while time.time() < deadline and _pid_alive(pid):
            time.sleep(0.2)
        if _pid_alive(pid):
            try:
                pgid = os.getpgid(pid)
                os.killpg(pgid, signal.SIGKILL)
                killed = True
            except (ProcessLookupError, PermissionError):
                pass
    gs.state = CANCELLED
    gs.ended_at = _now()
    gs.note = gs.note or f"cancelled; pid={pid} killed={killed}"
    _write(gs)
    return gs


def mark_stale(model_id: str, run_id: str) -> P33UGate | None:
    """Mark a gate STALE if open past its TTL. Does NOT kill — only the owner
    cancels. Returns the updated gate or None."""
    gs = _read(model_id, run_id)
    if gs is None or gs.state != OPEN:
        return gs
    try:
        started = time.mktime(time.strptime(gs.started_at, "%Y-%m-%dT%H:%M:%SZ"))
    except ValueError:
        return gs
    if time.time() - started > gs.ttl_seconds:
        gs.state = STALE
        _write(gs)
    return gs


def list_open_gates() -> list[P33UGate]:
    out: list[P33UGate] = []
    base = Path(GATE_ROOT)
    if not base.is_dir():
        return out
    for f in base.rglob("*.gate.json"):
        try:
            gs = P33UGate(**json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
        if gs.state == OPEN:
            out.append(gs)
    return out


def read_gate(model_id: str, run_id: str) -> P33UGate | None:
    return _read(model_id, run_id)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write(gs: P33UGate) -> None:
    p = _gate_path(gs.model_id, gs.run_id)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(gs.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, p)


def _read(model_id: str, run_id: str) -> P33UGate | None:
    p = _gate_path(model_id, run_id)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        # Tolerate extra fields added by future versions.
        known = {f for f in P33UGate.__dataclass_fields__}
        clean = {k: v for k, v in data.items() if k in known}
        return P33UGate(**clean)
    except Exception:
        return None
