"""Durable five-model execution service.

This module is deliberately model-agnostic.  Every production model is
launched through the same job state machine, structured JSONL logger, isolated
artifact tree and result normalizer.  Model-specific launchers are configured
as JSON argv arrays through ``STAMP_<MODEL>_RUNNER_COMMAND``; placeholders are
expanded without invoking a shell.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.orm import Session

from app.crud.jobs import create_job
from app.models.orm import Job
from app.schemas import JobCreate
from app.services.gpu_lock_service import acquire_gpu_lock, release_gpu_lock
from app.services.production_model_registry import MODEL_IDS, production_registry


MODEL_JOB_PREFIX = "model_generate:"
TERMINAL_STATES = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
AA = set("ACDEFGHIKLMNPQRSTVWY")
_SECRET = re.compile(
    r"(?i)(authorization|token|password|passwd|secret|cookie|api[_-]?key)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso() -> str:
    return utc_now().isoformat()


def _runtime_root() -> Path:
    return Path(
        os.environ.get(
            "STAMP_MODEL_RUNTIME_ROOT",
            str(Path(__file__).resolve().parents[2] / "data" / "model_runtime"),
        )
    ).expanduser().resolve()


def redact(value: Any) -> Any:
    """Recursively redact credential-shaped values before persistence."""
    if isinstance(value, dict):
        return {
            key: ("[REDACTED]" if re.search(
                r"(?i)token|password|passwd|secret|cookie|authorization|api[_-]?key", key
            ) else redact(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _SECRET.sub(r"\1\2[REDACTED]", value)
    return value


def job_paths(run_id: str, model_id: str, job_id: str) -> dict[str, Path]:
    root = _runtime_root()
    parts = (run_id, model_id, job_id)
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", p) for p in parts):
        raise ValueError("run_id, model_id and job_id must be filesystem-safe")
    base = (root / "artifacts" / run_id / model_id / job_id).resolve()
    base.relative_to(root)
    return {
        "root": root,
        "artifact_dir": base,
        "input_dir": base / "input",
        "output_dir": base / "output",
        "manifest_dir": base / "manifest",
        "tmp_dir": root / "tmp" / run_id / model_id / job_id,
        "log_path": root / "logs" / run_id / model_id / f"{job_id}.jsonl",
        "stdout_path": base / "logs" / "runner.log",
        "result_path": base / "output" / "result.json",
        "cancel_path": base / ".cancel",
        "busy_path": root / "busy" / f"{model_id}.busy",
        "lock_path": root / "locks" / "gpu.lock",
    }


def append_log(
    job: Job,
    event: str,
    message: str,
    *,
    level: str = "INFO",
    step: str = "RUNTIME",
    progress: int | None = None,
    duration_ms: int = 0,
) -> dict[str, Any]:
    meta = job.input_json or {}
    model_id = str(meta.get("model_id", "unknown"))
    run_id = str(meta.get("run_id", job.id))
    paths = job_paths(run_id, model_id, job.id)
    paths["log_path"].parent.mkdir(parents=True, exist_ok=True)
    record = redact({
        "timestamp": _iso(),
        "level": level,
        "service": "model-worker",
        "run_id": run_id,
        "job_id": job.id,
        "model_id": model_id,
        "step": step,
        "event": event,
        "message": message,
        "progress": int(job.progress or 0) if progress is None else progress,
        "pid": os.getpid(),
        "duration_ms": duration_ms,
    })
    with paths["log_path"].open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record


def _transition(
    db: Session,
    job: Job,
    state: str,
    *,
    progress: int,
    message: str,
    event: str | None = None,
) -> None:
    state = state.upper()
    job.status = state
    job.progress = progress
    job.message = message
    if state == "RUNNING" and job.started_at is None:
        job.started_at = utc_now()
    if state in TERMINAL_STATES:
        job.finished_at = utc_now()
    db.commit()
    append_log(job, event or f"STATE_{state}", message, progress=progress)


def submit_model_job(
    db: Session,
    model_id: str,
    payload: dict[str, Any],
    *,
    project_id: str = "production_models",
    run_id: str | None = None,
) -> Job:
    model_id = model_id.lower()
    if model_id not in MODEL_IDS:
        raise ValueError(f"Unknown production model: {model_id}")
    errors = production_registry.get(model_id).validate_input(payload)
    if errors:
        raise ValueError("; ".join(errors))
    run_id = run_id or f"models_{uuid.uuid4().hex[:16]}"
    clean_payload = redact(payload)
    job = create_job(db, JobCreate(
        project_id=project_id,
        job_type=f"{MODEL_JOB_PREFIX}{model_id}",
        input_json={"model_id": model_id, "run_id": run_id, "payload": clean_payload},
    ))
    job.status = "CREATED"
    db.commit()
    append_log(job, "REQUEST_RECEIVED", "Model generation request received", progress=0)
    _transition(db, job, "QUEUED", progress=1, message="Model job queued")
    return job


def _command_for(model_id: str, paths: dict[str, Path], payload: dict[str, Any]) -> list[str]:
    env_name = f"STAMP_{model_id.upper()}_RUNNER_COMMAND"
    raw = os.environ.get(env_name, "")
    if not raw:
        scripts = Path(__file__).resolve().parents[2] / "scripts"
        if model_id == "pepmlm":
            argv = [
                str(_resolve_runtime_path("STAMP_PEPMLM_PYTHON", "/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python")),
                str(_resolve_runtime_path("STAMP_PEPMLM_SCRIPT", "/home/xh/kxc/stampup/models_dev/pepmlm/scripts/pepmlm_infer.py")),
                "--model_path", str(_resolve_runtime_path("STAMP_PEPMLM_MODEL_DIR", "/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M")),
                "--target_sequence", "{target_sequence}", "--peptide_length", "{peptide_length}",
                "--num_candidates", "{num_candidates}", "--top_k", "3", "--device", "{device}",
                "--output_dir", "{output_dir}", "--seed", "{seed}",
            ]
        elif model_id == "pepprclip":
            argv = [
                str(_resolve_runtime_path(
                    "STAMP_PEPPRCLIP_PYTHON",
                    "/home/xh/kxc/stampup/models_dev/pepprclip/envs/pepprclip/bin/python",
                )),
                str(scripts / "unified_pepprclip_runner.py"),
                "--input-json", "{input_json}",
                "--output-dir", "{output_dir}",
                "--result-json", "{result_json}",
                "--checkpoint", str(_resolve_runtime_path(
                    "STAMP_PEPPRCLIP_CHECKPOINT",
                    "/home/xh/kxc/stampup/models_dev/pepprclip/weights/canonical_miniclip_4-22-23.ckpt",
                )),
                "--candidate-library", str(_resolve_runtime_path(
                    "STAMP_PEPPRCLIP_CANDIDATES",
                    "/home/xh/kxc/stampup/models_dev/pepprclip/candidate_peptides_lengths_5_to_30_25Keach.pkl",
                )),
            ]
        elif model_id in {"evobind2", "pephar", "pepflow"}:
            argv = [sys.executable, str(scripts / f"unified_{model_id}_runner.py"),
                    "--input-json", "{input_json}", "--output-dir", "{output_dir}",
                    "--result-json", "{result_json}"]
        else:
            raise RuntimeError(f"RUNNER_COMMAND_MISSING: set {env_name} to a JSON argv array")
    else:
        try:
            argv = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"RUNNER_COMMAND_INVALID_JSON: {env_name}: {exc}") from exc
    if not isinstance(argv, list) or not argv or not all(isinstance(v, str) for v in argv):
        raise RuntimeError(f"RUNNER_COMMAND_INVALID: {env_name} must be a non-empty JSON string array")
    values = {
        "model_id": model_id,
        "input_json": str(paths["input_dir"] / "request.json"),
        "input_dir": str(paths["input_dir"]),
        "output_dir": str(paths["output_dir"]),
        "result_json": str(paths["result_path"]),
        "artifact_dir": str(paths["artifact_dir"]),
        "tmp_dir": str(paths["tmp_dir"]),
        "target_sequence": str(payload.get("target_sequence", "")),
        "receptor_pdb": str(payload.get("receptor_pdb") or payload.get("target_pdb_path") or ""),
        "peptide_length": str(payload.get("peptide_length", 12)),
        "num_candidates": str(payload.get("num_candidates", 5)),
        "seed": str(payload.get("seed", 42)),
        "device": str(payload.get("device", "cuda")),
    }
    return [part.format_map(values) for part in argv]


def _resolve_runtime_path(env_name: str, default: str) -> Path:
    return Path(os.environ.get(env_name, default)).expanduser().resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _candidate(sequence: str, rank: int, model_id: str, **extra: Any) -> dict[str, Any] | None:
    sequence = sequence.strip().upper()
    if not sequence or set(sequence) - AA:
        return None
    return {
        "candidate_id": str(extra.pop("candidate_id", f"{model_id}_{rank:04d}")),
        "sequence": sequence,
        "length": len(sequence),
        "rank": rank,
        "score": extra.pop("score", None),
        "structure_path": extra.pop("structure_path", None),
        "source_model": model_id,
        **extra,
    }


def _load_candidates(result_path: Path, output_dir: Path, model_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw: dict[str, Any] = {}
    rows: list[Any] = []
    if result_path.is_file():
        parsed = json.loads(result_path.read_text(encoding="utf-8"))
        raw = parsed if isinstance(parsed, dict) else {"candidates": parsed}
        rows = raw.get("candidates", [])
    if not rows:
        for name in ("candidates.json", "candidate_sequences.json", "scores.json"):
            path = output_dir / name
            if path.is_file():
                parsed = json.loads(path.read_text(encoding="utf-8"))
                rows = parsed.get("candidates", parsed) if isinstance(parsed, dict) else parsed
                raw = parsed if isinstance(parsed, dict) else {}
                break
    if not rows:
        for name in ("candidates.csv", "candidate_sequences.csv", "ranking.csv", "outputs.csv", "metrics.csv", "test.csv"):
            path = output_dir / name
            if path.is_file():
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    rows = list(csv.DictReader(handle))
                break
    candidates: list[dict[str, Any]] = []
    for idx, item in enumerate(rows if isinstance(rows, list) else [], 1):
        if isinstance(item, str):
            normalized = _candidate(item, idx, model_id)
        elif isinstance(item, dict):
            sequence = next((str(item[k]) for k in ("sequence", "peptide", "candidate", "seq") if item.get(k)), "")
            score = next((item[k] for k in ("score", "ranking_score", "confidence") if item.get(k) is not None), None)
            normalized = _candidate(sequence, int(item.get("rank", idx)), model_id, score=score,
                                    structure_path=item.get("structure_path") or item.get("pdb_path"))
        else:
            normalized = None
        if normalized:
            candidates.append(normalized)
    return candidates, raw


def _artifact_manifest(paths: dict[str, Path]) -> list[dict[str, Any]]:
    root = paths["artifact_dir"]
    items = []
    for path in sorted(root.rglob("*")) if root.exists() else []:
        if path.is_file() and not path.is_symlink():
            items.append({
                "name": path.name,
                "path": str(path.relative_to(root)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": _sha256(path),
            })
    return items


def process_model_job(db: Session, job: Job) -> Job:
    meta = job.input_json or {}
    model_id = str(meta.get("model_id", ""))
    run_id = str(meta.get("run_id", job.id))
    payload = dict(meta.get("payload") or {})
    paths = job_paths(run_id, model_id, job.id)
    for key in ("input_dir", "output_dir", "manifest_dir", "tmp_dir"):
        paths[key].mkdir(parents=True, exist_ok=True)
    paths["stdout_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["busy_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["lock_path"].parent.mkdir(parents=True, exist_ok=True)
    (paths["input_dir"] / "request.json").write_text(
        json.dumps(redact(payload), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    started = time.monotonic()
    acquired = False
    proc: subprocess.Popen[str] | None = None
    try:
        _transition(db, job, "PREFLIGHT", progress=5, message="Runtime preflight started")
        probe = production_registry.get(model_id).probe()
        append_log(job, "RUNTIME_PROBED", f"Runtime probe state={probe['state']}", progress=8)
        command = _command_for(model_id, paths, payload)
        if paths["cancel_path"].exists() or job.status == "CANCELLED":
            _transition(db, job, "CANCELLED", progress=int(job.progress or 0), message="Cancelled before execution")
            return job
        acquired = acquire_gpu_lock(job.id, paths["lock_path"], timeout_seconds=float(os.environ.get("STAMP_GPU_LOCK_TTL_SECONDS", "14400")))
        if not acquired:
            _transition(db, job, "QUEUED", progress=5, message="Waiting for GPU lock", event="GPU_LOCK_BUSY")
            return job
        append_log(job, "GPU_LOCK_ACQUIRED", "GPU execution lock acquired", progress=10)
        paths["busy_path"].write_text(json.dumps({"job_id": job.id, "pid": os.getpid(), "created_at": _iso()}), encoding="utf-8")
        _transition(db, job, "RUNNING", progress=15, message="Model process started")
        env = dict(os.environ)
        env.update({
            "STAMP_RUN_ID": run_id,
            "STAMP_JOB_ID": job.id,
            "STAMP_MODEL_ID": model_id,
            "STAMP_OUTPUT_DIR": str(paths["output_dir"]),
            "STAMP_RESULT_JSON": str(paths["result_path"]),
            "PYTHONUNBUFFERED": "1",
        })
        timeout = int(os.environ.get(f"STAMP_{model_id.upper()}_TIMEOUT_SECONDS", "14400"))
        with paths["stdout_path"].open("w", encoding="utf-8") as log_handle:
            proc = subprocess.Popen(command, cwd=str(paths["tmp_dir"]), env=env,
                                    stdout=log_handle, stderr=subprocess.STDOUT,
                                    text=True, shell=False, start_new_session=True)
            job.output_json = {"pid": proc.pid, "run_id": run_id, "model_id": model_id}
            db.commit()
            append_log(job, "INFERENCE_STARTED", f"Model process pid={proc.pid}", progress=20)
            deadline = time.monotonic() + timeout
            while proc.poll() is None:
                db.refresh(job)
                if paths["cancel_path"].exists() or job.status == "CANCELLED":
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL)
                        proc.wait(timeout=10)
                    _transition(db, job, "CANCELLED", progress=int(job.progress or 20), message="Model process cancelled")
                    return job
                if time.monotonic() >= deadline:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=10)
                    _transition(db, job, "TIMED_OUT", progress=int(job.progress or 20), message=f"Model exceeded {timeout}s")
                    return job
                time.sleep(1)
        if proc.returncode != 0:
            raise RuntimeError(f"MODEL_PROCESS_NONZERO_EXIT: {proc.returncode}")
        _transition(db, job, "POSTPROCESSING", progress=90, message="Normalizing model output")
        candidates, raw = _load_candidates(paths["result_path"], paths["output_dir"], model_id)
        if not candidates:
            raise RuntimeError("EMPTY_MODEL_OUTPUT: no valid peptide candidates found")
        artifacts = _artifact_manifest(paths)
        checkpoint_sha = production_registry.get(model_id).probe().get("checkpoint_sha256")
        finished = utc_now()
        normalized = {
            "run_id": run_id,
            "job_id": job.id,
            "model_id": model_id,
            "model_version": production_registry.get(model_id).spec.version,
            "status": "SUCCEEDED",
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "finished_at": finished.isoformat(),
            "duration_seconds": round(time.monotonic() - started, 3),
            "device": payload.get("device", "cuda"),
            "checkpoint_sha256": checkpoint_sha,
            "input_sha256": _sha256(paths["input_dir"] / "request.json"),
            "candidates": candidates,
            "artifacts": artifacts,
            "metrics": raw.get("metrics", {}) if isinstance(raw, dict) else {},
            "warnings": raw.get("warnings", []) if isinstance(raw, dict) else [],
            "error": None,
            "provenance": "real_model",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        }
        paths["result_path"].write_text(json.dumps(normalized, indent=2, ensure_ascii=False), encoding="utf-8")
        job.output_json = normalized
        job.artifacts_json = {item["path"]: item for item in _artifact_manifest(paths)}
        _transition(db, job, "SUCCEEDED", progress=100, message=f"Generated {len(candidates)} candidates")
    except Exception as exc:  # noqa: BLE001
        job.error_message = str(exc)
        job.error_json = {"error_code": str(exc).split(":", 1)[0], "message": redact(str(exc))}
        append_log(job, "MODEL_FAILED", f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}", level="ERROR")
        _transition(db, job, "FAILED", progress=int(job.progress or 0), message=str(exc))
    finally:
        paths["busy_path"].unlink(missing_ok=True)
        if acquired:
            release_gpu_lock(job.id, paths["lock_path"])
            append_log(job, "GPU_LOCK_RELEASED", "GPU execution lock released")
        db.refresh(job)
    return job


def cancel_model_job(db: Session, job: Job) -> Job:
    meta = job.input_json or {}
    paths = job_paths(str(meta.get("run_id", job.id)), str(meta.get("model_id", "unknown")), job.id)
    paths["cancel_path"].parent.mkdir(parents=True, exist_ok=True)
    paths["cancel_path"].write_text(_iso(), encoding="utf-8")
    if job.status in {"CREATED", "QUEUED", "PREFLIGHT"}:
        _transition(db, job, "CANCELLED", progress=int(job.progress or 0), message="Job cancelled")
    else:
        append_log(job, "CANCEL_REQUESTED", "Cancellation requested")
    return job


def read_job_logs(
    job: Job, *, after_id: int = 0, limit: int = 200,
    level: str | None = None, model_id: str | None = None,
) -> list[dict[str, Any]]:
    meta = job.input_json or {}
    paths = job_paths(str(meta.get("run_id", job.id)), str(meta.get("model_id", "unknown")), job.id)
    if not paths["log_path"].is_file():
        return []
    records = []
    with paths["log_path"].open(encoding="utf-8") as handle:
        for line_id, line in enumerate(handle, 1):
            if line_id <= after_id:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if level and record.get("level") != level.upper():
                continue
            if model_id and record.get("model_id") != model_id:
                continue
            record["id"] = line_id
            records.append(record)
            if len(records) >= limit:
                break
    return records


def list_job_artifacts(job: Job) -> list[dict[str, Any]]:
    meta = job.input_json or {}
    paths = job_paths(str(meta.get("run_id", job.id)), str(meta.get("model_id", "unknown")), job.id)
    return _artifact_manifest(paths)


def resolve_job_artifact(job: Job, artifact_path: str) -> Path:
    """Resolve a manifest-relative artifact path with strict containment."""
    meta = job.input_json or {}
    paths = job_paths(str(meta.get("run_id", job.id)), str(meta.get("model_id", "unknown")), job.id)
    relative = Path(artifact_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("INVALID_ARTIFACT_PATH")
    resolved = (paths["artifact_dir"] / relative).resolve()
    resolved.relative_to(paths["artifact_dir"])
    if not resolved.is_file() or resolved.is_symlink():
        raise FileNotFoundError(artifact_path)
    return resolved


def recover_interrupted_model_jobs(db: Session) -> list[str]:
    """Move jobs left active by a service restart into RECOVERING then QUEUED."""
    jobs = db.query(Job).filter(
        Job.job_type.like(f"{MODEL_JOB_PREFIX}%"),
        Job.status.in_(["PREFLIGHT", "RUNNING", "POSTPROCESSING", "RECOVERING"]),
    ).all()
    recovered = []
    for job in jobs:
        _transition(db, job, "RECOVERING", progress=int(job.progress or 0), message="Recovered after service restart")
        _transition(db, job, "QUEUED", progress=1, message="Recovered job queued for a fresh worker process")
        recovered.append(job.id)
    return recovered


def get_next_queued_model_job(db: Session) -> Job | None:
    # Conditional UPDATE is the cross-worker claim. ``SELECT ... FOR UPDATE``
    # is ignored by SQLite and can still double-run a GPU job.
    while True:
        candidate = db.query(Job.id).filter(
            Job.job_type.like(f"{MODEL_JOB_PREFIX}%"), Job.status == "QUEUED"
        ).order_by(Job.created_at.asc()).first()
        if candidate is None:
            return None
        claimed = db.query(Job).filter(Job.id == candidate[0], Job.status == "QUEUED").update(
            {Job.status: "PREFLIGHT", Job.message: "Worker claimed queued model job"},
            synchronize_session=False,
        )
        db.commit()
        if claimed == 1:
            job = db.query(Job).filter(Job.id == candidate[0]).one()
            append_log(job, "WORKER_CLAIMED", "Worker atomically claimed queued model job", progress=3)
            return job


def model_jobs_for_run(db: Session, run_id: str) -> Iterable[Job]:
    jobs = db.query(Job).filter(Job.job_type.like(f"{MODEL_JOB_PREFIX}%")).order_by(Job.created_at).all()
    return [job for job in jobs if (job.input_json or {}).get("run_id") == run_id]
