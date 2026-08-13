"""Tests for pDockQ Readiness Audit (v0.10-P6f).

Validates that:
  1. Current LocalColabFold monomer outputs are NOT pDockQ-ready.
  2. Missing interface inputs are correctly identified.
  3. Forbidden metrics are detected and rejected.
  4. No fallback/mock/default pDockQ is ever accepted.
  5. The future interface_quality data contract is well-formed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.pdockq_readiness_audit import (
    INTERFACE_QUALITY_CONTRACT,
    REQUIRED_INTERFACE_INPUTS,
    audit_pdockq_readiness,
    get_interface_quality_contract,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "localcolabfold_smoke"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_structure_prediction_metrics(**overrides) -> dict:
    """Build a realistic structure_prediction metrics dict."""
    base = {
        "mode": "LOCALCOLABFOLD_IMPORTED_RESULT",
        "model_source": "LocalColabFold",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "prediction_status": "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY",
        "metrics_are_real": True,
        "mean_plddt": 65.23,
        "ptm": 0.28,
        "iptm": None,
        "structure_file": "/path/to/model.pdb",
        "pae_file": "/path/to/pae.png",
        "raw_score_json": "/path/to/scores.json",
        "source_job_id": "job-123",
        "source_result_dir": "/path/to/results",
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Current fixture audit
# ---------------------------------------------------------------------------


def test_fixture_parsed_metrics_is_not_pdockq_ready():
    """The real LocalColabFold smoke fixture must be flagged as NOT ready."""
    parsed_path = FIXTURE_DIR / "parsed_metrics.json"
    raw = json.loads(parsed_path.read_text(encoding="utf-8"))

    # Build the structure_prediction metrics shape as it would appear in DB
    metrics = {
        "model_source": raw.get("model_source", "LocalColabFold"),
        "validation_status": raw.get("validation_status"),
        "prediction_status": raw.get("prediction_status"),
        "metrics_are_real": raw.get("metrics_are_real"),
        "mean_plddt": raw.get("mean_plddt"),
        "ptm": raw.get("ptm"),
        "iptm": raw.get("iptm"),
        "structure_file": raw.get("best_model_pdb"),
        "pae_file": raw.get("pae_file"),
        "raw_score_json": raw.get("raw_score_json"),
        "forbidden_metrics": {"pDockQ": None, "delta_G": None, "docking_score": None},
    }

    report = audit_pdockq_readiness(metrics)
    assert report["pdockq_ready"] is False
    assert report["is_monomer"] is True
    assert "monomer" in report["reason"].lower()


def test_fixture_has_mean_plddt_and_ptm():
    """Available inputs must include mean_plddt and ptm."""
    metrics = _make_structure_prediction_metrics()
    report = audit_pdockq_readiness(metrics)
    assert "mean_plddt" in report["available_inputs"]
    assert "ptm" in report["available_inputs"]


def test_fixture_missing_interface_inputs():
    """All interface-level inputs must be listed as missing."""
    metrics = _make_structure_prediction_metrics()
    report = audit_pdockq_readiness(metrics)
    missing = report["missing_inputs"]
    assert "chain_pair_interface_contacts" in missing
    assert "interface_residue_plddt" in missing
    assert "complex_chain_mapping" in missing
    assert "pae_matrix_or_interface_confidence" in missing
    assert "binding_interface_geometry" in missing


# ---------------------------------------------------------------------------
# Monomer vs complex detection
# ---------------------------------------------------------------------------


def test_monomer_run_detected_when_iptm_null_and_ptm_present():
    """iptm=null + ptm=0.28 must be detected as monomer."""
    metrics = _make_structure_prediction_metrics(iptm=None, ptm=0.28)
    report = audit_pdockq_readiness(metrics)
    assert report["is_monomer"] is True
    assert report["pdockq_ready"] is False


def test_multimer_run_detected_when_iptm_present():
    """iptm=0.45 + ptm=0.28 must be detected as NOT monomer."""
    metrics = _make_structure_prediction_metrics(iptm=0.45, ptm=0.28)
    report = audit_pdockq_readiness(metrics)
    assert report["is_monomer"] is False


def test_multimer_without_pdb_still_not_ready():
    """Even with iptm, missing PDB means not ready."""
    metrics = _make_structure_prediction_metrics(
        iptm=0.45, ptm=0.28, structure_file=None
    )
    report = audit_pdockq_readiness(metrics)
    assert report["is_monomer"] is False
    assert report["has_complex_structure"] is False
    assert report["pdockq_ready"] is False


# ---------------------------------------------------------------------------
# Forbidden metrics detection
# ---------------------------------------------------------------------------


def test_detects_non_null_pdockq_in_forbidden_metrics():
    """Non-null pDockQ in forbidden_metrics must be detected."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": 0.75, "delta_G": None, "docking_score": None}
    )
    report = audit_pdockq_readiness(metrics)
    assert "pDockQ" in report["forbidden_metrics_detected"]
    assert report["forbidden_metrics_detected"]["pDockQ"] == 0.75
    assert report["pdockq_ready"] is False


def test_detects_non_null_delta_g_in_forbidden_metrics():
    """Non-null delta_G in forbidden_metrics must be detected."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": None, "delta_G": -8.5, "docking_score": None}
    )
    report = audit_pdockq_readiness(metrics)
    assert "delta_G" in report["forbidden_metrics_detected"]
    assert report["pdockq_ready"] is False


def test_detects_non_null_docking_score_in_forbidden_metrics():
    """Non-null docking_score in forbidden_metrics must be detected."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": None, "delta_G": None, "docking_score": -7.2}
    )
    report = audit_pdockq_readiness(metrics)
    assert "docking_score" in report["forbidden_metrics_detected"]
    assert report["pdockq_ready"] is False


def test_detects_top_level_forbidden_metrics():
    """Forbidden metrics at top-level must also be detected."""
    metrics = _make_structure_prediction_metrics()
    metrics["pDockQ"] = 0.75  # top-level injection
    report = audit_pdockq_readiness(metrics)
    assert "pDockQ" in report["forbidden_metrics_detected"]


def test_clean_data_has_no_forbidden_metrics_detected():
    """Clean data must have empty forbidden_metrics_detected."""
    metrics = _make_structure_prediction_metrics()
    report = audit_pdockq_readiness(metrics)
    assert report["forbidden_metrics_detected"] == {}


# ---------------------------------------------------------------------------
# No fallback / mock / default pDockQ
# ---------------------------------------------------------------------------


def test_rejects_fallback_pdockq_of_zero():
    """pDockQ=0 must be treated as forbidden (non-null)."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": 0, "delta_G": None, "docking_score": None}
    )
    report = audit_pdockq_readiness(metrics)
    assert "pDockQ" in report["forbidden_metrics_detected"]
    assert report["pdockq_ready"] is False


def test_rejects_mock_pdockq_string():
    """pDockQ='mock' must be treated as forbidden (non-null)."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": "mock", "delta_G": None, "docking_score": None}
    )
    report = audit_pdockq_readiness(metrics)
    assert "pDockQ" in report["forbidden_metrics_detected"]


def test_rejects_default_delta_g_of_zero():
    """delta_G=0 must be treated as forbidden (non-null)."""
    metrics = _make_structure_prediction_metrics(
        forbidden_metrics={"pDockQ": None, "delta_G": 0, "docking_score": None}
    )
    report = audit_pdockq_readiness(metrics)
    assert "delta_G" in report["forbidden_metrics_detected"]


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def test_recommendation_warns_against_premature_pdockq():
    """The recommendation must explicitly warn against premature pDockQ."""
    metrics = _make_structure_prediction_metrics()
    report = audit_pdockq_readiness(metrics)
    rec = report["recommendation"].lower()
    assert "do not compute or display pdockq" in rec
    assert "interface-level features" in rec


# ---------------------------------------------------------------------------
# Future data contract
# ---------------------------------------------------------------------------


def test_interface_quality_contract_has_null_pdockq():
    """The future contract must have pdockq=None (not a number)."""
    contract = get_interface_quality_contract()
    assert contract["pdockq"] is None


def test_interface_quality_contract_validation_status():
    """The future contract must mark computational-only."""
    contract = get_interface_quality_contract()
    assert "COMPUTATIONAL" in contract["validation_status"]
    assert contract["not_experimentally_validated"] is True


def test_interface_quality_contract_is_well_formed():
    """The future contract must contain all expected keys."""
    contract = get_interface_quality_contract()
    expected_keys = {
        "source",
        "metrics_are_real",
        "pdockq",
        "interface_contacts_count",
        "interface_residue_count",
        "chain_pair",
        "pae_interface_mean",
        "validation_status",
        "not_experimentally_validated",
        "provenance",
    }
    assert expected_keys.issubset(set(contract.keys()))


def test_interface_quality_contract_is_separate_from_structure_prediction():
    """The interface_quality contract must not be the same as structure_prediction."""
    contract = get_interface_quality_contract()
    sp_keys = {"mean_plddt", "ptm", "iptm"}
    # interface_quality should NOT have these keys (they belong to structure_prediction)
    for key in sp_keys:
        assert key not in contract
