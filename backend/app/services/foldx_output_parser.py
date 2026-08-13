"""STAMP Platform — FoldX Output Parser (v0.10-P6m).

Parses FoldX AnalyseComplex Interaction_*.fxout files to extract
interaction energy and component energy terms.

Current stage: FOLDX_ENERGY_QUALITY_ESTIMATE_ONLY.
NO delta_G, NO docking_score, NO MM-GBSA.
"""

from __future__ import annotations

import csv
import logging
from io import StringIO
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY"

# Thresholds for quality flags
VDW_CLASHES_HIGH_THRESHOLD = 20.0
INTERACTION_ENERGY_FAVORABLE_THRESHOLD = 0.0


class FoldXParserError(ValueError):
    """Raised when FoldX output parsing fails."""

    pass


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------


def parse_foldx_interaction_fxout(fxout_path: str) -> dict[str, Any]:
    """Parse a FoldX AnalyseComplex Interaction_*.fxout file.

    Args:
        fxout_path: Path to the Interaction_*.fxout file.

    Returns:
        Structured dict with interaction_energy, energy_terms, quality_flags,
        and raw metadata.

    Raises:
        FoldXParserError: If file not found, empty, or required fields missing.
    """
    path = Path(fxout_path)
    if not path.exists():
        raise FoldXParserError(f"FoldX fxout file not found: {fxout_path}")

    content = path.read_text(encoding="utf-8")
    if not content.strip():
        raise FoldXParserError(f"FoldX fxout file is empty: {fxout_path}")

    # Split into lines and find the tab-separated data section
    lines = content.splitlines()

    # Find the header line (starts with "Pdb\t" or contains "Interaction Energy")
    header_idx = None
    for idx, line in enumerate(lines):
        if "Interaction Energy" in line and "\t" in line:
            header_idx = idx
            break

    if header_idx is None:
        raise FoldXParserError(
            f"FoldX fxout file missing 'Interaction Energy' header: {fxout_path}"
        )

    header_line = lines[header_idx]
    data_lines = lines[header_idx + 1 :]
    data_lines = [line for line in data_lines if line.strip()]

    if not data_lines:
        raise FoldXParserError(f"FoldX fxout file has header but no data rows: {fxout_path}")

    # Parse with csv reader using tab delimiter
    reader = csv.DictReader(
        StringIO(header_line + "\n" + data_lines[0]),
        delimiter="\t",
    )
    rows = list(reader)
    if not rows:
        raise FoldXParserError(f"Failed to parse FoldX fxout data row: {fxout_path}")

    row = rows[0]

    # Required fields mapping: FoldX header -> canonical key
    field_map = {
        "Interaction Energy": "interaction_energy_kcal_mol",
        "Backbone Hbond": "backbone_hbond",
        "Sidechain Hbond": "sidechain_hbond",
        "Van der Waals": "van_der_waals",
        "Electrostatics": "electrostatics",
        "Solvation Polar": "solvation_polar",
        "Solvation Hydrophobic": "solvation_hydrophobic",
        "Van der Waals clashes": "vdw_clashes",
        "entropy sidechain": "entropy_sidechain",
        "entropy mainchain": "entropy_mainchain",
        "Entropy Complex": "entropy_complex",
    }

    energy_terms: dict[str, float | None] = {}
    for foldx_key, canonical_key in field_map.items():
        raw = row.get(foldx_key)
        if raw is None:
            raise FoldXParserError(
                f"Missing required field '{foldx_key}' in FoldX fxout: {fxout_path}"
            )
        try:
            energy_terms[canonical_key] = float(raw)
        except (TypeError, ValueError) as exc:
            raise FoldXParserError(
                f"Field '{foldx_key}' is not numeric: {raw!r}"
            ) from exc

    interaction_energy = energy_terms["interaction_energy_kcal_mol"]
    vdw_clashes = energy_terms["vdw_clashes"]

    # Build quality flags
    quality_flags = _build_quality_flags(interaction_energy, vdw_clashes)

    # Provenance / metadata from row
    pdb_path = row.get("Pdb", "")
    group1 = row.get("Group1", "")
    group2 = row.get("Group2", "")
    intraclashes1 = _safe_float(row.get("IntraclashesGroup1"))
    intraclashes2 = _safe_float(row.get("IntraclashesGroup2"))
    num_residues = _safe_float(row.get("Number of Residues"))
    interface_residues = _safe_float(row.get("Interface Residues"))
    interface_residues_clashing = _safe_float(row.get("Interface Residues Clashing"))
    interface_residues_vdw_clashing = _safe_float(row.get("Interface Residues VdW Clashing"))
    interface_residues_bb_clashing = _safe_float(row.get("Interface Residues BB Clashing"))

    return {
        "source": "foldx_analysecomplex",
        "algorithm": "FoldX AnalyseComplex",
        "algorithm_version": "FoldX 5.1",
        "metrics_are_real": True,
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "chain_mapping": {group1: "target", group2: "peptide"},
        "interaction_energy_kcal_mol": interaction_energy,
        "energy_terms": energy_terms,
        "quality_flags": quality_flags,
        "metadata": {
            "intraclashes_group1": intraclashes1,
            "intraclashes_group2": intraclashes2,
            "number_of_residues": num_residues,
            "interface_residues": interface_residues,
            "interface_residues_clashing": interface_residues_clashing,
            "interface_residues_vdw_clashing": interface_residues_vdw_clashing,
            "interface_residues_bb_clashing": interface_residues_bb_clashing,
        },
        "provenance": {
            "input_complex_pdb": pdb_path,
            "foldx_command": "RepairPDB + AnalyseComplex --analyseComplexChains=A,B",
            "foldx_executable": "/home/xh/kxc/tools/foldx/foldx_20270131",
            "interaction_fxout": str(path.name),
        },
        "forbidden_metrics": {
            "docking_score": None,
            "mmgbsa_delta_G": None,
            "experimental_delta_G": None,
        },
    }


def _build_quality_flags(
    interaction_energy: float,
    vdw_clashes: float,
) -> dict[str, Any]:
    """Build interpretive quality flags from FoldX energy values.

    These are computational interpretation markers, not experimental conclusions.
    """
    flags: dict[str, Any] = {
        "unfavorable_interaction_energy": False,
        "favorable_interaction_energy": False,
        "high_vdw_clashes": False,
        "interpretation": "",
    }

    if interaction_energy > INTERACTION_ENERGY_FAVORABLE_THRESHOLD:
        flags["unfavorable_interaction_energy"] = True
        flags["interpretation"] = (
            "Positive interaction energy suggests an unfavorable or poorly relaxed complex model. "
            "This is a computational estimate, not an experimentally validated binding affinity."
        )
    elif interaction_energy < INTERACTION_ENERGY_FAVORABLE_THRESHOLD:
        flags["favorable_interaction_energy"] = True
        flags["interpretation"] = (
            "Negative interaction energy suggests a favorable binding interface. "
            "This is a computational estimate, not an experimentally validated binding affinity."
        )
    else:
        flags["interpretation"] = (
            "Interaction energy is near zero. This is a computational estimate, "
            "not an experimentally validated binding affinity."
        )

    if vdw_clashes > VDW_CLASHES_HIGH_THRESHOLD:
        flags["high_vdw_clashes"] = True
        if flags["interpretation"]:
            flags["interpretation"] += " High VdW clashes indicate structural strain."

    return flags


def _safe_float(value: str | None) -> float | None:
    """Safely convert a string to float, returning None on failure."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
