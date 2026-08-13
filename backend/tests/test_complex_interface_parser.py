"""Tests for complex interface parser (v0.10-P6i).

Uses real ColabFold complex output fixtures to validate interface
contact detection, residue extraction, pLDDT averaging, and PAE parsing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.complex_interface_parser import (
    DEFAULT_DISTANCE_CUTOFF,
    ComplexInterfaceError,
    _compute_cross_chain_pae_mean,
    _find_interface_residues,
    _group_atoms_by_residue,
    _load_pae_matrix,
    _min_distance_between_residues,
    _parse_pdb_atoms,
    parse_complex_interface,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "complex_interface_parser"
PDB_PATH = str(FIXTURES_DIR / "complex_unrelaxed.pdb")
PAE_JSON_PATH = str(FIXTURES_DIR / "predicted_aligned_error.json")


# ---------------------------------------------------------------------------
# Low-level PDB parsing
# ---------------------------------------------------------------------------


def test_parse_pdb_atoms_reads_all_atoms():
    atoms = _parse_pdb_atoms(PDB_PATH)
    assert len(atoms) == 932  # 808 chain A + 124 chain B


def test_parse_pdb_atoms_chain_a_present():
    atoms = _parse_pdb_atoms(PDB_PATH)
    chain_a_atoms = [a for a in atoms if a.chain_id == "A"]
    assert len(chain_a_atoms) == 808


def test_parse_pdb_atoms_chain_b_present():
    atoms = _parse_pdb_atoms(PDB_PATH)
    chain_b_atoms = [a for a in atoms if a.chain_id == "B"]
    assert len(chain_b_atoms) == 124


def test_parse_pdb_atoms_has_b_factors():
    atoms = _parse_pdb_atoms(PDB_PATH)
    assert all(a.b_factor > 0 for a in atoms)
    # First atom is MET A 1 with pLDDT ~39.56
    assert atoms[0].b_factor == pytest.approx(39.56, abs=0.01)


def test_parse_pdb_atoms_residue_names():
    atoms = _parse_pdb_atoms(PDB_PATH)
    assert atoms[0].res_name == "MET"


def test_group_atoms_by_residue_count():
    atoms = _parse_pdb_atoms(PDB_PATH)
    residues = _group_atoms_by_residue(atoms)
    # Chain A has 100 residues, chain B has 15 residues
    chain_a_res = {k for k, r in residues.items() if r.chain_id == "A"}
    chain_b_res = {k for k, r in residues.items() if r.chain_id == "B"}
    assert len(chain_a_res) == 100
    assert len(chain_b_res) == 15


def test_min_distance_between_residues():
    atoms = _parse_pdb_atoms(PDB_PATH)
    residues = _group_atoms_by_residue(atoms)
    # Compare first residue of A with first residue of B
    res_a = residues[("A", 1)]
    res_b = residues[("B", 1)]
    dist = _min_distance_between_residues(res_a, res_b)
    assert dist > 0.0
    assert dist < 100.0


# ---------------------------------------------------------------------------
# Interface detection
# ---------------------------------------------------------------------------


def test_find_interface_residues_detects_contacts():
    atoms = _parse_pdb_atoms(PDB_PATH)
    residues = _group_atoms_by_residue(atoms)
    residues_a = [r for k, r in residues.items() if r.chain_id == "A"]
    residues_b = [r for k, r in residues.items() if r.chain_id == "B"]

    interface_a, interface_b, contact_count = _find_interface_residues(
        residues_a, residues_b, cutoff=DEFAULT_DISTANCE_CUTOFF
    )

    assert contact_count > 0
    assert len(interface_a) > 0
    assert len(interface_b) > 0
    assert len(interface_a) <= len(residues_a)
    assert len(interface_b) <= len(residues_b)


def test_find_interface_residues_with_tight_cutoff():
    atoms = _parse_pdb_atoms(PDB_PATH)
    residues = _group_atoms_by_residue(atoms)
    residues_a = [r for k, r in residues.items() if r.chain_id == "A"]
    residues_b = [r for k, r in residues.items() if r.chain_id == "B"]

    interface_a_loose, interface_b_loose, count_loose = _find_interface_residues(
        residues_a, residues_b, cutoff=8.0
    )
    interface_a_tight, interface_b_tight, count_tight = _find_interface_residues(
        residues_a, residues_b, cutoff=4.0
    )

    assert count_tight <= count_loose
    assert len(interface_a_tight) <= len(interface_a_loose)
    assert len(interface_b_tight) <= len(interface_b_loose)


# ---------------------------------------------------------------------------
# PAE parsing
# ---------------------------------------------------------------------------


def test_load_pae_matrix_shape():
    matrix = _load_pae_matrix(PAE_JSON_PATH)
    assert len(matrix) == 115
    assert all(len(row) == 115 for row in matrix)


def test_compute_cross_chain_pae_mean():
    matrix = _load_pae_matrix(PAE_JSON_PATH)
    mean = _compute_cross_chain_pae_mean(matrix, len_a=100, len_b=15)
    assert mean is not None
    assert mean > 0.0
    assert mean < 50.0


def test_compute_cross_chain_pae_mean_dimension_mismatch():
    matrix = _load_pae_matrix(PAE_JSON_PATH)
    mean = _compute_cross_chain_pae_mean(matrix, len_a=50, len_b=50)
    assert mean is None


def test_compute_cross_chain_pae_mean_empty():
    mean = _compute_cross_chain_pae_mean([], len_a=0, len_b=0)
    assert mean is None


# ---------------------------------------------------------------------------
# Full integration: parse_complex_interface
# ---------------------------------------------------------------------------


def test_parse_complex_interface_ran_true():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["interface_parser_ran"] is True


def test_parse_complex_interface_chain_mapping():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["chain_mapping"]["A"] == "target"
    assert result["chain_mapping"]["B"] == "peptide"


def test_parse_complex_interface_structure_summary():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    ss = result["structure_summary"]
    assert ss["has_chain_A"] is True
    assert ss["has_chain_B"] is True
    assert ss["chain_A_atom_count"] == 808
    assert ss["chain_B_atom_count"] == 124


def test_parse_complex_interface_has_contacts():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    iface = result["interface_summary"]
    assert iface["interface_contact_count"] is not None
    assert iface["interface_contact_count"] > 0


def test_parse_complex_interface_has_interface_residues():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    iface = result["interface_summary"]
    assert iface["interface_residue_count_A"] is not None
    assert iface["interface_residue_count_B"] is not None
    assert iface["interface_residue_count_A"] > 0
    assert iface["interface_residue_count_B"] > 0


def test_parse_complex_interface_has_plddt_mean():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    iface = result["interface_summary"]
    assert iface["interface_residue_plddt_mean"] is not None
    assert 0.0 < iface["interface_residue_plddt_mean"] <= 100.0


def test_parse_complex_interface_has_pae_mean():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    iface = result["interface_summary"]
    assert iface["pae_interface_mean"] is not None
    assert iface["pae_interface_mean"] > 0.0


def test_parse_complex_interface_cutoff_recorded():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["interface_summary"]["distance_cutoff_angstrom"] == 8.0


def test_parse_complex_interface_custom_cutoff():
    result = parse_complex_interface(
        PDB_PATH, pae_json_path=PAE_JSON_PATH, distance_cutoff=4.0
    )
    assert result["interface_summary"]["distance_cutoff_angstrom"] == 4.0
    assert result["interface_summary"]["interface_contact_count"] is not None


def test_parse_complex_interface_custom_chain_mapping():
    result = parse_complex_interface(
        PDB_PATH,
        pae_json_path=PAE_JSON_PATH,
        chain_mapping={"A": "receptor", "B": "ligand"},
    )
    assert result["chain_mapping"]["A"] == "receptor"
    assert result["chain_mapping"]["B"] == "ligand"


def test_parse_complex_interface_without_pae():
    result = parse_complex_interface(PDB_PATH)
    assert result["interface_summary"]["pae_interface_mean"] is None
    assert result["interface_summary"]["interface_contact_count"] is not None


def test_parse_complex_interface_missing_pdb_raises():
    with pytest.raises(ComplexInterfaceError, match="not found"):
        parse_complex_interface("/nonexistent/file.pdb")


def test_parse_complex_interface_empty_pdb_raises(tmp_path: Path):
    empty_pdb = tmp_path / "empty.pdb"
    empty_pdb.write_text("REMARK   1 EMPTY\n", encoding="utf-8")
    with pytest.raises(ComplexInterfaceError, match="No ATOM"):
        parse_complex_interface(str(empty_pdb))


# ---------------------------------------------------------------------------
# Scientific-integrity boundaries
# ---------------------------------------------------------------------------


def test_no_pdockq_computed():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["forbidden_metrics"]["pDockQ"] is None
    assert "pDockQ" not in result.get("interface_summary", {})
    assert result["ready_for_pdockq"] is False


def test_no_delta_g_computed():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["forbidden_metrics"]["delta_G"] is None


def test_no_docking_score_computed():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["forbidden_metrics"]["docking_score"] is None


def test_prediction_status_is_computational_only():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["prediction_status"] == "COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY"


def test_validation_status_not_experimentally_validated():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_metrics_are_real_is_true():
    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    assert result["metrics_are_real"] is True


# ---------------------------------------------------------------------------
# JSON round-trip
# ---------------------------------------------------------------------------


def test_result_is_json_serializable():
    import json

    result = parse_complex_interface(PDB_PATH, pae_json_path=PAE_JSON_PATH)
    serialized = json.dumps(result, indent=2)
    deserialized = json.loads(serialized)
    assert deserialized["interface_parser_ran"] is True
    assert deserialized["structure_summary"]["chain_A_atom_count"] == 808
