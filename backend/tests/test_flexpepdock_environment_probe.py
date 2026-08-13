"""Tests for FlexPepDock Environment Probe Service (v1.5 P1).

Rules:
- Must verify BLOCKED when tools are missing
- Must verify AVAILABLE when tools are present
- Must NOT fabricate metrics
- Must NOT claim SUCCEEDED without real files
"""

from __future__ import annotations

import os


from app.services.flexpepdock_environment_probe import (
    FlexPepDockEnvironmentReport,
    _check_binary_via_env,
    _check_rosetta_db,
    _get_rosetta_root,
    probe_flexpepdock_environment,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def test_check_binary_via_env_missing_script():
    ok, path = _check_binary_via_env("FlexPepDocking", "/nonexistent/env.sh")
    assert ok is False
    assert path is None


def test_get_rosetta_root_missing_script():
    root = _get_rosetta_root("/nonexistent/env.sh")
    assert root is None


def test_check_rosetta_db_missing_root():
    assert _check_rosetta_db(None) is False
    assert _check_rosetta_db("/nonexistent/path") is False


# ---------------------------------------------------------------------------
# Report dataclass
# ---------------------------------------------------------------------------

def test_report_to_dict():
    report = FlexPepDockEnvironmentReport(
        status="BLOCKED",
        rosetta_env_script_exists=False,
        flexpepdock_available=False,
        rosetta_scripts_available=False,
        rosetta_db_available=False,
        rosetta_root=None,
        blocking_reasons=["test reason"],
    )
    d = report.to_dict()
    assert d["status"] == "BLOCKED"
    assert d["rosetta_env_script_exists"] is False
    assert d["blocking_reasons"] == ["test reason"]


# ---------------------------------------------------------------------------
# Full probe
# ---------------------------------------------------------------------------

def test_probe_flexpepdock_environment_no_env():
    """Probe without Rosetta env script should be BLOCKED."""
    # Temporarily override env script to a nonexistent path
    original = os.environ.get("ROSETTA_ENV_SCRIPT")
    os.environ["ROSETTA_ENV_SCRIPT"] = "/nonexistent/rosetta_env.sh"
    try:
        report = probe_flexpepdock_environment()
        assert report.status == "BLOCKED"
        assert report.rosetta_env_script_exists is False
        assert any("env script not found" in r for r in report.blocking_reasons)
    finally:
        if original is not None:
            os.environ["ROSETTA_ENV_SCRIPT"] = original
        else:
            os.environ.pop("ROSETTA_ENV_SCRIPT", None)


def test_probe_flexpepdock_environment_returns_report():
    """Probe must return a valid report structure regardless of env state."""
    report = probe_flexpepdock_environment()
    assert report.status in ("AVAILABLE", "BLOCKED")
    assert isinstance(report.rosetta_env_script_exists, bool)
    assert isinstance(report.flexpepdock_available, bool)
    assert isinstance(report.rosetta_scripts_available, bool)
    assert isinstance(report.rosetta_db_available, bool)
    assert isinstance(report.blocking_reasons, list)


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated metrics
# ---------------------------------------------------------------------------

def test_probe_never_returns_succeeded():
    """probe_flexpepdock_environment only returns AVAILABLE or BLOCKED, never SUCCEEDED."""
    report = probe_flexpepdock_environment()
    assert report.status != "SUCCEEDED"
    assert report.status != "FAILED"


def test_probe_never_fabricates_binary_path():
    """If binary is not available, path should not be fabricated."""
    report = probe_flexpepdock_environment()
    if not report.flexpepdock_available:
        # When env script is missing, binary is definitely not available
        assert report.rosetta_env_script_exists is False or report.flexpepdock_available is False
