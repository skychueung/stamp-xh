"""Uniform manifest writer for P33L real runs.

Every run directory receives:
  - manifest/run_manifest.json
  - manifest/sha256_manifest.txt

The manifest includes full provenance, execution metadata, resource summary,
and the required NOT_EXPERIMENTALLY_VALIDATED disclaimer.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from .config import get_model_config
from .security import safe_relative_path


def write_manifest(
    run_dir: str,
    job: Any,
    result: Dict[str, Any],
    input_provenance: Dict[str, Any],
) -> None:
    """Write run_manifest.json and sha256_manifest.txt for a P33L job."""
    run_path = Path(run_dir)
    manifest_dir = run_path / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)

    cfg = get_model_config(job.model_id)

    manifest: Dict[str, Any] = {
        "task_id": "P33L",
        "job_id": job.job_id,
        "model_id": job.model_id,
        "model_display_name": cfg.display_name,
        "attempt_number": job.attempt_number,
        "manifest_sha": job.manifest_sha,
        "disclaimer": "NOT_EXPERIMENTALLY_VALIDATED",
        "computational_prediction_only": True,
        "experimental_validation": False,
        "input": input_provenance,
        "command": result.get("command", []),
        "environment": {
            "python": cfg.env_python,
            "conda_env": "",
            "cuda_visible_devices": os.environ.get("CUDA_VISIBLE_DEVICES", "auto"),
        },
        "provenance": {
            "source_path": cfg.source_path,
            "source_sha256": cfg.source_sha256,
            "runner_script_path": cfg.runner_script_path,
            "runner_script_sha256": cfg.runner_script_sha256,
            "checkpoint_path": cfg.checkpoint_path,
            "checkpoint_sha256": cfg.checkpoint_sha256,
            "fixture_path": cfg.fixture_path,
            "fixture_sha256": cfg.fixture_sha256,
        },
        "execution": {
            "status": result.get("status", "UNKNOWN"),
            "exit_code": result.get("exit_code"),
            "started_at": result.get("started_at") or job.started_at,
            "finished_at": result.get("finished_at") or job.finished_at or _now_iso(),
            "timeout_seconds": cfg.timeout_seconds,
            "disk_quota_bytes": cfg.disk_quota_bytes,
            "disk_used_bytes": result.get("disk_used_bytes", 0),
            "file_count": result.get("file_count", 0),
            "max_output_files": cfg.max_output_files,
        },
        "result": result,
        "artifact_download_base": f"/api/v1/p33l/jobs/{job.job_id}/download/",
    }

    run_manifest_path = manifest_dir / "run_manifest.json"
    tmp = run_manifest_path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, run_manifest_path)
    os.chmod(run_manifest_path, 0o644)

    sha_lines = []
    for f in sorted(run_path.rglob("*")):
        if not f.is_file():
            continue
        try:
            rel = f.relative_to(run_path).as_posix()
            h = hashlib.sha256(f.read_bytes()).hexdigest()
            sha_lines.append(f"{h}  {rel}")
        except (OSError, ValueError):
            continue
    sha_path = manifest_dir / "sha256_manifest.txt"
    with open(sha_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(sha_lines) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    os.chmod(sha_path, 0o644)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_run_manifest(run_dir: str) -> Dict[str, Any]:
    """Read the run_manifest.json from a run directory."""
    path = Path(run_dir) / "manifest" / "run_manifest.json"
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)
