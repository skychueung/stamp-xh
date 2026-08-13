"""EvoBind2 wrapper — command builder, dry-run planner, and environment probe (v0.4-phase9a).

Constructs mc_design.py command lines, validates model names against a
whitelist, enforces output_dir guard, and produces safety flags.

The `probe()` function performs read-only environment checks without running
EvoBind2, HHblits searches, AlphaFold2 forward passes, or generating any
scientific artifacts.

Does NOT execute subprocesses during normal import.  Real execution is
delegated to the gated runner in `evobind2_runner.py`.
"""

from __future__ import annotations

import ast
import json
import logging
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.config.model_paths import EVOBIND2_PATHS
from app.services.compute_wrappers.evobind2_gate import validate_run_id

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Centralized storage paths (P21) — kept from server; no hardcoded fallbacks.
# ---------------------------------------------------------------------------

EVOBIND2_ROOT = EVOBIND2_PATHS.source_dir
EVOBIND2_WORK_ROOT = EVOBIND2_PATHS.cache_dir
EVOBIND2_ARTIFACT_ROOT = EVOBIND2_PATHS.artifact_dir
EVOBIND2_LOG_ROOT = f"{EVOBIND2_PATHS.cache_dir}/logs"
AF2_PARAMS_DIR = EVOBIND2_PATHS.af2_params_dir
AF2_DATA_DIR = EVOBIND2_PATHS.af2_data_dir
UNIREF30_DIR = EVOBIND2_PATHS.uniref30_dir
UNIREF30_PREFIX = EVOBIND2_PATHS.uniref30_prefix
HHBLITS_BIN = EVOBIND2_PATHS.hhblits_bin
EVOBIND2_ENV_PYTHON = EVOBIND2_PATHS.env_python
CONDA_ENV_PATH = os.path.dirname(os.path.dirname(EVOBIND2_ENV_PYTHON))
EVOBIND2_REAL_RUN_ENABLED = False
EVOBIND2_PROBE_ENABLED = True

DEFAULT_MODEL_NAME = "model_1_ptm"
ALLOWED_MODEL_NAMES = {"model_1", "model_1_ptm"}
BLOCKED_MODEL_NAMES = {"model_1_multimer_v3"}

# Phase 9A input guards
MAX_RECEPTOR_FASTA_LEN = 50_000
MAX_PEPTIDE_LENGTH_DRY_RUN = 50  # predict_only closed gate: 1-50 only
MIN_PEPTIDE_LENGTH = 1
MAX_MAX_RECYCLES = 10
MAX_NUM_ITERATIONS = 100
AMINO_ACID_PATTERN = re.compile(r"^[ACDEFGHIKLMNPQRSTVWYX\s]*$", re.IGNORECASE)

# Backwards compatibility: EVOBIND_RUNS is now an alias for the unified
# artifact root.  New code should use EVOBIND2_ARTIFACT_ROOT.
EVOBIND_RUNS = EVOBIND2_ARTIFACT_ROOT

# ---------------------------------------------------------------------------
# Input / Output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class EvoBind2Input:
    """Validated input for an EvoBind2 run."""

    run_id: str
    receptor_fasta: str
    peptide_length: int = 10
    mode: str = "predict_only"
    peptide_sequence: str | None = None
    model_name: str = DEFAULT_MODEL_NAME
    max_recycles: int = 1
    num_iterations: int = 1
    use_gpu: bool = True
    selected_gpu: str | int = "auto"
    msa_mode: str = "single_sequence"
    receptor_msa_a3m: str | None = None


@dataclass
class EvoBind2Output:
    """Structured output from an EvoBind2 dry-run or execution."""

    run_id: str
    status: str
    mode: str
    model_name: str
    used_gpu: bool
    selected_gpu: int | None = None
    runtime_seconds: int | None = None
    artifacts: dict[str, str | None] = field(default_factory=dict)
    safety_flags: dict[str, bool] = field(default_factory=dict)
    command_preview: list[str] | None = None
    env_preview: dict[str, str] = field(default_factory=dict)
    error_message: str | None = None


# ---------------------------------------------------------------------------
# Probe helpers
# ---------------------------------------------------------------------------


def _run_cmd(cmd: list[str], timeout: int = 30, env: dict[str, str] | None = None) -> tuple[bool, str, str]:
    """Run a command and return (ok, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**os.environ, **(env or {})},
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except FileNotFoundError:
        return False, "", "Command not found"
    except Exception as exc:  # noqa: BLE001
        return False, "", str(exc)


def _check_path(name: str, path: str, must_be_executable: bool = False) -> dict[str, Any]:
    """Return a probe check dict for a filesystem path."""
    exists = os.path.exists(path)
    is_exec = os.access(path, os.X_OK) if exists and must_be_executable else None
    status = "PASS"
    message = f"{name} exists"
    detail = path
    severity = "INFO"

    if not exists:
        status = "FAIL"
        message = f"{name} missing"
        detail = path
        severity = "ERROR"
    elif must_be_executable and not is_exec:
        status = "FAIL"
        message = f"{name} exists but is not executable"
        detail = path
        severity = "ERROR"

    return {
        "name": name,
        "status": status,
        "message": message,
        "detail": detail,
        "severity": severity,
    }


def _check_af2_params() -> dict[str, Any]:
    """Check that AF2 params include model_1..model_5 npz files."""
    required = [f"params_model_{i}.npz" for i in range(1, 6)]
    missing = []
    for name in required:
        path = os.path.join(AF2_PARAMS_DIR, name)
        if not os.path.exists(path):
            missing.append(name)

    if missing:
        return {
            "name": "af2_params_models",
            "status": "FAIL",
            "message": f"Missing AF2 params: {', '.join(missing)}",
            "detail": AF2_PARAMS_DIR,
            "severity": "ERROR",
        }
    return {
        "name": "af2_params_models",
        "status": "PASS",
        "message": "AF2 params model_1..model_5 present",
        "detail": AF2_PARAMS_DIR,
        "severity": "INFO",
    }


def _check_mc_design_static() -> dict[str, Any]:
    """Parse mc_design.py without compilation or bytecode writes."""
    mc_design_path = f"{EVOBIND2_ROOT}/src/mc_design.py"
    if not os.path.exists(mc_design_path):
        return {
            "name": "mc_design_py_static", "status": "FAIL",
            "message": "mc_design.py not found", "detail": mc_design_path,
            "severity": "ERROR",
        }

    try:
        with open(mc_design_path, "r", encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        flag_count = sum(
            1 for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("DEFINE_")
        )
        return {
            "name": "mc_design_py_static", "status": "PASS",
            "message": f"mc_design.py parses and defines {flag_count} flags",
            "detail": mc_design_path, "severity": "INFO",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "name": "mc_design_py_static", "status": "FAIL",
            "message": "mc_design.py AST parse failed", "detail": str(exc),
            "severity": "ERROR",
        }


def _check_hhblits_help() -> dict[str, Any]:
    """Run hhblits -h (no search)."""
    if not shutil.which(HHBLITS_BIN):
        return {
            "name": "hhblits_help",
            "status": "FAIL",
            "message": "hhblits binary not found",
            "detail": HHBLITS_BIN,
            "severity": "ERROR",
        }
    ok, stdout, stderr = _run_cmd([HHBLITS_BIN, "-h"], timeout=15)
    combined = (stdout + stderr).strip()
    if not ok or not combined:
        return {
            "name": "hhblits_help",
            "status": "FAIL",
            "message": "hhblits -h did not return help text",
            "detail": stderr or stdout,
            "severity": "ERROR",
        }
    version = ""
    if combined:
        first_line = combined.splitlines()[0]
        version = first_line.strip()
    return {
        "name": "hhblits_help",
        "status": "PASS",
        "message": "hhblits help/version returned",
        "detail": version or HHBLITS_BIN,
        "severity": "INFO",
    }


def _check_uniref30() -> dict[str, Any]:
    """Check UniRef30 prefix files (no search)."""
    candidates = [
        f"{UNIREF30_PREFIX}_cs219.ffdata",
        f"{UNIREF30_PREFIX}_cs219.ffindex",
    ]
    # Fallback: top-level ffdata/ffindex if prefix files are absent
    if not any(os.path.exists(p) for p in candidates):
        top_level = [
            os.path.join(UNIREF30_DIR, "UniRef30_2023_02_cs219.ffdata"),
            os.path.join(UNIREF30_DIR, "UniRef30_2023_02_cs219.ffindex"),
        ]
        if any(os.path.exists(p) for p in top_level):
            return {
                "name": "uniref30_database",
                "status": "PASS",
                "message": "UniRef30 top-level ffdata/ffindex found",
                "detail": UNIREF30_DIR,
                "severity": "INFO",
            }
        return {
            "name": "uniref30_database",
            "status": "DEGRADED",
            "message": "UniRef30 prefix files not found",
            "detail": UNIREF30_PREFIX,
            "severity": "WARNING",
        }
    return {
        "name": "uniref30_database",
        "status": "PASS",
        "message": "UniRef30 prefix ffdata/ffindex found",
        "detail": UNIREF30_PREFIX,
        "severity": "INFO",
    }


def _check_conda_python_version() -> dict[str, Any]:
    """Get conda env python version."""
    conda_python = EVOBIND2_ENV_PYTHON
    ok, stdout, stderr = _run_cmd([conda_python, "--version"], timeout=15)
    version = (stdout + stderr).strip()
    if not ok or not version:
        return {
            "name": "conda_python_version",
            "status": "FAIL",
            "message": "Could not get conda env python version",
            "detail": stderr or stdout,
            "severity": "ERROR",
        }
    return {
        "name": "conda_python_version",
        "status": "PASS",
        "message": f"Conda env python: {version}",
        "detail": conda_python,
        "severity": "INFO",
    }


def _check_jax_devices() -> dict[str, Any]:
    """Import jax in the isolated conda env and list devices (no model run)."""
    conda_python = EVOBIND2_ENV_PYTHON
    script = (
        "import json, sys; "
        "import jax; "
        "devices = [str(d) for d in jax.devices()]; "
        "print(json.dumps({'version': jax.__version__, 'devices': devices}))"
    )
    env = {
        "PYTHONPATH": f"{EVOBIND2_ROOT}/src:{EVOBIND2_ROOT}/src/AF2:{os.environ.get('PYTHONPATH', '')}",
    }
    ok, stdout, stderr = _run_cmd([conda_python, "-c", script], timeout=60, env=env)
    if not ok or not stdout.strip():
        return {
            "name": "jax_devices",
            "status": "DEGRADED",
            "message": "JAX import/device probe failed",
            "detail": stderr or stdout,
            "severity": "WARNING",
        }
    try:
        data = json.loads(stdout.strip().splitlines()[-1])
        devices = data.get("devices", [])
        version = data.get("version", "unknown")
        return {
            "name": "jax_devices",
            "status": "PASS",
            "message": f"JAX {version} sees {len(devices)} device(s)",
            "detail": json.dumps(devices),
            "severity": "INFO",
        }
    except json.JSONDecodeError:
        return {
            "name": "jax_devices",
            "status": "DEGRADED",
            "message": "JAX probe output could not be parsed",
            "detail": stdout,
            "severity": "WARNING",
        }


def _check_nvidia_smi() -> dict[str, Any]:
    """Run nvidia-smi (no GPU workload)."""
    if not shutil.which("nvidia-smi"):
        return {
            "name": "nvidia_smi",
            "status": "DEGRADED",
            "message": "nvidia-smi not found in PATH",
            "detail": "",
            "severity": "WARNING",
        }
    ok, stdout, stderr = _run_cmd(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], timeout=15)
    if not ok:
        return {
            "name": "nvidia_smi",
            "status": "DEGRADED",
            "message": "nvidia-smi returned non-zero",
            "detail": stderr,
            "severity": "WARNING",
        }
    lines = [line.strip() for line in (stdout + stderr).strip().splitlines() if line.strip()]
    return {
        "name": "nvidia_smi",
        "status": "PASS",
        "message": f"nvidia-smi reports {len(lines)} GPU(s)",
        "detail": "; ".join(lines[:2]),
        "severity": "INFO",
    }


# ---------------------------------------------------------------------------
# Readiness probe (P2B1) — kept for backwards compatibility
# ---------------------------------------------------------------------------


def probe_readiness() -> dict[str, Any]:
    """Probe environment readiness without running the model.

    Returns a dict with:
        - overall_status: READY_FOR_DRY_RUN | READY_FOR_PROBE | BLOCKED_FOR_REAL_RUN
        - real_run_enabled: bool
        - checks: dict of per-item bools
        - missing: list of str
    """
    checks: dict[str, bool] = {}
    missing: list[str] = []

    def _check(name: str, path: str) -> None:
        exists = os.path.exists(path)
        checks[name] = exists
        if not exists:
            missing.append(name)

    _check("evobind2_source", EVOBIND2_ROOT)
    _check("mc_design_py", f"{EVOBIND2_ROOT}/src/mc_design.py")
    _check("af2_data_dir", AF2_DATA_DIR)
    _check("af2_params_dir", AF2_PARAMS_DIR)
    _check("af2_params_symlink", f"{AF2_DATA_DIR}/params")
    _check("hhblits_binary", HHBLITS_BIN)
    _check("uniref30_dir", UNIREF30_DIR)
    _check("conda_env_python", EVOBIND2_ENV_PYTHON)

    if missing:
        overall = "BLOCKED_FOR_REAL_RUN"
    elif EVOBIND2_PROBE_ENABLED:
        overall = "READY_FOR_PROBE"
    else:
        overall = "BLOCKED_FOR_REAL_RUN"

    return {
        "overall_status": overall,
        "real_run_enabled": EVOBIND2_REAL_RUN_ENABLED,
        "probe_enabled": EVOBIND2_PROBE_ENABLED,
        "checks": checks,
        "missing": missing,
    }


# ---------------------------------------------------------------------------
# Full probe (P2C)
# ---------------------------------------------------------------------------


def probe() -> dict[str, Any]:
    """Run a full read-only environment probe.

    This function NEVER runs EvoBind2, HHblits searches, AlphaFold2 forward
    passes, or generates MSA/candidate/PDB/scientific outputs.  It only checks
    filesystem paths and runs lightweight help/version/import commands in the
    isolated conda environment.
    """
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []
    errors: list[str] = []
    warnings.extend(EVOBIND2_PATHS.legacy_fallback_warnings)

    # Path checks
    path_checks = [
        ("evobind2_source", EVOBIND2_ROOT, False),
        ("mc_design_py", f"{EVOBIND2_ROOT}/src/mc_design.py", False),
        ("af2_data_dir", AF2_DATA_DIR, False),
        ("af2_params_dir", AF2_PARAMS_DIR, False),
        ("hhblits_binary", HHBLITS_BIN, True),
        ("uniref30_dir", UNIREF30_DIR, False),
        ("conda_env_python", EVOBIND2_ENV_PYTHON, True),
    ]
    for name, path, executable in path_checks:
        check = _check_path(name, path, executable)
        checks.append(check)
        if check["severity"] == "ERROR":
            errors.append(check["message"])
        elif check["severity"] == "WARNING":
            warnings.append(check["message"])

    # AF2 params models
    checks.append(_check_af2_params())

    # mc_design.py static checks
    checks.append(_check_mc_design_static())

    # HHblits help
    hhblits_check = _check_hhblits_help()
    checks.append(hhblits_check)

    # UniRef30
    uniref_check = _check_uniref30()
    checks.append(uniref_check)

    # Conda python version
    py_check = _check_conda_python_version()
    checks.append(py_check)

    # JAX devices (in conda env)
    jax_check = _check_jax_devices()
    checks.append(jax_check)

    # nvidia-smi
    nvidia_check = _check_nvidia_smi()
    checks.append(nvidia_check)

    # Categorize failures
    critical_names = {
        "evobind2_source",
        "mc_design_py",
        "af2_data_dir",
        "af2_params_dir",
        "af2_params_models",
        "conda_env_python",
    }
    failed_critical = [c for c in checks if c["name"] in critical_names and c["status"] == "FAIL"]
    failed_any = [c for c in checks if c["status"] == "FAIL"]
    degraded_any = [c for c in checks if c["status"] == "DEGRADED"]

    if failed_critical:
        status = "UNAVAILABLE"
    elif failed_any or degraded_any:
        status = "DEGRADED"
    else:
        status = "AVAILABLE"

    install_status = "INSTALL_COMPLETE" if not failed_critical else "INSTALL_INCOMPLETE"
    dry_run_status = "READY_FOR_DRY_RUN" if status in ("AVAILABLE", "DEGRADED") and not failed_critical else "BLOCKED"
    real_run_status = "BLOCKED"  # Always blocked in this phase

    # GPU devices from JAX probe
    gpu_devices: list[dict[str, Any]] = []
    if jax_check["status"] == "PASS":
        try:
            devices = json.loads(jax_check["detail"])
            for idx, dev in enumerate(devices):
                gpu_devices.append({"id": idx, "name": str(dev)})
        except (json.JSONDecodeError, TypeError):
            gpu_devices = []

    resolved_paths = {
        "evobind2_root": EVOBIND2_ROOT,
        "mc_design_py": f"{EVOBIND2_ROOT}/src/mc_design.py",
        "af2_data_dir": AF2_DATA_DIR,
        "af2_params_dir": AF2_PARAMS_DIR,
        "uniref30_dir": UNIREF30_DIR,
        "uniref30_prefix": UNIREF30_PREFIX,
        "hhblits_bin": HHBLITS_BIN,
        "conda_env_python": EVOBIND2_ENV_PYTHON,
        "storage_root": EVOBIND2_PATHS.storage_root,
        "cache_dir": EVOBIND2_PATHS.cache_dir,
        "artifact_dir": EVOBIND2_PATHS.artifact_dir,
        "path_sources": EVOBIND2_PATHS.sources,
        "note": "internal engineering paths",
    }

    safety_flags = {
        "real_run_enabled": EVOBIND2_REAL_RUN_ENABLED,
        "executed_model": False,
        "executed_hhblits_search": False,
        "generated_msa": False,
        "generated_candidates": False,
        "generated_pdb": False,
        "is_candidate_generation": False,
        "is_scientific_result": False,
        "runs_model": False,
        "generates_candidates": False,
        "experimental_validation": False,
        "computational_prediction_only": True,
    }

    return {
        "status": status,
        "dry_run_status": dry_run_status,
        "real_run_status": real_run_status,
        "install_status": install_status,
        "checks": checks,
        "warnings": warnings,
        "errors": errors,
        "resolved_paths": resolved_paths,
        "gpu_devices": gpu_devices,
        "safety_flags": safety_flags,
        "real_run_enabled": EVOBIND2_REAL_RUN_ENABLED,
        "executed_model": False,
        "executed_hhblits_search": False,
        "generated_msa": False,
        "generated_candidates": False,
        "generated_pdb": False,
        "is_candidate_generation": False,
        "is_scientific_result": False,
        "runs_model": False,
        "generates_candidates": False,
        "experimental_validation": False,
        "computational_prediction_only": True,
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    }


# ---------------------------------------------------------------------------
# Phase 8 input validation
# ---------------------------------------------------------------------------


def validate_run_id_local(run_id: str) -> tuple[bool, str | None]:
    """Delegate run_id validation to the gate module."""
    return validate_run_id(run_id)


def validate_fasta_local(receptor_fasta: str) -> tuple[bool, str | None]:
    """Validate receptor FASTA content locally (no server access)."""
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


def validate_model_name(name: str) -> tuple[bool, str | None]:
    """Validate model name against whitelist / blacklist.

    Returns:
        (is_valid, error_message)
    """
    if name in BLOCKED_MODEL_NAMES:
        return False, (
            f"{name} parameter exists but current EvoBind2 "
            "mc_design.py/config.py path does not support it."
        )
    if name not in ALLOWED_MODEL_NAMES:
        return False, f"Invalid model name: {name}. Allowed: {ALLOWED_MODEL_NAMES}"
    return True, None


def validate_peptide_sequence(
    peptide_sequence: str | None,
    peptide_length: int,
    required: bool = True,
) -> tuple[bool, str | None]:
    """Validate a user-provided peptide sequence for predict_only mode.

    Rules when required=True (predict_only):
      - must be a non-empty string
      - must contain only standard amino-acid letters or X
      - length must equal peptide_length
      - peptide_length must be between MIN_PEPTIDE_LENGTH and MAX_PEPTIDE_LENGTH_DRY_RUN

    Returns (is_valid, error_message).
    """
    if not (MIN_PEPTIDE_LENGTH <= peptide_length <= MAX_PEPTIDE_LENGTH_DRY_RUN):
        return False, (
            f"peptide_length must be between {MIN_PEPTIDE_LENGTH} and "
            f"{MAX_PEPTIDE_LENGTH_DRY_RUN}, got {peptide_length}"
        )

    if peptide_sequence is None or peptide_sequence == "":
        if required:
            return False, "peptide_sequence is required for predict_only mode"
        return True, None

    if not isinstance(peptide_sequence, str):
        return False, "peptide_sequence must be a string"

    if not AMINO_ACID_PATTERN.match(peptide_sequence):
        return False, "peptide_sequence contains invalid characters"

    if len(peptide_sequence) != peptide_length:
        return False, (
            f"peptide_sequence length ({len(peptide_sequence)}) must equal "
            f"peptide_length ({peptide_length})"
        )

    return True, None


def validate_input_local(inp: EvoBind2Input) -> tuple[bool, str | None]:
    """Validate EvoBind2Input with Phase 9A hard limits."""
    ok, error = validate_run_id(inp.run_id)
    if not ok:
        return False, error

    ok, error = validate_fasta_local(inp.receptor_fasta)
    if not ok:
        return False, error

    ok, error = validate_model_name(inp.model_name)
    if not ok:
        return False, error

    if not (1 <= inp.max_recycles <= MAX_MAX_RECYCLES):
        return False, f"max_recycles must be 1..{MAX_MAX_RECYCLES}, got {inp.max_recycles}"

    if not (1 <= inp.num_iterations <= MAX_NUM_ITERATIONS):
        return False, (
            f"num_iterations must be 1..{MAX_NUM_ITERATIONS}, got {inp.num_iterations}"
        )

    # Phase 9A: predict_only requires an explicit peptide_sequence.
    if inp.mode == "predict_only":
        ok, error = validate_peptide_sequence(inp.peptide_sequence, inp.peptide_length)
        if not ok:
            return False, error
    elif inp.mode == "design":
        return False, "Design mode is not yet supported. Use predict_only."

    return True, None


# ---------------------------------------------------------------------------
# Path / directory helpers
# ---------------------------------------------------------------------------


def normalize_output_dir(path: str) -> str:
    """Ensure output_dir ends with exactly one '/'.

    Prevents the 'outputmetrics.csv' concatenation bug.
    """
    return path.rstrip("/\\") + "/"


def build_run_paths(run_id: str) -> dict[str, str]:
    """Construct standard run directory paths.

    Validates run_id and rejects path traversal attempts.
    """
    ok, error = validate_run_id(run_id)
    if not ok:
        raise ValueError(error)

    run_dir = f"{EVOBIND2_ARTIFACT_ROOT}/{run_id}"
    input_dir = f"{run_dir}/input"
    output_dir = normalize_output_dir(f"{run_dir}/output")
    logs_dir = f"{run_dir}/logs"

    # Path traversal sanity check: resolved path must stay under artifact root.
    try:
        resolved_run_dir = Path(run_dir).resolve()
        resolved_root = Path(EVOBIND2_ARTIFACT_ROOT).resolve()
        resolved_run_dir.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError(f"run_id '{run_id}' produces an unsafe run path: {exc}") from exc

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
# Environment builder
# ---------------------------------------------------------------------------


def build_environment(selected_gpu: int | None) -> dict[str, str]:
    """Build the environment variables required for EvoBind2 GPU execution.

    Args:
        selected_gpu: GPU index (0 or 1), or None for CPU fallback.

    Returns:
        Dict of env var name → value.
    """
    env: dict[str, str] = {
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        "TF_FORCE_GPU_ALLOW_GROWTH": "true",
        "TF_CPP_MIN_LOG_LEVEL": "2",
        "PYTHONPATH": f"{EVOBIND2_ROOT}/src:{EVOBIND2_ROOT}/src/AF2:${{PYTHONPATH:-}}",
        "PATH": f"{os.path.dirname(HHBLITS_BIN)}:${{PATH:-}}",
        # Phase 9A: keep transient files under the project cache tmp root.
        "TMPDIR": "/home/xh/kxc/stampup/cache/tmp",
        "HOME": "/home/xh/kxc/stampup/cache/tmp",
    }

    if selected_gpu is not None:
        env["CUDA_VISIBLE_DEVICES"] = str(selected_gpu)
    # NOTE: never set CUDA_VISIBLE_DEVICES="" here — that would break JAX GPU.

    return env


# ---------------------------------------------------------------------------
# Command builder
# ---------------------------------------------------------------------------


def build_mc_design_command(
    paths: dict[str, str],
    inp: EvoBind2Input,
) -> list[str]:
    """Construct the mc_design.py command as a list of arguments.

    Args:
        paths: Result of build_run_paths().
        inp: Validated EvoBind2Input.

    Returns:
        Command tokens (suitable for subprocess or display).
    """
    cmd: list[str] = [
        EVOBIND2_ENV_PYTHON,
        f"{EVOBIND2_ROOT}/src/mc_design.py",
        f"--receptor_fasta_path={paths['receptor_fasta_path']}",
        f"--peptide_length={inp.peptide_length}",
        f"--output_dir={paths['output_dir']}",
        f"--model_names={inp.model_name}",
        f"--data_dir={AF2_DATA_DIR}",
        f"--max_recycles={inp.max_recycles}",
        f"--num_iterations={inp.num_iterations}",
        f"--predict_only={str(inp.mode == 'predict_only').capitalize()}",
    ]

    if inp.mode == "predict_only":
        # Phase 9A: predict_only REQUIRES an explicit user-provided peptide_sequence.
        # The wrapper validation guarantees it is present and valid before this point.
        cmd.append(f"--peptide_sequence={inp.peptide_sequence}")
    elif inp.peptide_sequence:
        cmd.append(f"--peptide_sequence={inp.peptide_sequence}")

    if inp.receptor_msa_a3m:
        cmd.append(f"--msas={paths['receptor_msa_path']}")

    return cmd


# ---------------------------------------------------------------------------
# Dry-run planner
# ---------------------------------------------------------------------------


def dry_run_plan(inp: EvoBind2Input) -> EvoBind2Output:
    """Plan an EvoBind2 run without executing it.

    Returns:
        EvoBind2Output with paths, env preview, command preview, and safety flags.
    """
    # Phase 8: validate all inputs with hard limits before planning.
    valid, error = validate_input_local(inp)
    if not valid:
        return EvoBind2Output(
            run_id=inp.run_id if isinstance(inp.run_id, str) else "",
            status="BLOCKED",
            mode=inp.mode if isinstance(inp.mode, str) else "predict_only",
            model_name=inp.model_name if isinstance(inp.model_name, str) else DEFAULT_MODEL_NAME,
            used_gpu=False,
            error_message=error,
            safety_flags=_default_safety_flags(),
        )

    # Block design mode for now
    if inp.mode != "predict_only":
        return EvoBind2Output(
            run_id=inp.run_id,
            status="BLOCKED",
            mode=inp.mode,
            model_name=inp.model_name,
            used_gpu=False,
            error_message="Design mode is not yet supported. Use predict_only.",
            safety_flags=_default_safety_flags(),
        )

    # Resolve GPU
    selected_gpu: int | None = None
    if inp.use_gpu:
        if isinstance(inp.selected_gpu, int):
            selected_gpu = inp.selected_gpu
        else:
            # "auto" placeholder — real implementation would probe nvidia-smi
            selected_gpu = 0

    # Build paths, env, command
    paths = build_run_paths(inp.run_id)
    env = build_environment(selected_gpu)
    command = build_mc_design_command(paths, inp)

    safety = _default_safety_flags()
    safety["is_candidate_generation"] = inp.mode == "design"

    return EvoBind2Output(
        run_id=inp.run_id,
        status="READY",
        mode=inp.mode,
        model_name=inp.model_name,
        used_gpu=inp.use_gpu and selected_gpu is not None,
        selected_gpu=selected_gpu,
        artifacts={
            "metrics_csv": paths["metrics_csv"],
            "pdb": paths["pdb"],
            "gpu_sample_csv": paths["gpu_sample_csv"],
            "run_log": paths["run_log"],
            "jax_precheck_log": paths["jax_precheck_log"],
        },
        safety_flags=safety,
        command_preview=command,
        env_preview=env,
        error_message=None,
    )


# ---------------------------------------------------------------------------
# Safety flags helper
# ---------------------------------------------------------------------------


def _default_safety_flags() -> dict[str, bool]:
    """Return the default safety flags for any EvoBind2 run."""
    return {
        "is_candidate_generation": False,
        "is_scientific_result": False,
        "uses_uniref30": False,
        "runs_model": False,
        "generates_candidates": False,
        "experimental_validation": False,
        "computational_prediction_only": True,
    }


# Backwards compatibility aliases (used by legacy tests)
EVOBIND_ROOT = EVOBIND2_ROOT
EVOBIND_SRC = EVOBIND2_ROOT
EVOBIND_ENV = CONDA_ENV_PATH
EVOBIND_DATA_DIR = AF2_DATA_DIR
