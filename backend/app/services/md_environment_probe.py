"""MD Environment Probe Service (v1.5 P2).

Detects whether the server has the necessary MD tools and GPU resources
to run molecular dynamics simulations.

Rules:
- BLOCKED if gmx is missing
- BLOCKED if stamp-md conda env is missing
- BLOCKED if input files are missing (only when explicitly provided)
- AVAILABLE if all critical dependencies are present
- GPU missing is a WARNING, not a BLOCKER (CPU MD is still possible)
- NEVER synthesize metrics
- NEVER claim SUCCEEDED without real output files
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings

logger = logging.getLogger("stamp")

STAMP_MD_ENV = os.environ.get("STAMP_MD_ENV", "stamp-md")
CONDA_BASE = os.environ.get("CONDA_BASE", "/home/xh/miniconda3")


def _find_conda_exe() -> str | None:
    """Find the conda executable, checking PATH then common locations."""
    conda = shutil.which("conda")
    if conda:
        return conda
    # Common fallback paths
    candidates = [
        os.path.join(CONDA_BASE, "bin", "conda"),
        "/opt/miniconda3/bin/conda",
        "/usr/local/miniconda3/bin/conda",
        "/root/miniconda3/bin/conda",
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


@dataclass
class MdEnvironmentReport:
    status: str  # "AVAILABLE" | "BLOCKED"
    stamp_md_env_available: bool
    gromacs_available: bool
    gromacs_version: Optional[str]
    gpu_available: bool
    gpu_info: Optional[list[dict]]
    mdanalysis_available: bool
    openmm_available: bool
    parmed_available: bool
    amber_available: bool
    mmgbsa_available: bool
    mmgbsa_version: Optional[str]
    input_pdb_valid: bool
    input_pdb_path: Optional[str]
    blocking_reasons: list[str]
    next_actions: list[str]
    platform_version: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "stamp_md_env_available": self.stamp_md_env_available,
            "gromacs_available": self.gromacs_available,
            "gromacs_version": self.gromacs_version,
            "gpu_available": self.gpu_available,
            "gpu_info": self.gpu_info,
            "mdanalysis_available": self.mdanalysis_available,
            "openmm_available": self.openmm_available,
            "parmed_available": self.parmed_available,
            "amber_available": self.amber_available,
            "mmgbsa_available": self.mmgbsa_available,
            "mmgbsa_version": self.mmgbsa_version,
            "platform_version": self.platform_version,
            "input_pdb_valid": self.input_pdb_valid,
            "input_pdb_path": self.input_pdb_path,
            "blocking_reasons": self.blocking_reasons,
            "next_actions": self.next_actions,
        }


def _check_conda_env(env_name: str) -> bool:
    """Check if a conda environment exists."""
    conda_exe = _find_conda_exe()
    if not conda_exe:
        # Fallback: check env directory
        env_dir = os.path.join(CONDA_BASE, "envs", env_name)
        return os.path.isdir(env_dir) and os.path.isfile(os.path.join(env_dir, "bin", "python"))
    conda_exe = _find_conda_exe()
    if not conda_exe:
        # Fallback: check env directory
        env_dir = os.path.join(CONDA_BASE, "envs", env_name)
        return os.path.isdir(env_dir) and os.path.isfile(os.path.join(env_dir, "bin", "python"))
    try:
        result = subprocess.run(
            [conda_exe, "env", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            envs = json.loads(result.stdout).get("envs", [])
            for env_path in envs:
                if env_name in env_path.split(os.sep):
                    return True
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, ImportError, json.JSONDecodeError):
        pass
    # Fallback
    env_dir = os.path.join(CONDA_BASE, "envs", env_name)
    return os.path.isdir(env_dir) and os.path.isfile(os.path.join(env_dir, "bin", "python"))


def _check_mmgbsa_in_conda_env(env_name: str) -> tuple[bool, Optional[str]]:
    """Check if gmx_MMPBSA is available inside the stamp-md conda env."""
    conda_exe = _find_conda_exe()
    if not conda_exe:
        return check_command("gmx_MMPBSA")
    try:
        result = subprocess.run(
            [conda_exe, "run", "-n", env_name, "gmx_MMPBSA", "--help"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            version_line = None
            for line in result.stdout.strip().splitlines()[:5]:
                if "version" in line.lower() or "gmx_mmpbsa" in line.lower():
                    version_line = line.strip()
                    break
            return True, version_line
        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, None


def _check_gmx_in_conda_env(env_name: str) -> tuple[bool, Optional[str]]:
    """Check if gmx is available inside the stamp-md conda env."""
    conda_exe = _find_conda_exe()
    if not conda_exe:
        # Try direct gmx
        return check_command("gmx")
    try:
        result = subprocess.run(
            [conda_exe, "run", "-n", env_name, "gmx", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode == 0:
            version_line = result.stdout.strip().splitlines()[0] if result.stdout else None
            return True, version_line
        # gmx may not respond to --version; try gmx -h
        result2 = subprocess.run(
            [conda_exe, "run", "-n", env_name, "gmx", "-h"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result2.returncode == 0:
            return True, None
        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, None


def check_command(cmd: str) -> tuple[bool, Optional[str]]:
    """Check if a command exists and return its version string."""
    if not shutil.which(cmd):
        return False, None
    try:
        result = subprocess.run(
            [cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        version_line = result.stdout.strip().splitlines()[0] if result.stdout else None
        return True, version_line
    except (subprocess.TimeoutExpired, FileNotFoundError, IndexError):
        return True, None


def check_gpu() -> tuple[bool, Optional[list[dict]]]:
    """Check if NVIDIA GPU is available via nvidia-smi."""
    if not shutil.which("nvidia-smi"):
        return False, None
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False, None
        gpus = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 3:
                gpus.append({
                    "name": parts[0],
                    "driver_version": parts[1],
                    "memory": parts[2],
                })
        return len(gpus) > 0, gpus if gpus else None
    except subprocess.TimeoutExpired:
        return False, None


def check_python_module_in_conda_env(module_name: str, env_name: str) -> bool:
    """Check if a Python module is importable inside a conda env."""
    conda_exe = _find_conda_exe()
    if not conda_exe:
        # Fallback: try system python
        return check_python_module(module_name)
    try:
        result = subprocess.run(
            [conda_exe, "run", "-n", env_name, "python", "-c", f"import {module_name}; print('OK')"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return result.returncode == 0 and "OK" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_python_module(module_name: str) -> bool:
    """Check if a Python module is importable in the current Python."""
    try:
        __import__(module_name)
        return True
    except ImportError:
        return False


def validate_pdb(pdb_path: str) -> bool:
    """Validate that a PDB file contains ATOM records.

    Does NOT check structural quality — only file existence and minimal format.
    """
    if not os.path.isfile(pdb_path):
        return False
    try:
        with open(pdb_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    return True
        return False
    except OSError:
        return False


def probe_md_environment(input_pdb_path: Optional[str] = None) -> MdEnvironmentReport:
    """Probe the server environment for MD readiness.

    Returns BLOCKED if any critical dependency is missing.
    Returns AVAILABLE only if all critical dependencies are present.
    """
    blocking_reasons: list[str] = []
    next_actions: list[str] = []

    # 1. stamp-md conda env
    env_ok = _check_conda_env(STAMP_MD_ENV)
    if not env_ok:
        blocking_reasons.append(
            f"stamp-md conda env not found. Create it: conda create -n {STAMP_MD_ENV} python=3.11"
        )
        next_actions.append(f"conda create -n {STAMP_MD_ENV} python=3.11")

    # 2. GROMACS
    if env_ok:
        gromacs_ok, gromacs_version = _check_gmx_in_conda_env(STAMP_MD_ENV)
    else:
        gromacs_ok, gromacs_version = check_command("gmx")
    if not gromacs_ok:
        blocking_reasons.append(
            "GROMACS (gmx) not found. Install: conda install -c conda-forge gromacs"
        )
        next_actions.append("conda install -c conda-forge -n stamp-md gromacs")

    # 3. GPU (warning only, not blocking)
    gpu_ok, gpu_info = check_gpu()
    if not gpu_ok:
        next_actions.append(
            "NVIDIA GPU not detected. MD will run on CPU (much slower). "
            "Install NVIDIA drivers and CUDA toolkit for GPU acceleration."
        )
    else:
        logger.info("GPU detected: %s", gpu_info)

    # 4. Python MD libs (inside stamp-md env if available)
    python_check_env = STAMP_MD_ENV if env_ok else None

    mdanalysis_ok = check_python_module_in_conda_env("MDAnalysis", python_check_env) if python_check_env else check_python_module("MDAnalysis")
    if not mdanalysis_ok:
        blocking_reasons.append("MDAnalysis not installed. Install: conda install -c conda-forge mdanalysis")
        next_actions.append("conda install -c conda-forge -n stamp-md mdanalysis")

    openmm_ok = check_python_module_in_conda_env("openmm", python_check_env) if python_check_env else check_python_module("openmm")
    if not openmm_ok:
        blocking_reasons.append("OpenMM not installed. Install: conda install -c conda-forge openmm")
        next_actions.append("conda install -c conda-forge -n stamp-md openmm")

    parmed_ok = check_python_module_in_conda_env("parmed", python_check_env) if python_check_env else check_python_module("parmed")
    if not parmed_ok:
        blocking_reasons.append("ParmEd not installed. Install: conda install -c conda-forge parmed")
        next_actions.append("conda install -c conda-forge -n stamp-md parmed")

    amber_ok = shutil.which("sander") is not None or shutil.which("pmemd") is not None

    # 5. MM-GBSA (gmx_MMPBSA)
    if env_ok:
        mmgbsa_ok, mmgbsa_version = _check_mmgbsa_in_conda_env(STAMP_MD_ENV)
    else:
        mmgbsa_ok, mmgbsa_version = check_command("gmx_MMPBSA")
    if not mmgbsa_ok:
        next_actions.append(
            "gmx_MMPBSA not found. Install: pip install gmx-MMPBSA"
        )

    # 6. Input PDB
    input_pdb_valid = False
    if input_pdb_path:
        input_pdb_valid = validate_pdb(input_pdb_path)
        if not input_pdb_valid:
            blocking_reasons.append(f"Input PDB invalid or missing: {input_pdb_path}")
    # Note: if input_pdb_path is None, we don't block — the caller may provide it later

    status = "BLOCKED" if blocking_reasons else "AVAILABLE"

    return MdEnvironmentReport(
        status=status,
        stamp_md_env_available=env_ok,
        gromacs_available=gromacs_ok,
        gromacs_version=gromacs_version,
        gpu_available=gpu_ok,
        gpu_info=gpu_info,
        mdanalysis_available=mdanalysis_ok,
        openmm_available=openmm_ok,
        parmed_available=parmed_ok,
        amber_available=amber_ok,
        mmgbsa_available=mmgbsa_ok,
        mmgbsa_version=mmgbsa_version,
        platform_version=settings.app_version,
        input_pdb_valid=input_pdb_valid,
        input_pdb_path=input_pdb_path,
        blocking_reasons=blocking_reasons,
        next_actions=next_actions,
    )
