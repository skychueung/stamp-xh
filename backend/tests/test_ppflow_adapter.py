"""Safety tests for the P29A PPFlow probe/dry-run/blocked adapter."""

from __future__ import annotations

import builtins
import sys
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters import PPFlowAdapter
from app.services.model_adapters import ppflow_adapter as module
from app.services.target_peptide_model_registry import get_model


def payload() -> ModelDryRunPayload:
    return ModelDryRunPayload(
        target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example_missing.pdb",
        target_chain="A",
        peptide_length=12,
        num_candidates=4,
        seed=123,
    )


def tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def test_router_returns_ppflow_adapter() -> None:
    from app.routers.model_registry import _get_adapter

    adapter = _get_adapter("ppflow")
    assert isinstance(adapter, PPFlowAdapter)


def test_registry_lists_ppflow_as_controlled_smoke_verified() -> None:
    model = get_model("ppflow")
    assert model is not None
    assert model["status"] == "controlled_smoke_verified"
    assert model["adapter_id"] == "ppflow"


def test_probe_success_path(tmp_path: Path, monkeypatch: Any) -> None:
    model_root = tmp_path / "model-root"
    source_dir = model_root / "source" / "ppflow" / "extracted_p25_install_probe" / "ppflow-main"
    checkpoint = (
        model_root
        / "checkpoints"
        / "ppflow"
        / "p25_install_probe"
        / "ppflow"
        / "pretrained.pt"
    )
    summary = tmp_path / "STAMP_PPFLOW_CHECKPOINT_SAFE_GLOBALS_SAFE_LOAD_P28J_SUMMARY.json"
    env_dir = model_root / "envs" / "ppflow_p28g_safeglobals_diag"
    env_python = env_dir / "bin" / "python"
    artifact_root = model_root / "artifacts" / "ppflow"

    source_dir.mkdir(parents=True)
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("dummy")
    env_python.parent.mkdir(parents=True)
    env_python.write_text("#!/bin/sh\necho 3.10.20")
    summary.write_text(
        '{"safe_load_passed": true, "tensor_count": 1174, '
        '"checkpoint_sha256": "be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d"}'
    )

    monkeypatch.setattr(module, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(module, "CHECKPOINT_PATH", checkpoint)
    monkeypatch.setattr(module, "SUMMARY_PATH", summary)
    monkeypatch.setattr(module, "ENV_PATH", env_dir)
    monkeypatch.setattr(module, "ENV_PYTHON", env_python)
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)
    monkeypatch.delenv(module.PYTHON_ENV_VAR, raising=False)

    before = tree(tmp_path)
    result = PPFlowAdapter("ppflow").probe()
    after = tree(tmp_path)

    assert result.status == "available_for_probe"
    assert result.real_run_status == "blocked"
    assert result.real_run_blocked_reason == "ppflow_runner_not_implemented"
    assert result.detail["source_exists"] is True
    assert result.detail["checkpoint_exists"] is True
    assert result.detail["safe_load_summary_exists"] is True
    assert result.detail["env_python_exists"] is True
    assert result.detail["safe_load_gate"] == "SAFE_GLOBALS_SAFE_LOAD_GO"
    assert result.detail["safe_load_tensor_count"] == 1174
    assert result.detail["checkpoint_sha256"] == module._EXPECTED_SHA256
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.generates_pdb is False
    assert result.experimental_validation is False
    assert result.is_scientific_result is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
    assert after == before


def test_probe_missing_checkpoint_blocked(tmp_path: Path, monkeypatch: Any) -> None:
    model_root = tmp_path / "model-root"
    source_dir = model_root / "source" / "ppflow" / "extracted_p25_install_probe" / "ppflow-main"
    checkpoint = (
        model_root
        / "checkpoints"
        / "ppflow"
        / "p25_install_probe"
        / "ppflow"
        / "pretrained.pt"
    )
    summary = tmp_path / "summary.json"
    env_dir = model_root / "envs" / "ppflow_p28g_safeglobals_diag"
    env_python = env_dir / "bin" / "python"
    artifact_root = model_root / "artifacts" / "ppflow"

    source_dir.mkdir(parents=True)
    # checkpoint intentionally absent
    env_python.parent.mkdir(parents=True)
    env_python.write_text("#!/bin/sh\necho 3.10.20")
    summary.write_text(
        '{"safe_load_passed": true, "tensor_count": 1174, '
        '"checkpoint_sha256": "be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d"}'
    )

    monkeypatch.setattr(module, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(module, "CHECKPOINT_PATH", checkpoint)
    monkeypatch.setattr(module, "SUMMARY_PATH", summary)
    monkeypatch.setattr(module, "ENV_PATH", env_dir)
    monkeypatch.setattr(module, "ENV_PYTHON", env_python)
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)

    result = PPFlowAdapter("ppflow").probe()
    assert result.status == "blocked"
    assert "missing_checkpoint" in result.detail["blocked_reasons"]
    assert result.real_run_status == "blocked"


def test_probe_missing_summary_blocked(tmp_path: Path, monkeypatch: Any) -> None:
    model_root = tmp_path / "model-root"
    source_dir = model_root / "source" / "ppflow" / "extracted_p25_install_probe" / "ppflow-main"
    checkpoint = (
        model_root
        / "checkpoints"
        / "ppflow"
        / "p25_install_probe"
        / "ppflow"
        / "pretrained.pt"
    )
    summary = tmp_path / "summary.json"  # does not exist
    env_dir = model_root / "envs" / "ppflow_p28g_safeglobals_diag"
    env_python = env_dir / "bin" / "python"
    artifact_root = model_root / "artifacts" / "ppflow"

    source_dir.mkdir(parents=True)
    checkpoint.parent.mkdir(parents=True)
    checkpoint.write_text("dummy")
    env_python.parent.mkdir(parents=True)
    env_python.write_text("#!/bin/sh\necho 3.10.20")

    monkeypatch.setattr(module, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(module, "CHECKPOINT_PATH", checkpoint)
    monkeypatch.setattr(module, "SUMMARY_PATH", summary)
    monkeypatch.setattr(module, "ENV_PATH", env_dir)
    monkeypatch.setattr(module, "ENV_PYTHON", env_python)
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)

    result = PPFlowAdapter("ppflow").probe()
    assert result.status == "blocked"
    assert "missing_safe_load_summary" in result.detail["blocked_reasons"]


def test_dry_run_zero_write(tmp_path: Path, monkeypatch: Any) -> None:
    artifact_root = tmp_path / "artifacts" / "ppflow"
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)

    before = tree(tmp_path)
    result = PPFlowAdapter("ppflow").dry_run(payload())
    after = tree(tmp_path)

    assert result.status == "BLOCKED"
    assert result.mode == "dry_run"
    assert result.reason == "ppflow_real_run_not_implemented"
    assert result.creates_job is False
    assert result.writes_artifacts is False
    assert result.runs_subprocess is False
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.generates_pdb is False
    assert result.would_use_checkpoint == str(module.CHECKPOINT_PATH)
    assert result.would_use_env == str(module.ENV_PATH)
    assert result.artifact_plan["directory_created"] is False
    assert result.artifact_plan["artifacts_written"] is False
    assert after == before


def test_submit_blocked() -> None:
    result = PPFlowAdapter("ppflow").submit(payload())
    assert result.status == "BLOCKED"
    assert result.run_id is None
    assert result.creates_job is False
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.generates_pdb is False
    assert "ppflow_real_run_not_implemented" in result.blocked_reasons
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


def test_probe_does_not_torch_load_or_import_ppflow(monkeypatch: Any) -> None:
    fake_torch = ModuleType("torch")
    load_mock = MagicMock(side_effect=RuntimeError("torch.load must not be called"))
    fake_torch.load = load_mock
    monkeypatch.setitem(sys.modules, "torch", fake_torch)

    disallowed_prefixes = ("ppflow", "PPFlow")

    original_import = builtins.__import__

    def guarded_import(name: str, *args: Any, **kwargs: Any) -> Any:
        lower_name = name.lower()
        if any(lower_name.startswith(prefix) for prefix in disallowed_prefixes):
            raise AssertionError(f"Import of '{name}' is not allowed in P29A")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)

    result = PPFlowAdapter("ppflow").probe()
    assert result.model_id == "ppflow"
    load_mock.assert_not_called()


def test_safety_fields_are_false() -> None:
    adapter = PPFlowAdapter("ppflow")
    probe = adapter.probe()
    dry = adapter.dry_run(payload())
    sub = adapter.submit(payload())

    for result in (probe, dry, sub):
        assert result.runs_model is False
        assert result.generates_candidates is False
        assert result.generates_pdb is False
        assert result.experimental_validation is False
        assert result.is_scientific_result is False
        assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"


def test_artifact_root_and_empty_listing_and_traversal_guard() -> None:
    assert str(module.ARTIFACT_ROOT) == "/mnt/sdb/kxc/stamp_models/artifacts/ppflow"
    adapter = PPFlowAdapter("ppflow")
    response = adapter.list_artifacts("job-123")
    assert response.status == "empty"
    assert response.artifacts == []
    for unsafe in ("../etc", "a/b", "a\\b", ""):
        with pytest.raises(ValueError):
            adapter.list_artifacts(unsafe)


def test_no_legacy_root_path_hardcoding() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")
    legacy_root = "/home/xh/kxc/stampup/models_dev" + "/ppflow"
    assert legacy_root not in source
