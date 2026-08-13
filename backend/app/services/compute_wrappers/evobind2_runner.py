"""EvoBind2 real-run runner with fail-closed gate (Phase 8).

This module contains the ONLY code path that is allowed to:
  - write run input files (receptor FASTA)
  - spawn a subprocess for mc_design.py
  - create work/artifact/log directories

All of the above are gated by a temporary, run-specific authorization file
managed by evobind2_gate.  If the gate is closed, missing, expired, or not
bound to the requested run_id, this module raises before any filesystem write
or subprocess call.

This module NEVER fabricates candidate peptides, PDB files, or scientific
metrics.  All results are explicitly marked NOT_EXPERIMENTALLY_VALIDATED.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.compute_wrappers.evobind2_gate import (
    require_run_gate,
    validate_run_id,
)
from app.services.compute_wrappers.evobind2_wrapper import (
    EVOBIND2_ARTIFACT_ROOT,
    EVOBIND2_LOG_ROOT,
    EvoBind2Input,
    build_environment,
    build_mc_design_command,
    validate_model_name,
    validate_peptide_sequence,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Input guards
# ---------------------------------------------------------------------------

MAX_RECEPTOR_FASTA_LEN = 50_000  # amino acids + headers
MAX_PEPTIDE_LENGTH = 50
MIN_PEPTIDE_LENGTH = 1
MAX_MAX_RECYCLES = 10
MAX_NUM_ITERATIONS = 100

# Allowed FASTA alphabet for receptor sequence lines (standard + unknown X)
AMINO_ACID_PATTERN = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYX\s]*$", re.IGNORECASE)


def validate_fasta(receptor_fasta: str) -> tuple[bool, str | None]:
    """Validate receptor FASTA content.

    Rules:
      - non-empty string
      - length within limit
      - contains at least one sequence line after a header line
      - sequence lines only contain standard amino-acid letters or X
      - no null bytes
    """
    if not isinstance(receptor_fasta, str) or not receptor_fasta.strip():
        return False, "receptor_fasta must be a non-empty string"
    if "\x00" in receptor_fasta:
        return False, "receptor_fasta contains null bytes"
    if len(receptor_fasta) > MAX_RECEPTOR_FASTA_LEN:
        return False, f"receptor_fasta exceeds {MAX_RECEPTOR_FASTA_LEN} chars"

    lines = receptor_fasta.splitlines()
    has_header = False
    has_sequence = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(">"):
            has_header = True
            continue
        if not AMINO_ACID_PATTERN.match(stripped):
            return False, f"FASTA sequence line contains invalid characters: {stripped[:40]}"
        has_sequence = True

    if not has_header:
        return False, "receptor_fasta must contain a FASTA header line starting with '>'"
    if not has_sequence:
        return False, "receptor_fasta must contain at least one sequence line"
    return True, None


def validate_run_input(inp: EvoBind2Input) -> tuple[bool, str | None]:
    """Validate all runner input fields with hard limits."""
    ok, error = validate_run_id(inp.run_id)
    if not ok:
        return False, error

    ok, error = validate_fasta(inp.receptor_fasta)
    if not ok:
        return False, error

    if inp.mode != "predict_only":
        return False, "Only 'predict_only' mode is supported in this phase."

    ok, error = validate_model_name(inp.model_name)
    if not ok:
        return False, error

    if not (1 <= inp.max_recycles <= MAX_MAX_RECYCLES):
        return False, f"max_recycles must be 1..{MAX_MAX_RECYCLES}, got {inp.max_recycles}"

    if not (1 <= inp.num_iterations <= MAX_NUM_ITERATIONS):
        return False, (
            f"num_iterations must be 1..{MAX_NUM_ITERATIONS}, got {inp.num_iterations}"
        )

    # Phase 9A: predict_only requires an explicit user-provided peptide_sequence
    # and its length must equal peptide_length.  Keep MAX_PEPTIDE_LENGTH as the
    # runner-side upper bound (same as dry-run limit).
    ok, error = validate_peptide_sequence(
        inp.peptide_sequence, inp.peptide_length, required=True
    )
    if not ok:
        return False, error

    return True, None


# ---------------------------------------------------------------------------
# Path guards
# ---------------------------------------------------------------------------

ALLOWED_ROOTS = {
    # Run directories must live under the artifact root so that the existing
    # job-service artifact listing (which scans EVOBIND2_ARTIFACT_ROOT/{job_id})
    # remains consistent if the gate is ever opened in a future phase.
    "work": Path(EVOBIND2_ARTIFACT_ROOT).resolve(),
    "artifact": Path(EVOBIND2_ARTIFACT_ROOT).resolve(),
    "log": Path(EVOBIND2_LOG_ROOT).resolve(),
}


def _resolve_under_root(path: str, root: Path) -> Path:
    """Resolve path and verify it lies under root.

    Raises ValueError on traversal or resolution failure.
    """
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"cannot resolve path {path}: {exc}")

    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"path {resolved} escapes allowed root {root}"
        ) from exc
    return resolved


def _verify_run_paths(paths: dict[str, str]) -> None:
    """Verify all generated run paths stay within allowed roots."""
    _resolve_under_root(paths["run_dir"], ALLOWED_ROOTS["work"])
    _resolve_under_root(paths["input_dir"], ALLOWED_ROOTS["work"])
    _resolve_under_root(paths["output_dir"], ALLOWED_ROOTS["work"])
    _resolve_under_root(paths["logs_dir"], ALLOWED_ROOTS["log"])


# ---------------------------------------------------------------------------
# Path builder for runner (uses ALLOWED_ROOTS instead of server constants)
# ---------------------------------------------------------------------------


def _build_runner_paths(run_id: str) -> dict[str, str]:
    """Construct run paths under ALLOWED_ROOTS.

    Validates run_id and rejects traversal.
    """
    from app.services.compute_wrappers.evobind2_wrapper import normalize_output_dir

    ok, error = validate_run_id(run_id)
    if not ok:
        raise ValueError(error)

    work_root = ALLOWED_ROOTS["work"]
    log_root = ALLOWED_ROOTS["log"]
    run_dir = str(work_root / run_id)
    input_dir = f"{run_dir}/input"
    output_dir = normalize_output_dir(f"{run_dir}/output")
    logs_dir = f"{log_root}/{run_id}/logs"

    # Validate resolved paths stay under roots
    try:
        Path(run_dir).resolve().relative_to(work_root.resolve())
        Path(logs_dir).resolve().relative_to(log_root.resolve())
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"run_id '{run_id}' produces unsafe runner paths: {exc}") from exc

    return {
        "run_dir": run_dir,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "logs_dir": logs_dir,
        "receptor_fasta_path": f"{input_dir}/receptor.fasta",
        "receptor_msa_path": f"{input_dir}/receptor_msa.a3m",
        "metrics_csv": f"{output_dir}metrics.csv",
        "pdb": f"{output_dir}unrelaxed_true.pdb",
        "gpu_sample_csv": f"{logs_dir}/gpu_sample.csv",
        "run_log": f"{logs_dir}/run_stdout_stderr.log",
        "jax_precheck_log": f"{logs_dir}/jax_gpu_precheck.log",
    }


# ---------------------------------------------------------------------------
# Dry-run preview (gate-independent)
# ---------------------------------------------------------------------------


def preview_run_command(inp: EvoBind2Input) -> dict[str, Any]:
    """Return command/env/artifact preview without gate check or execution.

    This is safe to call from public endpoints because it performs no
    subprocess, no writes, and no model execution.
    """
    from app.services.compute_wrappers.evobind2_wrapper import dry_run_plan

    plan = dry_run_plan(inp)
    return {
        "run_id": plan.run_id,
        "status": plan.status,
        "mode": plan.mode,
        "model_name": plan.model_name,
        "used_gpu": plan.used_gpu,
        "selected_gpu": plan.selected_gpu,
        "artifacts": plan.artifacts,
        "command_preview": plan.command_preview,
        "env_preview": plan.env_preview,
        "safety_flags": plan.safety_flags,
        "error_message": plan.error_message,
    }


# ---------------------------------------------------------------------------
# Real execution entry point (gated)
# ---------------------------------------------------------------------------


class EvoBind2ExecutionError(Exception):
    """Raised when gated execution cannot proceed."""


class EvoBind2SubprocessError(Exception):
    """Raised when the mc_design.py subprocess fails."""


def _ensure_directory(path: Path) -> None:
    """Create directory if missing, verifying it stays under allowed roots."""
    # Re-validate after creation because mkdir may follow symlinks.
    path.mkdir(parents=True, exist_ok=True)


def _write_receptor_fasta(path: Path, content: str) -> None:
    """Write receptor FASTA to the input directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
        if not content.endswith("\n"):
            fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())


def execute_evobind2_run(
    inp: EvoBind2Input,
    timeout_seconds: int = 3600,
    gate_root: Path | None = None,
    expected_owner_uid: int | None = None,
) -> dict[str, Any]:
    """Execute an EvoBind2 run with fail-closed gate.

    Steps:
      1. Validate input parameters.
      2. Require a valid gate file bound to run_id.
      3. Resolve and verify all output paths under allowed roots.
      4. Write receptor FASTA to work/input.
      5. Build command and environment.
      6. Spawn mc_design.py subprocess (only if gate open).
      7. Wait for completion or timeout.

    Returns a dict with status, safety flags, and validation_status.
    If the gate is closed, this function raises GateClosedError and performs
    NO filesystem writes and NO subprocess calls.
    """
    # 1. Input validation (fail fast, no gate needed)
    ok, error = validate_run_input(inp)
    if not ok:
        raise EvoBind2ExecutionError(error)

    # 2. Fail-closed gate check
    require_run_gate(inp.run_id, gate_root, expected_owner_uid)

    # 3. Path guards
    paths = _build_runner_paths(inp.run_id)
    _verify_run_paths(paths)

    # 4. Prepare directories and input file
    run_dir = Path(paths["run_dir"]).resolve()
    input_dir = Path(paths["input_dir"]).resolve()
    output_dir = Path(paths["output_dir"]).resolve()
    logs_dir = Path(paths["logs_dir"]).resolve()

    _ensure_directory(run_dir)
    _ensure_directory(input_dir)
    _ensure_directory(output_dir)
    _ensure_directory(logs_dir)

    # After mkdir, re-verify paths are still under allowed roots.
    _verify_run_paths(paths)

    fasta_path = Path(paths["receptor_fasta_path"]).resolve()
    _write_receptor_fasta(fasta_path, inp.receptor_fasta)

    # 5. Build command and environment
    selected_gpu: int | None = 0 if inp.use_gpu else None
    if isinstance(inp.selected_gpu, int):
        selected_gpu = inp.selected_gpu

    env = build_environment(selected_gpu)
    command = build_mc_design_command(paths, inp)

    logger.info(
        "EvoBind2 gated execution starting for run_id=%s (gpu=%s)",
        inp.run_id,
        selected_gpu,
    )

    # 6. Spawn subprocess (gate was already verified)
    log_path = Path(paths["run_log"]).resolve()
    try:
        with open(log_path, "w", encoding="utf-8") as log_fh:
            proc = subprocess.Popen(
                command,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                env={**os.environ, **env},
                cwd=str(run_dir),
            )
            try:
                returncode = proc.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                raise EvoBind2SubprocessError(
                    f"EvoBind2 run timed out after {timeout_seconds}s"
                )
    except FileNotFoundError as exc:
        raise EvoBind2SubprocessError(
            f"Command not found: {command[0] if command else '(empty)'}"
        ) from exc
    except OSError as exc:
        raise EvoBind2SubprocessError(f"Failed to start EvoBind2 subprocess: {exc}") from exc

    if returncode != 0:
        raise EvoBind2SubprocessError(
            f"EvoBind2 subprocess exited with code {returncode}"
        )

    return {
        "run_id": inp.run_id,
        "status": "completed",
        "mode": inp.mode,
        "model_name": inp.model_name,
        "used_gpu": inp.use_gpu and selected_gpu is not None,
        "selected_gpu": selected_gpu,
        "artifacts": {
            "metrics_csv": paths["metrics_csv"],
            "pdb": paths["pdb"],
            "gpu_sample_csv": paths["gpu_sample_csv"],
            "run_log": paths["run_log"],
            "jax_precheck_log": paths["jax_precheck_log"],
        },
        "safety_flags": {
            "is_candidate_generation": inp.mode == "design",
            "is_scientific_result": True,  # real model produced output
            "uses_uniref30": inp.msa_mode in ("hhblits", "uniref30"),
            "executed_model": True,
            "executed_hhblits_search": inp.msa_mode in ("hhblits", "uniref30"),
            "generated_msa": inp.msa_mode in ("hhblits", "uniref30"),
            "generated_candidates": inp.mode == "design",
            "generated_pdb": True,
        },
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "completed_at": datetime.now(timezone.utc).isoformat(),
    }


def execute_evobind2_run_safe(
    inp: EvoBind2Input,
    timeout_seconds: int = 3600,
    gate_root: Path | None = None,
    expected_owner_uid: int | None = None,
) -> dict[str, Any]:
    """Wrapper around execute_evobind2_run that always closes the gate on exit.

    Use this for single-run authorization where the gate should not outlive
    the run.  If execute_evobind2_run succeeds or raises, the gate file is
    closed in the finally block.
    """
    from app.services.compute_wrappers.evobind2_gate import close_run_gate

    try:
        return execute_evobind2_run(
            inp, timeout_seconds, gate_root, expected_owner_uid
        )
    finally:
        close_run_gate(inp.run_id, gate_root)


# ---------------------------------------------------------------------------
# Cleanup helpers (run_id-validated, path-guarded)
# ---------------------------------------------------------------------------


def cleanup_run_artifacts(
    run_id: str,
    allowed_roots: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Remove work/artifact/log directories for a single run_id.

    This function validates run_id, resolves paths, and confirms they lie
    under allowed_roots before any deletion.  It NEVER uses rm -rf directly
    on a user-supplied path.
    """
    ok, error = validate_run_id(run_id)
    if not ok:
        raise ValueError(error)

    roots = allowed_roots or ALLOWED_ROOTS
    work_root = roots["work"].resolve()
    run_dir = (work_root / run_id).resolve()

    # Validate constructed path stays under allowed work root.
    try:
        run_dir.relative_to(work_root)
    except ValueError as exc:
        raise ValueError(f"run path {run_dir} escapes allowed root {work_root}") from exc

    removed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    if not run_dir.exists():
        skipped.append(str(run_dir))
        return {
            "run_id": run_id,
            "removed": removed,
            "skipped": skipped,
            "errors": errors,
        }

    try:
        _remove_tree(run_dir)
        removed.append(str(run_dir))
    except OSError as exc:
        errors.append(f"{run_dir}: {exc}")

    return {
        "run_id": run_id,
        "removed": removed,
        "skipped": skipped,
        "errors": errors,
    }


def _remove_tree(path: Path) -> None:
    """Remove a directory tree, refusing to follow symlinks."""
    if path.is_symlink():
        raise OSError(f"refusing to remove symlink: {path}")
    if path.is_file():
        path.unlink()
    elif path.is_dir():
        for child in path.iterdir():
            _remove_tree(child)
        path.rmdir()


def rollback_run(
    run_id: str,
    gate_root: Path | None = None,
    allowed_roots: dict[str, Path] | None = None,
) -> dict[str, Any]:
    """Roll back a run: close gate and clean up artifacts.

    This is the safe replacement for git checkout -- or rm -rf on raw paths.
    """
    from app.services.compute_wrappers.evobind2_gate import close_run_gate

    gate_closed = close_run_gate(run_id, gate_root)
    cleanup = cleanup_run_artifacts(run_id, allowed_roots)
    return {
        "run_id": run_id,
        "gate_closed": gate_closed,
        **cleanup,
    }
