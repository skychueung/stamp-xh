"""Tests for PepHAR real runner skeleton (P31C)."""


import pytest

from app.services.pephar_real_runner import (
    PepHARRunner,
    PepHARRunnerBlocked,
    ENV_PYTHON,
    DENSITY_CHECKPOINT,
    PREDICTION_CHECKPOINT,
    DEFAULT_DENSITY_CONFIG,
    DEFAULT_PREDICTION_CONFIG,
)


def test_default_gate_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.pephar_real_runner.GATE_FILE", tmp_path / "nonexistent_gate"
    )
    assert PepHARRunner.gate_open() is False


def test_gate_open_only_when_file_contains_true(tmp_path, monkeypatch):
    gate = tmp_path / "gate"
    gate.write_text("true")
    monkeypatch.setattr("app.services.pephar_real_runner.GATE_FILE", gate)
    assert PepHARRunner.gate_open() is True


def test_runner_blocks_run_by_default(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.pephar_real_runner.GATE_FILE", tmp_path / "nonexistent_gate"
    )
    runner = PepHARRunner()
    with pytest.raises(PepHARRunnerBlocked):
        runner.run("/mnt/sdb/kxc/stamp_models/artifacts/pephar/test_complex.pdb")


def test_command_preview_constructed_not_executed():
    runner = PepHARRunner(job_id="test_job", model_variant="prediction")
    cmd = runner.build_command("/mnt/sdb/kxc/stamp_models/artifacts/pephar/test_complex.pdb")
    assert cmd[0] == str(ENV_PYTHON)
    assert str(PREDICTION_CHECKPOINT) in cmd
    assert str(DEFAULT_PREDICTION_CONFIG) in cmd
    assert "--model_variant" in cmd
    assert "prediction" in cmd


def test_density_variant_uses_density_checkpoint():
    runner = PepHARRunner(job_id="test_job", model_variant="density")
    assert runner.checkpoint_path == DENSITY_CHECKPOINT
    assert runner.config_path == DEFAULT_DENSITY_CONFIG


def test_invalid_variant_rejected():
    with pytest.raises(PepHARRunnerBlocked):
        PepHARRunner(model_variant="invalid")


def test_forbidden_out_root_rejected():
    with pytest.raises(PepHARRunnerBlocked):
        PepHARRunner(out_root="/tmp/pephar_out")


def test_out_root_must_be_under_artifacts_base(tmp_path):
    with pytest.raises(PepHARRunnerBlocked):
        PepHARRunner(out_root=str(tmp_path / "pephar_out"))


def test_forbidden_checkpoint_rejected():
    with pytest.raises(PepHARRunnerBlocked):
        PepHARRunner(checkpoint_path="/tmp/1400.pt")


def test_manifest_post_contains_safety_fields():
    runner = PepHARRunner(job_id="test_job")
    manifest = runner.build_manifest_post("/mnt/sdb/kxc/stamp_models/artifacts/pephar/test_complex.pdb")
    assert manifest["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert manifest["computational_prediction_only"] is True
    assert manifest["experimental_validation"] is False
    assert manifest["runs_model"] is False
    assert manifest["creates_job"] is False
    assert manifest["writes_artifacts"] is False
    assert manifest["subprocess_spawned"] is False


def test_failure_schema_contains_safety_fields():
    runner = PepHARRunner(job_id="test_job")
    failure = runner.build_failure("test_reason")
    assert failure["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert failure["computational_prediction_only"] is True
    assert failure["experimental_validation"] is False
    assert failure["status"] == "BLOCKED"


def test_invalid_job_id_rejected():
    with pytest.raises(PepHARRunnerBlocked):
        PepHARRunner(job_id="../../etc/passwd")
