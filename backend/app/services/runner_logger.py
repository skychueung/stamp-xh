"""Runner Logger — Unified log capture for STAMP compute runners.

v1.5-md-computation-pilot

Standardizes log directory structure:
    data/batch_jobs/{batch_id}/{job_type}/{item_id}/logs/
        command.txt
        stdout.log
        stderr.log
        returncode.txt
        started_at
        finished_at

All real command executions must go through execute_command() so that
stdout/stderr/returncode are captured and persisted to disk.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.services.batch_dir_service import get_item_logs_dir

logger = logging.getLogger("stamp")

DEFAULT_TAIL_LINES = 200
MAX_LOG_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB safety cap


class RunLogResult:
    """Result of a logged command execution."""

    def __init__(
        self,
        returncode: int,
        stdout_path: str,
        stderr_path: str,
        command_path: str,
        started_at: datetime,
        finished_at: datetime,
        stdout_text: str,
        stderr_text: str,
    ):
        self.returncode = returncode
        self.stdout_path = stdout_path
        self.stderr_path = stderr_path
        self.command_path = command_path
        self.started_at = started_at
        self.finished_at = finished_at
        self.stdout_text = stdout_text
        self.stderr_text = stderr_text

    def to_dict(self) -> dict:
        return {
            "returncode": self.returncode,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "command_path": self.command_path,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "duration_seconds": (
                self.finished_at - self.started_at
            ).total_seconds(),
        }


def ensure_log_dir(batch_id: str, item_id: str, job_type: str) -> str:
    """Create and return the logs directory for a batch item.

    Path: data/batch_jobs/{batch_id}/{job_type}/{item_id}/logs/
    """
    log_dir = get_item_logs_dir(batch_id, item_id, job_type)
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    return log_dir


def execute_command(
    cmd: list[str] | str,
    log_dir: str,
    timeout: Optional[int] = None,
    env: Optional[dict] = None,
    shell: bool = False,
) -> RunLogResult:
    """Execute a command and persist all outputs to the log directory.

    Files written:
        - command.txt   : the command string
        - started_at    : ISO timestamp of start
        - stdout.log    : captured stdout
        - stderr.log    : captured stderr
        - returncode.txt: exit code as string
        - finished_at   : ISO timestamp of finish

    Args:
        cmd: Command as list of args or single string.
        log_dir: Directory where log files will be written.
        timeout: Optional subprocess timeout in seconds.
        env: Optional environment variable overrides.
        shell: Whether to run via shell (default False).

    Returns:
        RunLogResult with paths and captured output.
    """
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    # Normalize command for recording
    if isinstance(cmd, list):
        command_str = " ".join(cmd)
        execution_cmd = list(cmd)
        if execution_cmd and execution_cmd[0] in {"python", "python3"}:
            execution_cmd[0] = sys.executable
    else:
        command_str = cmd
        execution_cmd = cmd
        if not shell:
            shell = True

    # Record command
    command_path = Path(log_dir) / "command.txt"
    command_path.write_text(command_str, encoding="utf-8")

    # Record start time
    started_at = datetime.now(timezone.utc)
    (Path(log_dir) / "started_at").write_text(started_at.isoformat(), encoding="utf-8")

    logger.info("[RUNNER] Command starting. log_dir=%s cmd=%s", log_dir, command_str[:500])

    try:
        result = subprocess.run(
            execution_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            shell=shell,
        )
        stdout_text = result.stdout or ""
        stderr_text = result.stderr or ""
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout_text = (exc.stdout or b"").decode("utf-8", errors="replace")
        stderr_text = (exc.stderr or b"").decode("utf-8", errors="replace")
        returncode = -1
        stderr_text += f"\n[RUNNER_LOGGER] Command timed out after {timeout}s"
        logger.warning("[RUNNER] Command timed out. log_dir=%s", log_dir)
    except Exception as exc:
        stdout_text = ""
        stderr_text = f"[RUNNER_LOGGER] Failed to execute command: {type(exc).__name__}: {exc}"
        returncode = -1
        logger.error("[RUNNER] Command execution error: %s", exc)

    finished_at = datetime.now(timezone.utc)

    # Write outputs
    stdout_path = Path(log_dir) / "stdout.log"
    stderr_path = Path(log_dir) / "stderr.log"
    returncode_path = Path(log_dir) / "returncode.txt"
    finished_at_path = Path(log_dir) / "finished_at"

    _safe_write(stdout_path, stdout_text)
    _safe_write(stderr_path, stderr_text)
    returncode_path.write_text(str(returncode), encoding="utf-8")
    finished_at_path.write_text(finished_at.isoformat(), encoding="utf-8")

    logger.info(
        "[RUNNER] Command finished. rc=%s duration=%.2fs log_dir=%s",
        returncode,
        (finished_at - started_at).total_seconds(),
        log_dir,
    )

    return RunLogResult(
        returncode=returncode,
        stdout_path=str(stdout_path),
        stderr_path=str(stderr_path),
        command_path=str(command_path),
        started_at=started_at,
        finished_at=finished_at,
        stdout_text=stdout_text,
        stderr_text=stderr_text,
    )


def _safe_write(path: Path, text: str) -> None:
    """Write text to path, truncating if it exceeds MAX_LOG_SIZE_BYTES."""
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_LOG_SIZE_BYTES:
        truncated = encoded[:MAX_LOG_SIZE_BYTES].decode("utf-8", errors="replace")
        truncated += "\n[RUNNER_LOGGER] LOG TRUNCATED: exceeded 50 MB limit"
        path.write_text(truncated, encoding="utf-8")
    else:
        path.write_text(text, encoding="utf-8")


def read_log(log_path: str) -> str:
    """Read the full contents of a log file."""
    p = Path(log_path)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"[Error reading log: {exc}]"


def read_log_tail(log_path: str, n: int = DEFAULT_TAIL_LINES) -> str:
    """Read the last N lines of a log file."""
    p = Path(log_path)
    if not p.exists():
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return "".join(lines[-n:])
    except Exception as exc:
        return f"[Error reading log tail: {exc}]"


class LogMetadata:
    """Metadata about a runner log directory."""

    def __init__(self, log_dir: str):
        self.log_dir = Path(log_dir)
        self.exists = self.log_dir.is_dir()

    def _read_text(self, name: str) -> Optional[str]:
        p = self.log_dir / name
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                return None
        return None

    def to_dict(self) -> dict:
        return {
            "log_dir": str(self.log_dir),
            "exists": self.exists,
            "command": self._read_text("command.txt"),
            "returncode": self._read_text("returncode.txt"),
            "started_at": self._read_text("started_at"),
            "finished_at": self._read_text("finished_at"),
            "stdout_exists": (self.log_dir / "stdout.log").exists(),
            "stderr_exists": (self.log_dir / "stderr.log").exists(),
            "stdout_size": (self.log_dir / "stdout.log").stat().st_size
            if (self.log_dir / "stdout.log").exists()
            else 0,
            "stderr_size": (self.log_dir / "stderr.log").stat().st_size
            if (self.log_dir / "stderr.log").exists()
            else 0,
        }


def get_log_metadata(log_dir: str) -> LogMetadata:
    """Return metadata for a log directory."""
    return LogMetadata(log_dir)


def get_log_dir_for_item(batch_id: str, item_id: str, job_type: str) -> str:
    """Return the canonical log directory path for a batch item."""
    return ensure_log_dir(batch_id, item_id, job_type)
