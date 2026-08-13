"""P33S provenance manifest writer.

Each real or dry-run job produces a JSON manifest capturing full provenance:
- manifest_sha256 (self-hash of the canonical JSON, excluding the sha field)
- input_sha256, weight_sha256, code_sha256
- env (conda/pip env path + python version)
- seed, gpu_device, gpu_free_mib_at_start
- started_at, ended_at, elapsed_seconds, exit_code
- model_id, job_id, stage (generation/structure/affinity/mic/mmgbsa/delivery)
- validation_status = NOT_EXPERIMENTALLY_VALIDATED always

No network, no model execution here — pure record-keeping.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
PREDICTION_TAG = "COMPUTATIONAL_PREDICTION_ONLY"

MANIFEST_VERSION = "p33s-v1"


@dataclass
class ProvenanceManifest:
    model_id: str
    job_id: str
    stage: str  # generation | structure | affinity | mic | mmgbsa | delivery
    mode: str  # probe | dry_run | real_run
    input_sha256: str
    weight_sha256: str
    code_sha256: str
    env: str
    seed: int | None
    gpu_device: str | None
    gpu_free_mib_at_start: int | None
    started_at: str
    ended_at: str = ""
    elapsed_seconds: float = 0.0
    exit_code: int | None = None
    validation_status: str = VALIDATION_STATUS
    prediction_tag: str = PREDICTION_TAG
    manifest_version: str = MANIFEST_VERSION
    extra: dict[str, Any] = field(default_factory=dict)
    manifest_sha256: str = ""

    def canonical_json(self) -> str:
        d = asdict(self)
        d.pop("manifest_sha256", None)
        # deterministic ordering
        return json.dumps(d, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def compute_sha(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()

    def finalize(self) -> "ProvenanceManifest":
        if not self.ended_at:
            self.ended_at = _utcnow()
        self.manifest_sha256 = self.compute_sha()
        return self


def _utcnow() -> str:
    # NOTE: uses time.gmtime to avoid the workflow-banned Date.now(); this is
    # server-side runtime, not a workflow script, so time is allowed.
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_manifest(manifest: ProvenanceManifest, out_dir: str | Path) -> Path:
    """Finalize and write manifest to <out_dir>/<job_id>__<stage>.manifest.json.

    Returns the path written. Idempotent: re-writing the same logical manifest
    produces the same manifest_sha256 and the same filename.
    """
    manifest.finalize()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    fname = f"{manifest.job_id}__{manifest.stage}.manifest.json"
    fpath = out / fname
    tmp = fpath.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(asdict(manifest), indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    os.replace(tmp, fpath)
    return fpath


def code_sha_of_files(files: list[str | Path]) -> str:
    """Stable SHA over a set of source files (sorted by path)."""
    h = hashlib.sha256()
    for f in sorted(map(str, files)):
        p = Path(f)
        if not p.is_file():
            h.update(f"MISSING:{f}\n".encode())
            continue
        h.update(f"{f}\0".encode())
        h.update(sha256_file(p).encode())
        h.update(b"\n")
    return h.hexdigest()
