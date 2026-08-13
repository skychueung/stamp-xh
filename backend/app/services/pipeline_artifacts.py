"""Durable, path-safe artifact storage for pipeline runs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import settings


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def sequence_sha256(sequence: str) -> str:
    normalized = "".join(sequence.split()).upper()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def run_root(run_id: str, *, create: bool = True) -> Path:
    # UUIDs are generated internally, but this also protects callers that accept
    # a route parameter before a database lookup has happened.
    if not run_id or any(ch not in "0123456789abcdef-" for ch in run_id.lower()):
        raise ValueError("Invalid pipeline run id")
    parent = Path(settings.stamp_pipeline_artifact_root).expanduser().resolve()
    root = (parent / run_id).resolve()
    if root.parent != parent:
        raise ValueError("Invalid pipeline run path")
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_artifact(run_id: str, relative_path: str, *, must_exist: bool = True) -> Path:
    root = run_root(run_id, create=False)
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artifact path leaves the run directory") from exc
    if must_exist and not candidate.is_file():
        raise FileNotFoundError(relative_path)
    return candidate


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def initialize_run_artifacts(
    run_id: str,
    *,
    target_name: str,
    target_sequence: str,
    project_id: str | None,
    created_by: str | None,
) -> Path:
    root = run_root(run_id)
    (root / "steps").mkdir(exist_ok=True)
    (root / "artifacts").mkdir(exist_ok=True)
    request = {
        "run_id": run_id,
        "project_id": project_id,
        "target_name": target_name,
        "target_sequence": target_sequence,
        "input_hash": sequence_sha256(target_sequence),
        "created_by": created_by,
        "created_at": utc_iso(),
    }
    atomic_write_json(root / "request.json", request)
    atomic_write_json(
        root / "manifest.json",
        {
            "schema_version": 1,
            "run_id": run_id,
            "input_hash": request["input_hash"],
            "status": "PENDING",
            "created_at": request["created_at"],
            "updated_at": request["created_at"],
            "steps": {},
            "artifacts": [],
        },
    )
    (root / "logs.jsonl").touch(exist_ok=True)
    return root


def update_step_state(
    run_id: str,
    step_name: str,
    status: str,
    *,
    attempt: int,
    input_hash: str,
    error: str | None = None,
    artifacts: list[str] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    root = run_root(run_id)
    step_dir = root / "steps" / step_name.lower()
    state_path = step_dir / "status.json"
    previous: dict[str, Any] = {}
    if state_path.is_file():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    now = utc_iso()
    started_at = started_at or previous.get("started_at") or (now if status == "RUNNING" else None)
    finished_at = finished_at or (now if status in {"SUCCEEDED", "FAILED", "BLOCKED", "CANCELLED", "INTERRUPTED"} else None)
    state = {
        "step": step_name,
        "status": status,
        "attempt": attempt,
        "input_hash": input_hash,
        "started_at": started_at,
        "finished_at": finished_at,
        "updated_at": now,
        "error": error,
        "artifacts": artifacts or previous.get("artifacts", []),
    }
    atomic_write_json(state_path, state)

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["steps"][step_name] = state
    manifest["status"] = status if status in {"FAILED", "BLOCKED", "CANCELLED", "INTERRUPTED"} else "RUNNING"
    manifest["updated_at"] = now
    atomic_write_json(manifest_path, manifest)


def mark_manifest_status(run_id: str, status: str) -> None:
    path = run_root(run_id) / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest["updated_at"] = utc_iso()
    atomic_write_json(path, manifest)


def reset_step_state(run_id: str, step_name: str, *, attempt: int, input_hash: str) -> None:
    """Reset one step for retry without carrying old completion timestamps."""
    root = run_root(run_id)
    state = {
        "step": step_name,
        "status": "PENDING",
        "attempt": attempt,
        "input_hash": input_hash,
        "started_at": None,
        "finished_at": None,
        "updated_at": utc_iso(),
        "error": None,
        "artifacts": [],
    }
    atomic_write_json(root / "steps" / step_name.lower() / "status.json", state)
    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["steps"][step_name] = state
    manifest["updated_at"] = state["updated_at"]
    atomic_write_json(manifest_path, manifest)
