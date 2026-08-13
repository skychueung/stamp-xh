"""Safety tests for the RFpeptides staging adapter."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.schemas.model_registry import ModelDryRunPayload, ModelProbeResult, ModelDryRunResult, ModelArtifactsResponse
from app.services.model_adapters import RFpeptidesAdapter
from app.services.model_adapters import rfpeptides_adapter as module
from app.services.target_peptide_model_registry import get_model


def payload() -> ModelDryRunPayload:
    return ModelDryRunPayload(
        target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example.pdb",
        target_chain="A",
        peptide_length=12,
        num_candidates=1,
        seed=2024,
    )


def test_router_returns_rfpeptides_adapter() -> None:
    from app.routers.model_registry import _get_adapter

    adapter = _get_adapter("rfpeptides")
    assert isinstance(adapter, RFpeptidesAdapter)


def test_registry_lists_rfpeptides() -> None:
    model = get_model("rfpeptides")
    assert model is not None
    assert model["model_id"] == "rfpeptides"


def test_probe_validates_against_schema(tmp_path: Path, monkeypatch: Any) -> None:
    model_root = tmp_path / "model-root"
    source_dir = model_root / "source" / "rfpeptides" / "rfd_macro"
    weights_dir = model_root / "weights" / "rfpeptides"
    base_ckpt = weights_dir / "Base_ckpt.pt"
    env_python = model_root / "envs" / "rfpeptides_py310" / "bin" / "python"
    artifact_root = model_root / "artifacts" / "rfpeptides"

    source_dir.mkdir(parents=True)
    weights_dir.mkdir(parents=True)
    base_ckpt.write_bytes(b"x" * 483616107)
    env_python.parent.mkdir(parents=True)
    env_python.write_text("#!/bin/sh\necho 3.10.20")

    monkeypatch.setattr(module, "MODEL_ROOT", model_root)
    monkeypatch.setattr(module, "SOURCE_DIR", source_dir)
    monkeypatch.setattr(module, "WEIGHTS_DIR", weights_dir)
    monkeypatch.setattr(module, "BASE_CKPT", base_ckpt)
    monkeypatch.setattr(module, "ENV_PYTHON", env_python)
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)

    result = RFpeptidesAdapter("rfpeptides").probe()
    validated = ModelProbeResult.model_validate(result.__dict__)
    assert validated.model_id == "rfpeptides"
    assert validated.status in ("available_for_probe", "blocked")
    assert validated.safety_flags.runs_model is False


def test_dry_run_validates_against_schema(tmp_path: Path, monkeypatch: Any) -> None:
    artifact_root = tmp_path / "artifacts" / "rfpeptides"
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)

    result = RFpeptidesAdapter("rfpeptides").dry_run(payload())
    validated = ModelDryRunResult.model_validate(result.__dict__)
    assert validated.status == "BLOCKED"
    assert validated.model_id == "rfpeptides"
    assert "real_run_disabled" in validated.blocked_reasons
    assert validated.safety_flags.runs_model is False


def test_submit_blocked() -> None:
    result = RFpeptidesAdapter("rfpeptides").submit(payload())
    assert result.status == "BLOCKED"
    assert "submit_unconditionally_blocked_in_p33" in result.blocked_reasons


def test_list_artifacts_guard() -> None:
    adapter = RFpeptidesAdapter("rfpeptides")
    try:
        response = adapter.list_artifacts("job-123")
    except AttributeError:
        pytest.fail("RFpeptidesAdapter is missing list_artifacts")
    assert response.status in ("empty", "disabled")
