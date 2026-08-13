"""FlexPepDock Environment Probe Service (v1.5 P1).

Detects whether the server has the necessary Rosetta/FlexPepDock tools
to run peptide-protein docking simulations.

Rules:
- BLOCKED if rosetta_env.sh is missing
- BLOCKED if FlexPepDocking binary is not available after sourcing env
- BLOCKED if ROSETTA3_DB is missing
- AVAILABLE if all tools are present
- NEVER synthesize metrics
- NEVER claim SUCCEEDED without real output files
"""

from __future__ import annotations

import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("stamp")

ROSETTA_ENV_SCRIPT = os.environ.get(
    "ROSETTA_ENV_SCRIPT", "/home/xh/kxc/tools/rosetta/rosetta_env.sh"
)
FLEXPEPDOCK_CANDIDATES = [
    "FlexPepDocking.default.linuxgccrelease",
    "FlexPepDocking.static.linuxgccrelease",
]
ROSETTA_SCRIPTS_CANDIDATES = [
    "rosetta_scripts.default.linuxgccrelease",
    "rosetta_scripts.static.linuxgccrelease",
]


@dataclass
class FlexPepDockEnvironmentReport:
    status: str  # "AVAILABLE" | "BLOCKED"
    rosetta_env_script_exists: bool
    flexpepdock_available: bool
    rosetta_scripts_available: bool
    rosetta_db_available: bool
    rosetta_root: Optional[str]
    blocking_reasons: list[str]

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "rosetta_env_script_exists": self.rosetta_env_script_exists,
            "flexpepdock_available": self.flexpepdock_available,
            "rosetta_scripts_available": self.rosetta_scripts_available,
            "rosetta_db_available": self.rosetta_db_available,
            "rosetta_root": self.rosetta_root,
            "blocking_reasons": self.blocking_reasons,
        }


def _check_binary_via_env(binary_name: str, env_script: str) -> tuple[bool, Optional[str]]:
    """Check if a Rosetta binary is available after sourcing the env script."""
    if not os.path.isfile(env_script):
        return False, None
    try:
        result = subprocess.run(
            ["bash", "-c", f"source '{env_script}' && which {binary_name}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            path = result.stdout.strip().splitlines()[-1]
            return os.path.isfile(path), path
        return False, None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, None


def _find_any_binary(candidates: list[str], env_script: str) -> tuple[bool, Optional[str]]:
    """Try multiple binary names and return the first one found."""
    for name in candidates:
        ok, path = _check_binary_via_env(name, env_script)
        if ok:
            return ok, path
    return False, None


def _get_rosetta_root(env_script: str) -> Optional[str]:
    """Extract ROSETTA_ROOT from the env script if possible."""
    if not os.path.isfile(env_script):
        return None
    try:
        result = subprocess.run(
            ["bash", "-c", f"source '{env_script}' && echo $ROSETTA_ROOT"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            root = result.stdout.strip().splitlines()[-1]
            return root if root else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _check_rosetta_db(rosetta_root: Optional[str]) -> bool:
    """Check if ROSETTA3_DB directory exists under ROSETTA_ROOT.

    Tries common locations:
      - {rosetta_root}/database
      - {rosetta_root}/rosetta.binary.*/main/database
    """
    if not rosetta_root:
        return False
    candidates = [os.path.join(rosetta_root, "database")]
    # Some Rosetta installations nest the database deeper
    import glob
    candidates.extend(
        glob.glob(os.path.join(rosetta_root, "rosetta.binary.*", "main", "database"))
    )
    for db_path in candidates:
        if os.path.isdir(db_path):
            return True
    return False


def probe_flexpepdock_environment() -> FlexPepDockEnvironmentReport:
    """Probe the server environment for FlexPepDock readiness.

    Returns BLOCKED if any critical dependency is missing.
    Returns AVAILABLE only if all critical dependencies are present.
    """
    blocking_reasons: list[str] = []

    # 1. Check env script exists
    env_exists = os.path.isfile(ROSETTA_ENV_SCRIPT)
    if not env_exists:
        blocking_reasons.append(
            f"Rosetta env script not found: {ROSETTA_ENV_SCRIPT}. "
            "Install Rosetta or set ROSETTA_ENV_SCRIPT environment variable."
        )

    # 2. Check ROSETTA_ROOT
    rosetta_root = _get_rosetta_root(ROSETTA_ENV_SCRIPT) if env_exists else None
    if env_exists and not rosetta_root:
        blocking_reasons.append("ROSETTA_ROOT not set after sourcing env script.")

    # 3. Check FlexPepDock binary
    flex_ok = False
    flex_path = None
    if env_exists:
        flex_ok, flex_path = _find_any_binary(FLEXPEPDOCK_CANDIDATES, ROSETTA_ENV_SCRIPT)
        if not flex_ok:
            blocking_reasons.append(
                f"FlexPepDock binary not found after sourcing env. "
                f"Tried: {', '.join(FLEXPEPDOCK_CANDIDATES)}. "
                "Verify Rosetta installation includes FlexPepDock."
            )
        else:
            logger.info("FlexPepDock binary found at: %s", flex_path)

    # 4. Check rosetta_scripts binary (used for pre-processing)
    scripts_ok = False
    if env_exists:
        scripts_ok, _ = _find_any_binary(ROSETTA_SCRIPTS_CANDIDATES, ROSETTA_ENV_SCRIPT)
        if not scripts_ok:
            blocking_reasons.append(
                f"Rosetta scripts binary not found after sourcing env. "
                f"Tried: {', '.join(ROSETTA_SCRIPTS_CANDIDATES)}."
            )

    # 5. Check database
    db_ok = _check_rosetta_db(rosetta_root)
    if not db_ok:
        blocking_reasons.append(
            "ROSETTA database not found. Verify database directory under ROSETTA_ROOT."
        )

    status = "BLOCKED" if blocking_reasons else "AVAILABLE"

    return FlexPepDockEnvironmentReport(
        status=status,
        rosetta_env_script_exists=env_exists,
        flexpepdock_available=flex_ok,
        rosetta_scripts_available=scripts_ok,
        rosetta_db_available=db_ok,
        rosetta_root=rosetta_root,
        blocking_reasons=blocking_reasons,
    )
