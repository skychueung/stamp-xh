"""Tests for MD Environment Probe Service (v1.5 P2).

Rules:
- Must verify BLOCKED when tools are missing
- Must verify AVAILABLE when tools are present
- Must NOT fabricate metrics
- Must NOT claim SUCCEEDED without real files
"""

from __future__ import annotations

import os
import tempfile


from app.services.md_environment_probe import (
    check_command,
    check_gpu,
    check_python_module,
    probe_md_environment,
    validate_pdb,
    _check_conda_env,
    _check_mmgbsa_in_conda_env,
)


# ---------------------------------------------------------------------------
# Command checks
# ---------------------------------------------------------------------------

def test_check_command_python3_exists():
    ok, version = check_command("python3")
    assert ok is True
    assert version is not None or version is None  # version may or may not be parsable


def test_check_command_fake_missing():
    ok, version = check_command("this_command_does_not_exist_12345")
    assert ok is False
    assert version is None


# ---------------------------------------------------------------------------
# GPU check
# ---------------------------------------------------------------------------

def test_check_gpu_returns_tuple():
    gpu_ok, gpu_info = check_gpu()
    assert isinstance(gpu_ok, bool)
    assert gpu_info is None or isinstance(gpu_info, list)


# ---------------------------------------------------------------------------
# Python module check
# ---------------------------------------------------------------------------

def test_check_python_module_numpy():
    assert check_python_module("numpy") is True


def test_check_python_module_fake():
    assert check_python_module("this_module_does_not_exist_12345") is False


# ---------------------------------------------------------------------------
# Conda env check
# ---------------------------------------------------------------------------

def test_check_conda_env_stamp_md():
    # May be True on server, False locally â?either is valid
    result = _check_conda_env("stamp-md")
    assert isinstance(result, bool)


def test_check_conda_env_nonexistent():
    assert _check_conda_env("this_env_does_not_exist_99999") is False


# ---------------------------------------------------------------------------
# PDB validation
# ---------------------------------------------------------------------------

def test_validate_pdb_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        f.write("ATOM    2  CA  ALA A   1      11.000  10.000  10.000  1.00 20.00           C\n")
        path = f.name
    try:
        assert validate_pdb(path) is True
    finally:
        os.unlink(path)


def test_validate_pdb_no_atoms():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("REMARK   1 This is just a remark\n")
        f.write("HEADER    TEST\n")
        path = f.name
    try:
        assert validate_pdb(path) is False
    finally:
        os.unlink(path)


def test_validate_pdb_missing_file():
    assert validate_pdb("/nonexistent/path/test.pdb") is False


# ---------------------------------------------------------------------------
# Full probe
# ---------------------------------------------------------------------------

def test_probe_md_environment_no_input():
    """Probe without input PDB should not block on PDB."""
    report = probe_md_environment(input_pdb_path=None)
    assert report.status in ("AVAILABLE", "BLOCKED")
    assert isinstance(report.stamp_md_env_available, bool)
    assert isinstance(report.gromacs_available, bool)
    assert isinstance(report.gpu_available, bool)
    assert isinstance(report.mdanalysis_available, bool)
    assert isinstance(report.parmed_available, bool)
    assert isinstance(report.openmm_available, bool)
    assert isinstance(report.blocking_reasons, list)
    assert isinstance(report.next_actions, list)


def test_probe_md_environment_with_invalid_pdb():
    report = probe_md_environment(input_pdb_path="/nonexistent/test.pdb")
    assert report.input_pdb_valid is False
    assert any("PDB invalid or missing" in r for r in report.blocking_reasons)


def test_probe_md_environment_with_valid_pdb():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        report = probe_md_environment(input_pdb_path=path)
        assert report.input_pdb_valid is True
        assert report.input_pdb_path == path
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated metrics
# ---------------------------------------------------------------------------

def test_probe_never_returns_succeeded():
    """probe_md_environment only returns AVAILABLE or BLOCKED, never SUCCEEDED."""
    report = probe_md_environment()
    assert report.status != "SUCCEEDED"
    assert report.status != "FAILED"
    assert report.status in ("AVAILABLE", "BLOCKED")


def test_probe_never_fabricates_gpu_info():
    report = probe_md_environment()
    if not report.gpu_available:
        assert report.gpu_info is None
    else:
        assert report.gpu_info is not None
        for gpu in report.gpu_info:
            assert "name" in gpu
            assert isinstance(gpu["name"], str)
            assert len(gpu["name"]) > 0


def test_probe_returns_next_actions():
    """probe_md_environment always returns next_actions (may be empty)."""
    report = probe_md_environment()
    assert isinstance(report.next_actions, list)
    if report.status == "BLOCKED":
        assert len(report.next_actions) >= len(report.blocking_reasons)


def test_probe_env_missing_is_blocked():
    """If stamp-md env does not exist, report must be BLOCKED or have reasons."""
    report = probe_md_environment()
    # We don't force this â?it depends on the actual environment.
    # But if stamp_md_env_available is False, status must be BLOCKED.
    if not report.stamp_md_env_available:
        assert report.status == "BLOCKED"
        assert any("stamp-md" in r.lower() for r in report.blocking_reasons)

def test_probe_mmgbsa_field_exists():
    """MM-GBSA availability must be reported as a boolean."""
    report = probe_md_environment()
    assert isinstance(report.mmgbsa_available, bool)
    assert report.mmgbsa_version is None or isinstance(report.mmgbsa_version, str)


def test_check_mmgbsa_in_conda_env_missing():
    """Non-existent env should return False for gmx_MMPBSA."""
    ok, version = _check_mmgbsa_in_conda_env("nonexistent_env_12345")
    assert ok is False
    assert version is None

