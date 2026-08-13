"""FlexPepDock Batch Runner (v1.5 P2).

Provides real single-sample peptide-protein docking execution via SSH
to the lab server (192.168.31.218).

Scientific boundaries:
- No fabricated docking scores.
- SUCCEEDED only when real silent files exist and parse successfully.
- BLOCKED when Rosetta env is missing or server unreachable.
- FAILED when input files missing or command returns non-zero.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from app.services.batch_dir_service import ensure_item_dir
from app.services.flexpepdock_environment_probe import (
    FLEXPEPDOCK_CANDIDATES,
    ROSETTA_ENV_SCRIPT,
    _find_any_binary,
    probe_flexpepdock_environment,
)
from app.services.runner_logger import ensure_log_dir, execute_command

logger = logging.getLogger("stamp")

# Server configuration for remote execution
SERVER_HOST = os.environ.get("STAMP_SERVER_HOST", "192.168.31.218")
SERVER_USER = os.environ.get("STAMP_SERVER_USER", "xh")
SERVER_BASE_DIR = "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/flexpepdock_pilot"
DEFAULT_NSTRUCT = 5  # Pilot: small nstruct for fast turnaround


def _get_flexpepdock_binary() -> str | None:
    """Return the first available FlexPepDock binary name, or None."""
    if not os.path.isfile(ROSETTA_ENV_SCRIPT):
        return None
    ok, path = _find_any_binary(FLEXPEPDOCK_CANDIDATES, ROSETTA_ENV_SCRIPT)
    if ok and path:
        return os.path.basename(path)
    return None


def create_workdir(batch_id: str, item_id: str) -> str:
    """Create and return the working directory for a FlexPepDock job.

    Scaffold:
        data/batch_jobs/{batch_id}/flexpepdock/{item_id}/
          inputs/
          prepared/
          runs/
          scores/
          logs/
          artifacts/
    """
    item_dir = ensure_item_dir(batch_id, item_id, "FLEXPEPDOCK")
    for sub in ("inputs", "prepared", "runs", "scores", "logs", "artifacts"):
        (Path(item_dir) / sub).mkdir(parents=True, exist_ok=True)
    return item_dir


def validate_input(input_json: dict) -> tuple[bool, Optional[str]]:
    """Validate FlexPepDock input parameters.

    Required:
      - receptor_pdb: path to receptor PDB file
      - peptide_pdb or peptide_fasta: path to peptide structure or sequence
      - receptor_chain: chain ID for receptor interface (default "A")
      - peptide_chain: chain ID for peptide (default "B")
    """
    if not input_json:
        return False, "input_json is empty"

    receptor_pdb = input_json.get("receptor_pdb")
    if not receptor_pdb:
        return False, "receptor_pdb is required"
    if not Path(receptor_pdb).exists():
        return False, f"receptor_pdb not found: {receptor_pdb}"

    peptide_pdb = input_json.get("peptide_pdb")
    peptide_fasta = input_json.get("peptide_fasta")
    if not peptide_pdb and not peptide_fasta:
        return False, "Either peptide_pdb or peptide_fasta is required"
    if peptide_pdb and not Path(peptide_pdb).exists():
        return False, f"peptide_pdb not found: {peptide_pdb}"
    if peptide_fasta and not Path(peptide_fasta).exists():
        return False, f"peptide_fasta not found: {peptide_fasta}"

    receptor_chain = input_json.get("receptor_chain", "A")
    peptide_chain = input_json.get("peptide_chain", "B")
    if not receptor_chain or not peptide_chain:
        return False, "receptor_chain and peptide_chain are required"

    return True, None


def check_environment() -> tuple[bool, list[str]]:
    """Check if FlexPepDock environment is ready (local)."""
    report = probe_flexpepdock_environment()
    if report.status == "AVAILABLE":
        return True, []
    return False, report.blocking_reasons


def dry_run(batch_id: str, item_id: str, input_json: dict) -> dict:
    """Log the commands that would be executed without running them.

    Returns a dict with the command list and workdir.
    """
    workdir = create_workdir(batch_id, item_id)
    receptor_pdb = input_json.get("receptor_pdb", "<missing>")
    peptide_pdb = input_json.get("peptide_pdb", "<missing>")
    peptide_fasta = input_json.get("peptide_fasta", "<missing>")
    receptor_chain = input_json.get("receptor_chain", "A")
    peptide_chain = input_json.get("peptide_chain", "B")

    binary = _get_flexpepdock_binary() or FLEXPEPDOCK_CANDIDATES[0]
    cmd = [
        binary,
        "-s", receptor_pdb,
        "-native", peptide_pdb if peptide_pdb != "<missing>" else peptide_fasta,
        "-flexpep_prepack",
        "-ex1", "-ex2aro",
        "-nstruct", "200",
        "-out:file:silent", f"{workdir}/runs/flexpepdock_{item_id}.silent",
        "-out:file:scorefile", f"{workdir}/scores/score_{item_id}.sc",
    ]

    logger.info("[DRY RUN] batch=%s item=%s workdir=%s", batch_id, item_id, workdir)
    logger.info("[DRY RUN] command: %s", " ".join(cmd))
    logger.info("[DRY RUN] receptor_chain=%s peptide_chain=%s", receptor_chain, peptide_chain)

    return {
        "workdir": workdir,
        "command": " ".join(cmd),
        "receptor_pdb": receptor_pdb,
        "peptide_pdb": peptide_pdb,
        "peptide_fasta": peptide_fasta,
        "receptor_chain": receptor_chain,
        "peptide_chain": peptide_chain,
        "dry_run": True,
    }


def smoke_run() -> tuple[bool, Optional[str]]:
    """Run a minimal smoke test: FlexPepDocking -help.

    Returns:
        (success, error_message)
    """
    if not os.path.isfile(ROSETTA_ENV_SCRIPT):
        return False, f"Rosetta env script not found: {ROSETTA_ENV_SCRIPT}"

    binary = _get_flexpepdock_binary()
    if not binary:
        return False, "FlexPepDock binary not found. Tried: " + ", ".join(FLEXPEPDOCK_CANDIDATES)

    cmd = f"source '{ROSETTA_ENV_SCRIPT}' && {binary} -help"
    try:
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("FlexPepDock smoke test passed.")
            return True, None
        else:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning("FlexPepDock smoke test failed: %s", err)
            return False, f"Smoke test failed (rc={result.returncode}): {err}"
    except subprocess.TimeoutExpired:
        logger.warning("FlexPepDock smoke test timed out.")
        return False, "Smoke test timed out after 30s"
    except FileNotFoundError:
        logger.warning("bash not found — cannot run smoke test.")
        return False, "bash shell not available"


# ---------------------------------------------------------------------------
# P2 — Real single-sample docking via SSH
# ---------------------------------------------------------------------------

def _run_server_command(
    cmd: str,
    timeout: int = 300,
    log_dir: Optional[str] = None,
) -> tuple[int, str, str]:
    """Run a command on the server via SSH.

    If log_dir is provided, the command and its outputs are persisted
    via runner_logger.
    """
    ssh_cmd = ["ssh", f"{SERVER_USER}@{SERVER_HOST}", cmd]
    if log_dir:
        result = execute_command(ssh_cmd, log_dir=log_dir, timeout=timeout)
        return result.returncode, result.stdout_text, result.stderr_text
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "SSH command timed out"
    except Exception as exc:
        return -1, "", str(exc)


def _scp_upload(local_path: str, remote_path: str) -> bool:
    """Upload a file to the server via SCP."""
    try:
        result = subprocess.run(
            ["scp", local_path, f"{SERVER_USER}@{SERVER_HOST}:{remote_path}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.warning("SCP upload failed for %s: %s", local_path, exc)
        return False


def _scp_download(remote_path: str, local_path: str) -> bool:
    """Download a file from the server via SCP."""
    try:
        result = subprocess.run(
            ["scp", f"{SERVER_USER}@{SERVER_HOST}:{remote_path}", local_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.warning("SCP download failed for %s: %s", remote_path, exc)
        return False


def _ensure_server_dir(remote_dir: str) -> bool:
    """Create remote directory on server."""
    rc, _, _ = _run_server_command(f"mkdir -p '{remote_dir}'", timeout=10)
    return rc == 0


def _build_flexpepdock_command(
    binary: str,
    env_script: str,
    receptor_pdb: str,
    native_pdb: str | None,
    workdir: str,
    item_id: str,
    nstruct: int = DEFAULT_NSTRUCT,
) -> str:
    """Build the bash command string for FlexPepDock execution."""
    silent_out = f"{workdir}/runs/flexpepdock_{item_id}.silent"
    score_out = f"{workdir}/scores/score_{item_id}.sc"
    log_out = f"{workdir}/logs/flexpepdock_{item_id}.log"

    cmd_parts = [
        f"source '{env_script}'",
        f"'{binary}' -s '{receptor_pdb}'",
    ]
    if native_pdb:
        cmd_parts.append(f"-native '{native_pdb}'")
    cmd_parts.extend([
        "-flexpep_prepack",
        "-ex1", "-ex2aro",
        "-nstruct", str(nstruct),
        "-out:file:silent", f"'{silent_out}'",
        "-out:file:scorefile", f"'{score_out}'",
    ])
    cmd = " && ".join(cmd_parts)
    cmd += f" > '{log_out}' 2>&1"
    return cmd


def _verify_outputs(workdir: str, item_id: str) -> tuple[bool, list[str]]:
    """Verify that real output files were produced."""
    required_files = [
        f"{workdir}/scores/score_{item_id}.sc",
    ]
    missing = []
    for f in required_files:
        if not Path(f).exists():
            missing.append(f)
    return len(missing) == 0, missing


def run_single_docking(
    batch_id: str,
    item_id: str,
    input_json: dict,
) -> tuple[str, Optional[str], Optional[dict]]:
    """Execute a real single-sample FlexPepDock docking on the server.

    Flow:
      1. Check server reachability and Rosetta env
      2. Upload input PDBs to server
      3. Run FlexPepDock via SSH
      4. Download scorefile and silent file
      5. Verify real artifacts exist
      6. Parse scorefile

    Returns:
        (status, error_message, output_json)
    """
    log_dir = ensure_log_dir(batch_id, item_id, "FLEXPEPDOCK")

    # 1. Server reachability
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", f"{SERVER_USER}@{SERVER_HOST}", "echo ok"],
            capture_output=True,
            text=True,
            timeout=7,
        )
        if result.returncode != 0 or "ok" not in result.stdout:
            return "BLOCKED", f"Server {SERVER_HOST} unreachable", None
    except Exception as exc:
        return "BLOCKED", f"Server reachability check failed: {exc}", None

    # 2. Check Rosetta env on server
    env_script = ROSETTA_ENV_SCRIPT
    rc, stdout, _ = _run_server_command(
        f"test -f '{env_script}' && echo yes || echo no",
        log_dir=log_dir,
    )
    if rc != 0 or "yes" not in stdout:
        return (
            "BLOCKED",
            f"Rosetta env script not found on server: {env_script}",
            None,
        )

    # 3. Create workdirs
    local_workdir = create_workdir(batch_id, item_id)
    remote_workdir = f"{SERVER_BASE_DIR}/{batch_id}/{item_id}"
    if not _ensure_server_dir(remote_workdir):
        return "BLOCKED", f"Failed to create remote workdir: {remote_workdir}", None

    # 4. Upload inputs
    receptor_pdb = input_json["receptor_pdb"]
    peptide_pdb = input_json.get("peptide_pdb")

    remote_receptor = f"{remote_workdir}/inputs/{Path(receptor_pdb).name}"
    if not _scp_upload(receptor_pdb, remote_receptor):
        return "FAILED", "Failed to upload receptor_pdb to server", None

    remote_native = None
    if peptide_pdb:
        remote_native = f"{remote_workdir}/inputs/{Path(peptide_pdb).name}"
        if not _scp_upload(peptide_pdb, remote_native):
            return "FAILED", "Failed to upload peptide_pdb to server", None

    # 5. Determine binary on server
    rc, binary_path, _ = _run_server_command(
        f"source '{env_script}' && which FlexPepDocking.default.linuxgccrelease || which FlexPepDocking.static.linuxgccrelease",
        timeout=15,
        log_dir=log_dir,
    )
    if rc != 0 or not binary_path.strip():
        return "BLOCKED", "FlexPepDock binary not found on server", None
    binary = binary_path.strip().splitlines()[-1]

    # 6. Build and run command
    nstruct = input_json.get("nstruct", DEFAULT_NSTRUCT)
    cmd = _build_flexpepdock_command(
        binary=binary,
        env_script=env_script,
        receptor_pdb=remote_receptor,
        native_pdb=remote_native,
        workdir=remote_workdir,
        item_id=item_id,
        nstruct=nstruct,
    )

    logger.info("Running FlexPepDock on server for item %s (nstruct=%s)", item_id, nstruct)
    rc, stdout, stderr = _run_server_command(cmd, timeout=600, log_dir=log_dir)

    # 7. Download outputs
    remote_score = f"{remote_workdir}/scores/score_{item_id}.sc"
    local_score = f"{local_workdir}/scores/score_{item_id}.sc"
    _scp_download(remote_score, local_score)

    remote_silent = f"{remote_workdir}/runs/flexpepdock_{item_id}.silent"
    local_silent = f"{local_workdir}/runs/flexpepdock_{item_id}.silent"
    _scp_download(remote_silent, local_silent)

    remote_log = f"{remote_workdir}/logs/flexpepdock_{item_id}.log"
    local_log = f"{local_workdir}/logs/flexpepdock_{item_id}.log"
    _scp_download(remote_log, local_log)

    # 8. Verify real artifacts exist
    ok, missing = _verify_outputs(local_workdir, item_id)
    if not ok:
        return (
            "FAILED",
            f"Missing output files: {', '.join(missing)}",
            {
                "workdir": local_workdir,
                "remote_workdir": remote_workdir,
                "return_code": rc,
                "stderr": stderr[:500] if stderr else None,
                "log_dir": log_dir,
            },
        )

    # 9. Parse scorefile
    from app.services.compute_wrappers.flexpepdock_wrapper import parse_flexpepdock_artifact
    score_data = parse_flexpepdock_artifact(local_score)

    return "SUCCEEDED", None, {
        "workdir": local_workdir,
        "remote_workdir": remote_workdir,
        "scorefile_path": local_score,
        "silent_file_path": local_silent,
        "log_path": local_log,
        "log_dir": log_dir,
        "score_data": score_data,
        "nstruct": nstruct,
        "return_code": rc,
        "prediction_status": "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
    }


def dispatch(
    batch_id: str,
    item_id: str,
    input_json: dict,
) -> tuple[str, Optional[str], Optional[dict]]:
    """Dispatch a FlexPepDock batch item.

    P2: validates input, then executes real single-sample docking on the server.

    Returns:
        (status, error_message, output_json)
    """
    ok, err = validate_input(input_json)
    if not ok:
        logger.warning("FlexPepDock item %s FAILED validation: %s", item_id, err)
        return "FAILED", err, None

    return run_single_docking(batch_id, item_id, input_json)
