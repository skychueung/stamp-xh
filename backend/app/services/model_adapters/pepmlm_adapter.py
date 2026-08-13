"""PepMLM adapter for the unified Model Registry.

PepMLM is a target-sequence-conditioned masked-language-model peptide generator.
This adapter performs read-only environment/weight probes and can generate a small
number of candidate peptides when the real-run gate is explicitly opened.

All outputs are computational predictions only and marked NOT_EXPERIMENTALLY_VALIDATED.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from app.schemas.model_registry import (
    ModelArtifactsResponse,
    ModelDryRunPayload,
    ModelDryRunResult,
    ModelProbeResult,
    ModelSafetyFlags,
)
from app.services.model_adapters.base import BaseModelAdapter
from app.services.target_peptide_model_registry import (
    SCIENTIFIC_BOUNDARY_NOTE,
    build_default_safety_flags,
)

# ---------------------------------------------------------------------------
# Paths and gates (all isolated under /home/xh/kxc/stampup)
# ---------------------------------------------------------------------------

PEPMLM_ROOT = Path("/home/xh/kxc/stampup/models_dev/pepmlm")
PEPMLM_MODEL_PATH = PEPMLM_ROOT / "ChatterjeeLab_PepMLM-650M"
PEPMLM_ENV_PYTHON = Path("/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python")
PEPMLM_INFER_SCRIPT = PEPMLM_ROOT / "scripts" / "pepmlm_infer.py"
PEPMLM_ARTIFACT_ROOT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepmlm"
)
PEPMLM_LOG_ROOT = PEPMLM_ROOT / "logs"
PEPMLM_GATE_FILE = PEPMLM_ROOT / ".real_run_enabled"

# Real-run gate.  Default is CLOSED.  Three ways to open it for a controlled run:
#   1. Set PEPMLM_REAL_RUN_ENABLED=true in the server environment (rarely used).
#   2. Create the gate file PEPMLM_GATE_FILE (operational mechanism for smoke runs).
#   3. Export PEPMLM_REAL_RUN_TOKEN=<opaque-token> (used by tests / one-shot tokens).
# The gate file is created by the orchestrator script and removed by the script
# and by the worker in its finally block.


def _real_run_allowed() -> bool:
    """Return True only when an explicit real-run gate is open."""
    enabled = os.environ.get("PEPMLM_REAL_RUN_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    token = os.environ.get("PEPMLM_REAL_RUN_TOKEN", "")
    return enabled or PEPMLM_GATE_FILE.exists() or bool(token)


def _close_real_run_gate() -> None:
    """Close the real-run gate by removing the gate file and clearing the token."""
    try:
        PEPMLM_GATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    os.environ.pop("PEPMLM_REAL_RUN_TOKEN", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_safety_flags() -> ModelSafetyFlags:
    flags = build_default_safety_flags()
    flags["generated_candidates"] = False
    flags["generated_structure"] = False
    flags["generated_msa"] = False
    flags["executed_model"] = False
    flags["is_scientific_result"] = False
    flags["computational_prediction_only"] = True
    return ModelSafetyFlags(**flags)


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _parse_target_sequence(raw: str) -> str:
    """Return the first sequence from a FASTA string or the raw string."""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    seq_lines = [line for line in lines if not line.startswith(">")]
    return "".join(seq_lines) if seq_lines else "".join(lines)


def _ensure_dirs() -> None:
    PEPMLM_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    PEPMLM_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def _build_run_artifact_paths(run_id: str) -> dict[str, Path]:
    run_dir = PEPMLM_ARTIFACT_ROOT / run_id
    return {
        "run_dir": run_dir,
        "input_dir": run_dir / "input",
        "output_dir": run_dir / "output",
        "logs_dir": run_dir / "logs",
        "manifest_dir": run_dir / "manifest",
    }


def _artifact_name_to_path(paths: dict[str, Path], artifact_name: str) -> Path | None:
    """Map a well-known artifact name to an absolute path."""
    mapping = {
        "target.fasta": paths["input_dir"] / "target.fasta",
        "candidate_sequences.csv": paths["output_dir"] / "candidate_sequences.csv",
        "candidate_sequences.json": paths["output_dir"] / "candidate_sequences.json",
        "run_stdout_stderr.log": paths["logs_dir"] / "run_stdout_stderr.log",
        "manifest_pre.json": paths["manifest_dir"] / "manifest_pre.json",
        "manifest_post.json": paths["manifest_dir"] / "manifest_post.json",
    }
    return mapping.get(artifact_name)


def _path_within_root(path: Path, root: Path) -> bool:
    """Return True if *path* resolves to a location under *root*."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _post_process_candidates(paths: dict[str, Path], run_id: str) -> None:
    """Add required safety/tracking columns to candidate CSV/JSON outputs."""
    csv_path = paths["output_dir"] / "candidate_sequences.csv"
    json_path = paths["output_dir"] / "candidate_sequences.json"
    safety_note = "computational prediction only"
    validation_status = "NOT_EXPERIMENTALLY_VALIDATED"

    candidates: list[dict[str, Any]] = []
    if csv_path.exists():
        with open(csv_path, "r", newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                candidate = dict(row)
                candidate["source_model"] = candidate.get("model_name", "PepMLM-650M")
                candidate["job_id"] = run_id
                candidate["validation_status"] = validation_status
                candidate["safety_note"] = safety_note
                candidate["length"] = candidate.get("peptide_length", len(candidate.get("sequence", "")))
                candidates.append(candidate)
        if candidates:
            fieldnames = list(candidates[0].keys())
            with open(csv_path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(candidates)

    if json_path.exists():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        raw_candidates = data.get("candidates", [])
        annotated: list[dict[str, Any]] = []
        for candidate in raw_candidates:
            if not isinstance(candidate, dict):
                continue
            candidate["source_model"] = candidate.get("model_name", "PepMLM-650M")
            candidate["job_id"] = run_id
            candidate["validation_status"] = validation_status
            candidate["safety_note"] = safety_note
            candidate["length"] = candidate.get("peptide_length", len(candidate.get("sequence", "")))
            annotated.append(candidate)
        data["candidates"] = annotated
        data["validation_status"] = validation_status
        data["safety_note"] = safety_note
        data["job_id"] = run_id
        data["computational_prediction_only"] = True
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _relocate_manifests(
    paths: dict[str, Path],
    run_id: str,
    seq: str,
    peptide_length: int,
    num_candidates: int,
    device: str,
    seed: int | None,
) -> None:
    """Move manifest files produced by pepmlm_infer.py into manifest/ and merge metadata."""
    paths["manifest_dir"].mkdir(parents=True, exist_ok=True)
    checkpoint = PEPMLM_MODEL_PATH / "model.safetensors"
    if not checkpoint.is_file():
        checkpoint = PEPMLM_MODEL_PATH / "pytorch_model.bin"
    checkpoint_sha256 = None
    if checkpoint.is_file():
        digest = hashlib.sha256()
        with checkpoint.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
                digest.update(chunk)
        checkpoint_sha256 = digest.hexdigest()
    input_hash = hashlib.sha256(seq.encode("utf-8")).hexdigest()
    base_metadata = {
        "model_id": "pepmlm",
        "model_version": "PepMLM-650M",
        "run_id": run_id,
        "model_path": str(PEPMLM_MODEL_PATH),
        "checkpoint_sha256": checkpoint_sha256,
        "input_hash": input_hash,
        "seed": seed,
        "target_sequence_length": len(seq),
        "peptide_length": peptide_length,
        "num_candidates": num_candidates,
        "device_requested": device,
        "computational_prediction_only": True,
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "safety_note": "computational prediction only",
    }

    pre_src = paths["output_dir"] / "manifest_pre.json"
    pre_dst = paths["manifest_dir"] / "manifest_pre.json"
    post_src = paths["output_dir"] / "manifest_post.json"
    post_dst = paths["manifest_dir"] / "manifest_post.json"

    for src, dst, is_post in [(pre_src, pre_dst, False), (post_src, post_dst, True)]:
        if src.exists():
            try:
                script_meta = json.loads(src.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                script_meta = {}
            merged = {**base_metadata, **script_meta}
            if is_post:
                merged["run_completed"] = True
            dst.write_text(json.dumps(merged, indent=2), encoding="utf-8")
            src.unlink()
        else:
            meta = dict(base_metadata)
            if is_post:
                meta["run_completed"] = True
            dst.write_text(json.dumps(meta, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PepMLMAdapter(BaseModelAdapter):
    """PepMLM sequence-generation adapter."""

    def __init__(self, model_id: str = "pepmlm") -> None:
        super().__init__(model_id)

    def probe(self) -> ModelProbeResult:
        """Read-only probe of PepMLM environment and weights."""
        checks: list[dict[str, str]] = []
        errors: list[str] = []

        def check(name: str, condition: bool, message: str, detail: str = ""):
            checks.append(
                {
                    "name": name,
                    "status": "PASS" if condition else "FAIL",
                    "message": message,
                    "detail": detail,
                    "severity": "INFO" if condition else "ERROR",
                }
            )
            if not condition:
                errors.append(message)

        check(
            "pepmlm_root",
            PEPMLM_ROOT.exists(),
            "PepMLM root directory exists",
            str(PEPMLM_ROOT),
        )
        check(
            "pepmlm_model_path",
            PEPMLM_MODEL_PATH.exists(),
            "PepMLM model weights directory exists",
            str(PEPMLM_MODEL_PATH),
        )
        has_weights = (
            (PEPMLM_MODEL_PATH / "pytorch_model.bin").exists()
            or (PEPMLM_MODEL_PATH / "model.safetensors").exists()
        )
        check(
            "pepmlm_pytorch_model_bin",
            has_weights,
            "model weights exist (pytorch_model.bin or model.safetensors)",
            str(PEPMLM_MODEL_PATH),
        )
        check(
            "pepmlm_config_json",
            (PEPMLM_MODEL_PATH / "config.json").exists(),
            "config.json exists",
        )
        check(
            "pepmlm_tokenizer_config",
            (PEPMLM_MODEL_PATH / "tokenizer_config.json").exists(),
            "tokenizer_config.json exists",
        )
        check(
            "pepmlm_env_python",
            PEPMLM_ENV_PYTHON.exists(),
            "PepMLM conda env python exists",
            str(PEPMLM_ENV_PYTHON),
        )
        check(
            "pepmlm_infer_script",
            PEPMLM_INFER_SCRIPT.exists(),
            "PepMLM inference script exists",
            str(PEPMLM_INFER_SCRIPT),
        )

        env_ok = PEPMLM_ENV_PYTHON.exists()
        torch_cuda_ok = False
        env_detail = ""
        if env_ok:
            try:
                result = subprocess.run(
                    [
                        str(PEPMLM_ENV_PYTHON),
                        "-c",
                        "import torch, transformers; print(torch.__version__); print(transformers.__version__); print(torch.cuda.is_available())",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().splitlines()
                    torch_cuda_ok = len(lines) >= 3 and lines[2].lower() == "true"
                    env_detail = " ".join(lines[:3])
            except Exception as exc:  # pragma: no cover - probe should not crash
                errors.append(f"env probe failed: {exc}")

        check(
            "pepmlm_torch_cuda",
            torch_cuda_ok,
            "PepMLM env sees CUDA torch",
            env_detail,
        )

        overall_status = "PROBED" if not errors else "DEGRADED"
        if not env_ok:
            overall_status = "UNAVAILABLE"

        safety = _base_safety_flags()
        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=overall_status,
            message=(
                "PepMLM probe completed without running the model."
                if not errors
                else f"PepMLM probe found issues: {'; '.join(errors)}"
            ),
            probe_time=_now(),
            adapter_id=self.adapter_id,
            safety_flags=safety,
            detail={
                "checks": checks,
                "errors": errors,
                "real_run_enabled": _real_run_allowed(),
                "model_path": str(PEPMLM_MODEL_PATH),
                "env_python": str(PEPMLM_ENV_PYTHON),
            },
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Plan a PepMLM run without executing it."""
        run_id = f"pepmlm_dryrun_{uuid.uuid4().hex[:12]}"
        paths = _build_run_artifact_paths(run_id)
        seq = _parse_target_sequence(payload.target_sequence)
        peptide_length = payload.peptide_length or payload.max_length or 10
        num_candidates = payload.num_candidates or payload.num_iterations or 5
        device = payload.device or "auto"
        _ = payload.seed

        command_preview = [
            str(PEPMLM_ENV_PYTHON),
            str(PEPMLM_INFER_SCRIPT),
            "--model_path",
            str(PEPMLM_MODEL_PATH),
            "--target_sequence",
            seq,
            "--peptide_length",
            str(peptide_length),
            "--num_candidates",
            str(num_candidates),
            "--device",
            device,
            "--output_dir",
            str(paths["output_dir"]),
        ]

        artifacts = {
            "input/target.fasta": str(paths["input_dir"] / "target.fasta"),
            "output/candidate_sequences.csv": str(paths["output_dir"] / "candidate_sequences.csv"),
            "output/candidate_sequences.json": str(paths["output_dir"] / "candidate_sequences.json"),
            "logs/run_stdout_stderr.log": str(paths["logs_dir"] / "run_stdout_stderr.log"),
            "manifest/manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
            "manifest/manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
        }

        safety = _base_safety_flags()
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="READY",
            message="PepMLM dry-run planned without executing the model.",
            run_id=run_id,
            artifacts=artifacts,
            command_preview=command_preview,
            env_preview={
                "PEPMLM_MODEL_PATH": str(PEPMLM_MODEL_PATH),
                "PEPMLM_ARTIFACT_ROOT": str(PEPMLM_ARTIFACT_ROOT),
                "PYTHONUNBUFFERED": "1",
            },
            safety_flags=safety,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit(
        self, payload: ModelDryRunPayload, run_id: str | None = None
    ) -> ModelDryRunResult:
        """Generate candidates if the real-run gate is open; otherwise block."""
        if not _real_run_allowed():
            safety = _base_safety_flags()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message="PepMLM real execution is disabled (gate closed).",
                run_id=None,
                artifacts={},
                command_preview=None,
                env_preview={},
                safety_flags=safety,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            )

        run_id = run_id or f"pepmlm_{uuid.uuid4().hex}"
        paths = _build_run_artifact_paths(run_id)
        _ensure_dirs()
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)

        seq = _parse_target_sequence(payload.target_sequence)
        peptide_length = payload.peptide_length or payload.max_length or 10
        num_candidates = payload.num_candidates or payload.num_iterations or 5
        device = payload.device or "auto"
        seed = payload.seed

        # Persist input FASTA
        fasta_path = paths["input_dir"] / "target.fasta"
        fasta_path.write_text(f">target\n{seq}\n", encoding="utf-8")

        cmd = [
            str(PEPMLM_ENV_PYTHON),
            str(PEPMLM_INFER_SCRIPT),
            "--model_path",
            str(PEPMLM_MODEL_PATH),
            "--target_sequence",
            seq,
            "--peptide_length",
            str(peptide_length),
            "--num_candidates",
            str(num_candidates),
            "--device",
            device,
            "--output_dir",
            str(paths["output_dir"]),
        ]
        if seed is not None:
            cmd.extend(["--seed", str(seed)])
        if payload.top_k is not None and payload.top_k > 0:
            cmd.extend(["--top_k", str(payload.top_k)])

        log_path = paths["logs_dir"] / "run_stdout_stderr.log"
        success = False
        try:
            with open(log_path, "w", encoding="utf-8") as log_f:
                result = subprocess.run(
                    cmd,
                    stdout=log_f,
                    stderr=subprocess.STDOUT,
                    timeout=3600,
                    check=False,
                )
            success = result.returncode == 0
        except subprocess.TimeoutExpired:
            success = False

        if success:
            _post_process_candidates(paths, run_id)
            _relocate_manifests(paths, run_id, seq, peptide_length, num_candidates, device, seed)

        artifacts = {
            "input/target.fasta": str(paths["input_dir"] / "target.fasta"),
            "output/candidate_sequences.csv": str(paths["output_dir"] / "candidate_sequences.csv"),
            "output/candidate_sequences.json": str(paths["output_dir"] / "candidate_sequences.json"),
            "logs/run_stdout_stderr.log": str(log_path),
            "manifest/manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
            "manifest/manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
        }

        safety = _base_safety_flags()
        if success:
            safety.generated_candidates = True
            safety.executed_model = True
            safety.is_scientific_result = True

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="SUCCEEDED" if success else "FAILED",
            message=(
                "PepMLM generated candidate sequences."
                if success
                else "PepMLM real run failed; see logs."
            ),
            run_id=run_id,
            artifacts=artifacts,
            command_preview=cmd,
            env_preview={"PEPMLM_MODEL_PATH": str(PEPMLM_MODEL_PATH)},
            safety_flags=safety,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def download_artifact_path(self, job_id: str, artifact_name: str) -> Path | None:
        """Resolve an absolute artifact path for a registered artifact name."""
        paths = _build_run_artifact_paths(job_id)
        candidate = _artifact_name_to_path(paths, artifact_name)
        if candidate is None:
            return None
        if not _path_within_root(candidate, PEPMLM_ARTIFACT_ROOT):
            return None
        return candidate if candidate.exists() else None

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """List PepMLM artifacts for a completed run."""
        paths = _build_run_artifact_paths(job_id)
        artifacts = []
        for rel, full in {
            "input/target.fasta": paths["input_dir"] / "target.fasta",
            "output/candidate_sequences.csv": paths["output_dir"] / "candidate_sequences.csv",
            "output/candidate_sequences.json": paths["output_dir"] / "candidate_sequences.json",
            "logs/run_stdout_stderr.log": paths["logs_dir"] / "run_stdout_stderr.log",
            "manifest/manifest_pre.json": paths["manifest_dir"] / "manifest_pre.json",
            "manifest/manifest_post.json": paths["manifest_dir"] / "manifest_post.json",
        }.items():
            if not _path_within_root(full, PEPMLM_ARTIFACT_ROOT):
                continue
            artifacts.append(
                {
                    "name": rel.split("/")[-1],
                    "path": rel,
                    "artifact_type": rel.split("/")[0],
                    "exists": full.exists(),
                    "size_bytes": full.stat().st_size if full.exists() else 0,
                    "download_url": f"/api/v1/models/{self.model_id}/jobs/{job_id}/artifacts/{rel.split('/')[-1]}/download",
                }
            )

        status = "succeeded" if (paths["output_dir"] / "candidate_sequences.csv").exists() else "unknown"
        return ModelArtifactsResponse(
            model_id=self.model_id,
            job_id=job_id,
            status=status,
            artifacts=artifacts,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )
