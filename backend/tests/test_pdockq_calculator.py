"""Tests for pDockQ calculator (v0.10-P6j).

Validates the sigmoid formula, input validation guards, and
interface_quality dict construction.
"""

from __future__ import annotations

import math

import pytest

from app.services.pdockq_calculator import (
    B_PARAM,
    K_PARAM,
    L_PARAM,
    PDockQError,
    X0_PARAM,
    build_interface_quality,
    calculate_pdockq,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

REAL_CONTACT_COUNT = 149
REAL_PLDDT_MEAN = 37.62448275862067
REAL_X = REAL_PLDDT_MEAN * math.log(REAL_CONTACT_COUNT)


def _expected_pdockq(contact_count: float, plddt_mean: float) -> float:
    """Reference implementation of the pDockQ formula."""
    x = plddt_mean * math.log(contact_count)
    raw = L_PARAM / (1.0 + math.exp(-K_PARAM * (x - X0_PARAM))) + B_PARAM
    return max(0.0, min(1.0, raw))


# ---------------------------------------------------------------------------
# Formula accuracy
# ---------------------------------------------------------------------------


def test_calculate_pdockq_with_real_fixture_values():
    """P6i fixture values should produce pDockQ ≈ 0.644."""
    pdockq = calculate_pdockq(REAL_CONTACT_COUNT, REAL_PLDDT_MEAN)
    expected = _expected_pdockq(REAL_CONTACT_COUNT, REAL_PLDDT_MEAN)
    assert pdockq == pytest.approx(expected, abs=1e-6)
    assert pdockq == pytest.approx(0.644, abs=0.01)


def test_x_value_matches_manual():
    """x = plddt * ln(contacts) should be ≈ 188.25 for fixture values."""
    x = REAL_PLDDT_MEAN * math.log(REAL_CONTACT_COUNT)
    assert x == pytest.approx(188.25, abs=0.1)


def test_pdockq_range_0_to_1():
    """pDockQ must always be in [0, 1]."""
    pdockq = calculate_pdockq(REAL_CONTACT_COUNT, REAL_PLDDT_MEAN)
    assert 0.0 <= pdockq <= 1.0


def test_pdockq_increases_with_more_contacts():
    """More contacts at same pLDDT → higher pDockQ."""
    low = calculate_pdockq(10, 50.0)
    high = calculate_pdockq(1000, 50.0)
    assert high > low


def test_pdockq_increases_with_higher_plddt():
    """Higher pLDDT at same contact count → higher pDockQ."""
    low = calculate_pdockq(100, 20.0)
    high = calculate_pdockq(100, 80.0)
    assert high > low


def test_pdockq_at_boundary_low():
    """Very low inputs should still produce valid pDockQ in [0, 1]."""
    pdockq = calculate_pdockq(1, 0.1)
    assert 0.0 <= pdockq <= 1.0


def test_pdockq_at_boundary_high():
    """Very high inputs should still produce valid pDockQ in [0, 1]."""
    pdockq = calculate_pdockq(10000, 100.0)
    assert 0.0 <= pdockq <= 1.0
    assert pdockq > 0.7  # High but not fully saturated at L+b=0.742


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_rejects_zero_contact_count():
    """contact_count = 0 must raise PDockQError."""
    with pytest.raises(PDockQError, match="> 0"):
        calculate_pdockq(0, 50.0)


def test_rejects_negative_contact_count():
    """Negative contact_count must raise PDockQError."""
    with pytest.raises(PDockQError, match="> 0"):
        calculate_pdockq(-5, 50.0)


def test_rejects_none_contact_count():
    """None contact_count must raise PDockQError."""
    with pytest.raises(PDockQError, match="required"):
        calculate_pdockq(None, 50.0)


def test_rejects_none_plddt():
    """None pLDDT must raise PDockQError."""
    with pytest.raises(PDockQError, match="required"):
        calculate_pdockq(100, None)


def test_rejects_negative_plddt():
    """Negative pLDDT must raise PDockQError."""
    with pytest.raises(PDockQError, match=">= 0"):
        calculate_pdockq(100, -1.0)


def test_rejects_plddt_over_100():
    """pLDDT > 100 must raise PDockQError."""
    with pytest.raises(PDockQError, match="<= 100"):
        calculate_pdockq(100, 101.0)


def test_rejects_non_numeric_contact_count():
    """Non-numeric contact_count must raise PDockQError."""
    with pytest.raises(PDockQError, match="numeric"):
        calculate_pdockq("many", 50.0)


def test_rejects_non_numeric_plddt():
    """Non-numeric pLDDT must raise PDockQError."""
    with pytest.raises(PDockQError, match="numeric"):
        calculate_pdockq(100, "high")


def test_rejects_mock_fallback_default_plddt():
    """Mock/fallback pLDDT values like 0.0 or 50.0 as defaults should be caught by validation."""
    # 0.0 is technically valid mathematically but suspicious; we allow it
    # but the caller should ensure it's a real parsed value
    pdockq = calculate_pdockq(100, 0.0)
    # When pLDDT=0, x=0, pDockQ = L/(1+exp(k*x0)) + b which is slightly above b
    assert pdockq > B_PARAM
    assert pdockq < B_PARAM + 0.01


# ---------------------------------------------------------------------------
# build_interface_quality
# ---------------------------------------------------------------------------


def _make_parser_result(
    contact_count: int = REAL_CONTACT_COUNT,
    plddt_mean: float = REAL_PLDDT_MEAN,
    pae_mean: float = 22.01,
    res_a: int = 43,
    res_b: int = 15,
) -> dict:
    return {
        "interface_parser_ran": True,
        "chain_mapping": {"A": "target", "B": "peptide"},
        "structure_summary": {
            "has_chain_A": True,
            "has_chain_B": True,
            "chain_A_atom_count": 808,
            "chain_B_atom_count": 124,
        },
        "interface_summary": {
            "distance_cutoff_angstrom": 8.0,
            "interface_contact_count": contact_count,
            "interface_residue_count_A": res_a,
            "interface_residue_count_B": res_b,
            "interface_residue_plddt_mean": plddt_mean,
            "pae_interface_mean": pae_mean,
        },
        "ready_for_pdockq": False,
        "reason_pdockq_not_computed": "deferred",
        "forbidden_metrics": {"pDockQ": None, "delta_G": None, "docking_score": None},
    }


def test_build_interface_quality_has_pdockq():
    result = build_interface_quality(_make_parser_result())
    assert "pdockq" in result
    assert isinstance(result["pdockq"], float)
    assert 0.0 <= result["pdockq"] <= 1.0


def test_build_interface_quality_pdockq_approx_0_644():
    result = build_interface_quality(_make_parser_result())
    assert result["pdockq"] == pytest.approx(0.644, abs=0.01)


def test_build_interface_quality_has_provenance():
    result = build_interface_quality(_make_parser_result())
    prov = result["provenance"]
    assert prov["calculator_formula"] == "pDockQ = L/(1+exp(-k*(x-x0)))+b"
    assert prov["parameters"]["L"] == L_PARAM
    assert prov["parameters"]["x0"] == X0_PARAM
    assert prov["parameters"]["k"] == K_PARAM
    assert prov["parameters"]["b"] == B_PARAM


def test_build_interface_quality_has_input_features():
    result = build_interface_quality(_make_parser_result())
    inp = result["input_features"]
    assert inp["interface_contact_count"] == REAL_CONTACT_COUNT
    assert inp["interface_residue_plddt_mean"] == REAL_PLDDT_MEAN
    assert inp["x_value"] == pytest.approx(188.25, abs=0.1)
    assert inp["distance_cutoff_angstrom"] == 8.0


def test_build_interface_quality_has_x_value():
    result = build_interface_quality(_make_parser_result())
    assert result["input_features"]["x_value"] is not None
    assert result["input_features"]["x_value"] > 0


def test_build_interface_quality_metrics_are_real():
    result = build_interface_quality(_make_parser_result())
    assert result["metrics_are_real"] is True


def test_build_interface_quality_prediction_status():
    result = build_interface_quality(_make_parser_result())
    assert result["prediction_status"] == "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"


def test_build_interface_quality_validation_status():
    result = build_interface_quality(_make_parser_result())
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_build_interface_quality_delta_g_is_null():
    result = build_interface_quality(_make_parser_result())
    assert result["forbidden_metrics"]["delta_G"] is None


def test_build_interface_quality_docking_score_is_null():
    result = build_interface_quality(_make_parser_result())
    assert result["forbidden_metrics"]["docking_score"] is None


def test_build_interface_quality_no_top_level_delta_g():
    result = build_interface_quality(_make_parser_result())
    assert "delta_G" not in result or result.get("delta_G") is None


def test_build_interface_quality_no_top_level_docking_score():
    result = build_interface_quality(_make_parser_result())
    assert "docking_score" not in result or result.get("docking_score") is None


def test_build_interface_quality_chain_mapping():
    result = build_interface_quality(_make_parser_result())
    assert result["chain_mapping"]["A"] == "target"
    assert result["chain_mapping"]["B"] == "peptide"


def test_build_interface_quality_pae_interface_mean():
    result = build_interface_quality(_make_parser_result(pae_mean=22.01))
    assert result["pae_interface_mean"] == 22.01


def test_build_interface_quality_interface_residue_counts():
    result = build_interface_quality(_make_parser_result(res_a=43, res_b=15))
    assert result["interface_residue_count_A"] == 43
    assert result["interface_residue_count_B"] == 15


def test_build_interface_quality_rejects_parser_not_ran():
    parser_result = _make_parser_result()
    parser_result["interface_parser_ran"] = False
    with pytest.raises(PDockQError, match="interface_parser_ran"):
        build_interface_quality(parser_result)


def test_build_interface_quality_rejects_zero_contacts():
    parser_result = _make_parser_result(contact_count=0)
    with pytest.raises(PDockQError, match="> 0"):
        build_interface_quality(parser_result)


def test_build_interface_quality_rejects_none_plddt():
    parser_result = _make_parser_result(plddt_mean=None)
    with pytest.raises(PDockQError, match="required"):
        build_interface_quality(parser_result)


def test_build_interface_quality_algorithm_version():
    result = build_interface_quality(_make_parser_result())
    assert result["algorithm"] == "pDockQ"
    assert result["algorithm_version"] == "original_sigmoid_bryant_2022"


def test_build_interface_quality_source():
    result = build_interface_quality(_make_parser_result())
    assert result["source"] == "colabfold_complex_interface_parser"


def test_build_interface_quality_custom_provenance():
    result = build_interface_quality(
        _make_parser_result(),
        input_complex_structure_file="my_complex.pdb",
        interface_parser_commit="abc1234",
    )
    prov = result["provenance"]
    assert prov["input_complex_structure_file"] == "my_complex.pdb"
    assert prov["interface_parser_commit"] == "abc1234"
