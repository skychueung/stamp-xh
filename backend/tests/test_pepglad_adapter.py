"""Tests for the PepGLAD adapter probe / dry-run strengthening (P9C).

These tests verify that the adapter never executes the model, returns the
expected P9C probe statuses, and builds a sensible command preview with
expected artifacts, blocked reasons, environment summary, and weight checksums.
"""
from __future__ import annotations

import uuid

import pytest

from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters import PepGLADAdapter
from app.services.model_adapters.pepglad_adapter import (
    PEPGLAD_ARTIFACT_ROOT,
    PEPGLAD_CODESIGN_CKPT,
    PEPGLAD_ENV_PYTHON,
    PEPGLAD_FIXSEQ_CKPT,
    PEPGLAD_SOURCE,
    PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE,
    PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED,
    PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE,
    PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING,
    PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED,
    PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE,
    PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS,
    PEPGLAD_STATUS_BLOCKED_PYROSETTA_REQUIRED,
    PEPGLAD_STATUS_DEGRADED,
    PEPGLAD_STATUS_READY_FOR_DRY_RUN,
)


def test_pepglad_adapter_probe_returns_p9c_status() -> None:
    adapter = PepGLADAdapter("pepglad")
    result = adapter.probe()
    assert result.model_id == "pepglad"
    assert result.display_name == "PepGLAD"
    assert result.adapter_id == "pepglad"
    assert result.status in (
        PEPGLAD_STATUS_READY_FOR_DRY_RUN,
        PEPGLAD_STATUS_DEGRADED,
        PEPGLAD_STATUS_BLOCKED_MISSING_SOURCE,
        PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS,
        PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE,
        PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED,
        PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING,
        PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED,
        PEPGLAD_STATUS_BLOCKED_PYROSETTA_REQUIRED,
        PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE,
    )
    assert result.safety_flags.executed_model is False
    assert result.safety_flags.generated_structure is False
    assert result.safety_flags.computational_prediction_only is True


def test_pepglad_adapter_probe_detail_flags() -> None:
    adapter = PepGLADAdapter("pepglad")
    result = adapter.probe()
    detail = result.detail
    assert "source_present" in detail
    assert "license_present" in detail
    assert "entrypoint_present" in detail
    assert "requirements_present" in detail
    assert "env_present" in detail
    assert "env_python_path" in detail
    assert "weights_present" in detail
    assert "weights_files" in detail
    assert "weights_sha256" in detail
    assert "pyrosetta_available" in detail
    assert "pyrosetta_required" in detail
    assert "cuda_available" in detail
    assert "dependency_summary" in detail
    assert "checkpoint_load_probe" in detail
    assert "entrypoint_help_probe" in detail
    assert "env_toolchain" in detail
    assert "manual_upload_required" in detail
    assert "checks" in detail
    assert "errors" in detail
    assert detail["env_python_path"] == str(PEPGLAD_ENV_PYTHON)
    assert detail["real_run_enabled"] is False
    if detail["env_present"]:
        assert detail["env_python_path"].endswith("pepglad_p31b_py39_torch113/bin/python")
        assert detail["env_toolchain"] == "conda-pack-p9c4"
        assert "pdbfixer" in detail["dependency_summary"]


def test_pepglad_adapter_probe_checks_include_license_and_entrypoint() -> None:
    adapter = PepGLADAdapter("pepglad")
    result = adapter.probe()
    names = {c["name"] for c in result.detail.get("checks", [])}
    assert "pepglad_license" in names
    assert "pepglad_entrypoint" in names
    assert "pepglad_requirements" in names


def test_pepglad_adapter_probe_weights_sha256_when_present() -> None:
    adapter = PepGLADAdapter("pepglad")
    result = adapter.probe()
    detail = result.detail
    if detail.get("weights_present"):
        assert detail.get("weights_files")
        sha256_map = detail.get("weights_sha256", {})
        for name in detail["weights_files"]:
            assert name in sha256_map
            assert len(sha256_map[name]) == 64


def test_pepglad_adapter_dry_run_does_not_execute() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
        num_candidates=3,
        target_pdb_path="example_target.pdb",
        pocket_residues=["A:45", "A:46"],
    )
    result = adapter.dry_run(payload)
    assert result.model_id == "pepglad"
    assert result.status in (
        "READY",
        "NOT_CONNECTED",
        PEPGLAD_STATUS_BLOCKED_MISSING_WEIGHTS,
        PEPGLAD_STATUS_BLOCKED_ENV_INCOMPLETE,
        PEPGLAD_STATUS_BLOCKED_MANUAL_UPLOAD_REQUIRED,
        PEPGLAD_STATUS_BLOCKED_DEPENDENCY_MISSING,
        PEPGLAD_STATUS_BLOCKED_CHECKPOINT_LOAD_FAILED,
        PEPGLAD_STATUS_READY_FOR_REAL_RUN_GATE,
    )
    assert result.safety_flags.executed_model is False
    assert result.safety_flags.generated_candidates is False
    assert result.safety_flags.generated_structure is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result.command_preview is not None
    assert "api.run" in result.command_preview
    assert "--mode" in result.command_preview
    assert "codesign" in result.command_preview
    assert str(PEPGLAD_SOURCE) in result.env_preview.get("PYTHONPATH", "")


def test_pepglad_adapter_dry_run_expected_artifacts() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
        num_candidates=3,
    )
    result = adapter.dry_run(payload)
    artifacts = result.expected_artifacts or result.artifacts
    assert "input/target.pdb" in artifacts
    assert "input/pocket.json" in artifacts
    assert "output/generated_peptides.csv" in artifacts
    assert "output/generated_structures" in artifacts
    assert "output/pepglad_summary.json" in artifacts
    assert "logs/run_stdout_stderr.log" in artifacts
    assert "manifest/manifest_pre.json" in artifacts
    assert "manifest/manifest_post.json" in artifacts


def test_pepglad_adapter_dry_run_includes_environment_summary() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
    )
    result = adapter.dry_run(payload)
    summary = result.environment_summary
    assert "source_present" in summary
    assert "weights_present" in summary
    assert "env_present" in summary
    assert "env_toolchain" in summary
    assert "manual_upload_required" in summary
    assert "cuda_available" in summary
    assert "weights_files" in summary


def test_pepglad_adapter_dry_run_blocked_reasons_when_weights_missing() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
    )
    result = adapter.dry_run(payload)
    if not (PEPGLAD_CODESIGN_CKPT.exists() or PEPGLAD_FIXSEQ_CKPT.exists()):
        assert result.blocked_reasons
        assert any("checkpoint" in br.lower() for br in result.blocked_reasons)


def test_pepglad_adapter_dry_run_command_preview_length() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=10,
        num_candidates=5,
    )
    result = adapter.dry_run(payload)
    cp = result.command_preview or []
    assert "--length_min" in cp
    assert "--length_max" in cp
    assert "--n_samples" in cp
    assert "--mode" in cp
    assert "codesign" in cp
    assert "--pdb" in cp
    assert "--pocket" in cp


def test_pepglad_adapter_submit_is_blocked() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
    )
    result = adapter.submit(payload)
    assert result.status == "BLOCKED"
    assert result.run_id is None
    assert result.safety_flags.executed_model is False
    assert result.blocked_reasons


def test_pepglad_adapter_list_artifacts_empty() -> None:
    adapter = PepGLADAdapter("pepglad")
    job_id = str(uuid.uuid4())
    response = adapter.list_artifacts(job_id)
    assert response.model_id == "pepglad"
    assert response.job_id == job_id
    assert response.status in ("not_connected", "planned", "disabled")
    assert all(not a.exists for a in response.artifacts)
    for artifact in response.artifacts:
        assert "/home/" not in artifact.path


def test_pepglad_adapter_capabilities() -> None:
    adapter = PepGLADAdapter("pepglad")
    caps = adapter.get_capabilities()
    assert caps["model_id"] == "pepglad"
    assert caps["real_run_enabled"] is False


def test_pepglad_adapter_paths_are_under_stampup() -> None:
    assert str(PEPGLAD_SOURCE).startswith("/home/xh/kxc/stampup/models_dev/pepglad")
    assert str(PEPGLAD_ARTIFACT_ROOT).startswith(
        "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/artifacts/pepglad"
    )
    assert str(PEPGLAD_CODESIGN_CKPT).startswith("/home/xh/kxc/stampup/models_dev/pepglad/weights")
    assert str(PEPGLAD_FIXSEQ_CKPT).startswith("/home/xh/kxc/stampup/models_dev/pepglad/weights")


def test_pepglad_adapter_dry_run_respects_pdb_and_pocket_inputs() -> None:
    adapter = PepGLADAdapter("pepglad")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTIIALSYIFCLVFADYKDDDDK",
        peptide_length=12,
        num_candidates=3,
        target_pdb_path="/custom/target.pdb",
        pocket_residues=["B:10", "B:11", "B:12"],
    )
    result = adapter.dry_run(payload)
    cp = result.command_preview or []
    assert "/custom/target.pdb" in cp
    assert any("pocket.json" in part for part in cp)
