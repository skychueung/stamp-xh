"""P21 tests for centralized EvoBind2 paths and zero-write planning."""

from __future__ import annotations

from pathlib import Path

from app.config.model_paths import (
    DEFAULT_EVOBIND2_ENV_PYTHON,
    LEGACY_EVOBIND2_AF2_PARAMS_DIR,
    resolve_evobind2_paths,
)
from app.services.compute_wrappers.evobind2_wrapper import EvoBind2Input, dry_run_plan, probe
from app.services.model_adapters.evobind2_adapter import EvoBind2Adapter
from app.schemas.model_registry import ModelDryRunPayload


def test_storage_root_paths_preferred_when_present() -> None:
    root = "/mnt/sdb/kxc/stamp_models"
    preferred = {
        f"{root}/source/evobind2/src/mc_design.py",
        f"{root}/checkpoints/evobind2/af2_params/params_model_1.npz",
        f"{root}/cache/evobind2/af2_data_dir",
        f"{root}/source/evobind2/tools/bin/hhblits",
    }
    paths = resolve_evobind2_paths({}, exists=lambda value: value in preferred)
    assert paths.source_dir == f"{root}/source/evobind2"
    assert paths.af2_params_dir == f"{root}/checkpoints/evobind2/af2_params"
    assert paths.hhblits_bin == f"{root}/source/evobind2/tools/bin/hhblits"
    assert not paths.legacy_fallback_warnings


def test_explicit_environment_overrides_win_even_before_materialization() -> None:
    paths = resolve_evobind2_paths(
        {
            "STAMP_MODEL_STORAGE_ROOT": "/mnt/custom/models",
            "EVOBIND2_SOURCE_DIR": "/srv/evobind2",
            "EVOBIND2_ENV_PYTHON": "/opt/evobind/bin/python",
        },
        exists=lambda _: False,
    )
    assert paths.source_dir == "/srv/evobind2"
    assert paths.env_python == "/opt/evobind/bin/python"
    assert paths.sources["source_dir"] == "environment_override"


def test_legacy_fallback_is_explicitly_warned() -> None:
    paths = resolve_evobind2_paths({}, exists=lambda value: value == f"{LEGACY_EVOBIND2_AF2_PARAMS_DIR}/params_model_1.npz")
    assert paths.af2_params_dir == LEGACY_EVOBIND2_AF2_PARAMS_DIR
    assert paths.sources["af2_params_dir"] == "legacy_fallback"
    assert any("EVOBIND2_AF2_PARAMS_DIR" in warning for warning in paths.legacy_fallback_warnings)
    assert paths.env_python == DEFAULT_EVOBIND2_ENV_PYTHON


def test_dry_run_plan_does_not_create_artifact_tree() -> None:
    inp = EvoBind2Input(run_id="p21_zero_write", receptor_fasta=">target\nMKTAYIAKQR", peptide_sequence="AAAAAAAAAA", peptide_length=10)
    plan = dry_run_plan(inp)
    assert plan.status == "READY"
    run_dir = Path(next(iter(plan.artifacts.values()))).parents[1]
    assert not run_dir.exists()
    assert plan.safety_flags["runs_model"] is False
    assert plan.safety_flags["generates_candidates"] is False


def test_adapter_dry_run_reports_expected_outputs_not_written_artifacts() -> None:
    result = EvoBind2Adapter().dry_run(
        ModelDryRunPayload(target_sequence="MKTAYIAKQRQISFVK", peptide_sequence="MKTAAYIAKQ", peptide_length=10)
    )
    assert result.status == "READY"
    assert result.artifacts == {}
    assert result.expected_outputs
    assert result.environment_summary["directory_created"] is False
    assert result.environment_summary["artifacts_written"] is False
    assert result.environment_summary["runs_model"] is False
    assert result.blocked_reasons == ["real_run_gate_blocked"]


def test_probe_keeps_real_run_blocked_and_reports_fallback() -> None:
    result = probe()
    assert result["status"] in {"AVAILABLE", "DEGRADED"}
    assert result["dry_run_status"] == "READY_FOR_DRY_RUN"
    assert result["real_run_status"] == "BLOCKED"
    assert result["real_run_enabled"] is False
    assert any(item.startswith("legacy_fallback_warning:") for item in result["warnings"])
    assert result["runs_model"] is False
    assert result["generates_candidates"] is False
    assert result["experimental_validation"] is False
    assert result["computational_prediction_only"] is True
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
