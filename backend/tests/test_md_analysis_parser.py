"""Tests for MD Analysis Parser (v1.5 P3).

Rules:
- Must not fabricate metrics.
- Must return BLOCKED for missing files.
- Must return SUCCEEDED only for real parsed data.
"""

from __future__ import annotations

import os
import tempfile

import pytest

from app.services.md_analysis_parser import (
    MdAnalysisResult,
    XvgData,
    analyze_md_pilot,
    parse_xvg,
)


# ---------------------------------------------------------------------------
# parse_xvg
# ---------------------------------------------------------------------------

def test_parse_xvg_missing_file():
    assert parse_xvg("/nonexistent/file.xvg") is None


def test_parse_xvg_valid():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xvg", delete=False) as f:
        f.write("# This is a comment\n")
        f.write('@    title "RMSD"\n')
        f.write('@    xaxis  "Time (ps)"\n')
        f.write('@    yaxis  "RMSD (nm)"\n')
        f.write('@    legend "Backbone"\n')
        f.write("0.0   0.123\n")
        f.write("1.0   0.456\n")
        f.write("2.0   0.789\n")
        path = f.name
    try:
        data = parse_xvg(path)
        assert data is not None
        assert data.title == "RMSD"
        assert data.xlabel == "Time (ps)"
        assert data.ylabel == "RMSD (nm)"
        assert data.legend == ["Backbone"]
        assert data.time == [0.0, 1.0, 2.0]
        assert data.columns == [[0.123, 0.456, 0.789]]
    finally:
        os.unlink(path)


def test_parse_xvg_multi_column():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xvg", delete=False) as f:
        f.write('@    title "RG"\n')
        f.write("0.0   1.1   2.2\n")
        f.write("1.0   1.2   2.3\n")
        path = f.name
    try:
        data = parse_xvg(path)
        assert data is not None
        assert data.time == [0.0, 1.0]
        assert len(data.columns) == 2
        assert data.columns[0] == [1.1, 1.2]
        assert data.columns[1] == [2.2, 2.3]
    finally:
        os.unlink(path)


def test_parse_xvg_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xvg", delete=False) as f:
        f.write("# only comments\n")
        path = f.name
    try:
        assert parse_xvg(path) is None
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# analyze_md_pilot
# ---------------------------------------------------------------------------

def test_analyze_md_pilot_missing_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, "analysis"))
        result = analyze_md_pilot(tmpdir)
        assert result.status == "BLOCKED"
        assert "Missing" in result.error


def test_analyze_md_pilot_succeeded():
    with tempfile.TemporaryDirectory() as tmpdir:
        analysis_dir = os.path.join(tmpdir, "analysis")
        os.makedirs(analysis_dir)
        # Write rmsd.xvg
        with open(os.path.join(analysis_dir, "rmsd.xvg"), "w") as f:
            f.write("0.0 0.1\n1.0 0.2\n")
        # Write rmsf.xvg
        with open(os.path.join(analysis_dir, "rmsf.xvg"), "w") as f:
            f.write("1 0.15\n2 0.25\n")
        # Write rg.xvg
        with open(os.path.join(analysis_dir, "rg.xvg"), "w") as f:
            f.write("0.0 1.0\n1.0 1.1\n")

        result = analyze_md_pilot(tmpdir)
        assert result.status == "SUCCEEDED"
        assert result.rmsd is not None
        assert result.rmsf is not None
        assert result.rg is not None
        assert result.error is None


def test_analyze_md_pilot_never_fabricates():
    """analyze_md_pilot must never return SUCCEEDED with fake data."""
    result = analyze_md_pilot("/nonexistent/dir")
    assert result.status != "SUCCEEDED"
    assert result.rmsd is None
    assert result.rmsf is None
    assert result.rg is None


# ---------------------------------------------------------------------------
# Scientific boundary
# ---------------------------------------------------------------------------

def test_analyze_returns_blocked_not_succeeded_for_missing():
    """Missing files → BLOCKED, never SUCCEEDED."""
    with tempfile.TemporaryDirectory() as tmpdir:
        result = analyze_md_pilot(tmpdir)
        assert result.status == "BLOCKED"
        assert result.status != "SUCCEEDED"


def test_parse_real_rmsd_xvg():
    """Parse real RMSD .xvg from 1 ns MD pilot."""
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "md_analysis")
    rmsd_path = os.path.join(fixture_dir, "rmsd.xvg")
    data = parse_xvg(rmsd_path)
    assert data is not None
    assert data.title == "RMSD"
    assert len(data.time) > 0
    assert len(data.columns) == 1
    assert all(isinstance(v, float) for v in data.time)
    assert all(isinstance(v, float) for v in data.columns[0])


def test_parse_real_rmsf_xvg():
    """Parse real RMSF .xvg from 1 ns MD pilot."""
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "md_analysis")
    rmsf_path = os.path.join(fixture_dir, "rmsf.xvg")
    data = parse_xvg(rmsf_path)
    assert data is not None
    assert "RMS fluctuation" in (data.title or "")
    assert len(data.time) > 0
    assert len(data.columns) == 1


def test_parse_real_rg_xvg():
    """Parse real Rg .xvg from 1 ns MD pilot."""
    fixture_dir = os.path.join(os.path.dirname(__file__), "fixtures", "md_analysis")
    rg_path = os.path.join(fixture_dir, "rg.xvg")
    data = parse_xvg(rg_path)
    assert data is not None
    assert "Radius of gyration" in (data.title or "")
    assert len(data.time) > 0
    assert len(data.columns) == 4  # total + 3 axes
