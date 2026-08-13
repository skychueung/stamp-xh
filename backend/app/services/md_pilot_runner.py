"""MD Pilot Runner Service (v1.5 P2).

Prepares MD pilot workdirs, validates inputs/env, supports dry_run and smoke_run.
Does NOT launch long production MD yet.

Scientific boundaries:
- No fabricated RMSD / RMSF / Rg / ΔG / trajectory / energy.
- SUCCEEDED only when real artifacts exist.
- BLOCKED when env is missing.
- FAILED when input files missing or command returns non-zero.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Optional

from app.services.batch_dir_service import ensure_item_dir
from app.services.md_environment_probe import (
    STAMP_MD_ENV,
    _find_conda_exe,
    probe_md_environment,
    validate_pdb,
)
from app.services.runner_logger import execute_command

logger = logging.getLogger("stamp")

MD_PILOT_SUBDIRS = (
    "inputs",
    "topology",
    "solvated",
    "minimization",
    "equilibration",
    "production",
    "analysis",
    "logs",
    "artifacts",
)


def create_workdir(batch_id: str, item_id: str) -> str:
    """Create and return the working directory for an MD pilot job.

    Scaffold:
        data/batch_jobs/{batch_id}/md_pilot/{item_id}/
          inputs/
          topology/
          solvated/
          minimization/
          equilibration/
          production/
          analysis/
          logs/
          artifacts/
    """
    item_dir = ensure_item_dir(batch_id, item_id, "MD_PILOT")
    for sub in MD_PILOT_SUBDIRS:
        (Path(item_dir) / sub).mkdir(parents=True, exist_ok=True)
    return item_dir


def validate_input(input_json: dict) -> tuple[bool, Optional[str]]:
    """Validate MD pilot input parameters.

    Required:
      - input_pdb: path to input PDB file
    Optional:
      - forcefield: e.g. "amber99sb-ildn" (default)
      - water_model: e.g. "tip3p" (default)
      - box_type: e.g. "dodecahedron" (default)
      - ion_conc: mM (default 0.15)
    """
    if not input_json:
        return False, "input_json is empty"

    input_pdb = input_json.get("input_pdb")
    if not input_pdb:
        return False, "input_pdb is required"
    if not Path(input_pdb).exists():
        return False, f"input_pdb not found: {input_pdb}"
    if not validate_pdb(input_pdb):
        return False, f"input_pdb is not a valid PDB file: {input_pdb}"

    return True, None


def check_environment() -> tuple[bool, list[str]]:
    """Check if MD environment is ready."""
    report = probe_md_environment()
    if report.status == "AVAILABLE":
        return True, []
    return False, report.blocking_reasons


def _gmx_cmd(subcmd: str, args: list[str]) -> list[str]:
    """Build a GROMACS command list that runs inside the stamp-md conda env."""
    conda_exe = _find_conda_exe() or "conda"
    # Use conda run to execute gmx inside stamp-md env
    return [
        conda_exe, "run", "-n", STAMP_MD_ENV,
        "gmx", subcmd,
    ] + args


def dry_run(batch_id: str, item_id: str, input_json: dict) -> dict:
    """Log the commands that would be executed without running them.

    Returns a dict with the command list and workdir.
    """
    workdir = create_workdir(batch_id, item_id)
    input_pdb = input_json.get("input_pdb", "<missing>")
    forcefield = input_json.get("forcefield", "amber99sb-ildn")
    water_model = input_json.get("water_model", "tip3p")
    box_type = input_json.get("box_type", "dodecahedron")
    ion_conc = input_json.get("ion_conc", 0.15)

    # Build a representative command sequence (P2 skeleton — not exhaustive)
    commands = [
        # 1. PDB to GRO + topology
        _gmx_cmd("pdb2gmx", [
            "-f", input_pdb,
            "-o", f"{workdir}/topology/conf.gro",
            "-p", f"{workdir}/topology/topol.top",
            "-ff", forcefield,
            "-water", water_model,
            "-ignh",
        ]),
        # 2. Define box
        _gmx_cmd("editconf", [
            "-f", f"{workdir}/topology/conf.gro",
            "-o", f"{workdir}/solvated/box.gro",
            "-bt", box_type,
            "-d", "1.0",
        ]),
        # 3. Solvate
        _gmx_cmd("solvate", [
            "-cp", f"{workdir}/solvated/box.gro",
            "-cs", "spc216.gro",
            "-o", f"{workdir}/solvated/solvated.gro",
            "-p", f"{workdir}/topology/topol.top",
        ]),
        # 4. Add ions (genion)
        _gmx_cmd("grompp", [
            "-f", "ions.mdp",
            "-c", f"{workdir}/solvated/solvated.gro",
            "-p", f"{workdir}/topology/topol.top",
            "-o", f"{workdir}/solvated/ions.tpr",
            "-maxwarn", "1",
        ]),
        _gmx_cmd("genion", [
            "-s", f"{workdir}/solvated/ions.tpr",
            "-o", f"{workdir}/solvated/ions.gro",
            "-p", f"{workdir}/topology/topol.top",
            "-pname", "NA", "-nname", "CL",
            "-neutral", "-conc", str(ion_conc),
        ]),
        # 5. Energy minimization
        _gmx_cmd("grompp", [
            "-f", "em.mdp",
            "-c", f"{workdir}/solvated/ions.gro",
            "-p", f"{workdir}/topology/topol.top",
            "-o", f"{workdir}/minimization/em.tpr",
        ]),
        _gmx_cmd("mdrun", [
            "-deffnm", f"{workdir}/minimization/em",
        ]),
        # 6. Equilibration (NVT)
        _gmx_cmd("grompp", [
            "-f", "nvt.mdp",
            "-c", f"{workdir}/minimization/em.gro",
            "-r", f"{workdir}/minimization/em.gro",
            "-p", f"{workdir}/topology/topol.top",
            "-o", f"{workdir}/equilibration/nvt.tpr",
        ]),
        _gmx_cmd("mdrun", [
            "-deffnm", f"{workdir}/equilibration/nvt",
        ]),
        # 7. Equilibration (NPT)
        _gmx_cmd("grompp", [
            "-f", "npt.mdp",
            "-c", f"{workdir}/equilibration/nvt.gro",
            "-r", f"{workdir}/equilibration/nvt.gro",
            "-t", f"{workdir}/equilibration/nvt.cpt",
            "-p", f"{workdir}/topology/topol.top",
            "-o", f"{workdir}/equilibration/npt.tpr",
        ]),
        _gmx_cmd("mdrun", [
            "-deffnm", f"{workdir}/equilibration/npt",
        ]),
        # 8. Production MD (1 ns pilot)
        _gmx_cmd("grompp", [
            "-f", "md.mdp",
            "-c", f"{workdir}/equilibration/npt.gro",
            "-t", f"{workdir}/equilibration/npt.cpt",
            "-p", f"{workdir}/topology/topol.top",
            "-o", f"{workdir}/production/md_1ns.tpr",
        ]),
        _gmx_cmd("mdrun", [
            "-deffnm", f"{workdir}/production/md_1ns",
            "-nb", "gpu" if _gpu_available() else "cpu",
        ]),
    ]

    logger.info("[DRY RUN] batch=%s item=%s workdir=%s", batch_id, item_id, workdir)
    logger.info("[DRY RUN] input_pdb=%s forcefield=%s water=%s", input_pdb, forcefield, water_model)

    return {
        "workdir": workdir,
        "commands": [" ".join(cmd) for cmd in commands],
        "input_pdb": input_pdb,
        "forcefield": forcefield,
        "water_model": water_model,
        "box_type": box_type,
        "ion_conc": ion_conc,
        "dry_run": True,
    }


def _gpu_available() -> bool:
    """Quick check if GPU is available (cached)."""
    from app.services.md_environment_probe import check_gpu
    ok, _ = check_gpu()
    return ok


def smoke_run(batch_id: Optional[str] = None, item_id: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """Run a minimal smoke test: gmx -h inside stamp-md env.

    Args:
        batch_id: Optional batch ID for log persistence.
        item_id: Optional item ID for log persistence.

    Returns:
        (success, error_message)
    """
    report = probe_md_environment()
    if report.status == "BLOCKED":
        return False, f"Environment BLOCKED: {'; '.join(report.blocking_reasons)}"

    conda_exe = _find_conda_exe() or "conda"
    # Try gmx -h via conda run
    cmd = [conda_exe, "run", "-n", STAMP_MD_ENV, "gmx", "-h"]

    log_dir = None
    if batch_id and item_id:
        from app.services.runner_logger import ensure_log_dir
        log_dir = ensure_log_dir(batch_id, item_id, "MD_PILOT")

    try:
        if log_dir:
            result = execute_command(cmd, log_dir=log_dir, timeout=30)
            if result.returncode == 0:
                logger.info("MD smoke test passed (gmx -h responded).")
                return True, None
            else:
                err = result.stderr_text.strip() or result.stdout_text.strip() or "Unknown error"
                logger.warning("MD smoke test failed: %s", err)
                return False, f"Smoke test failed (rc={result.returncode}): {err}"
        else:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                logger.info("MD smoke test passed (gmx -h responded).")
                return True, None
            else:
                err = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.warning("MD smoke test failed: %s", err)
                return False, f"Smoke test failed (rc={result.returncode}): {err}"
    except subprocess.TimeoutExpired:
        logger.warning("MD smoke test timed out.")
        return False, "Smoke test timed out after 30s"
    except FileNotFoundError:
        logger.warning("conda not found — cannot run smoke test.")
        return False, "conda not available"


def dispatch(
    batch_id: str,
    item_id: str,
    input_json: dict,
) -> tuple[str, Optional[str], Optional[dict]]:
    """Dispatch an MD pilot batch item.

    P2 skeleton: validates input, checks environment, creates workdir,
    marks RUNNING, but does NOT execute actual MD.

    Returns:
        (status, error_message, output_json)
    """
    # 1. Validate input
    ok, err = validate_input(input_json)
    if not ok:
        logger.warning("MD item %s FAILED validation: %s", item_id, err)
        return "FAILED", err, None

    # 2. Check environment
    env_ok, env_reasons = check_environment()
    if not env_ok:
        logger.warning("MD item %s BLOCKED: %s", item_id, "; ".join(env_reasons))
        return "BLOCKED", "; ".join(env_reasons), None

    # 3. Create workdir
    workdir = create_workdir(batch_id, item_id)

    # 4. Return RUNNING status (actual MD execution deferred to P3)
    logger.info("MD item %s prepared workdir=%s, status=RUNNING", item_id, workdir)
    return "RUNNING", None, {
        "workdir": workdir,
        "status": "RUNNING",
        "note": "P2 skeleton — actual MD execution deferred to P3",
    }
