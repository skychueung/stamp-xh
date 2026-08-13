"""STAMP Platform — Complex Interface Parser (v0.10-P6i).

Parses target + peptide complex structure output to extract:
  - Chain presence and atom counts
  - Interface contacts and residues
  - Interface residue pLDDT (from B-factors)
  - Cross-chain PAE mean (from PAE JSON)

Current stage: INTERFACE_FEATURE_PARSING_ONLY.
NO pDockQ, NO delta_G, NO docking_score computation.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DISTANCE_CUTOFF = 8.0  # Ångström

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_COMPLEX_STRUCTURE_PREDICTION_ONLY"


class ComplexInterfaceError(ValueError):
    """Raised when complex interface parsing fails."""

    pass


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class Atom:
    """Minimal PDB ATOM record representation."""

    def __init__(
        self,
        serial: int,
        name: str,
        res_name: str,
        chain_id: str,
        res_seq: int,
        x: float,
        y: float,
        z: float,
        b_factor: float,
    ):
        self.serial = serial
        self.name = name
        self.res_name = res_name
        self.chain_id = chain_id
        self.res_seq = res_seq
        self.x = x
        self.y = y
        self.z = z
        self.b_factor = b_factor


class Residue:
    """Collection of atoms belonging to one residue."""

    def __init__(self, chain_id: str, res_seq: int, res_name: str):
        self.chain_id = chain_id
        self.res_seq = res_seq
        self.res_name = res_name
        self.atoms: list[Atom] = []

    def add_atom(self, atom: Atom) -> None:
        self.atoms.append(atom)

    def mean_b_factor(self) -> float | None:
        if not self.atoms:
            return None
        return sum(a.b_factor for a in self.atoms) / len(self.atoms)


# ---------------------------------------------------------------------------
# PDB parsing
# ---------------------------------------------------------------------------


def _parse_pdb_atoms(pdb_path: str) -> list[Atom]:
    """Parse ATOM and HETATM records from a PDB file."""
    atoms: list[Atom] = []
    with open(pdb_path, "r", encoding="utf-8") as fh:
        for line in fh:
            if not (line.startswith("ATOM  ") or line.startswith("HETATM")):
                continue
            try:
                serial = int(line[6:11].strip())
                name = line[12:16].strip()
                res_name = line[17:20].strip()
                chain_id = line[21].strip()
                res_seq = int(line[22:26].strip())
                x = float(line[30:38].strip())
                y = float(line[38:46].strip())
                z = float(line[46:54].strip())
                b_factor_str = line[60:66].strip()
                b_factor = float(b_factor_str) if b_factor_str else 0.0
                atoms.append(
                    Atom(serial, name, res_name, chain_id, res_seq, x, y, z, b_factor)
                )
            except (ValueError, IndexError) as exc:
                logger.warning("Skipping malformed PDB line: %s... (%s)", line[:50], exc)
                continue
    return atoms


def _group_atoms_by_residue(atoms: list[Atom]) -> dict[tuple[str, int], Residue]:
    """Group atoms into residues keyed by (chain_id, res_seq)."""
    residues: dict[tuple[str, int], Residue] = {}
    for atom in atoms:
        key = (atom.chain_id, atom.res_seq)
        if key not in residues:
            residues[key] = Residue(atom.chain_id, atom.res_seq, atom.res_name)
        residues[key].add_atom(atom)
    return residues


def _min_distance_between_residues(res_a: Residue, res_b: Residue) -> float:
    """Compute minimum Euclidean distance between any two atoms of two residues."""
    min_dist = float("inf")
    for a in res_a.atoms:
        for b in res_b.atoms:
            dx = a.x - b.x
            dy = a.y - b.y
            dz = a.z - b.z
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < min_dist:
                min_dist = dist
    return min_dist


# ---------------------------------------------------------------------------
# Interface detection
# ---------------------------------------------------------------------------


def _find_interface_residues(
    residues_a: list[Residue],
    residues_b: list[Residue],
    cutoff: float = DEFAULT_DISTANCE_CUTOFF,
) -> tuple[set[tuple[str, int]], set[tuple[str, int]], int]:
    """Find interface residues between two chains.

    Returns:
        (interface_keys_a, interface_keys_b, contact_count)
        where contact_count is the number of residue-residue pairs within cutoff.
    """
    interface_a: set[tuple[str, int]] = set()
    interface_b: set[tuple[str, int]] = set()
    contact_count = 0

    for res_a in residues_a:
        for res_b in residues_b:
            if _min_distance_between_residues(res_a, res_b) <= cutoff:
                interface_a.add((res_a.chain_id, res_a.res_seq))
                interface_b.add((res_b.chain_id, res_b.res_seq))
                contact_count += 1

    return interface_a, interface_b, contact_count


# ---------------------------------------------------------------------------
# PAE parsing
# ---------------------------------------------------------------------------


def _load_pae_matrix(pae_json_path: str) -> list[list[float]]:
    """Load predicted aligned error matrix from ColabFold PAE JSON."""
    with open(pae_json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "predicted_aligned_error" in data:
        return data["predicted_aligned_error"]
    if "pae" in data:
        return data["pae"]
    raise ComplexInterfaceError(
        f"No 'predicted_aligned_error' or 'pae' key found in {pae_json_path}"
    )


def _compute_cross_chain_pae_mean(
    pae_matrix: list[list[float]],
    len_a: int,
    len_b: int,
) -> float | None:
    """Compute mean PAE for cross-chain region (A-B and B-A blocks).

    Args:
        pae_matrix: N×N matrix where N = len_a + len_b.
        len_a: Number of residues in chain A.
        len_b: Number of residues in chain B.

    Returns:
        Mean PAE for all A↔B cross-chain pairs, or None if dimensions mismatch.
    """
    n = len_a + len_b
    if len(pae_matrix) != n or any(len(row) != n for row in pae_matrix):
        logger.warning(
            "PAE matrix dimension mismatch: expected %dx%d, got %dx%d",
            n,
            n,
            len(pae_matrix),
            len(pae_matrix[0]) if pae_matrix else 0,
        )
        return None

    values: list[float] = []
    # A -> B block
    for i in range(len_a):
        for j in range(len_a, n):
            values.append(pae_matrix[i][j])
    # B -> A block
    for i in range(len_a, n):
        for j in range(len_a):
            values.append(pae_matrix[i][j])

    if not values:
        return None
    return sum(values) / len(values)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def parse_complex_interface(
    pdb_path: str,
    *,
    pae_json_path: str | None = None,
    chain_mapping: dict[str, str] | None = None,
    target_chain_id: str = "A",
    peptide_chain_id: str = "B",
    distance_cutoff: float = DEFAULT_DISTANCE_CUTOFF,
) -> dict[str, Any]:
    """Parse a ColabFold complex PDB and optional PAE JSON to extract interface features.

    This function does NOT compute pDockQ, delta_G, or docking_score.
    It only extracts geometry and confidence metrics already present in the
    ColabFold output files.

    Args:
        pdb_path: Path to the complex PDB file.
        pae_json_path: Optional path to ColabFold PAE JSON.
        chain_mapping: Optional dict mapping chain IDs to semantic names,
            e.g. {"A": "target", "B": "peptide"}.
        target_chain_id: Chain ID for the target protein.
        peptide_chain_id: Chain ID for the peptide.
        distance_cutoff: Distance threshold in Ångström for interface contacts.

    Returns:
        Structured dict with interface analysis results.
    """
    pdb_file = Path(pdb_path)
    if not pdb_file.exists():
        raise ComplexInterfaceError(f"PDB file not found: {pdb_path}")

    atoms = _parse_pdb_atoms(pdb_path)
    if not atoms:
        raise ComplexInterfaceError(f"No ATOM records found in {pdb_path}")

    residues = _group_atoms_by_residue(atoms)

    # Separate residues by chain
    residues_a = [r for k, r in residues.items() if r.chain_id == target_chain_id]
    residues_b = [r for k, r in residues.items() if r.chain_id == peptide_chain_id]

    has_chain_a = len(residues_a) > 0
    has_chain_b = len(residues_b) > 0
    chain_a_atom_count = sum(len(r.atoms) for r in residues_a)
    chain_b_atom_count = sum(len(r.atoms) for r in residues_b)

    # Interface analysis
    interface_contact_count: int | None = None
    interface_residue_count_a: int | None = None
    interface_residue_count_b: int | None = None
    interface_residue_plddt_mean: float | None = None

    if has_chain_a and has_chain_b:
        interface_a, interface_b, contact_count = _find_interface_residues(
            residues_a, residues_b, cutoff=distance_cutoff
        )
        interface_contact_count = contact_count
        interface_residue_count_a = len(interface_a)
        interface_residue_count_b = len(interface_b)

        # Compute mean pLDDT of interface residues
        interface_residues = []
        for key in interface_a:
            if key in residues:
                interface_residues.append(residues[key])
        for key in interface_b:
            if key in residues:
                interface_residues.append(residues[key])

        if interface_residues:
            b_factors = []
            for res in interface_residues:
                mean_b = res.mean_b_factor()
                if mean_b is not None:
                    b_factors.append(mean_b)
            if b_factors:
                interface_residue_plddt_mean = sum(b_factors) / len(b_factors)

    # PAE cross-chain mean
    pae_interface_mean: float | None = None
    if pae_json_path and Path(pae_json_path).exists():
        try:
            pae_matrix = _load_pae_matrix(pae_json_path)
            pae_interface_mean = _compute_cross_chain_pae_mean(
                pae_matrix,
                len_a=len(residues_a),
                len_b=len(residues_b),
            )
        except (json.JSONDecodeError, ComplexInterfaceError) as exc:
            logger.warning("Failed to parse PAE JSON: %s", exc)

    mapping = chain_mapping or {
        target_chain_id: "target",
        peptide_chain_id: "peptide",
    }

    return {
        "interface_parser_ran": True,
        "source": "colabfold_complex_smoke",
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "metrics_are_real": True,
        "chain_mapping": mapping,
        "structure_summary": {
            "has_chain_A": has_chain_a,
            "has_chain_B": has_chain_b,
            "chain_A_atom_count": chain_a_atom_count,
            "chain_B_atom_count": chain_b_atom_count,
        },
        "interface_summary": {
            "distance_cutoff_angstrom": distance_cutoff,
            "interface_contact_count": interface_contact_count,
            "interface_residue_count_A": interface_residue_count_a,
            "interface_residue_count_B": interface_residue_count_b,
            "interface_residue_plddt_mean": interface_residue_plddt_mean,
            "pae_interface_mean": pae_interface_mean,
        },
        "ready_for_pdockq": False,
        "reason_pdockq_not_computed": (
            "P6i only parses interface features; pDockQ calculation is deferred to P6j."
        ),
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
    }
