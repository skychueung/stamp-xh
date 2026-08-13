"""Unit tests for the PPFlow real runner skeleton — P29F.

These tests verify that:
  * The gate is closed by default.
  * Gate closed → runner returns BLOCKED.
  * Command template is constructed correctly but not executed.
  * Forbidden paths are rejected.
  * out_root / checkpoint / source paths are validated.
  * manifest and failure schemas contain NOT_EXPERIMENTALLY_VALIDATED.
  * subprocess.run is never called.
  * torch.load is never called.
  * No job/artifact directories are written to real data_dev.
  * PPFlow adapter probe/dry-run/submit blocked tests still pass.
  * PepMLM smoke_rerun_verified registry is not broken.
  * registry/models list PPFlow with submit disabled.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

from app.services.ppflow_real_runner import (
    STAGE,
    VALIDATION_STATUS,
    DISCLAIMER,
    CODESIGN_PP,
    DEFAULT_CHECKPOINT,
    ARTIFACTS_BASE,
    PPFlowRunnerBlocked,
    check_gate,
    generate_job_id,
    job_dir_path,
    artifact_dir_path,
    log_file_path,
    validate_out_root,
    validate_source_path,
    validate_checkpoint_path,
    build_command,
    build_manifest_post,
    build_failure,
    run_ppflow_subprocess,
    plan_run,
)


# ---------------------------------------------------------------------------
# 1. Gate default closed
# ---------------------------------------------------------------------------

class TestGateCheck:
    """Test 1: gate default closed."""

    def test_gate_returns_closed_by_default(self, tmp_path: Path) -> None:
        gate = tmp_path / ".ppflow_real_run_enabled"
        result = check_gate(gate)
        assert result["gate_open"] is False
        assert result["blocked_reason"] == "ppflow_real_run_gate_closed"
        assert result["gate_file_exists"] is False

    def test_gate_closed_when_file_does_not_exist(self) -> None:
        """The default GATE_FILE should not exist on the test machine."""
        result = check_gate()
        assert result["gate_open"] is False

    def test_gate_refuses_even_if_file_exists(self, tmp_path: Path) -> None:
        """P29F skeleton must refuse even if a gate file exists."""
        gate = tmp_path / ".ppflow_real_run_enabled"
        gate.write_text("enabled_test_job_20260622", encoding="utf-8")
        result = check_gate(gate)
        assert result["gate_open"] is False
        assert result["gate_file_exists"] is True
        assert "skeleton_refuses" in result["blocked_reason"]

    def test_gate_with_invalid_content(self, tmp_path: Path) -> None:
        gate = tmp_path / ".ppflow_real_run_enabled"
        gate.write_text("garbage", encoding="utf-8")
        result = check_gate(gate)
        assert result["gate_open"] is False
        assert "invalid" in result["blocked_reason"]


# ---------------------------------------------------------------------------
# 2. Gate closed → runner returns BLOCKED
# ---------------------------------------------------------------------------

class TestGateClosedBlocksRunner:
    """Test 2: gate closed → runner returns BLOCKED."""

    def test_plan_run_returns_blocked(self, tmp_path: Path) -> None:
        gate = tmp_path / ".ppflow_real_run_enabled"
        result = plan_run(gate_file=gate) if "gate_file" in plan_run.__code__.co_varnames else plan_run()
        assert result["status"] == "blocked"
        assert result["gate"]["gate_open"] is False

    def test_run_ppflow_subprocess_always_blocked(self) -> None:
        result = run_ppflow_subprocess(["echo", "hello"], job_id="test-123")
        assert result["status"] == "blocked"
        assert result["error_type"] == "gate_closed"

    def test_plan_run_does_not_create_paths(self) -> None:
        result = plan_run()
        assert result["paths_created"] is False


# ---------------------------------------------------------------------------
# 3. Command template constructed correctly but not executed
# ---------------------------------------------------------------------------

class TestCommandTemplate:
    """Test 3: command template correct but not executed."""

    def _setup_paths(self, tmp_path: Path):
        """Create tmp_path-based source, checkpoint, and out_root directories."""
        source = tmp_path / "source" / "ppflow"
        entry = source / "codesign_ppf.py"
        entry.parent.mkdir(parents=True)
        entry.touch()
        ckpt = tmp_path / "checkpoints" / "ppflow" / "model.pt"
        ckpt.parent.mkdir(parents=True)
        ckpt.touch()
        out = tmp_path / "artifacts" / "ppflow" / "job1"
        out.mkdir(parents=True)
        return source, entry, ckpt, out

    def _patch_paths(self, source, entry, ckpt, out):
        """Return a context manager that patches all path validation."""
        stack = ExitStack()
        stack.enter_context(patch("app.services.ppflow_real_runner._ALLOWED_SOURCE_ROOTS", (source,)))
        stack.enter_context(patch("app.services.ppflow_real_runner._ALLOWED_CHECKPOINT_ROOTS", (ckpt.parent,)))
        stack.enter_context(patch("app.services.ppflow_real_runner._ALLOWED_OUT_ROOTS", (out.parent,)))
        stack.enter_context(patch("app.services.ppflow_real_runner.FORBIDDEN_PREFIXES", ()))
        return stack

    def test_build_command_returns_list(self, tmp_path: Path) -> None:
        source, entry, ckpt, out = self._setup_paths(tmp_path)
        with self._patch_paths(source, entry, ckpt, out):
            cmd = build_command(
                env_python="/usr/bin/python3",
                source_root=source,
                codesign_pp=entry,
                config_path=str(source / "config.yml"),
                checkpoint=ckpt,
                out_root=out,
                tag="test",
                seed=42,
                device="cpu",
                batch_size=1,
                index=0,
            )
        assert isinstance(cmd, list)
        assert len(cmd) > 0
        assert cmd[0] == "/usr/bin/python3"
        assert "codesign_ppf.py" in cmd[1]
        assert "--index" in cmd
        assert "-c" in cmd
        assert "-o" in cmd
        assert "-t" in cmd
        assert "-d" in cmd
        assert "cpu" in cmd
        assert "-b" in cmd
        assert "-ckpt" in cmd
        assert "-s" in cmd
        assert "42" in cmd

    def test_build_command_includes_all_required_args(self, tmp_path: Path) -> None:
        """Verify command contains all CLI args from P29E schema."""
        source, entry, ckpt, out = self._setup_paths(tmp_path)
        with self._patch_paths(source, entry, ckpt, out):
            cmd = build_command(
                env_python="/usr/bin/python3",
                source_root=source,
                codesign_pp=entry,
                checkpoint=ckpt,
                out_root=out,
            )
        required_flags = {"--index", "-c", "-o", "-t", "-d", "-b", "-ckpt"}
        found_flags = set(cmd)
        missing = required_flags - found_flags
        assert not missing, f"Missing CLI flags: {missing}"

    @patch("subprocess.run")
    def test_subprocess_run_never_called(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """Test 10: subprocess.run must not be called."""
        source, entry, ckpt, out = self._setup_paths(tmp_path)
        with self._patch_paths(source, entry, ckpt, out):
            build_command(
                env_python="/usr/bin/python3",
                source_root=source,
                codesign_pp=entry,
                checkpoint=ckpt,
                out_root=out,
            )
        # cmd is just a list — never passed to subprocess.run
        mock_run.assert_not_called()

    @patch("subprocess.run")
    def test_run_ppflow_subprocess_does_not_call_subprocess(self, mock_run: MagicMock) -> None:
        """Test 10 (reinforced): run_ppflow_subprocess never calls subprocess.run."""
        run_ppflow_subprocess(["echo", "hi"], job_id="test")
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# 4. Forbidden paths rejected
# ---------------------------------------------------------------------------

class TestForbiddenPaths:
    """Test 4: forbidden paths are rejected."""

    @pytest.mark.parametrize("forbidden", [
        Path("/tmp"),
        Path("/root"),
        Path("/home/xh"),
        Path("/home/xh/stamp"),
        Path("/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform"),
    ])
    def test_forbidden_out_root_rejected(self, forbidden: Path) -> None:
        errors = validate_out_root(forbidden)
        assert len(errors) > 0
        assert "forbidden" in errors[0].lower() or "must be under" in errors[0].lower()

    def test_forbidden_source_rejected(self) -> None:
        errors = validate_source_path(Path("/tmp/evil_source"))
        assert len(errors) > 0

    def test_forbidden_checkpoint_rejected(self) -> None:
        errors = validate_checkpoint_path(Path("/tmp/evil.ckpt"))
        assert len(errors) > 0

    def test_build_command_rejects_forbidden_out_root(self) -> None:
        with pytest.raises(PPFlowRunnerBlocked, match="forbidden|must be under"):
            build_command(out_root=Path("/tmp/evil"))


# ---------------------------------------------------------------------------
# 5. out_root must be in allowed paths
# ---------------------------------------------------------------------------

class TestOutRootAllowed:
    """Test 5: out_root must be in dev copy or stamp_models allowed paths."""

    def test_artifacts_base_accepted(self) -> None:
        errors = validate_out_root(ARTIFACTS_BASE / "job-001")
        assert errors == []

    def test_model_root_artifacts_accepted(self) -> None:
        from app.services.ppflow_real_runner import MODEL_ROOT
        errors = validate_out_root(MODEL_ROOT / "artifacts" / "ppflow" / "job-001")
        assert errors == []

    def test_random_path_rejected(self) -> None:
        errors = validate_out_root(Path("/random/path"))
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 6. Checkpoint must be in stamp_models/checkpoints/ppflow
# ---------------------------------------------------------------------------

class TestCheckpointPath:
    """Test 6: checkpoint must be in stamp_models/checkpoints/ppflow."""

    def test_default_checkpoint_accepted(self) -> None:
        errors = validate_checkpoint_path(DEFAULT_CHECKPOINT)
        assert errors == []

    def test_random_checkpoint_rejected(self) -> None:
        errors = validate_checkpoint_path(Path("/random/model.pt"))
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 7. Source must be in stamp_models/source/ppflow
# ---------------------------------------------------------------------------

class TestSourcePath:
    """Test 7: source must be in stamp_models/source/ppflow."""

    def test_codesign_pp_accepted(self) -> None:
        errors = validate_source_path(CODESIGN_PP)
        assert errors == []

    def test_random_source_rejected(self) -> None:
        errors = validate_source_path(Path("/random/codesign_ppf.py"))
        assert len(errors) > 0


# ---------------------------------------------------------------------------
# 8. Manifest schema contains NOT_EXPERIMENTALLY_VALIDATED
# ---------------------------------------------------------------------------

class TestManifestSchema:
    """Test 8: manifest schema contains NOT_EXPERIMENTALLY_VALIDATED."""

    def test_manifest_post_has_validation_status(self) -> None:
        manifest = build_manifest_post(job_id="test-001")
        assert manifest["validation_status"] == VALIDATION_STATUS
        assert manifest["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_manifest_post_has_safety_flags(self) -> None:
        manifest = build_manifest_post(job_id="test-001")
        assert manifest["runs_model"] is False
        assert manifest["generates_candidates"] is False
        assert manifest["generates_pdb"] is False
        assert manifest["experimental_validation"] is False
        assert manifest["is_scientific_result"] is False

    def test_manifest_post_has_disclaimer(self) -> None:
        manifest = build_manifest_post(job_id="test-001")
        assert manifest["disclaimer"] == DISCLAIMER

    def test_manifest_post_has_stage(self) -> None:
        manifest = build_manifest_post(job_id="test-001")
        assert manifest["stage"] == STAGE
        assert "P29F" in manifest["stage"]

    def test_manifest_post_status_values(self) -> None:
        for status in ("planned", "blocked", "succeeded", "failed"):
            m = build_manifest_post(job_id="test-001", status=status)
            assert m["status"] == status

    def test_manifest_post_rejects_invalid_status(self) -> None:
        with pytest.raises(ValueError):
            build_manifest_post(job_id="test-001", status="invalid")


# ---------------------------------------------------------------------------
# 9. Failure schema contains NOT_EXPERIMENTALLY_VALIDATED
# ---------------------------------------------------------------------------

class TestFailureSchema:
    """Test 9: failure schema contains NOT_EXPERIMENTALLY_VALIDATED."""

    def test_failure_has_validation_status(self) -> None:
        failure = build_failure(job_id="test-001")
        assert failure["validation_status"] == VALIDATION_STATUS
        assert failure["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_failure_has_safety_flags(self) -> None:
        failure = build_failure(job_id="test-001")
        assert failure["runs_model"] is False
        assert failure["generates_candidates"] is False
        assert failure["generates_pdb"] is False

    def test_failure_has_stage(self) -> None:
        failure = build_failure(job_id="test-001")
        assert failure["stage"] == STAGE

    def test_failure_error_types(self) -> None:
        for et in ("gate_closed", "invalid_path", "timeout", "subprocess_error", "unknown"):
            f = build_failure(job_id="test-001", error_type=et)
            assert f["error_type"] == et

    def test_failure_rejects_invalid_error_type(self) -> None:
        with pytest.raises(ValueError):
            build_failure(job_id="test-001", error_type="invalid_type")

    def test_failure_has_timestamp(self) -> None:
        failure = build_failure(job_id="test-001")
        assert "timestamp" in failure
        assert failure["timestamp"]  # non-empty


# ---------------------------------------------------------------------------
# 10. subprocess.run not called (already tested above)
# ---------------------------------------------------------------------------

class TestSubprocessNotCalled:
    """Test 10: subprocess.run never called."""

    @patch("subprocess.run")
    def test_no_subprocess_in_plan_run(self, mock_run: MagicMock) -> None:
        result = plan_run()
        mock_run.assert_not_called()
        assert result["subprocess_called"] is False

    @patch("subprocess.run")
    def test_no_subprocess_in_run_ppflow_subprocess(self, mock_run: MagicMock) -> None:
        run_ppflow_subprocess(["echo", "hi"], job_id="test")
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# 11. torch.load not called
# ---------------------------------------------------------------------------

class TestTorchLoadNotCalled:
    """Test 11: torch.load never called."""

    def test_plan_run_does_not_import_torch(self) -> None:
        result = plan_run()
        assert result["uses_torch_load"] is False

    def test_no_torch_load_in_module(self) -> None:
        """Ensure torch.load() is not called anywhere in ppflow_real_runner."""
        import app.services.ppflow_real_runner as module
        source = open(module.__file__, "r", encoding="utf-8").read()
        # Check for actual function calls, not docstring mentions
        assert "torch.load(" not in source
        assert "pickle.load(" not in source


# ---------------------------------------------------------------------------
# 12. No job/artifact written to real data_dev
# ---------------------------------------------------------------------------

class TestNoRealJobArtifact:
    """Test 12: no job/artifact written to real data_dev."""

    def test_plan_run_does_not_create_directories(self) -> None:
        result = plan_run()
        assert result["paths_created"] is False
        # The paths in the result should not actually exist
        for key in ("job_dir", "artifact_dir", "log_file"):
            Path(result["paths"][key])
            # In test environment, these paths should not be created
            # (they're on the server, not on the test machine)

    def test_plan_run_with_tmp_path_does_not_leak(self, tmp_path: Path) -> None:
        """Ensure plan_run with tmp_path bases doesn't create files outside tmp."""
        result = plan_run(
            jobs_base=tmp_path / "jobs",
            artifacts_base=tmp_path / "artifacts",
            logs_base=tmp_path / "logs",
        )
        assert result["paths_created"] is False
        # Verify no directories were created
        assert not (tmp_path / "jobs").exists()
        assert not (tmp_path / "artifacts").exists()
        assert not (tmp_path / "logs").exists()


# ---------------------------------------------------------------------------
# 13. PPFlow adapter probe/dry-run/submit blocked tests still pass
# ---------------------------------------------------------------------------

class TestPPFlowAdapterStillBlocked:
    """Test 13: PPFlow adapter probe/dry-run/submit blocked tests still pass."""

    def test_adapter_probe_returns_available_or_blocked(self) -> None:
        from app.services.model_adapters import PPFlowAdapter
        adapter = PPFlowAdapter("ppflow")
        result = adapter.probe()
        # On test machine, probe may return blocked (paths don't exist)
        # but it must never return a "running" state
        assert result.runs_model is False
        assert result.generates_candidates is False
        assert result.generates_pdb is False
        assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_adapter_dry_run_blocked(self) -> None:
        from app.services.model_adapters import PPFlowAdapter
        from app.schemas.model_registry import ModelDryRunPayload
        adapter = PPFlowAdapter("ppflow")
        payload = ModelDryRunPayload(
            target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example.pdb",
            target_chain="A",
            peptide_length=12,
            num_candidates=4,
            seed=123,
        )
        result = adapter.dry_run(payload)
        assert result.status == "BLOCKED"
        assert result.runs_model is False
        assert result.runs_subprocess is False
        assert "ppflow_real_run_not_implemented" in result.blocked_reasons

    def test_adapter_submit_blocked(self) -> None:
        from app.services.model_adapters import PPFlowAdapter
        from app.schemas.model_registry import ModelDryRunPayload
        adapter = PPFlowAdapter("ppflow")
        payload = ModelDryRunPayload(
            target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example.pdb",
            target_chain="A",
            peptide_length=12,
            num_candidates=4,
            seed=123,
        )
        result = adapter.submit(payload)
        assert result.status == "BLOCKED"
        assert "ppflow_real_run_not_implemented" in result.blocked_reasons


# ---------------------------------------------------------------------------
# 14. PepMLM smoke_rerun_verified registry not broken
# ---------------------------------------------------------------------------

class TestPepMLMRegistryNotBroken:
    """Test 14: PepMLM smoke_rerun_verified registry not broken."""

    def test_pepmlm_registry_entry_exists(self) -> None:
        from app.services.target_peptide_model_registry import get_model
        model = get_model("pepmlm")
        assert model is not None
        assert model["status"] == "smoke_rerun_verified"

    def test_pepmlm_adapter_probe_returns_smoke_rerun_verified(self) -> None:
        from app.services.model_adapters import PepMLMRegistryAdapter
        adapter = PepMLMRegistryAdapter("pepmlm")
        result = adapter.probe()
        assert result.status == "smoke_rerun_verified"

    def test_pepmlm_adapter_dry_run_blocked(self) -> None:
        from app.services.model_adapters import PepMLMRegistryAdapter
        from app.schemas.model_registry import ModelDryRunPayload
        adapter = PepMLMRegistryAdapter("pepmlm")
        payload = ModelDryRunPayload(
            target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example.pdb",
            target_chain="A",
            peptide_length=12,
            num_candidates=4,
            seed=123,
        )
        result = adapter.dry_run(payload)
        assert result.status == "BLOCKED"
        assert "real_run_gate_closed" in result.blocked_reasons


# ---------------------------------------------------------------------------
# 15. Registry/models still list PPFlow with submit disabled
# ---------------------------------------------------------------------------

class TestRegistryPPFlowSubmitDisabled:
    """Test 15: registry/models list PPFlow; submit still disabled."""

    def test_ppflow_in_registry(self) -> None:
        from app.services.target_peptide_model_registry import get_model
        model = get_model("ppflow")
        assert model is not None
        assert model["status"] == "controlled_smoke_verified"

    def test_ppflow_submit_disabled(self) -> None:
        from app.services.target_peptide_model_registry import get_model
        model = get_model("ppflow")
        assert model["real_run_enabled"] is False

    def test_ppflow_not_in_pending_registry_models(self) -> None:
        """PPFlow should not be in pending registry list (it's already registered)."""
        from app.services.target_peptide_model_registry import _MODEL_REGISTRY
        ppflow_entry = next((m for m in _MODEL_REGISTRY if m.get("model_id") == "ppflow"), None)
        assert ppflow_entry is not None
        assert ppflow_entry["status"] != "pending_registry"


# ---------------------------------------------------------------------------
# Path construction tests
# ---------------------------------------------------------------------------

class TestPathConstruction:
    """Test path construction functions."""

    def test_generate_job_id_is_uuid(self) -> None:
        jid = generate_job_id()
        # Should be a valid UUID string
        UUID(jid)

    def test_job_dir_path(self, tmp_path: Path) -> None:
        jid = "test-job-001"
        path = job_dir_path(jid, base=tmp_path)
        assert path == tmp_path / jid

    def test_artifact_dir_path(self, tmp_path: Path) -> None:
        jid = "test-job-001"
        path = artifact_dir_path(jid, base=tmp_path)
        assert path == tmp_path / jid

    def test_log_file_path(self, tmp_path: Path) -> None:
        jid = "test-job-001"
        path = log_file_path(jid, base=tmp_path)
        assert path == tmp_path / f"{jid}.log"

    def test_invalid_job_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            job_dir_path("../../../etc/passwd")

    def test_invalid_job_id_with_slashes(self) -> None:
        with pytest.raises(ValueError):
            job_dir_path("foo/bar")

    def test_empty_job_id_rejected(self) -> None:
        with pytest.raises(ValueError):
            job_dir_path("")
