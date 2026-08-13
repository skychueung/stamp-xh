"""MM-GBSA Pilot Runner Service (v1.5 P3).

Prepares MM-GBSA pilot workdirs, validates inputs/env, supports dry_run and smoke_run.
Does NOT launch full MM-GBSA production runs yet.

Scientific boundaries:
- No fabricated ΔG values.
- SUCCEEDED only when real artifacts exist.
- BLOCKED when env is missing.
- FAILED when input files missing or command returns non-zero.
- official_mm_gbsa_delta_g is ALWAYS null for pilot/smoke.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from app.services.batch_dir_service import ensure_item_dir
from app.services.md_environment_probe import (
    _find_conda_exe,
    probe_md_environment,
)

logger = logging.getLogger("stamp")

MMGBSA_SUBDIRS = (
    "inputs",
    "topology",
    "trajectory",
    "analysis",
    "logs",
    "artifacts",
)

MMGBSA_ENV = os.environ.get("MMGBSA_ENV", "mmgbsa")
MICROMAMBA_EXE = _find_conda_exe()


def create_workdir(batch_id: str, item_id: str) -> str:
    """Create and return the working directory for an MM-GBSA pilot job.

    Scaffold:
        data/batch_jobs/{batch_id}/mmgbsa/{item_id}/
          inputs/
          topology/
          trajectory/
          analysis/
          logs/
          artifacts/
    """
    item_dir = ensure_item_dir(batch_id, item_id, "MMGBSA")
    for sub in MMGBSA_SUBDIRS:
        (Path(item_dir) / sub).mkdir(parents=True, exist_ok=True)
    return item_dir


def validate_input(input_json: dict) -> tuple[bool, Optional[str]]:
    """Validate MM-GBSA pilot input parameters.

    Required:
      - topology: path to topology file (.tpr or .top)
      - trajectory: path to trajectory file (.xtc or .trr)
      - index: path to index file (.ndx) with receptor/ligand groups
    Optional:
      - mdp: path to mdp file (for topology regeneration)
      - ligand_mask: e.g. ":1-10" for ante-MMPBSA
      - receptor_mask: e.g. ":11-100"
      - frames: number of frames to analyze (default all)
    """
    if not input_json:
        return False, "input_json is empty"

    topology = input_json.get("topology")
    trajectory = input_json.get("trajectory")
    index = input_json.get("index")

    if not topology:
        return False, "topology is required"
    if not trajectory:
        return False, "trajectory is required"
    if not index:
        return False, "index is required"

    if not Path(topology).exists():
        return False, f"topology not found: {topology}"
    if not Path(trajectory).exists():
        return False, f"trajectory not found: {trajectory}"
    if not Path(index).exists():
        return False, f"index not found: {index}"

    return True, None


def check_environment() -> tuple[bool, list[str]]:
    """Check if MM-GBSA environment is ready."""
    report = probe_md_environment()
    if report.status == "BLOCKED":
        return False, report.blocking_reasons
    if not report.mmgbsa_available:
        return False, ["gmx_MMPBSA not available in any detected environment"]
    return True, []


def _mmgbsa_cmd(args: list[str]) -> list[str]:
    """Build an MM-GBSA command list that runs inside the mmgbsa env."""
    mm_exe = MICROMAMBA_EXE or "conda"
    return [
        mm_exe, "run", "-n", MMGBSA_ENV,
    ] + args


def dry_run(batch_id: str, item_id: str, input_json: dict) -> dict:
    """Log the commands that would be executed without running them.

    Returns a dict with the command list and workdir.
    """
    workdir = create_workdir(batch_id, item_id)
    topology = input_json.get("topology", "<missing>")
    trajectory = input_json.get("trajectory", "<missing>")
    index = input_json.get("index", "<missing>")
    ligand_mask = input_json.get("ligand_mask", ":1-10")
    receptor_mask = input_json.get("receptor_mask", ":11-100")

    # Build representative command sequence (P3 skeleton)
    commands = [
        # 1. Generate index groups if needed (optional)
        _mmgbsa_cmd([
            "make_ndx",
            "-f", topology,
            "-o", f"{workdir}/inputs/complex_index.ndx",
        ]),
        # 2. ante-MMPBSA: generate receptor/ligand topologies
        _mmgbsa_cmd([
            "ante-MMPBSA.py",
            "-p", topology,
            "-c", f"{workdir}/topology/complex.pdb",
            "-r", f"{workdir}/topology/receptor.pdb",
            "-l", f"{workdir}/topology/ligand.pdb",
            "-s", "protein",
            "-n", index,
        ]),
        # 3. gmx_MMPBSA execution
        _mmgbsa_cmd([
            "gmx_MMPBSA",
            "-O",
            "-i", f"{workdir}/inputs/mmpbsa.in",
            "-cs", topology,
            "-ci", index,
            "-cg", "1", "13",  # receptor/ligand group numbers (placeholder)
            "-ct", trajectory,
            "-o", f"{workdir}/artifacts/FINAL_RESULTS_MMPBSA.dat",
            "-do", f"{workdir}/artifacts/DECOMP_MMPBSA.dat",
            "-eo", f"{workdir}/artifacts/energy.csv",
        ]),
    ]

    logger.info("[DRY RUN] batch=%s item=%s workdir=%s", batch_id, item_id, workdir)
    logger.info("[DRY RUN] topology=%s trajectory=%s index=%s", topology, trajectory, index)

    return {
        "workdir": workdir,
        "commands": [" ".join(cmd) for cmd in commands],
        "topology": topology,
        "trajectory": trajectory,
        "index": index,
        "ligand_mask": ligand_mask,
        "receptor_mask": receptor_mask,
        "dry_run": True,
    }


def smoke_run() -> tuple[bool, Optional[str]]:
    """Run a minimal smoke test: gmx_MMPBSA --version inside mmgbsa env.

    Returns:
        (success, error_message)
    """
    report = probe_md_environment()
    if report.status == "BLOCKED":
        return False, f"Environment BLOCKED: {'; '.join(report.blocking_reasons)}"
    if not report.mmgbsa_available:
        return False, "gmx_MMPBSA not available in any detected environment"

    mm_exe = MICROMAMBA_EXE or "conda"
    cmd = [mm_exe, "run", "-n", MMGBSA_ENV, "gmx_MMPBSA", "--version"]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            logger.info("MM-GBSA smoke test passed (gmx_MMPBSA --version responded).")
            return True, None
        else:
            err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
            logger.warning("MM-GBSA smoke test failed: %s", err)
            return False, f"Smoke test failed (rc={result.returncode}): {err}"
    except subprocess.TimeoutExpired:
        logger.warning("MM-GBSA smoke test timed out.")
        return False, "Smoke test timed out after 30s"
    except FileNotFoundError:
        logger.warning("micromamba not found — cannot run smoke test.")
        return False, "micromamba not available"


def dispatch(
    batch_id: str,
    item_id: str,
    input_json: dict,
) -> tuple[str, Optional[str], Optional[dict]]:
    """Dispatch an MM-GBSA pilot batch item.

    P3 skeleton: validates input, checks environment, creates workdir,
    marks RUNNING, but does NOT execute actual MM-GBSA.

    Returns:
        (status, error_message, output_json)
    """
    # 1. Validate input
    ok, err = validate_input(input_json)
    if not ok:
        logger.warning("MM-GBSA item %s FAILED validation: %s", item_id, err)
        return "FAILED", err, None

    # 2. Check environment
    env_ok, env_reasons = check_environment()
    if not env_ok:
        logger.warning("MM-GBSA item %s BLOCKED: %s", item_id, "; ".join(env_reasons))
        return "BLOCKED", "; ".join(env_reasons), None

    # 3. Create workdir
    workdir = create_workdir(batch_id, item_id)

    # 4. Return RUNNING status (actual MM-GBSA execution deferred)
    logger.info("MM-GBSA item %s prepared workdir=%s, status=RUNNING", item_id, workdir)
    return "RUNNING", None, {
        "workdir": workdir,
        "status": "RUNNING",
        "note": "P3 skeleton — actual MM-GBSA execution deferred to production phase",
    }
