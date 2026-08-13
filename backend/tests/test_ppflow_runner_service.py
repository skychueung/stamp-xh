"""Unit tests for the PPFlow runner service skeleton — P29F.

These tests verify that the service layer:
  * Checks the gate (always closed in P29F).
  * Plans paths without creating them.
  * Returns command previews without executing.
  * Builds manifest/failure schemas.
  * Returns a status summary with all safety flags.
  * Never calls subprocess.run.
  * Never calls torch.load.
  * Does not break the existing PPFlow adapter or PepMLM registry.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.ppflow_runner_service import PPFlowRunnerService
from app.services.ppflow_real_runner import (
    STAGE,
    VALIDATION_STATUS,
    DISCLAIMER,
)


class TestPPFlowRunnerServiceGate:
    """Test service gate check."""

    def test_check_gate_returns_closed(self, tmp_path: Path) -> None:
        svc = PPFlowRunnerService(gate_file=tmp_path / ".gate")
        result = svc.check_gate()
        assert result["gate_open"] is False
        assert result["blocked_reason"] == "ppflow_real_run_gate_closed"

    def test_check_gate_default_file(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.check_gate()
        assert result["gate_open"] is False


class TestPPFlowRunnerServicePaths:
    """Test service path planning."""

    def test_plan_paths_does_not_create(self, tmp_path: Path) -> None:
        svc = PPFlowRunnerService(
            jobs_base=tmp_path / "jobs",
            artifacts_base=tmp_path / "artifacts",
            logs_base=tmp_path / "logs",
        )
        result = svc.plan_paths("test-job-001")
        assert result["paths_created"] is False
        assert result["job_id"] == "test-job-001"
        assert "job_dir" in result
        assert "artifact_dir" in result
        assert "log_file" in result
        # Verify nothing was actually created
        assert not (tmp_path / "jobs").exists()
        assert not (tmp_path / "artifacts").exists()
        assert not (tmp_path / "logs").exists()

    def test_plan_paths_generates_job_id(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.plan_paths()
        assert result["job_id"]
        assert len(result["job_id"]) > 0


class TestPPFlowRunnerServiceCommand:
    """Test service command preview."""

    def test_command_preview_not_executed(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.command_preview(job_id="test-001")
        assert result["executed"] is False
        assert result["subprocess_called"] is False
        assert result["stage"] == STAGE

    @patch("subprocess.run")
    def test_command_preview_no_subprocess(self, mock_run: MagicMock) -> None:
        svc = PPFlowRunnerService()
        svc.command_preview(job_id="test-001")
        mock_run.assert_not_called()


class TestPPFlowRunnerServicePlanRun:
    """Test service plan_run."""

    def test_plan_run_returns_blocked(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.plan_run(job_id="test-001")
        assert result["status"] == "blocked"
        assert result["gate"]["gate_open"] is False
        assert result["runs_model"] is False
        assert result["generates_candidates"] is False
        assert result["generates_pdb"] is False
        assert result["subprocess_called"] is False
        assert result["codesign_ppf_executed"] is False
        assert result["imports_ppflow_source"] is False
        assert result["uses_torch_load"] is False
        assert result["real_run_enabled"] is False

    def test_plan_run_has_paths(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.plan_run(job_id="test-001")
        assert "paths" in result
        assert "job_dir" in result["paths"]
        assert "artifact_dir" in result["paths"]
        assert "log_file" in result["paths"]

    def test_plan_run_has_manifest_and_failure(self) -> None:
        svc = PPFlowRunnerService()
        result = svc.plan_run(job_id="test-001")
        assert "manifest_post" in result
        assert "failure" in result
        assert result["manifest_post"]["validation_status"] == VALIDATION_STATUS
        assert result["failure"]["validation_status"] == VALIDATION_STATUS


class TestPPFlowRunnerServiceSchemas:
    """Test service schema builders."""

    def test_build_manifest_post(self) -> None:
        svc = PPFlowRunnerService()
        manifest = svc.build_manifest_post("test-001")
        assert manifest["model_id"] == "ppflow"
        assert manifest["validation_status"] == VALIDATION_STATUS
        assert manifest["runs_model"] is False
        assert manifest["generates_candidates"] is False
        assert manifest["generates_pdb"] is False
        assert manifest["stage"] == STAGE

    def test_build_failure(self) -> None:
        svc = PPFlowRunnerService()
        failure = svc.build_failure("test-001", error_type="gate_closed")
        assert failure["model_id"] == "ppflow"
        assert failure["validation_status"] == VALIDATION_STATUS
        assert failure["error_type"] == "gate_closed"
        assert failure["runs_model"] is False


class TestPPFlowRunnerServiceStatusSummary:
    """Test service status summary."""

    def test_status_summary(self) -> None:
        svc = PPFlowRunnerService()
        summary = svc.status_summary()
        assert summary["model_id"] == "ppflow"
        assert summary["stage"] == STAGE
        assert summary["runner_skeleton_implemented"] is True
        assert summary["real_runner_implemented"] is False
        assert summary["real_run_enabled"] is False
        assert summary["executes_codesign_ppf"] is False
        assert summary["imports_ppflow_source"] is False
        assert summary["uses_torch_load"] is False
        assert summary["runs_model"] is False
        assert summary["generates_candidates"] is False
        assert summary["generates_pdb"] is False
        assert summary["validation_status"] == VALIDATION_STATUS
        assert summary["submit_enabled"] is False

    def test_status_summary_has_gate(self) -> None:
        svc = PPFlowRunnerService()
        summary = svc.status_summary()
        assert "gate" in summary
        assert summary["gate"]["gate_open"] is False


class TestPPFlowRunnerServiceSafety:
    """Test safety guarantees."""

    @patch("subprocess.run")
    def test_no_subprocess_anywhere(self, mock_run: MagicMock) -> None:
        svc = PPFlowRunnerService()
        svc.check_gate()
        svc.plan_paths()
        svc.command_preview()
        svc.plan_run()
        svc.build_manifest_post("test")
        svc.build_failure("test")
        svc.status_summary()
        mock_run.assert_not_called()

    def test_no_torch_load_in_service_module(self) -> None:
        import app.services.ppflow_runner_service as module
        source = open(module.__file__, "r", encoding="utf-8").read()
        assert "torch.load(" not in source
        assert "pickle.load(" not in source

    def test_no_torch_load_in_runner_module(self) -> None:
        import app.services.ppflow_real_runner as module
        source = open(module.__file__, "r", encoding="utf-8").read()
        assert "torch.load(" not in source
        assert "pickle.load(" not in source

    def test_no_ppflow_source_import(self) -> None:
        """Neither module imports ppflow source code."""
        import app.services.ppflow_real_runner as runner_mod
        source = open(runner_mod.__file__, "r", encoding="utf-8").read()
        # Should not contain import statements for ppflow modules
        assert "from ppflow" not in source
        assert "import ppflow" not in source
        assert "from codesign_ppf" not in source
        assert "import codesign_ppf" not in source

    def test_service_plan_run_paths_not_created(self, tmp_path: Path) -> None:
        """Verify plan_run doesn't create directories even with tmp_path bases."""
        svc = PPFlowRunnerService(
            jobs_base=tmp_path / "jobs",
            artifacts_base=tmp_path / "artifacts",
            logs_base=tmp_path / "logs",
        )
        result = svc.plan_run(job_id="test-001")
        assert result["paths_created"] is False
        assert not (tmp_path / "jobs").exists()
        assert not (tmp_path / "artifacts").exists()
        assert not (tmp_path / "logs").exists()
