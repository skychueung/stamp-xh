"""STAMP Platform — Job Failure Diagnosis Service (v1.5).

Provides human-readable failure diagnosis for BLOCKED / FAILED / 422 / CONFIG_REQUIRED
jobs across all supported compute types (MD, FlexPepDock, MM-GBSA, LIMS, etc.).

Design principles:
- Never fabricate root causes.
- Parse error_message and error_json to infer error_category.
- Return actionable fix suggestions scoped to the job_type.
- Include related log paths and artifact hints when available.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.models.orm import Job

logger = logging.getLogger("stamp")

# ---------------------------------------------------------------------------
# Error taxonomy
# ---------------------------------------------------------------------------

ERROR_CATEGORIES = {
    "tool_missing",
    "input_missing",
    "invalid_parameter",
    "command_failed",
    "artifact_missing",
    "permission_denied",
    "storage_unwritable",
    "gpu_locked",
    "external_api_failed",
    "unknown",
}

# Keyword → category mappings (ordered by specificity — more specific first)
_KEYWORD_PATTERNS: list[tuple[re.Pattern, str]] = [
    # GPU lock
    (re.compile(r"gpu[_\s]?lock|gpu_lock|gpu.*unavailable|cuda.*out of memory", re.I), "gpu_locked"),
    # External API failed (must come before command_failed to avoid "ssh command failed" being classified as command_failed)
    (re.compile(r"sidecar.*error|sidecar.*timeout|sidecar.*unavailable|http error|connection refused|external api|server unreachable|ssh.*failed|scp.*failed", re.I), "external_api_failed"),
    # Tool / command missing
    (re.compile(r"command not found|not found in path|binary not found|env script not found|conda env not found|(?:gmx|rosetta|colabfold|foldx|gmx_mmpbsa)\s+not\s+found", re.I), "tool_missing"),
    # Input missing
    (re.compile(r"input_.*not found|missing input|not found:\s*\S*\.(pdb|fasta|cif|gro|top|mdp)|receptor_pdb not found|peptide_pdb not found|result_dir required|sequence must be", re.I), "input_missing"),
    # Invalid parameter
    (re.compile(r"input validation failed|invalid parameter|validation failed|pydantic|required field|must be at least|type error|bad request|422", re.I), "invalid_parameter"),
    # Command failed (non-zero return code)
    (re.compile(r"command failed|non-zero|returncode|rc=\d+|subprocess.*error|smoke test failed|execution failed", re.I), "command_failed"),
    # Artifact missing
    (re.compile(r"missing output|no real artifacts|artifact directory empty|missing output files|silent file not found|scorefile not found", re.I), "artifact_missing"),
    # Permission denied
    (re.compile(r"permission denied|access denied|unauthorized|forbidden|403", re.I), "permission_denied"),
    # Storage unwritable
    (re.compile(r"read-only|cannot write|disk full|no space left|i/o error|storage_unwritable", re.I), "storage_unwritable"),
]

# ---------------------------------------------------------------------------
# Job-type-specific diagnosis knowledge base
# ---------------------------------------------------------------------------

_JOB_TYPE_HINTS: dict[str, dict] = {
    "epitope_scan": {
        "tool_missing": "BepiPred3 sidecar or required Python packages are missing. Verify the sidecar is running and accessible.",
        "input_missing": "Target protein sequence or required parameters are missing. Check the input form and re-submit.",
        "external_api_failed": "BepiPred3 sidecar returned an error or is unreachable. Check sidecar logs and network connectivity.",
    },
    "peptide_generation": {
        "tool_missing": "PepMLM sidecar or model files are missing. Ensure the sidecar service is deployed and models are loaded.",
        "input_missing": "Epitope sequence or epitope_id is missing. Provide a valid epitope sequence or select an existing epitope candidate.",
        "external_api_failed": "PepMLM sidecar returned an error or timed out. Check sidecar health and GPU availability.",
    },
    "stamp_assembly": {
        "input_missing": "Required targeting peptide or linker sequence is missing. Verify all input fields are filled.",
        "invalid_parameter": "Assembly parameters failed validation. Check sequence lengths and allowed characters.",
    },
    "bepipred3_scan": {
        "tool_missing": "BepiPred3 sidecar is not reachable. Start the sidecar service or check the configured sidecar_url.",
        "input_missing": "Target protein sequence could not be resolved. Ensure target_protein_id is valid or provide the sequence directly.",
        "external_api_failed": "BepiPred3 sidecar HTTP error or timeout. Check sidecar_url, network, and sidecar logs.",
    },
    "pepmlm_generation": {
        "tool_missing": "PepMLM sidecar is not reachable. Start the sidecar service or check the configured sidecar_url.",
        "input_missing": "epitope_sequence or epitope_id is required. Provide a valid epitope sequence.",
        "external_api_failed": "PepMLM sidecar HTTP error or timeout. Check sidecar_url, network, GPU, and sidecar logs.",
    },
    "structure_prediction": {
        "tool_missing": "LocalColabFold or required dependencies are not installed. Install colabfold_batch and verify PATH.",
        "input_missing": "result_dir is required in input_json. Provide a valid directory containing AlphaFold outputs.",
        "artifact_missing": "Expected metrics files (e.g. rankings_*.json) not found in result_dir. Ensure the prediction completed successfully.",
    },
    "complex_structure_prediction": {
        "input_missing": "target_sequence and peptide_sequence are required. Provide both sequences in input_json.",
        "invalid_parameter": "Chain IDs or sequence format is invalid. Use standard single-letter amino-acid codes.",
    },
    "production_md": {
        "tool_missing": "GROMACS (gmx) or the stamp-md conda environment is missing. Run: conda env create -f environment-md.yml",
        "input_missing": "input_pdb is required and must exist. Provide a valid PDB file path.",
        "command_failed": "GROMACS command returned non-zero. Check the log file for forcefield mismatches or missing residues.",
        "gpu_locked": "GPU is locked by another MD job. Wait for the current job to finish or release the GPU lock manually.",
        "artifact_missing": "Expected trajectory or analysis files were not produced. Check if the simulation crashed during production.",
    },
    "flexpepdock": {
        "tool_missing": "Rosetta FlexPepDock binary or environment script is missing. Source the Rosetta environment script.",
        "input_missing": "receptor_pdb or peptide structure is missing. Provide valid PDB file paths.",
        "command_failed": "FlexPepDock execution returned non-zero. Check the log for Rosetta errors or missing flags.",
        "external_api_failed": "SSH/SCP to the lab server failed. Verify network connectivity, SSH keys, and server status (192.168.31.218).",
        "artifact_missing": "Scorefile or silent file was not produced. Check if the docking run crashed or nstruct was too low.",
    },
    "mmgbsa": {
        "tool_missing": "gmx_MMPBSA or AmberTools is not installed. Install via conda: conda install -c conda-forge gmx-mmpbsa",
        "input_missing": "Required topology or trajectory files are missing. Ensure prior MD steps completed and produced prmtop/mdcrd.",
        "command_failed": "gmx_MMPBSA calculation failed. Check input parameters and ensure the trajectory covers enough frames.",
        "artifact_missing": "Expected ΔG output files were not produced. Check the calculation log for energy term errors.",
    },
    "colamfold": {
        "tool_missing": "colabfold_batch is not in PATH. Install LocalColabFold and add it to the system PATH.",
        "input_missing": "A valid FASTA sequence is required. Provide a sequence of at least 5 residues.",
        "gpu_locked": "GPU is occupied by another ColabFold job. Wait or cancel the running job.",
    },
    "foldx": {
        "tool_missing": "FoldX binary is not in PATH. Install FoldX and configure the license.",
        "input_missing": "PDB file is required for FoldX energy calculation. Provide a valid PDB path.",
        "command_failed": "FoldX returned an error. Check the Rotabase.txt license and input PDB format.",
    },
    "lims_sync": {
        "tool_missing": "LIMS connector module is missing. Install the required LIMS SDK or client library.",
        "external_api_failed": "LIMS API returned an error or is unreachable. Check base_url, auth token, and network.",
        "permission_denied": "LIMS API credentials are invalid or expired. Renew the token or check field mappings.",
        "invalid_parameter": "Field mapping validation failed. Review the integration configuration and required fields.",
    },
}

_GENERIC_HINTS: dict[str, str] = {
    "tool_missing": "Required software or environment is not installed or not in PATH. Install the missing tool and verify with a smoke test.",
    "input_missing": "One or more required input files or parameters are missing. Review the job input_json and re-submit with complete data.",
    "invalid_parameter": "Input parameters failed validation. Check the error details, correct the values, and retry.",
    "command_failed": "The compute command returned a non-zero exit code. Inspect the associated log file for the exact error message.",
    "artifact_missing": "Expected output files were not produced. This usually means the compute step crashed before writing results.",
    "permission_denied": "The process lacks permission to access a file, directory, or API. Check ownership, chmod, or API credentials.",
    "storage_unwritable": "The output directory is read-only or the disk is full. Free disk space or change the output path.",
    "gpu_locked": "GPU is currently held by another job. Wait for it to complete or manually release the lock file.",
    "external_api_failed": "An external service (sidecar, server, LIMS) returned an error or is unreachable. Check network and service health.",
    "unknown": "The root cause could not be determined automatically. Review the raw error_message and system logs.",
}

_FIX_SUGGESTIONS: dict[str, list[str]] = {
    "tool_missing": [
        "Verify the required software is installed and available in PATH.",
        "Run the environment smoke-test endpoint (if available) to confirm readiness.",
        "For conda environments, ensure the env is activated or use 'conda run -n <env>'.",
    ],
    "input_missing": [
        "Check that all required input files exist at the specified paths.",
        "Re-upload missing files or regenerate them from upstream steps.",
        "Validate FASTA/PDB format if sequence/structure inputs are involved.",
    ],
    "invalid_parameter": [
        "Review the validation error details in error_message.",
        "Correct the parameter values and retry the job.",
        "Consult the job-type documentation for allowed parameter ranges.",
    ],
    "command_failed": [
        "Open the job log file (see Related Logs) and read the last 50 lines.",
        "Check for missing forcefields, unknown residues, or syntax errors.",
        "Re-run with dry_run=True if supported, to inspect the command sequence.",
    ],
    "artifact_missing": [
        "Check whether the compute process was killed (OOM, timeout, manual cancel).",
        "Verify the output path is writable and has enough disk space.",
        "Re-run the job; if it consistently fails, escalate as a tool/environment issue.",
    ],
    "permission_denied": [
        "Check file/directory ownership and permissions (ls -l / chmod).",
        "For API access, verify the token or API key is valid and not expired.",
        "Run the process as a user with sufficient privileges.",
    ],
    "storage_unwritable": [
        "Check disk usage with df -h and free space if needed.",
        "Ensure the output directory is not mounted read-only.",
        "Change the artifact_dir to a writable location.",
    ],
    "gpu_locked": [
        "Check which job holds the GPU lock via the health/queue endpoint.",
        "Wait for the holder job to finish, or cancel it if stuck.",
        "Manually remove the lock file if it is stale (older than 1 hour).",
    ],
    "external_api_failed": [
        "Ping the external service to confirm network connectivity.",
        "Check the service health endpoint or logs for outages.",
        "Verify credentials, URLs, and firewall rules.",
    ],
    "unknown": [
        "Review the full error_message and output_json manually.",
        "Check system logs (syslog, dmesg) for hardware or kernel issues.",
        "Escalate to the platform admin with the job ID and timestamps.",
    ],
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_category(error_message: str | None, error_json: dict | None) -> str:
    """Infer the error category from error_message and error_json."""
    text = ""
    if error_message:
        text += error_message + " "
    if isinstance(error_json, dict):
        text += " ".join(str(v) for v in error_json.values() if v is not None)

    if not text.strip():
        return "unknown"

    for pattern, category in _KEYWORD_PATTERNS:
        if pattern.search(text):
            return category

    return "unknown"


def _build_cause(error_category: str, job_type: str, error_message: str | None) -> str:
    """Build a human-readable root-cause sentence."""
    type_hint = _JOB_TYPE_HINTS.get(job_type, {}).get(error_category)
    if type_hint:
        return type_hint
    generic = _GENERIC_HINTS.get(error_category, _GENERIC_HINTS["unknown"])
    return generic


def _build_suggestions(error_category: str, job_type: str) -> list[str]:
    """Return actionable fix suggestions."""
    base = list(_FIX_SUGGESTIONS.get(error_category, _FIX_SUGGESTIONS["unknown"]))

    # Job-type-specific extra suggestions
    if job_type == "production_md" and error_category == "tool_missing":
        base.append("Also verify that the 'stamp-md' conda environment exists: conda env list | grep stamp-md")
    elif job_type == "flexpepdock" and error_category == "external_api_failed":
        base.append("Verify SSH key-based auth to xh@192.168.31.218 works from the app server.")
    elif job_type in ("pepmlm_generation", "bepipred3_scan") and error_category == "external_api_failed":
        base.append("Check the sidecar_url in input_json and confirm the sidecar process is running.")
    elif job_type == "lims_sync" and error_category == "permission_denied":
        base.append("Review the integration configuration page and re-test the connection.")

    return base


def _guess_log_paths(job: Job) -> list[str]:
    """Guess likely log file paths based on job metadata."""
    logs: list[str] = []

    # From output_json hints
    output = job.output_json or {}
    for key in ("log_path", "local_log", "remote_log", "stdout_log", "stderr_log"):
        val = output.get(key)
        if val and isinstance(val, str):
            logs.append(val)

    # From artifact_dir or workdir hints
    artifact_dir = output.get("workdir") or output.get("artifact_dir") or output.get("remote_workdir")
    if artifact_dir and isinstance(artifact_dir, str):
        import os
        for fname in ("stdout.log", "stderr.log", "job.log", "run.log", "flexpepdock.log", "md.log"):
            candidate = os.path.join(artifact_dir, "logs", fname)
            if candidate not in logs:
                logs.append(candidate)

    # From batch_dir_service convention
    from app.services.batch_dir_service import get_item_log_path
    if job.batch_id and job.id:
        try:
            for stream in ("stdout", "stderr"):
                p = get_item_log_path(job.batch_id, job.id, stream)
                if p and p not in logs:
                    logs.append(p)
        except Exception:
            pass

    return logs


def _guess_artifacts(job: Job) -> list[dict]:
    """Guess likely artifact files based on job metadata."""
    artifacts: list[dict] = []
    output = job.output_json or {}
    artifacts_json = job.artifacts_json or {}

    # Direct artifact references
    for key in ("scorefile_path", "silent_file_path", "pdb_path", "trajectory_path", "report_path"):
        val = output.get(key)
        if val and isinstance(val, str):
            artifacts.append({"type": key.replace("_path", ""), "path": val})

    # From artifacts_json
    if isinstance(artifacts_json, dict):
        for k, v in artifacts_json.items():
            if isinstance(v, str):
                artifacts.append({"type": k, "path": v})
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        artifacts.append({"type": k, "path": item})

    return artifacts


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def diagnose_job(job: Job) -> dict:
    """Diagnose a single job failure and return a structured report.

    Returns:
        Dict with keys:
          - job_id: str
          - job_type: str
          - status: str
          - error_category: str (one of ERROR_CATEGORIES)
          - cause: str (human-readable root cause)
          - suggestions: list[str] (actionable fixes)
          - related_logs: list[str] (likely log file paths)
          - related_artifacts: list[dict] (likely artifact file paths)
          - raw_error_message: str | None
          - raw_error_json: dict | None
    """
    if job is None:
        raise ValueError("Job is required for diagnosis")

    error_message = job.error_message
    error_json = job.error_json or {}
    error_category = _detect_category(error_message, error_json)
    cause = _build_cause(error_category, job.job_type, error_message)
    suggestions = _build_suggestions(error_category, job.job_type)
    related_logs = _guess_log_paths(job)
    related_artifacts = _guess_artifacts(job)

    return {
        "job_id": job.id,
        "job_type": job.job_type,
        "status": job.status,
        "error_category": error_category,
        "cause": cause,
        "suggestions": suggestions,
        "related_logs": related_logs,
        "related_artifacts": related_artifacts,
        "raw_error_message": error_message,
        "raw_error_json": error_json if isinstance(error_json, dict) else {},
    }


def diagnose_job_by_id(db: Session, job_id: str) -> dict | None:
    """Fetch a job and diagnose it. Returns None if job not found."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        return None
    return diagnose_job(job)
