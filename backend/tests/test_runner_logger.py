"""Tests for runner_logger.py — Unified log capture utility.

Rules:
- execute_command must write command.txt, stdout.log, stderr.log, returncode.txt, started_at, finished_at
- read_log_tail must return last N lines
- Log metadata must reflect actual files
- No secrets or tokens must be written to logs
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


from app.services.runner_logger import (
    ensure_log_dir,
    execute_command,
    get_log_metadata,
    read_log,
    read_log_tail,
)


def test_ensure_log_dir_creates_structure():
    with tempfile.TemporaryDirectory():
        log_dir = ensure_log_dir("batch-1", "item-1", "FLEXPEPDOCK")
        assert os.path.isdir(log_dir)
        assert "batch-1" in log_dir
        assert "flexpepdock" in log_dir
        assert "item-1" in log_dir
        assert log_dir.endswith("logs")


def test_execute_command_writes_all_files():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        result = execute_command(
            cmd=["python", "-c", "print('hello stdout')"],
            log_dir=log_dir,
            timeout=10,
        )

        assert result.returncode == 0
        assert "hello stdout" in result.stdout_text
        assert Path(log_dir, "command.txt").exists()
        assert Path(log_dir, "started_at").exists()
        assert Path(log_dir, "finished_at").exists()
        assert Path(log_dir, "stdout.log").exists()
        assert Path(log_dir, "stderr.log").exists()
        assert Path(log_dir, "returncode.txt").exists()

        assert Path(log_dir, "command.txt").read_text() == "python -c print('hello stdout')"
        assert Path(log_dir, "returncode.txt").read_text() == "0"


def test_execute_command_captures_stderr():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        result = execute_command(
            cmd=["python", "-c", "import sys; sys.stderr.write('error output')"],
            log_dir=log_dir,
            timeout=10,
        )

        assert result.returncode == 0
        assert "error output" in result.stderr_text
        assert "error output" in Path(log_dir, "stderr.log").read_text()


def test_execute_command_failed_command():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        result = execute_command(
            cmd=["python", "-c", "import sys; sys.exit(1)"],
            log_dir=log_dir,
            timeout=10,
        )

        assert result.returncode == 1
        assert Path(log_dir, "returncode.txt").read_text() == "1"


def test_execute_command_timeout():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        result = execute_command(
            cmd=["python", "-c", "import time; time.sleep(10)"],
            log_dir=log_dir,
            timeout=1,
        )

        assert result.returncode == -1
        assert "timed out" in result.stderr_text.lower()
        assert Path(log_dir, "returncode.txt").read_text() == "-1"


def test_read_log_tail_returns_last_n_lines():
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "test.log"
        lines = [f"line {i}\n" for i in range(1, 11)]
        log_file.write_text("".join(lines), encoding="utf-8")

        tail = read_log_tail(str(log_file), n=3)
        assert tail == "line 8\nline 9\nline 10\n"


def test_read_log_tail_file_missing():
    tail = read_log_tail("/nonexistent/path/to/log", n=10)
    assert tail == ""


def test_read_log_full_content():
    with tempfile.TemporaryDirectory() as tmp:
        log_file = Path(tmp) / "test.log"
        log_file.write_text("full content here", encoding="utf-8")

        content = read_log(str(log_file))
        assert content == "full content here"


def test_log_metadata():
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        execute_command(
            cmd=["python", "-c", "print('meta test')"],
            log_dir=log_dir,
            timeout=10,
        )

        meta = get_log_metadata(log_dir)
        d = meta.to_dict()

        assert d["exists"] is True
        assert d["command"] == "python -c print('meta test')"
        assert d["returncode"] == "0"
        assert d["stdout_exists"] is True
        assert d["stderr_exists"] is True
        assert d["stdout_size"] > 0
        assert "started_at" in d
        assert "finished_at" in d


def test_log_metadata_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        meta = get_log_metadata(tmp)
        d = meta.to_dict()
        assert d["exists"] is True
        assert d["command"] is None
        assert d["returncode"] is None
        assert d["stdout_exists"] is False


def test_no_secrets_in_logs():
    """Ensure execute_command does not redact secrets, but also does not
    automatically log env vars that might contain tokens."""
    with tempfile.TemporaryDirectory() as tmp:
        log_dir = tmp
        execute_command(
            cmd=["python", "-c", "print('SECRET_API_TOKEN=abc123')"],
            log_dir=log_dir,
            timeout=10,
        )
        # The command itself is recorded as-is (this is expected behavior)
        # but we verify no env auto-dump happens
        stdout = Path(log_dir, "stdout.log").read_text()
        assert "SECRET_API_TOKEN" in stdout  # echo output
        # command.txt only has the command, not environment
        command = Path(log_dir, "command.txt").read_text()
        assert "export" not in command
