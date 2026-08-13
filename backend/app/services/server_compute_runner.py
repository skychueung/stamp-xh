"""Server compute runner for dispatching heavy jobs to the lab server (v1.2-lab-production-fast).

Server: 192.168.31.218 (xh)
Policy: server_first_for_heavy_compute = true
If server unreachable: mark job BLOCKED.
"""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_SERVER_HOST = "192.168.31.218"
DEFAULT_SERVER_USER = "xh"

# Required conda/micromamba envs on server
REQUIRED_ENVS = {
    "stamp-colabfold",
    "stamp-foldx",
    "stamp-flexpepdock",
    "stamp-amber",
}


def is_server_reachable(host: str = DEFAULT_SERVER_HOST, timeout: int = 5) -> bool:
    """Check if server is reachable via SSH."""
    try:
        result = subprocess.run(
            ["ssh", "-o", f"ConnectTimeout={timeout}", f"{DEFAULT_SERVER_USER}@{host}", "echo ok"],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
        return result.returncode == 0 and "ok" in result.stdout
    except Exception as exc:
        logger.warning(f"Server reachability check failed: {exc}")
        return False


def check_server_env(env_name: str, host: str = DEFAULT_SERVER_HOST) -> bool:
    """Check if a conda/micromamba env exists on the server."""
    if not is_server_reachable(host):
        return False
    try:
        cmd = f"micromamba env list | grep {env_name} || conda env list | grep {env_name}"
        result = subprocess.run(
            ["ssh", f"{DEFAULT_SERVER_USER}@{host}", cmd],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and env_name in result.stdout
    except Exception as exc:
        logger.warning(f"Env check failed for {env_name}: {exc}")
        return False


def run_server_command(cmd: str, host: str = DEFAULT_SERVER_HOST, timeout: Optional[int] = None) -> subprocess.CompletedProcess:
    """Run a command on the server via SSH."""
    full_cmd = ["ssh", f"{DEFAULT_SERVER_USER}@{host}", cmd]
    return subprocess.run(full_cmd, capture_output=True, text=True, timeout=timeout)


def scp_to_server(local_path: str, remote_path: str, host: str = DEFAULT_SERVER_HOST) -> bool:
    """Upload a file to the server."""
    try:
        result = subprocess.run(
            ["scp", local_path, f"{DEFAULT_SERVER_USER}@{host}:{remote_path}"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.error(f"SCP upload failed: {exc}")
        return False


def scp_from_server(remote_path: str, local_path: str, host: str = DEFAULT_SERVER_HOST) -> bool:
    """Download a file from the server."""
    try:
        result = subprocess.run(
            ["scp", f"{DEFAULT_SERVER_USER}@{host}:{remote_path}", local_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except Exception as exc:
        logger.error(f"SCP download failed: {exc}")
        return False


class ServerComputeRunner:
    """High-level runner that dispatches compute jobs to the server."""

    def __init__(self, host: str = DEFAULT_SERVER_HOST):
        self.host = host
        self.reachable = is_server_reachable(host)

    def dispatch(self, job_type: str, input_json: dict) -> dict:
        """Dispatch a job. Returns result dict with status and error info."""
        if not self.reachable:
            return {
                "status": "BLOCKED",
                "error_code": "SERVER_UNREACHABLE",
                "message": f"Server {self.host} is not reachable. Job deferred.",
            }

        # P1/P2 MVP: return BLOCKED for all heavy compute until wrappers are ready
        # Actual command dispatch will be implemented in P3
        return {
            "status": "BLOCKED",
            "error_code": "WRAPPER_NOT_READY",
            "message": f"Wrapper for {job_type} not yet implemented. Job queued for P3.",
        }
