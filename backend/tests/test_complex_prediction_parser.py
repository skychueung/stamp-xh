"""Tests for complex prediction output parser (v0.10-P6h).

Validates that the parser correctly inspects complex prediction output
directories and reports readiness for interface parsing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.complex_prediction_parser import parse_complex_output

FIXTURE_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Mock fixtures
# ---------------------------------------------------------------------------


def _make_mock_pdb_with_chains(tmp_path: Path, chains: list[str]) -> Path:
    """Create a minimal mock PDB with specified chain IDs.

    PDB ATOM record format (relevant columns):
      - 1-6: RECORD
      - 7-11: serial
      - 13-16: atom name
      - 18-20: resName
      - 22: chainID (1-based column 22 = 0-based index 21)
    """
    pdb_path = tmp_path / "mock_complex.pdb"
    lines = ["REMARK   1 MOCK PDB FOR TESTING"]
    for chain in chains:
        # Column 22 (0-index 21) must be the chain ID
        line = (
            f"ATOM      1  N   ALA {chain}   1      10.000  10.000  10.000  1.00 20.00           N"
        )
        lines.append(line)
    lines.append("END")
    pdb_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return pdb_path


def _make_mock_ranking_json(tmp_path: Path) -> Path:
    """Create a mock ranking_debug.json."""
    ranking_path = tmp_path / "ranking_debug.json"
    ranking_path.write_text(
        json.dumps({"model_1": {"plddt": 75.0, "ptm": 0.55, "iptm": 0.35}}),
        encoding="utf-8",
    )
    return ranking_path


def _make_mock_pae_json(tmp_path: Path) -> Path:
    """Create a mock pae.json."""
    pae_path = tmp_path / "pae.json"
    pae_path.write_text(
        json.dumps({"pae": [[0.0, 5.0], [5.0, 0.0]]}),
        encoding="utf-8",
    )
    return pae_path


# ---------------------------------------------------------------------------
# Output directory does not exist
# ---------------------------------------------------------------------------


def test_parse_nonexistent_dir():
    """Non-existent output directory must be reported clearly."""
    report = parse_complex_output("/nonexistent/path/to/output")
    assert report["complex_prediction_ran"] is False
    assert "does not exist" in report["reason"]


# ---------------------------------------------------------------------------
# Empty output directory
# ---------------------------------------------------------------------------


def test_parse_empty_dir(tmp_path: Path):
    """Empty directory must report no files found."""
    report = parse_complex_output(tmp_path)
    assert report["complex_prediction_ran"] is False
    assert report["files_found"] == []
    assert report["ready_for_interface_parser"] is False


# ---------------------------------------------------------------------------
# Partial outputs (monomer-like)
# ---------------------------------------------------------------------------


def test_parse_monomer_pdb_no_chain_b(tmp_path: Path):
    """PDB with only chain A (monomer-like) must not be interface-ready."""
    _make_mock_pdb_with_chains(tmp_path, ["A"])
    _make_mock_ranking_json(tmp_path)
    report = parse_complex_output(tmp_path)
    assert report["complex_prediction_ran"] is True
    assert report["has_chain_A"] is True
    assert report["has_chain_B"] is False
    assert report["ready_for_interface_parser"] is False


# ---------------------------------------------------------------------------
# Full complex outputs (multimer-like)
# ---------------------------------------------------------------------------


def test_parse_complex_with_both_chains(tmp_path: Path):
    """PDB with chain A and chain B must be interface-ready."""
    _make_mock_pdb_with_chains(tmp_path, ["A", "B"])
    _make_mock_ranking_json(tmp_path)
    report = parse_complex_output(tmp_path)
    assert report["complex_prediction_ran"] is True
    assert report["has_chain_A"] is True
    assert report["has_chain_B"] is True
    assert report["has_complex_structure_file"] is True
    assert report["ready_for_interface_parser"] is True


def test_parse_complex_with_pae(tmp_path: Path):
    """Complex output with PAE file must report has_pae=True."""
    _make_mock_pdb_with_chains(tmp_path, ["A", "B"])
    _make_mock_pae_json(tmp_path)
    report = parse_complex_output(tmp_path)
    assert report["has_pae"] is True
    assert report["pae_file_path"] is not None


def test_parse_complex_with_ranking_json(tmp_path: Path):
    """Complex output with ranking JSON must report has_ranking_json=True."""
    _make_mock_pdb_with_chains(tmp_path, ["A", "B"])
    _make_mock_ranking_json(tmp_path)
    report = parse_complex_output(tmp_path)
    assert report["has_ranking_json"] is True
    assert report["ranking_json_path"] is not None


# ---------------------------------------------------------------------------
# Scientific boundary checks
# ---------------------------------------------------------------------------


def test_parse_forbidden_metrics_are_null():
    """Report must contain null forbidden metrics."""
    report = parse_complex_output("/nonexistent")
    fm = report["forbidden_metrics"]
    assert fm["pDockQ"] is None
    assert fm["delta_G"] is None
    assert fm["docking_score"] is None


def test_parse_pdockq_not_computed():
    """ready_for_pdockq must always be False in P6h."""
    report = parse_complex_output("/nonexistent")
    assert report["ready_for_pdockq"] is False
    assert "deferred to P6j" in report["reason_pdockq_not_computed"]


def test_parse_validation_status():
    """validation_status must be NOT_EXPERIMENTALLY_VALIDATED."""
    report = parse_complex_output("/nonexistent")
    assert report["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_parse_prediction_status():
    """prediction_status must be COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY."""
    report = parse_complex_output("/nonexistent")
    assert report["prediction_status"] == "COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY"


def test_parse_metrics_are_real_is_false():
    """metrics_are_real must be False (P6h is audit, not real prediction)."""
    report = parse_complex_output("/nonexistent")
    assert report["metrics_are_real"] is False


# ---------------------------------------------------------------------------
# Real monomer fixture audit (from P6b)
# ---------------------------------------------------------------------------


def test_parse_real_monomer_output_from_p6b():
    """Parse the real P6b monomer output to validate parser framework.

    This is a monomer run, so it should NOT be interface-ready.
    The parser must correctly detect that chain B is absent.
    """
    p6b_output = FIXTURE_DIR / "localcolabfold_smoke"
    # The fixture dir only has parsed_metrics.json, not actual PDB.
    # So this tests that the parser handles real dirs gracefully.
    report = parse_complex_output(p6b_output)
    assert report["complex_prediction_ran"] is False
    assert report["has_complex_structure_file"] is False
    assert report["has_chain_A"] is False
    assert report["has_chain_B"] is False
    assert report["ready_for_interface_parser"] is False


# ---------------------------------------------------------------------------
# CIF structure file support
# ---------------------------------------------------------------------------


def test_parse_cif_structure_file(tmp_path: Path):
    """CIF structure files must be detected."""
    cif_path = tmp_path / "model.cif"
    cif_path.write_text("data_model\n_atom_site.group_PDB ATOM\n", encoding="utf-8")
    report = parse_complex_output(tmp_path)
    assert report["has_complex_structure_file"] is True
    assert report["structure_file_path"] is not None
