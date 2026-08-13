"""Tests for PepMLM Registry Adapter (P30D).

Validates that:
1. PepMLM appears in the model registry.
2. /api/v1/models can see PepMLM.
3. /api/v1/models/pepmlm/probe returns smoke_rerun_verified.
4. probe does not run the model.
5. probe does not create a job.
6. probe does not write artifacts.
7. dry-run does not create a job (returns BLOCKED).
8. submit is blocked.
9. real_run_enabled=false.
10. validation_status=NOT_EXPERIMENTALLY_VALIDATED.
11. No Kd/MIC/MM-GBSA/ipTM/pLDDT/RMSD/RMSF in probe/dry-run/submit results.
12. PPFlow registry status is not broken.
"""
from __future__ import annotations

import json
import re

import pytest

from app.services.model_adapters.pepmlm_registry_adapter import (
    PepMLMRegistryAdapter,
    P30B_CANDIDATE_COUNT,
    P30B_SMOKE_JOB_ID,
    P30B_SMOKE_GATE,
    P30B_REASONIX_GATE,
    P30B_STAGE,
)
from app.services.target_peptide_model_registry import (
    get_model,
    list_models,
)

FORBIDDEN_METRICS = [
    "Kd",
    "MIC",
    "MM-GBSA",
    "ipTM",
    "pLDDT",
    "RMSD",
    "RMSF",
]


def _check_no_forbidden_metrics(data: dict) -> None:
    """Assert that no forbidden scientific metrics appear in the data."""
    text = json.dumps(data, default=str)
    for metric in FORBIDDEN_METRICS:
        # Use word-boundary regex to avoid false positives (e.g. "Kd" in "blocked")
        # But be strict: check if the metric appears as a value or label
        pattern = rf'["\']?{re.escape(metric)}["\']?\s*[:=]'
        assert not re.search(pattern, text), (
            f"Forbidden metric '{metric}' found in result: {text[:500]}"
        )


# ---------------------------------------------------------------------------
# Test 1: PepMLM appears in registry
# ---------------------------------------------------------------------------


class TestPepMLMRegistryEntry:
    """Verify PepMLM is registered with correct metadata."""

    def test_pepmlm_in_registry(self):
        """PepMLM must appear in the model registry list."""
        models = list_models()
        model_ids = [str(m["model_id"]) for m in models]
        assert "pepmlm" in model_ids, "PepMLM not found in model registry"

    def test_pepmlm_registry_entry_status(self):
        """PepMLM registry entry must have smoke_rerun_verified status."""
        model = get_model("pepmlm")
        assert model is not None, "PepMLM model entry is None"
        assert str(model["status"]) == "smoke_rerun_verified", (
            f"Expected status 'smoke_rerun_verified', got '{model['status']}'"
        )

    def test_pepmlm_registry_entry_stage(self):
        """PepMLM registry entry must have P30B stage."""
        model = get_model("pepmlm")
        assert model is not None
        assert str(model.get("stage", "")) == P30B_STAGE, (
            f"Expected stage '{P30B_STAGE}', got '{model.get('stage', '')}'"
        )

    def test_pepmlm_real_run_enabled_false(self):
        """PepMLM real_run_enabled must be False."""
        model = get_model("pepmlm")
        assert model is not None
        assert model.get("real_run_enabled") is False, (
            f"real_run_enabled must be False, got {model.get('real_run_enabled')}"
        )

    def test_pepmlm_validation_status(self):
        """PepMLM must carry NOT_EXPERIMENTALLY_VALIDATED."""
        model = get_model("pepmlm")
        assert model is not None
        safety_note = str(model.get("safety_note", ""))
        assert "NOT_EXPERIMENTALLY_VALIDATED" in safety_note

    def test_pepmlm_no_forbidden_metrics_in_registry(self):
        """Registry entry must not contain forbidden scientific metrics."""
        model = get_model("pepmlm")
        assert model is not None
        _check_no_forbidden_metrics(model)


# ---------------------------------------------------------------------------
# Test 2: /api/v1/models can see PepMLM
# ---------------------------------------------------------------------------


class TestModelsListIncludesPepMLM:
    """Verify the models list includes PepMLM."""

    def test_models_list_contains_pepmlm(self):
        models = list_models()
        pepmlm = None
        for m in models:
            if str(m["model_id"]) == "pepmlm":
                pepmlm = m
                break
        assert pepmlm is not None, "PepMLM not found in models list"


# ---------------------------------------------------------------------------
# Tests 3-6: Probe returns smoke_rerun_verified
# ---------------------------------------------------------------------------


class TestPepMLMRegistryProbe:
    """Verify probe() returns smoke_rerun_verified without side effects."""

    @pytest.fixture
    def adapter(self):
        return PepMLMRegistryAdapter("pepmlm")

    @pytest.fixture
    def probe_result(self, adapter):
        return adapter.probe()

    def test_probe_status_smoke_rerun_verified(self, probe_result):
        """probe must return status='smoke_rerun_verified'."""
        assert probe_result.status == "smoke_rerun_verified", (
            f"Expected 'smoke_rerun_verified', got '{probe_result.status}'"
        )

    def test_probe_does_not_run_model(self, probe_result):
        """probe must not run the model."""
        assert probe_result.runs_model is False
        assert probe_result.safety_flags.executed_model is False
        assert probe_result.safety_flags.runs_model is False

    def test_probe_does_not_create_job(self, probe_result):
        """probe must not create a job."""
        assert probe_result.creates_job is False

    def test_probe_does_not_write_artifacts(self, probe_result):
        """probe must not write artifacts."""
        assert probe_result.writes_artifacts is False
        assert probe_result.safety_flags.generated_candidates is False

    def test_probe_real_run_enabled_false(self, probe_result):
        """probe must report real_run_enabled=false."""
        assert probe_result.detail.get("real_run_enabled") is False

    def test_probe_real_run_status_blocked(self, probe_result):
        """probe must report real_run_status=blocked."""
        assert probe_result.real_run_status == "blocked"

    def test_probe_real_run_blocked_reason(self, probe_result):
        """probe must report real_run_blocked_reason=real_run_gate_closed."""
        assert probe_result.real_run_blocked_reason == "real_run_gate_closed"

    def test_probe_validation_status(self, probe_result):
        """probe must carry NOT_EXPERIMENTALLY_VALIDATED."""
        assert probe_result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_probe_stage(self, probe_result):
        """probe must report P30B stage."""
        assert probe_result.stage == P30B_STAGE

    def test_probe_contains_p30b_evidence(self, probe_result):
        """probe detail must contain P30B smoke rerun evidence."""
        detail = probe_result.detail
        assert detail["last_smoke_job_id"] == P30B_SMOKE_JOB_ID
        assert detail["last_smoke_gate"] == P30B_SMOKE_GATE
        assert detail["last_smoke_reasonix_gate"] == P30B_REASONIX_GATE
        assert detail["candidate_count"] == P30B_CANDIDATE_COUNT
        assert detail["uses_cuda"] is True
        assert detail["device"] == "cuda"
        assert "RTX 4090" in detail["gpu"]

    def test_probe_no_forbidden_metrics(self, probe_result):
        """probe result must not contain forbidden scientific metrics."""
        _check_no_forbidden_metrics(probe_result.model_dump(mode="json"))

    def test_probe_generates_pdb_false(self, probe_result):
        """probe must not generate PDB."""
        assert probe_result.generates_pdb is False

    def test_probe_experimental_validation_false(self, probe_result):
        """probe must not claim experimental validation."""
        assert probe_result.experimental_validation is False

    def test_probe_is_scientific_result_false(self, probe_result):
        """probe must not claim to be a scientific result."""
        assert probe_result.is_scientific_result is False


# ---------------------------------------------------------------------------
# Test 7: Dry-run returns BLOCKED
# ---------------------------------------------------------------------------


class TestPepMLMRegistryDryRun:
    """Verify dry_run() returns BLOCKED without side effects."""

    @pytest.fixture
    def adapter(self):
        return PepMLMRegistryAdapter("pepmlm")

    @pytest.fixture
    def dry_run_result(self, adapter):
        from app.schemas.model_registry import ModelDryRunPayload
        payload = ModelDryRunPayload(
            target_sequence="MKTIIALSYIFCLVFADYKDDDDK",
            peptide_length=12,
            num_candidates=3,
            device="auto",
            seed=42,
        )
        return adapter.dry_run(payload)

    def test_dry_run_status_blocked(self, dry_run_result):
        """dry-run must return status='BLOCKED'."""
        assert dry_run_result.status == "BLOCKED"

    def test_dry_run_does_not_create_job(self, dry_run_result):
        """dry-run must not create a job."""
        assert dry_run_result.creates_job is False
        assert dry_run_result.run_id is None

    def test_dry_run_does_not_write_artifacts(self, dry_run_result):
        """dry-run must not write artifacts."""
        assert dry_run_result.writes_artifacts is False
        assert dry_run_result.artifacts == {}

    def test_dry_run_does_not_run_model(self, dry_run_result):
        """dry-run must not run the model."""
        assert dry_run_result.runs_model is False
        assert dry_run_result.safety_flags.executed_model is False

    def test_dry_run_blocked_reasons(self, dry_run_result):
        """dry-run must include real_run_gate_closed in blocked_reasons."""
        assert "real_run_gate_closed" in dry_run_result.blocked_reasons

    def test_dry_run_validation_status(self, dry_run_result):
        """dry-run must carry NOT_EXPERIMENTALLY_VALIDATED."""
        assert dry_run_result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_dry_run_no_forbidden_metrics(self, dry_run_result):
        """dry-run result must not contain forbidden scientific metrics."""
        _check_no_forbidden_metrics(dry_run_result.model_dump(mode="json"))

    def test_dry_run_generates_candidates_false(self, dry_run_result):
        """dry-run must not generate candidates."""
        assert dry_run_result.generates_candidates is False
        assert dry_run_result.safety_flags.generated_candidates is False


# ---------------------------------------------------------------------------
# Test 8: Submit is blocked
# ---------------------------------------------------------------------------


class TestPepMLMRegistrySubmit:
    """Verify submit() is unconditionally blocked."""

    @pytest.fixture
    def adapter(self):
        return PepMLMRegistryAdapter("pepmlm")

    @pytest.fixture
    def submit_result(self, adapter):
        from app.schemas.model_registry import ModelDryRunPayload
        payload = ModelDryRunPayload(
            target_sequence="MKTIIALSYIFCLVFADYKDDDDK",
            peptide_length=12,
            num_candidates=3,
            device="auto",
            seed=42,
        )
        return adapter.submit(payload)

    def test_submit_status_blocked(self, submit_result):
        """submit must return status='BLOCKED'."""
        assert submit_result.status == "BLOCKED"

    def test_submit_does_not_create_job(self, submit_result):
        """submit must not create a job."""
        assert submit_result.creates_job is False
        assert submit_result.run_id is None

    def test_submit_does_not_write_artifacts(self, submit_result):
        """submit must not write artifacts."""
        assert submit_result.writes_artifacts is False
        assert submit_result.artifacts == {}

    def test_submit_does_not_run_model(self, submit_result):
        """submit must not run the model."""
        assert submit_result.runs_model is False
        assert submit_result.safety_flags.executed_model is False

    def test_submit_blocked_reasons(self, submit_result):
        """submit must include blocked reasons."""
        assert len(submit_result.blocked_reasons) > 0
        assert "real_run_gate_closed" in submit_result.blocked_reasons

    def test_submit_validation_status(self, submit_result):
        """submit must carry NOT_EXPERIMENTALLY_VALIDATED."""
        assert submit_result.validation_status == "NOT_EXPERIMENTALLY_VALIDATED"

    def test_submit_no_forbidden_metrics(self, submit_result):
        """submit result must not contain forbidden scientific metrics."""
        _check_no_forbidden_metrics(submit_result.model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Test 12: PPFlow registry not broken
# ---------------------------------------------------------------------------


class TestPPFlowRegistryIntact:
    """Verify PPFlow registry entry is not broken by P30D changes."""

    def test_ppflow_in_registry(self):
        """PPFlow must still appear in the model registry."""
        model = get_model("ppflow")
        assert model is not None, "PPFlow not found in model registry"

    def test_ppflow_status_unchanged(self):
        """PPFlow status must remain controlled_smoke_verified (P33P advanced stage, not status)."""
        model = get_model("ppflow")
        assert model is not None
        assert str(model["status"]) == "controlled_smoke_verified"
        assert str(model["stage"]) == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"

    def test_ppflow_real_run_enabled_false(self):
        """PPFlow real_run_enabled must remain False."""
        model = get_model("ppflow")
        assert model is not None
        assert model.get("real_run_enabled") is False
