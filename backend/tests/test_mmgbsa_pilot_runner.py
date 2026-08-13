"""Tests for mmgbsa_pilot_runner.py (v1.5 P3)."""

import pytest
from unittest.mock import patch, MagicMock

from app.services.mmgbsa_pilot_runner import (
    validate_input,
    check_environment,
    smoke_run,
    dry_run,
    dispatch,
    create_workdir,
)


class TestValidateInput:
    def test_empty_input(self):
        ok, err = validate_input({})
        assert not ok
        assert "input_json is empty" in err

    def test_missing_topology(self):
        ok, err = validate_input({"trajectory": "/tmp/t.xtc", "index": "/tmp/i.ndx"})
        assert not ok
        assert "topology is required" in err

    def test_missing_trajectory(self):
        ok, err = validate_input({"topology": "/tmp/t.top", "index": "/tmp/i.ndx"})
        assert not ok
        assert "trajectory is required" in err

    def test_missing_index(self):
        ok, err = validate_input({"topology": "/tmp/t.top", "trajectory": "/tmp/t.xtc"})
        assert not ok
        assert "index is required" in err

    def test_topology_not_found(self, tmp_path):
        ok, err = validate_input({
            "topology": str(tmp_path / "nonexistent.top"),
            "trajectory": str(tmp_path / "t.xtc"),
            "index": str(tmp_path / "i.ndx"),
        })
        assert not ok
        assert "topology not found" in err

    def test_valid_input(self, tmp_path):
        top = tmp_path / "t.top"
        traj = tmp_path / "t.xtc"
        idx = tmp_path / "i.ndx"
        top.write_text("")
        traj.write_text("")
        idx.write_text("")
        ok, err = validate_input({
            "topology": str(top),
            "trajectory": str(traj),
            "index": str(idx),
        })
        assert ok
        assert err is None


class TestCheckEnvironment:
    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_available(self, mock_probe):
        report = MagicMock()
        report.status = "AVAILABLE"
        report.mmgbsa_available = True
        mock_probe.return_value = report
        ok, reasons = check_environment()
        assert ok
        assert reasons == []

    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_blocked_by_probe(self, mock_probe):
        report = MagicMock()
        report.status = "BLOCKED"
        report.blocking_reasons = ["gmx missing"]
        mock_probe.return_value = report
        ok, reasons = check_environment()
        assert not ok
        assert "gmx missing" in reasons

    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_blocked_by_mmgbsa(self, mock_probe):
        report = MagicMock()
        report.status = "AVAILABLE"
        report.mmgbsa_available = False
        mock_probe.return_value = report
        ok, reasons = check_environment()
        assert not ok
        assert "gmx_MMPBSA not available" in reasons[0]


class TestSmokeRun:
    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    @patch("app.services.mmgbsa_pilot_runner.subprocess.run")
    def test_smoke_success(self, mock_run, mock_probe):
        report = MagicMock()
        report.status = "AVAILABLE"
        report.mmgbsa_available = True
        mock_probe.return_value = report

        mock_run.return_value = MagicMock(returncode=0, stdout="gmx_MMPBSA v1.5.0", stderr="")
        ok, err = smoke_run()
        assert ok
        assert err is None

    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_smoke_blocked(self, mock_probe):
        report = MagicMock()
        report.status = "BLOCKED"
        report.blocking_reasons = ["env missing"]
        mock_probe.return_value = report
        ok, err = smoke_run()
        assert not ok
        assert "BLOCKED" in err


class TestDryRun:
    def test_returns_commands(self, tmp_path):
        top = tmp_path / "t.top"
        traj = tmp_path / "t.xtc"
        idx = tmp_path / "i.ndx"
        top.write_text("")
        traj.write_text("")
        idx.write_text("")
        result = dry_run("batch-1", "item-1", {
            "topology": str(top),
            "trajectory": str(traj),
            "index": str(idx),
        })
        assert result["dry_run"] is True
        assert len(result["commands"]) > 0
        assert "gmx_MMPBSA" in " ".join(result["commands"])


class TestDispatch:
    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_dispatch_failed_validation(self, mock_probe):
        mock_probe.return_value = MagicMock(status="AVAILABLE", mmgbsa_available=True)
        status, err, out = dispatch("batch-1", "item-1", {})
        assert status == "FAILED"
        assert err is not None

    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_dispatch_blocked(self, mock_probe, tmp_path):
        report = MagicMock()
        report.status = "BLOCKED"
        report.blocking_reasons = ["env missing"]
        mock_probe.return_value = report

        top = tmp_path / "t.top"
        traj = tmp_path / "t.xtc"
        idx = tmp_path / "i.ndx"
        top.write_text("")
        traj.write_text("")
        idx.write_text("")
        status, err, out = dispatch("batch-1", "item-1", {
            "topology": str(top),
            "trajectory": str(traj),
            "index": str(idx),
        })
        assert status == "BLOCKED"
        assert "env missing" in err

    @patch("app.services.mmgbsa_pilot_runner.probe_md_environment")
    def test_dispatch_running(self, mock_probe, tmp_path):
        report = MagicMock()
        report.status = "AVAILABLE"
        report.mmgbsa_available = True
        mock_probe.return_value = report

        top = tmp_path / "t.top"
        traj = tmp_path / "t.xtc"
        idx = tmp_path / "i.ndx"
        top.write_text("")
        traj.write_text("")
        idx.write_text("")
        status, err, out = dispatch("batch-1", "item-1", {
            "topology": str(top),
            "trajectory": str(traj),
            "index": str(idx),
        })
        assert status == "RUNNING"
        assert err is None
        assert out["status"] == "RUNNING"
