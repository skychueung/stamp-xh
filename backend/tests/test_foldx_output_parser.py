"""Tests for FoldX output parser (v0.10-P6m).

Validates parsing of real FoldX AnalyseComplex Interaction_*.fxout files,
energy term extraction, quality flag computation, and error handling.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.services.foldx_output_parser import (
    INTERACTION_ENERGY_FAVORABLE_THRESHOLD,
    VDW_CLASHES_HIGH_THRESHOLD,
    FoldXParserError,
    _build_quality_flags,
    parse_foldx_interaction_fxout,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "foldx_output"
REAL_FXOUT = FIXTURES_DIR / "Interaction_complex_unrelaxed_Repair_AC.fxout"


# ---------------------------------------------------------------------------
# Success cases with real fixture
# ---------------------------------------------------------------------------


def test_parse_real_fixture_interaction_energy():
    """Parser must extract interaction_energy = 86.3008 from real fixture."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)


def test_parse_real_fixture_energy_terms():
    """Parser must extract all energy terms from real fixture."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    terms = result["energy_terms"]
    assert terms["backbone_hbond"] == pytest.approx(-4.28945, abs=0.0001)
    assert terms["sidechain_hbond"] == pytest.approx(-8.36149, abs=0.0001)
    assert terms["van_der_waals"] == pytest.approx(-17.5585, abs=0.0001)
    assert terms["electrostatics"] == pytest.approx(-1.66972, abs=0.0001)
    assert terms["solvation_polar"] == pytest.approx(30.1665, abs=0.0001)
    assert terms["solvation_hydrophobic"] == pytest.approx(-20.4973, abs=0.0001)
    assert terms["vdw_clashes"] == pytest.approx(89.0375, abs=0.0001)
    assert terms["entropy_sidechain"] == pytest.approx(12.4522, abs=0.0001)
    assert terms["entropy_mainchain"] == pytest.approx(7.17501, abs=0.0001)
    assert terms["entropy_complex"] == pytest.approx(2.384, abs=0.0001)


def test_parse_real_fixture_vdw_clashes():
    """vdw_clashes must be 89.04 from real fixture."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["energy_terms"]["vdw_clashes"] == pytest.approx(89.0375, abs=0.001)


def test_parse_real_fixture_quality_flags_high_vdw_clashes():
    """Quality flags must mark high_vdw_clashes=True when vdw_clashes > 20."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["quality_flags"]["high_vdw_clashes"] is True


def test_parse_real_fixture_quality_flags_unfavorable_energy():
    """Quality flags must mark unfavorable_interaction_energy=True when energy > 0."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["quality_flags"]["unfavorable_interaction_energy"] is True
    assert result["quality_flags"]["favorable_interaction_energy"] is False


def test_parse_real_fixture_quality_flags_interpretation():
    """Interpretation must mention unfavorable and high VdW clashes."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    interp = result["quality_flags"]["interpretation"]
    assert "unfavorable" in interp.lower() or "computational estimate" in interp.lower()
    assert "VdW clashes" in interp or "clashes" in interp


def test_parse_real_fixture_source_and_algorithm():
    """Source and algorithm fields must be correctly set."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["source"] == "foldx_analysecomplex"
    assert result["algorithm"] == "FoldX AnalyseComplex"
    assert result["algorithm_version"] == "FoldX 5.1"


def test_parse_real_fixture_prediction_status():
    """prediction_status must be COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["prediction_status"] == "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"


def test_parse_real_fixture_validation_status():
    """validation_status must be NOT_EXPERIMENTALLY_VALIDATED."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_parse_real_fixture_forbidden_metrics_null():
    """forbidden_metrics must all be null."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    fm = result["forbidden_metrics"]
    assert fm["docking_score"] is None
    assert fm["mmgbsa_delta_G"] is None
    assert fm["experimental_delta_G"] is None


def test_parse_real_fixture_metrics_are_real():
    """metrics_are_real must be True."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    assert result["metrics_are_real"] is True


def test_parse_real_fixture_provenance():
    """Provenance must contain FoldX executable and command info."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    prov = result["provenance"]
    assert "foldx_executable" in prov
    assert "foldx_command" in prov
    assert "interaction_fxout" in prov
    assert prov["interaction_fxout"] == "Interaction_complex_unrelaxed_Repair_AC.fxout"


def test_parse_real_fixture_chain_mapping():
    """Chain mapping must map Group1->target, Group2->peptide."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    cm = result["chain_mapping"]
    assert cm.get("A") == "target"
    assert cm.get("B") == "peptide"


def test_parse_real_fixture_metadata():
    """Metadata must contain intraclashes and residue counts."""
    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    meta = result["metadata"]
    assert meta["intraclashes_group1"] == pytest.approx(49.948, abs=0.001)
    assert meta["intraclashes_group2"] == pytest.approx(4.6752, abs=0.0001)
    assert meta["number_of_residues"] == pytest.approx(115, abs=0.1)
    assert meta["interface_residues"] == pytest.approx(29, abs=0.1)


# ---------------------------------------------------------------------------
# Quality flags computation
# ---------------------------------------------------------------------------


def test_build_quality_flags_favorable_energy():
    """Negative interaction energy marks favorable_interaction_energy=True."""
    flags = _build_quality_flags(-5.0, 10.0)
    assert flags["favorable_interaction_energy"] is True
    assert flags["unfavorable_interaction_energy"] is False
    assert "favorable" in flags["interpretation"].lower()


def test_build_quality_flags_unfavorable_energy():
    """Positive interaction energy marks unfavorable_interaction_energy=True."""
    flags = _build_quality_flags(5.0, 10.0)
    assert flags["unfavorable_interaction_energy"] is True
    assert flags["favorable_interaction_energy"] is False
    assert "unfavorable" in flags["interpretation"].lower()


def test_build_quality_flags_zero_energy():
    """Zero interaction energy gives neutral interpretation."""
    flags = _build_quality_flags(0.0, 10.0)
    assert flags["favorable_interaction_energy"] is False
    assert flags["unfavorable_interaction_energy"] is False
    assert "near zero" in flags["interpretation"].lower()


def test_build_quality_flags_high_vdw_clashes():
    """vdw_clashes > 20 marks high_vdw_clashes=True."""
    flags = _build_quality_flags(5.0, 25.0)
    assert flags["high_vdw_clashes"] is True
    assert "clashes" in flags["interpretation"].lower()


def test_build_quality_flags_low_vdw_clashes():
    """vdw_clashes <= 20 marks high_vdw_clashes=False."""
    flags = _build_quality_flags(5.0, 15.0)
    assert flags["high_vdw_clashes"] is False


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_parse_missing_file_raises():
    """Missing fxout file must raise FoldXParserError."""
    with pytest.raises(FoldXParserError, match="not found"):
        parse_foldx_interaction_fxout("/nonexistent/path/Interaction.fxout")


def test_parse_empty_file_raises(tmp_path: Path):
    """Empty fxout file must raise FoldXParserError."""
    empty_file = tmp_path / "empty.fxout"
    empty_file.write_text("", encoding="utf-8")
    with pytest.raises(FoldXParserError, match="empty"):
        parse_foldx_interaction_fxout(str(empty_file))


def test_parse_missing_header_raises(tmp_path: Path):
    """fxout without 'Interaction Energy' header must raise FoldXParserError."""
    bad_file = tmp_path / "bad.fxout"
    bad_file.write_text("Some random text\nwithout header\n", encoding="utf-8")
    with pytest.raises(FoldXParserError, match="missing"):
        parse_foldx_interaction_fxout(str(bad_file))


def test_parse_header_no_data_raises(tmp_path: Path):
    """fxout with header but no data rows must raise FoldXParserError."""
    bad_file = tmp_path / "bad.fxout"
    bad_file.write_text(
        "FoldX 5.1\nPdb\tGroup1\tInteraction Energy\n",
        encoding="utf-8",
    )
    with pytest.raises(FoldXParserError, match="no data"):
        parse_foldx_interaction_fxout(str(bad_file))


def test_parse_numeric_field_error_raises(tmp_path: Path):
    """Non-numeric Interaction Energy must raise FoldXParserError."""
    bad_file = tmp_path / "bad.fxout"
    bad_file.write_text(
        "FoldX 5.1\nPdb\tGroup1\tGroup2\tInteraction Energy\nfoo\tA\tB\tnot_a_number\n",
        encoding="utf-8",
    )
    with pytest.raises(FoldXParserError, match="not numeric"):
        parse_foldx_interaction_fxout(str(bad_file))


# ---------------------------------------------------------------------------
# JSON serializability
# ---------------------------------------------------------------------------


def test_result_is_json_serializable():
    """Parsed result must be JSON-serializable."""
    import json

    result = parse_foldx_interaction_fxout(str(REAL_FXOUT))
    serialized = json.dumps(result)
    deserialized = json.loads(serialized)
    assert deserialized["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)


# ---------------------------------------------------------------------------
# Windows/WSL path compatibility
# ---------------------------------------------------------------------------


def test_parse_accepts_windows_style_path(tmp_path: Path):
    """Parser must accept Windows-style paths."""
    # Copy fixture to tmp_path using Windows path
    dest = tmp_path / "Interaction_test.fxout"
    import shutil

    shutil.copy(REAL_FXOUT, dest)
    result = parse_foldx_interaction_fxout(str(dest))
    assert result["interaction_energy_kcal_mol"] == pytest.approx(86.3008, abs=0.0001)
