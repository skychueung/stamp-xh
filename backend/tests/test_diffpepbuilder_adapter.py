"""Safety tests for the P17 DiffPepBuilder probe/dry-run-only adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.model_registry import ModelDryRunPayload
from app.services.model_adapters import DiffPepBuilderAdapter
from app.services.model_adapters import diffpepbuilder_adapter as module


def _p32b_not_ok(step: str) -> dict:
    return {"ok": False, "errors": ["test_p32b_disabled"], "delivery_manifest": {"ok": False}, "step_manifest": {"ok": False}}


def payload() -> ModelDryRunPayload:
    return ModelDryRunPayload(target_pdb_path="/mnt/sdb/kxc/stamp_models/datasets/example_missing.pdb",
                              target_chain="A", peptide_length=12, num_candidates=4, seed=123)


def tree(root: Path) -> list[str]:
    if not root.exists():
        return []
    return sorted(str(path.relative_to(root)) for path in root.rglob("*"))


def test_router_returns_diffpepbuilder_adapter() -> None:
    from app.routers.model_registry import _get_adapter
    assert isinstance(_get_adapter("diffpepbuilder"), DiffPepBuilderAdapter)


def test_probe_reports_missing_resources_and_python_without_writes(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module, "p32b_evidence_ok", _p32b_not_ok)
    model_root = tmp_path / "model-root"
    monkeypatch.setattr(module, "MODEL_ROOT", model_root)
    monkeypatch.setattr(module, "SOURCE_DIR", model_root / "source" / "diffpepbuilder")
    monkeypatch.setattr(module, "WEIGHTS_DIR", model_root / "weights" / "diffpepbuilder")
    monkeypatch.setattr(module, "CHECKPOINT_DIR", model_root / "checkpoints" / "diffpepbuilder")
    monkeypatch.setattr(module, "CACHE_DIR", model_root / "cache" / "diffpepbuilder")
    monkeypatch.setattr(module, "ARTIFACT_ROOT", model_root / "artifacts" / "diffpepbuilder")
    monkeypatch.setattr(module, "GATE_FILE", module.CHECKPOINT_DIR / ".real_run_enabled")
    monkeypatch.delenv(module.PYTHON_ENV_VAR, raising=False)
    before = tree(tmp_path)
    result = DiffPepBuilderAdapter("diffpepbuilder").probe()
    assert {"missing_source", "missing_weights", "missing_checkpoints"} <= set(result.detail["blocked_reasons"])
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.experimental_validation is False
    assert tree(tmp_path) == before


def test_dry_run_is_zero_write_and_has_safe_plan(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module, "p32b_evidence_ok", _p32b_not_ok)
    artifact_root = tmp_path / "artifacts" / "diffpepbuilder"
    monkeypatch.setattr(module, "ARTIFACT_ROOT", artifact_root)
    before = tree(tmp_path)
    result = DiffPepBuilderAdapter("diffpepbuilder").dry_run(payload())
    assert result.status == "BLOCKED"
    assert isinstance(result.command_preview, list)
    assert result.expected_inputs["target_chain"] == "A"
    assert result.expected_outputs["candidate_sequences"] is None
    assert result.expected_outputs["pdb_files"] == []
    assert result.expected_outputs["scientific_metrics"] == {}
    assert result.artifact_plan["directory_created"] is False
    assert result.artifact_plan["artifacts_written"] is False
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.is_scientific_result is False
    assert tree(tmp_path) == before


@pytest.mark.parametrize("gate,env_enabled", [(False, False), (True, False), (False, True), (True, True)])
def test_submit_always_blocked_for_every_gate_combination(tmp_path, monkeypatch, gate, env_enabled) -> None:
    monkeypatch.setattr(module, "p32b_evidence_ok", _p32b_not_ok)
    checkpoint_dir = tmp_path / "checkpoints" / "diffpepbuilder"
    gate_file = checkpoint_dir / ".real_run_enabled"
    if gate:
        checkpoint_dir.mkdir(parents=True)
        gate_file.touch()
    monkeypatch.setattr(module, "CHECKPOINT_DIR", checkpoint_dir)
    monkeypatch.setattr(module, "GATE_FILE", gate_file)
    if env_enabled:
        monkeypatch.setenv(module.REAL_RUN_ENV_VAR, "true")
    else:
        monkeypatch.delenv(module.REAL_RUN_ENV_VAR, raising=False)
    result = DiffPepBuilderAdapter("diffpepbuilder").submit(payload())
    assert result.status == "BLOCKED"
    assert result.run_id is None
    assert result.artifacts == {}
    assert result.generates_candidates is False
    assert "submit_unconditionally_blocked_in_p17" in result.blocked_reasons or "submit_unconditionally_blocked" in result.blocked_reasons
    assert result.environment_summary["gate"]["and_condition_met"] is (gate and env_enabled)
    assert result.environment_summary["gate"]["phase_enforced_block"] is True


def test_p32b_controlled_smoke_verified_probe(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(module, "p32b_evidence_ok", lambda step: {
        "ok": True,
        "errors": [],
        "delivery_manifest": {"ok": True},
        "step_manifest": {"ok": True, "manifest": {"status": "SUCCESS", "exit_code": 0}},
    })
    result = DiffPepBuilderAdapter("diffpepbuilder").probe()
    assert result.status == "controlled_smoke_verified"
    assert result.stage == "P32B_CONTROLLED_SMOKE_OK"
    assert result.runs_model is False
    assert result.generates_candidates is False
    assert result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"
    assert result.available is True
    assert result.actionable is False


def test_artifact_root_and_empty_listing_and_traversal_guard() -> None:
    assert str(module.ARTIFACT_ROOT) == "/mnt/sdb/kxc/stamp_models/artifacts/diffpepbuilder"
    adapter = DiffPepBuilderAdapter("diffpepbuilder")
    response = adapter.list_artifacts("job-123")
    assert response.status == "empty"
    assert response.artifacts == []
    for unsafe in ("../etc", "a/b", "a\\b", ""):
        with pytest.raises(ValueError):
            adapter.list_artifacts(unsafe)


def test_no_legacy_root_path_hardcoding() -> None:
    source = Path(module.__file__).read_text(encoding="utf-8")
    legacy_root = "/home/xh/kxc/stampup/models_dev" + "/diffpepbuilder"
    assert legacy_root not in source
