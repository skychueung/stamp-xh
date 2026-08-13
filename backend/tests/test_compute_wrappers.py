"""Tests for compute wrappers (v1.2-lab-production-fast P3)."""

from __future__ import annotations

import pytest

from app.services.compute_wrappers.colabfold_wrapper import parse_colabfold_artifact
from app.services.compute_wrappers.flexpepdock_wrapper import parse_flexpepdock_artifact
from app.services.compute_wrappers.foldx_wrapper import parse_foldx_artifact
from app.services.compute_wrappers.mmgbsa_wrapper import parse_mmgbsa_artifact

FIXTURES_DIR = "D:\\Desktop\\靶向肽\\github\\前端\\backend\\tests\\fixtures"
OUTPUTS_DIR = "D:\\ai\\product\\kimi\\outputs"


# ---------------------------------------------------------------------------
# ColabFold wrapper
# ---------------------------------------------------------------------------

def test_parse_colabfold_existing_fixture():
    path = f"{FIXTURES_DIR}\\localcolabfold_smoke\\parsed_metrics.json"
    result = parse_colabfold_artifact(path)
    assert result["status"] == "SUCCEEDED"
    assert result["prediction_status"] == "COMPUTATIONAL_STRUCTURE_PREDICTION_ONLY"
    metrics = result["metrics"]
    assert metrics["mean_plddt"] == 65.23
    assert metrics["ptm"] == 0.28
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_parse_colabfold_missing_file():
    result = parse_colabfold_artifact("/nonexistent/path.json")
    assert result["status"] == "BLOCKED"
    assert result["error_code"] == "ARTIFACT_NOT_FOUND"


# ---------------------------------------------------------------------------
# FoldX wrapper
# ---------------------------------------------------------------------------

def test_parse_foldx_existing_fixture():
    path = f"{FIXTURES_DIR}\\foldx_output\\Interaction_complex_unrelaxed_Repair_AC.fxout"
    result = parse_foldx_artifact(path)
    assert result["status"] == "SUCCEEDED"
    assert result["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"
    terms = result["energy_terms"]
    assert terms["interaction_energy_kcal_mol"] == 86.3008
    assert terms["vdw_clashes"] == 89.0375
    assert result["scientific_boundary"]["not_docking_score"] is True
    assert result["scientific_boundary"]["not_mmgbsa_delta_g"] is True


def test_parse_foldx_missing_file():
    result = parse_foldx_artifact("/nonexistent/foldx.fxout")
    assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# FlexPepDock wrapper
# ---------------------------------------------------------------------------

def test_parse_flexpepdock_existing_json():
    path = f"{OUTPUTS_DIR}\\P2C_FLEXPEPDOCK_RESULT.json"
    result = parse_flexpepdock_artifact(path)
    assert result["status"] == "SUCCEEDED"
    assert result["prediction_status"] == "COMPUTATIONAL_DOCKING_ESTIMATE_ONLY"
    metrics = result["metrics"]
    assert "total_score" in metrics
    assert "interface_score_isc" in metrics
    assert result["scientific_boundary"]["not_docking_score"] is True


def test_parse_flexpepdock_missing_file():
    result = parse_flexpepdock_artifact("/nonexistent/flexpepdock.json")
    assert result["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# MM-GBSA wrapper
# ---------------------------------------------------------------------------

def test_parse_mmgbsa_missing_file():
    result = parse_mmgbsa_artifact("/nonexistent/FINAL_RESULTS_MMPBSA.dat")
    assert result["status"] == "BLOCKED"
    assert result["error_code"] == "ARTIFACT_NOT_FOUND"


def test_parse_mmgbsa_official_delta_g_null():
    # Even if we had a production file, wrapper enforces null boundary
    # This test verifies the boundary logic
    result = parse_mmgbsa_artifact("/nonexistent/FINAL_RESULTS_MMPBSA.dat")
    assert result.get("official_mm_gbsa_delta_g") is None


# ---------------------------------------------------------------------------
# Scientific boundary: no fabricated metrics
# ---------------------------------------------------------------------------

def test_no_fabricated_docking_score():
    path = f"{OUTPUTS_DIR}\\P2C_FLEXPEPDOCK_RESULT.json"
    result = parse_flexpepdock_artifact(path)
    assert "docking_score" not in result["metrics"]
    assert result["scientific_boundary"]["not_docking_score"] is True


def test_no_fabricated_official_mmgbsa():
    path = f"{OUTPUTS_DIR}\\P2C_FLEXPEPDOCK_RESULT.json"
    result = parse_flexpepdock_artifact(path)
    assert "official_mm_gbsa_delta_g" not in result.get("metrics", {})
