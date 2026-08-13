"""Tests for PepFlow real runner skeleton (P31C)."""


import pytest

from app.services.pepflow_real_runner import (
    PepFlowRunner,
    PepFlowRunnerBlocked,
    ENV_PYTHON,
    ARTIFACTS_BASE,
    DEFAULT_CHECKPOINT,
    DEFAULT_CONFIG,
    INFERENCE_ENTRY,
)


def test_default_gate_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.pepflow_real_runner.GATE_FILE", tmp_path / "nonexistent_gate"
    )
    assert PepFlowRunner.gate_open() is False


def test_gate_open_only_when_file_contains_true(tmp_path, monkeypatch):
    gate = tmp_path / "gate"
    gate.write_text("true")
    monkeypatch.setattr("app.services.pepflow_real_runner.GATE_FILE", gate)
    assert PepFlowRunner.gate_open() is True


def test_runner_blocks_run_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.pepflow_real_runner.GATE_FILE", tmp_path / "nonexistent_gate"
    )
    runner = PepFlowRunner()
    with pytest.raises(PepFlowRunnerBlocked):
        runner.run("/mnt/sdb/kxc/stamp_models/artifacts/pepflow/test_receptor.pdb")


def test_command_preview_constructed_not_executed():
    runner = PepFlowRunner(job_id="test_job", num_samples=2, num_steps=50)
    cmd = runner.build_command("/mnt/sdb/kxc/stamp_models/artifacts/pepflow/test_receptor.pdb")
    assert cmd[0] == str(ENV_PYTHON)
    assert str(INFERENCE_ENTRY) in cmd
    assert str(DEFAULT_CONFIG) in cmd
    assert str(DEFAULT_CHECKPOINT) in cmd
    assert "--num_samples" in cmd
    assert "2" in cmd
    assert "--num_steps" in cmd
    assert "50" in cmd


def test_forbidden_out_root_rejected():
    with pytest.raises(PepFlowRunnerBlocked):
        PepFlowRunner(out_root="/tmp/pepflow_out")


def test_out_root_must_be_under_artifacts_base(tmp_path):
    with pytest.raises(PepFlowRunnerBlocked):
        PepFlowRunner(out_root=str(tmp_path / "pepflow_out"))


def test_forbidden_checkpoint_rejected():
    with pytest.raises(PepFlowRunnerBlocked):
        PepFlowRunner(checkpoint_path="/tmp/model.pt")


def test_checkpoint_must_be_under_allowed_root(tmp_path):
    with pytest.raises(PepFlowRunnerBlocked):
        PepFlowRunner(checkpoint_path=str(tmp_path / "model.pt"))


def test_manifest_post_contains_safety_fields():
    runner = PepFlowRunner(job_id="test_job")
    manifest = runner.build_manifest_post("/mnt/sdb/kxc/stamp_models/artifacts/pepflow/test_receptor.pdb")
    assert manifest["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert manifest["computational_prediction_only"] is True
    assert manifest["experimental_validation"] is False
    assert manifest["runs_model"] is False
    assert manifest["creates_job"] is False
    assert manifest["writes_artifacts"] is False
    assert manifest["subprocess_spawned"] is False


def test_failure_schema_contains_safety_fields():
    runner = PepFlowRunner(job_id="test_job")
    failure = runner.build_failure("test_reason")
    assert failure["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert failure["computational_prediction_only"] is True
    assert failure["experimental_validation"] is False
    assert failure["status"] == "BLOCKED"


def test_artifact_dir_matches_out_root():
    runner = PepFlowRunner(job_id="test_job")
    assert runner.artifact_dir == ARTIFACTS_BASE / "test_job"


def test_invalid_job_id_rejected():
    with pytest.raises(PepFlowRunnerBlocked):
        PepFlowRunner(job_id="../../etc/passwd")
