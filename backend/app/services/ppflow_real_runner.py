"""PPFlow real runner skeleton — P29F.

This module provides the *skeleton* for the future PPFlow real runner.
It defines:

* Gate check (default CLOSED / BLOCKED).
* Path construction (job_dir, artifact_dir, logs).
* CLI command template construction (without execution).
* Path validation (forbidden paths rejected).
* manifest_post schema builder.
* failure schema builder.
* ``run_ppflow_subprocess`` — **always raises** in P29F; no subprocess is
  ever spawned.

P29F does **not**:
  * execute ``codesign_ppf.py``
  * import PPFlow source
  * ``torch.load`` any checkpoint
  * run the model
  * generate candidate peptides or PDB files
  * create real job/artifact directories
  * open the real-run gate

All of these guarantees are enforced by returning BLOCKED or raising
``PPFlowRunnerBlocked`` before any I/O occurs.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
SOURCE_ROOT = MODEL_ROOT / "source" / "ppflow" / "extracted_p25_install_probe" / "ppflow-main"
CODESIGN_PP = SOURCE_ROOT / "codesign_ppf.py"
CHECKPOINT_ROOT = MODEL_ROOT / "checkpoints" / "ppflow"
DEFAULT_CHECKPOINT = CHECKPOINT_ROOT / "p25_install_probe" / "ppflow" / "pretrained.pt"
RUNTIME_ENV = MODEL_ROOT / "envs" / "ppflow_runtime_cpu_smoke"
ENV_PYTHON = RUNTIME_ENV / "bin" / "python"
GATE_FILE = MODEL_ROOT / "reports" / "ppflow" / ".ppflow_real_run_enabled"

DEV_ROOT = Path("/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev")
DATA_DEV = DEV_ROOT / "data_dev"
JOBS_BASE = DATA_DEV / "jobs" / "ppflow"
ARTIFACTS_BASE = DATA_DEV / "artifacts" / "ppflow"
LOGS_BASE = DEV_ROOT / "logs_dev" / "ppflow"

VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
DISCLAIMER = "computational prediction only; not experimentally validated"
STAGE = "P29F_RUNNER_SKELETON_ONLY"

# Forbidden path prefixes — writing or pointing out_root here is rejected.
FORBIDDEN_PREFIXES: tuple[str, ...] = (
    "/tmp",
    "/root",
    "/home/xh",
    "/home/xh/stamp",
    "/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform",
    "/home/xh/kxc/靶向肽/backups",
)

# Allowed base directories for out_root / artifact_dir.
_ALLOWED_OUT_ROOTS: tuple[Path, ...] = (
    ARTIFACTS_BASE,
    MODEL_ROOT / "artifacts" / "ppflow",
)

# Allowed base directories for source.
_ALLOWED_SOURCE_ROOTS: tuple[Path, ...] = (
    MODEL_ROOT / "source" / "ppflow",
)

# Allowed base directories for checkpoint.
_ALLOWED_CHECKPOINT_ROOTS: tuple[Path, ...] = (
    CHECKPOINT_ROOT,
)

_SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class PPFlowRunnerBlocked(Exception):
    """Raised when the runner is blocked (gate closed or path invalid)."""


# ---------------------------------------------------------------------------
# 1. Gate check
# ---------------------------------------------------------------------------

def check_gate(gate_path: Path | None = None) -> dict[str, Any]:
    """Check whether the real-run gate is open.

    The gate is **always closed** by default.  In P29F the gate file must
    not exist; if it does exist it is only honoured when its content matches
    ``enabled_{job_id}_{timestamp}``.

    Returns a dict describing the gate state.  The returned
    ``gate_open`` value is **always** ``False`` in P29F because the runner
    skeleton never opens the gate.
    """
    path = gate_path or GATE_FILE
    exists = path.is_file()
    gate_open = False
    blocked_reason = "ppflow_real_run_gate_closed"
    raw_content: str | None = None

    if exists:
        try:
            raw_content = path.read_text(encoding="utf-8").strip()
        except OSError:
            raw_content = None
        # Even if the file exists and content looks like an enable token,
        # P29F skeleton refuses to run.  We report the state but keep
        # gate_open = False.
        if raw_content and raw_content.startswith("enabled_"):
            blocked_reason = "ppflow_skeleton_refuses_even_if_gate_file_exists"
        else:
            blocked_reason = "ppflow_real_run_gate_file_exists_but_invalid"

    return {
        "gate_open": gate_open,
        "gate_path": str(path),
        "blocked_reason": blocked_reason,
        "gate_file_exists": exists,
        "gate_file_content": raw_content,
        "stage": STAGE,
    }


# ---------------------------------------------------------------------------
# 2. Path construction
# ---------------------------------------------------------------------------

def generate_job_id() -> str:
    """Generate a UUID4-based job ID (no actual job is created)."""
    return str(uuid.uuid4())


def _validate_job_id(job_id: str) -> None:
    if not job_id or ".." in job_id or not _SAFE_JOB_ID.fullmatch(job_id):
        raise ValueError(f"Invalid PPFlow job_id: {job_id!r}")


def job_dir_path(job_id: str, base: Path | None = None) -> Path:
    """Return the planned job directory path (does NOT create it)."""
    _validate_job_id(job_id)
    root = base or JOBS_BASE
    return root / job_id


def artifact_dir_path(job_id: str, base: Path | None = None) -> Path:
    """Return the planned artifact directory path (does NOT create it)."""
    _validate_job_id(job_id)
    root = base or ARTIFACTS_BASE
    return root / job_id


def log_file_path(job_id: str, base: Path | None = None) -> Path:
    """Return the planned runner log file path (does NOT create it)."""
    _validate_job_id(job_id)
    root = base or LOGS_BASE
    return root / f"{job_id}.log"


# ---------------------------------------------------------------------------
# 3. Path validation
# ---------------------------------------------------------------------------

def _is_forbidden(path: Path) -> bool:
    """Return True if *path* falls under a forbidden prefix."""
    resolved = str(path.resolve()) if path.exists() else str(path)
    for prefix in FORBIDDEN_PREFIXES:
        if resolved == prefix or resolved.startswith(prefix + "/"):
            return True
    return False


def validate_out_root(out_root: Path) -> list[str]:
    """Validate that *out_root* is in an allowed directory.

    Returns a list of violation messages (empty = valid).

    The allowed-list check takes precedence: if the path is under an
    allowed root (e.g. ``data_dev/artifacts/ppflow`` which lives under
    ``/home/xh/kxc/stampup``), it is accepted even though ``/home/xh``
    appears in the forbidden-prefix list.  This is intentional — the
    dev copy root ``/home/xh/kxc/stampup`` is a carve-out from the
    general ``/home/xh`` write ban.
    """
    errors: list[str] = []

    # 1. Check allowed roots first (carve-out for /home/xh/kxc/stampup)
    for allowed in _ALLOWED_OUT_ROOTS:
        try:
            out_root.relative_to(allowed)
            return errors  # Allowed — skip forbidden check
        except ValueError:
            continue

    # 2. Not in allowed roots — check if forbidden
    if _is_forbidden(out_root):
        errors.append(f"out_root is in a forbidden path: {out_root}")
        return errors

    # 3. Neither allowed nor explicitly forbidden
    errors.append(
        f"out_root must be under one of "
        f"{', '.join(str(a) for a in _ALLOWED_OUT_ROOTS)}; got {out_root}"
    )
    return errors


def validate_source_path(source_path: Path) -> list[str]:
    """Validate that *source_path* is under the allowed PPFlow source root."""
    errors: list[str] = []

    # Check allowed roots first
    for allowed in _ALLOWED_SOURCE_ROOTS:
        try:
            source_path.relative_to(allowed)
            return errors
        except ValueError:
            continue

    if _is_forbidden(source_path):
        errors.append(f"source_path is in a forbidden path: {source_path}")
        return errors

    errors.append(
        f"source_path must be under {MODEL_ROOT}/source/ppflow; got {source_path}"
    )
    return errors


def validate_checkpoint_path(checkpoint_path: Path) -> list[str]:
    """Validate that *checkpoint_path* is under the allowed checkpoint root."""
    errors: list[str] = []

    # Check allowed roots first
    for allowed in _ALLOWED_CHECKPOINT_ROOTS:
        try:
            checkpoint_path.relative_to(allowed)
            return errors
        except ValueError:
            continue

    if _is_forbidden(checkpoint_path):
        errors.append(f"checkpoint_path is in a forbidden path: {checkpoint_path}")
        return errors

    errors.append(
        f"checkpoint_path must be under {CHECKPOINT_ROOT}; got {checkpoint_path}"
    )
    return errors


# ---------------------------------------------------------------------------
# 4. CLI command template
# ---------------------------------------------------------------------------

def build_command(
    *,
    env_python: Path | str | None = None,
    source_root: Path | None = None,
    codesign_pp: Path | None = None,
    config_path: Path | str | None = None,
    checkpoint: Path | str | None = None,
    out_root: Path | str | None = None,
    tag: str = "925",
    seed: int | None = None,
    device: str = "cpu",
    batch_size: int = 1,
    index: int = 0,
) -> list[str]:
    """Construct the CLI command list for ``codesign_ppf.py``.

    **This function does NOT execute the command.**  It only builds the
    argument list.  Path validation is performed and violations are
    collected; if any are found, ``PPFlowRunnerBlocked`` is raised.

    The caller can inspect the returned list for logging / dry-run preview
    but must **never** pass it to ``subprocess.run`` in P29F.
    """
    py = Path(env_python) if env_python else ENV_PYTHON
    src = source_root or SOURCE_ROOT
    entry = codesign_pp or CODESIGN_PP
    ckpt = Path(checkpoint) if checkpoint else DEFAULT_CHECKPOINT
    out = Path(out_root) if out_root else ARTIFACTS_BASE / "preview"
    cfg = str(config_path) if config_path else str(src / "configs" / "test" / "codesign_ppflow.yml")

    # Validate paths
    violations: list[str] = []
    violations.extend(validate_source_path(entry.parent if entry.is_file() else entry))
    violations.extend(validate_checkpoint_path(ckpt))
    violations.extend(validate_out_root(out))

    if violations:
        raise PPFlowRunnerBlocked(
            f"Path validation failed: {'; '.join(violations)}"
        )

    cmd: list[str] = [
        str(py),
        str(entry),
        "--index", str(index),
        "-c", cfg,
        "-o", str(out),
        "-t", str(tag),
        "-d", device,
        "-b", str(batch_size),
        "-ckpt", str(ckpt),
    ]
    if seed is not None:
        cmd.extend(["-s", str(seed)])

    return cmd


# ---------------------------------------------------------------------------
# 5. manifest_post schema
# ---------------------------------------------------------------------------

def build_manifest_post(
    *,
    job_id: str,
    status: str = "planned",
    artifacts: list[dict[str, Any]] | None = None,
    notes: str = "P29F skeleton only; no PPFlow execution",
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a manifest_post dict.

    The ``status`` field accepts ``planned | blocked | succeeded | failed``.
    In P29F the status is always ``planned`` or ``blocked``.
    """
    _validate_job_id(job_id)
    if status not in ("planned", "blocked", "succeeded", "failed"):
        raise ValueError(f"Invalid manifest status: {status!r}")

    return {
        "job_id": job_id,
        "model_id": "ppflow",
        "status": status,
        "stage": STAGE,
        "validation_status": VALIDATION_STATUS,
        "disclaimer": DISCLAIMER,
        "runs_model": False,
        "generates_candidates": False,
        "generates_pdb": False,
        "experimental_validation": False,
        "is_scientific_result": False,
        "artifacts": artifacts or [],
        "created_at": created_at or datetime.now(timezone.utc).isoformat(),
        "notes": notes,
    }


# ---------------------------------------------------------------------------
# 6. failure schema
# ---------------------------------------------------------------------------

def build_failure(
    *,
    job_id: str,
    error_type: str = "gate_closed",
    message: str = "",
    traceback_str: str | None = None,
    partial_artifacts: list[str] | None = None,
) -> dict[str, Any]:
    """Build a failure dict.

    ``error_type`` must be one of:
    ``gate_closed | invalid_path | timeout | subprocess_error | unknown``.
    """
    _validate_job_id(job_id)
    valid_types = ("gate_closed", "invalid_path", "timeout", "subprocess_error", "unknown")
    if error_type not in valid_types:
        raise ValueError(f"Invalid error_type: {error_type!r}")

    return {
        "job_id": job_id,
        "model_id": "ppflow",
        "status": "blocked",
        "error_type": error_type,
        "message": message or "PPFlow runner skeleton: execution blocked",
        "traceback": traceback_str or "",
        "partial_artifacts": partial_artifacts or [],
        "validation_status": VALIDATION_STATUS,
        "runs_model": False,
        "generates_candidates": False,
        "generates_pdb": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": STAGE,
    }


# ---------------------------------------------------------------------------
# 7. Subprocess stub (NEVER executes)
# ---------------------------------------------------------------------------

def run_ppflow_subprocess(
    command: list[str],
    *,
    timeout: int = 600,
    artifact_dir: Path | None = None,
    job_id: str = "",
) -> dict[str, Any]:
    """**Stub**: always returns BLOCKED.

    In P29F this function must **never** call ``subprocess.run``.
    It always returns a failure dict indicating the gate is closed.
    """
    return build_failure(
        job_id=job_id or "unknown",
        error_type="gate_closed",
        message=(
            "PPFlow subprocess execution is blocked in P29F skeleton. "
            "The real-run gate is closed and subprocess.run was not called."
        ),
    )


# ---------------------------------------------------------------------------
# 8. Full runner plan (returns BLOCKED, never executes)
# ---------------------------------------------------------------------------

def plan_run(
    *,
    job_id: str | None = None,
    config_path: Path | str | None = None,
    checkpoint: Path | str | None = None,
    tag: str = "smoke",
    seed: int | None = None,
    device: str = "cpu",
    batch_size: int = 1,
    index: int = 0,
    out_root: Path | str | None = None,
    jobs_base: Path | None = None,
    artifacts_base: Path | None = None,
    logs_base: Path | None = None,
) -> dict[str, Any]:
    """Plan a PPFlow run without executing anything.

    Returns a dict containing:
    * ``status``: always ``"blocked"`` in P29F.
    * ``gate``: gate check result.
    * ``command_preview``: the constructed CLI command (if paths valid).
    * ``paths``: planned job/artifact/log paths (not created).
    * ``manifest_post`` / ``failure``: schema dicts.
    """
    jid = job_id or generate_job_id()
    _validate_job_id(jid)

    gate = check_gate()

    j_dir = job_dir_path(jid, base=jobs_base)
    a_dir = artifact_dir_path(jid, base=artifacts_base)
    l_file = log_file_path(jid, base=logs_base)

    out = Path(out_root) if out_root else a_dir

    # Build command preview (may raise PPFlowRunnerBlocked on invalid paths)
    try:
        cmd_preview = build_command(
            env_python=ENV_PYTHON,
            source_root=SOURCE_ROOT,
            codesign_pp=CODESIGN_PP,
            config_path=config_path,
            checkpoint=checkpoint or DEFAULT_CHECKPOINT,
            out_root=out,
            tag=tag,
            seed=seed,
            device=device,
            batch_size=batch_size,
            index=index,
        )
        path_errors: list[str] = []
    except PPFlowRunnerBlocked as exc:
        cmd_preview = []
        path_errors = [str(exc)]

    failure = build_failure(
        job_id=jid,
        error_type="gate_closed" if not path_errors else "invalid_path",
        message=(
            "PPFlow runner skeleton: execution blocked. "
            f"Gate open={gate['gate_open']}; path_errors={path_errors}"
        ),
    )
    manifest = build_manifest_post(
        job_id=jid,
        status="blocked",
        notes="P29F skeleton only; no PPFlow execution",
    )

    return {
        "status": "blocked",
        "stage": STAGE,
        "gate": gate,
        "job_id": jid,
        "paths": {
            "job_dir": str(j_dir),
            "artifact_dir": str(a_dir),
            "log_file": str(l_file),
            "out_root": str(out),
        },
        "paths_created": False,
        "command_preview": cmd_preview,
        "path_errors": path_errors,
        "manifest_post": manifest,
        "failure": failure,
        "runs_model": False,
        "generates_candidates": False,
        "generates_pdb": False,
        "validation_status": VALIDATION_STATUS,
        "subprocess_called": False,
        "codesign_ppf_executed": False,
        "imports_ppflow_source": False,
        "uses_torch_load": False,
        "real_run_enabled": False,
    }
