"""PepPrCLIP adapter for the unified Model Registry.

PepPrCLIP ranks candidate peptides against a target protein sequence using
ESM-2 650M embeddings and a contrastive MiniCLIP encoder. This adapter only
performs read-only probes and dry-run planning in P6A; real ranking is gated
and requires the MiniCLIP checkpoint to be present.

All outputs are computational predictions only and marked
NOT_EXPERIMENTALLY_VALIDATED.
"""
from __future__ import annotations

import csv
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

PEPPRCLIP_ROOT = Path("/home/xh/kxc/stampup/models_dev/pepprclip")
PEPPRCLIP_SOURCE = PEPPRCLIP_ROOT / "source" / "pepprclip"
PEPPRCLIP_ENV_PYTHON = Path("/home/xh/kxc/stampup/models_dev/pepprclip/envs/pepprclip/bin/python")
PEPPRCLIP_RANK_SCRIPT = PEPPRCLIP_ROOT / "scripts" / "pepprclip_rank.py"
PEPPRCLIP_CHECKPOINT = PEPPRCLIP_ROOT / "weights" / "canonical_miniclip_4-22-23.ckpt"
PEPPRCLIP_ARTIFACT_ROOT = Path(
    "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepprclip"
)
PEPPRCLIP_LOG_ROOT = PEPPRCLIP_ROOT / "logs"
PEPPRCLIP_GATE_FILE = PEPPRCLIP_ROOT / ".real_run_enabled"


def _real_run_allowed() -> bool:
    """Return True only when an explicit real-run gate is open."""
    enabled = os.environ.get("PEPPRCLIP_REAL_RUN_ENABLED", "false").lower() in (
        "1",
        "true",
        "yes",
    )
    token = os.environ.get("PEPPRCLIP_REAL_RUN_TOKEN", "")
    return enabled or PEPPRCLIP_GATE_FILE.exists() or bool(token)


def _close_real_run_gate() -> None:
    """Close the real-run gate by removing the gate file and clearing the token."""
    try:
        PEPPRCLIP_GATE_FILE.unlink(missing_ok=True)
    except OSError:
        pass
    os.environ.pop("PEPPRCLIP_REAL_RUN_TOKEN", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _base_safety_flags() -> ModelSafetyFlags:
    flags = build_default_safety_flags()
    flags["executed_model"] = False
    flags["generated_candidates"] = False
    flags["generated_structure"] = False
    flags["generated_msa"] = False
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


def _parse_candidate_peptides(raw: str | list[str] | None) -> list[str]:
    """Parse a newline/comma separated string or a list of peptide sequences."""
    if not raw:
        return []
    if isinstance(raw, list):
        lines = [str(item).strip() for item in raw]
    else:
        lines = raw.replace(",", "\n").splitlines()
    sequences: list[str] = []
    for line in lines:
        seq = line.strip().upper()
        seq = "".join(c for c in seq if c.isalpha())
        if seq:
            sequences.append(seq)
    return sequences


def _ensure_dirs() -> None:
    PEPPRCLIP_ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    PEPPRCLIP_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def _build_run_artifact_paths(run_id: str) -> dict[str, Path]:
    run_dir = PEPPRCLIP_ARTIFACT_ROOT / run_id
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
        "candidate_peptides.csv": paths["input_dir"] / "candidate_peptides.csv",
        "ranking.csv": paths["output_dir"] / "ranking.csv",
        "scores.json": paths["output_dir"] / "scores.json",
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


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class PepPrCLIPAdapter(BaseModelAdapter):
    """PepPrCLIP peptide-protein ranking adapter."""

    def __init__(self, model_id: str = "pepprclip") -> None:
        super().__init__(model_id)

    def probe(self) -> ModelProbeResult:
        """Read-only probe of PepPrCLIP environment, source and weights."""
        checks: list[dict[str, str]] = []
        errors: list[str] = []

        def check(name: str, condition: bool, message: str, detail: str = "", fail_message: str = ""):
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
                errors.append(fail_message or message)

        check(
            "pepprclip_root",
            PEPPRCLIP_ROOT.exists(),
            "PepPrCLIP root directory exists",
            str(PEPPRCLIP_ROOT),
        )
        check(
            "pepprclip_source",
            PEPPRCLIP_SOURCE.exists(),
            "PepPrCLIP source repository exists",
            str(PEPPRCLIP_SOURCE),
        )
        check(
            "pepprclip_notebook",
            (PEPPRCLIP_SOURCE / "PepPrCLIP Quickstart.ipynb").exists(),
            "PepPrCLIP Quickstart notebook exists",
        )
        check(
            "pepprclip_env_python",
            PEPPRCLIP_ENV_PYTHON.exists(),
            "PepPrCLIP conda env python exists",
            str(PEPPRCLIP_ENV_PYTHON),
        )
        check(
            "pepprclip_rank_script",
            PEPPRCLIP_RANK_SCRIPT.exists(),
            "PepPrCLIP rank script exists",
            str(PEPPRCLIP_RANK_SCRIPT),
        )

        env_ok = PEPPRCLIP_ENV_PYTHON.exists()
        import_ok = False
        import_detail = ""
        esm2_ok = False
        esm2_detail = ""
        if env_ok:
            try:
                result = subprocess.run(
                    [
                        str(PEPPRCLIP_ENV_PYTHON),
                        "-c",
                        "import torch, esm, pytorch_lightning; "
                        "print(torch.__version__); print(esm.__version__); "
                        "print(pytorch_lightning.__version__); print(torch.cuda.is_available())",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=False,
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().splitlines()
                    import_ok = len(lines) >= 4
                    import_detail = " ".join(lines[:4])
                else:
                    import_detail = result.stderr.strip()[:200]
            except Exception as exc:  # pragma: no cover
                import_detail = f"import probe failed: {exc}"

            try:
                result = subprocess.run(
                    [
                        str(PEPPRCLIP_ENV_PYTHON),
                        "-c",
                        "import torch, esm; model, alphabet = esm.pretrained.esm2_t33_650M_UR50D(); "
                        "print('ESM2_LOADED')",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )
                esm2_ok = result.returncode == 0 and "ESM2_LOADED" in result.stdout
                esm2_detail = result.stdout.strip()[:200] if result.returncode == 0 else result.stderr.strip()[:200]
            except Exception as exc:  # pragma: no cover
                esm2_detail = f"esm2 load failed: {exc}"

        check(
            "pepprclip_env_imports",
            import_ok,
            "PepPrCLIP env imports torch, esm and pytorch_lightning",
            import_detail,
        )
        check(
            "pepprclip_esm2_load",
            esm2_ok,
            "ESM-2 650M can be loaded from local cache",
            esm2_detail,
        )

        checkpoint_exists = PEPPRCLIP_CHECKPOINT.exists()
        check(
            "pepprclip_checkpoint",
            checkpoint_exists,
            "MiniCLIP checkpoint is present",
            str(PEPPRCLIP_CHECKPOINT),
            fail_message="MiniCLIP checkpoint is not present",
        )
        if not checkpoint_exists:
            errors.append(
                "MiniCLIP checkpoint is not available. "
                "PepPrCLIP weights require HuggingFace login + license acceptance; "
                "server has no outbound HTTPS to huggingface.co."
            )

        overall_status = "PROBED" if not errors else "DEGRADED"
        if not env_ok:
            overall_status = "UNAVAILABLE"
        if checkpoint_exists and env_ok:
            overall_status = "INSTALLED"

        safety = _base_safety_flags()
        return ModelProbeResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status=overall_status,
            message=(
                "PepPrCLIP probe completed without running the model."
                if not errors
                else f"PepPrCLIP probe found issues: {'; '.join(errors)}"
            ),
            probe_time=_now(),
            adapter_id=self.adapter_id,
            safety_flags=safety,
            detail={
                "checks": checks,
                "errors": errors,
                "real_run_enabled": _real_run_allowed(),
                "checkpoint_path": str(PEPPRCLIP_CHECKPOINT),
                "env_python": str(PEPPRCLIP_ENV_PYTHON),
                "weights_available": checkpoint_exists,
                "block_reason": (
                    None
                    if checkpoint_exists
                    else "MiniCLIP checkpoint not available; HuggingFace license/token required and server has no outbound HTTPS."
                ),
            },
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def dry_run(self, payload: ModelDryRunPayload) -> ModelDryRunResult:
        """Plan a PepPrCLIP ranking run without executing it."""
        run_id = f"pepprclip_dryrun_{uuid.uuid4().hex[:12]}"
        paths = _build_run_artifact_paths(run_id)
        seq = _parse_target_sequence(payload.target_sequence)
        top_k = payload.top_k or 3
        device = payload.device or "auto"
        candidate_peptides = _parse_candidate_peptides(payload.candidate_peptides)

        command_preview = [
            str(PEPPRCLIP_ENV_PYTHON),
            str(PEPPRCLIP_RANK_SCRIPT),
            "--target_sequence",
            str(paths["input_dir"] / "target.fasta"),
            "--candidates_csv",
            str(paths["input_dir"] / "candidate_peptides.csv"),
            "--checkpoint",
            str(PEPPRCLIP_CHECKPOINT),
            "--output_dir",
            str(paths["output_dir"]),
            "--device",
            device,
            "--top_k",
            str(top_k),
        ]

        artifacts = {
            "input/target.fasta": str(paths["input_dir"] / "target.fasta"),
            "input/candidate_peptides.csv": str(paths["input_dir"] / "candidate_peptides.csv"),
            "output/ranking.csv": str(paths["output_dir"] / "ranking.csv"),
            "output/scores.json": str(paths["output_dir"] / "scores.json"),
            "logs/run_stdout_stderr.log": str(paths["logs_dir"] / "run_stdout_stderr.log"),
            "manifest/manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
            "manifest/manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
        }

        safety = _base_safety_flags()
        checkpoint_exists = PEPPRCLIP_CHECKPOINT.exists()
        message = "PepPrCLIP dry-run planned without executing the model."
        if not checkpoint_exists:
            message += (
                " MiniCLIP checkpoint is not present; real ranking remains gated."
                " Obtain the checkpoint legally and place it at the path shown in env_preview."
            )
        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="READY",
            message=message,
            run_id=run_id,
            artifacts=artifacts,
            command_preview=command_preview,
            env_preview={
                "PEPPRCLIP_CHECKPOINT": str(PEPPRCLIP_CHECKPOINT),
                "PEPPRCLIP_CHECKPOINT_EXISTS": str(checkpoint_exists),
                "PEPPRCLIP_ARTIFACT_ROOT": str(PEPPRCLIP_ARTIFACT_ROOT),
                "PYTHONUNBUFFERED": "1",
            },
            safety_flags=safety,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )

    def submit(
        self, payload: ModelDryRunPayload, run_id: str | None = None
    ) -> ModelDryRunResult:
        """Rank candidates if the real-run gate is open and weights exist; otherwise block."""
        if not _real_run_allowed():
            safety = _base_safety_flags()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message="PepPrCLIP real execution is disabled (gate closed).",
                run_id=None,
                artifacts={},
                command_preview=None,
                env_preview={},
                safety_flags=safety,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            )

        if not PEPPRCLIP_CHECKPOINT.exists():
            safety = _base_safety_flags()
            return ModelDryRunResult(
                model_id=self.model_id,
                display_name=self.display_name,
                status="BLOCKED",
                message="PepPrCLIP real execution is blocked: MiniCLIP checkpoint not available.",
                run_id=None,
                artifacts={},
                command_preview=None,
                env_preview={},
                safety_flags=safety,
                validation_status="NOT_EXPERIMENTALLY_VALIDATED",
                scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
            )

        run_id = run_id or f"pepprclip_{uuid.uuid4().hex}"
        paths = _build_run_artifact_paths(run_id)
        _ensure_dirs()
        for p in paths.values():
            p.mkdir(parents=True, exist_ok=True)

        seq = _parse_target_sequence(payload.target_sequence)
        top_k = payload.top_k or 3
        device = payload.device or "auto"
        candidate_peptides = _parse_candidate_peptides(payload.candidate_peptides)

        # Persist inputs
        fasta_path = paths["input_dir"] / "target.fasta"
        fasta_path.write_text(f">target\n{seq}\n", encoding="utf-8")
        candidates_csv = paths["input_dir"] / "candidate_peptides.csv"
        with open(candidates_csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=["sequence"])
            writer.writeheader()
            for pep in candidate_peptides:
                writer.writerow({"sequence": pep})

        cmd = [
            str(PEPPRCLIP_ENV_PYTHON),
            str(PEPPRCLIP_RANK_SCRIPT),
            "--target_sequence",
            str(fasta_path),
            "--candidates_csv",
            str(candidates_csv),
            "--checkpoint",
            str(PEPPRCLIP_CHECKPOINT),
            "--output_dir",
            str(paths["output_dir"]),
            "--device",
            device,
            "--top_k",
            str(top_k),
        ]

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

        # Write manifests
        _write_manifests(paths, run_id, seq, candidate_peptides, device, success)

        artifacts = {
            "input/target.fasta": str(fasta_path),
            "input/candidate_peptides.csv": str(candidates_csv),
            "output/ranking.csv": str(paths["output_dir"] / "ranking.csv"),
            "output/scores.json": str(paths["output_dir"] / "scores.json"),
            "logs/run_stdout_stderr.log": str(log_path),
            "manifest/manifest_pre.json": str(paths["manifest_dir"] / "manifest_pre.json"),
            "manifest/manifest_post.json": str(paths["manifest_dir"] / "manifest_post.json"),
        }

        safety = _base_safety_flags()
        if success:
            safety.executed_model = True
            safety.is_scientific_result = True

        return ModelDryRunResult(
            model_id=self.model_id,
            display_name=self.display_name,
            status="SUCCEEDED" if success else "FAILED",
            message=(
                "PepPrCLIP ranked candidate peptides."
                if success
                else "PepPrCLIP real run failed; see logs."
            ),
            run_id=run_id,
            artifacts=artifacts,
            command_preview=cmd,
            env_preview={"PEPPRCLIP_CHECKPOINT": str(PEPPRCLIP_CHECKPOINT)},
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
        if not _path_within_root(candidate, PEPPRCLIP_ARTIFACT_ROOT):
            return None
        return candidate if candidate.exists() else None

    def list_artifacts(self, job_id: str) -> ModelArtifactsResponse:
        """List PepPrCLIP artifacts for a completed run."""
        paths = _build_run_artifact_paths(job_id)
        artifacts = []
        for rel, full in {
            "input/target.fasta": paths["input_dir"] / "target.fasta",
            "input/candidate_peptides.csv": paths["input_dir"] / "candidate_peptides.csv",
            "output/ranking.csv": paths["output_dir"] / "ranking.csv",
            "output/scores.json": paths["output_dir"] / "scores.json",
            "logs/run_stdout_stderr.log": paths["logs_dir"] / "run_stdout_stderr.log",
            "manifest/manifest_pre.json": paths["manifest_dir"] / "manifest_pre.json",
            "manifest/manifest_post.json": paths["manifest_dir"] / "manifest_post.json",
        }.items():
            if not _path_within_root(full, PEPPRCLIP_ARTIFACT_ROOT):
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

        status = "succeeded" if (paths["output_dir"] / "ranking.csv").exists() else "unknown"
        return ModelArtifactsResponse(
            model_id=self.model_id,
            job_id=job_id,
            status=status,
            artifacts=artifacts,
            validation_status="NOT_EXPERIMENTALLY_VALIDATED",
            scientific_boundary=SCIENTIFIC_BOUNDARY_NOTE,
        )


def _write_manifests(
    paths: dict[str, Path],
    run_id: str,
    seq: str,
    candidate_peptides: list[str],
    device: str,
    success: bool,
) -> None:
    """Write pre/post run manifest files with safety metadata."""
    paths["manifest_dir"].mkdir(parents=True, exist_ok=True)
    base_metadata = {
        "model_id": "pepprclip",
        "run_id": run_id,
        "checkpoint_path": str(PEPPRCLIP_CHECKPOINT),
        "esm_model": "esm2_t33_650M_UR50D",
        "target_sequence_length": len(seq),
        "num_candidates": len(candidate_peptides),
        "device_requested": device,
        "computational_prediction_only": True,
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "safety_note": "clip_score is not Kd, MIC, or experimental binding affinity",
    }

    pre_path = paths["manifest_dir"] / "manifest_pre.json"
    post_path = paths["manifest_dir"] / "manifest_post.json"
    pre_path.write_text(json.dumps(base_metadata, indent=2), encoding="utf-8")
    post_meta = {**base_metadata, "run_completed": success}
    post_path.write_text(json.dumps(post_meta, indent=2), encoding="utf-8")
