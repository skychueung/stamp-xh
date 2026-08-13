"""Tests for MD Pilot Runner (v1.5 P2).

Rules:
- GROMACS missing → BLOCKED
- stamp-md env missing → BLOCKED
- Input PDB missing → FAILED
- Workdir creation succeeds
- Artifact missing → not SUCCEEDED
- dry_run produces no fake results
- probe returns complete structure
- GPU info can be empty but must not error
- No fake trajectory/RMSD/RMSF/energy without real files
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.services.md_pilot_runner import (
    check_environment,
    create_workdir,
    dry_run,
    smoke_run,
    validate_input,
    dispatch,
)


# ---------------------------------------------------------------------------
# validate_input
# ---------------------------------------------------------------------------

def test_validate_input_empty():
    ok, err = validate_input({})
    assert ok is False
    assert "empty" in err.lower()


def test_validate_input_missing_pdb():
    ok, err = validate_input({"forcefield": "amber99sb-ildn"})
    assert ok is False
    assert "input_pdb" in err.lower()


def test_validate_input_missing_file():
    ok, err = validate_input({"input_pdb": "/nonexistent/file.pdb"})
    assert ok is False
    assert "not found" in err.lower()


def test_validate_input_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        ok, err = validate_input({"input_pdb": path})
        assert ok is True
        assert err is None
    finally:
        os.unlink(path)


def test_validate_input_invalid_pdb_format():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("REMARK   1 This is just a remark\n")
        path = f.name
    try:
        ok, err = validate_input({"input_pdb": path})
        assert ok is False
        assert "not a valid PDB" in err
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# create_workdir
# ---------------------------------------------------------------------------

def test_create_workdir():
    workdir = create_workdir("batch-test-123", "item-test-456")
    assert os.path.isdir(workdir)
    for sub in ("inputs", "topology", "solvated", "minimization",
                "equilibration", "production", "analysis", "logs", "artifacts"):
        assert os.path.isdir(os.path.join(workdir, sub))


# ---------------------------------------------------------------------------
# check_environment
# ---------------------------------------------------------------------------

def test_check_environment_returns_tuple():
    ok, reasons = check_environment()
    assert isinstance(ok, bool)
    assert isinstance(reasons, list)
    if ok:
        assert len(reasons) == 0


# ---------------------------------------------------------------------------
# dry_run
# ---------------------------------------------------------------------------

def test_dry_run_returns_structure():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        result = dry_run("batch-dry", "item-dry", {"input_pdb": path})
        assert "workdir" in result
        assert "commands" in result
        assert isinstance(result["commands"], list)
        assert len(result["commands"]) > 0
        assert result["dry_run"] is True
        assert result["input_pdb"] == path
        assert result["forcefield"] == "amber99sb-ildn"
        assert result["water_model"] == "tip3p"
        assert result["box_type"] == "dodecahedron"
        assert result["ion_conc"] == 0.15
    finally:
        os.unlink(path)


def test_dry_run_no_fake_metrics():
    """dry_run must not return fake RMSD/RMSF/Rg/ΔG/trajectory/energy."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        result = dry_run("batch-dry", "item-dry", {"input_pdb": path})
        # Should not contain any fabricated scientific results
        for key in ("rmsd", "rmsf", "rg", "delta_g", "energy", "trajectory"):
            assert key not in result, f"dry_run must not contain fabricated '{key}'"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# smoke_run
# ---------------------------------------------------------------------------

def test_smoke_run_returns_tuple():
    success, error = smoke_run()
    assert isinstance(success, bool)
    # May be True (env ready) or False (env missing) — both are valid
    if success:
        assert error is None
    else:
        assert error is not None


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------

def test_dispatch_missing_input():
    status, error, output = dispatch("batch-1", "item-1", {})
    assert status == "FAILED"
    assert error is not None
    assert output is None


def test_dispatch_valid_input():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        status, error, output = dispatch("batch-1", "item-1", {"input_pdb": path})
        # May be BLOCKED (env missing) or RUNNING (env ready)
        assert status in ("BLOCKED", "RUNNING", "FAILED")
        if status == "RUNNING":
            assert output is not None
            assert "workdir" in output
            assert "status" in output
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated results
# ---------------------------------------------------------------------------

def test_dispatch_never_returns_succeeded():
    """P2 dispatch must never return SUCCEEDED — real MD not yet implemented."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pdb", delete=False) as f:
        f.write("ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00 20.00           N\n")
        path = f.name
    try:
        status, error, output = dispatch("batch-1", "item-1", {"input_pdb": path})
        assert status != "SUCCEEDED", "P2 must not claim SUCCEEDED without real MD output"
    finally:
        os.unlink(path)
