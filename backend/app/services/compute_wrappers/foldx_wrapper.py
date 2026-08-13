"""FoldX wrapper — parses real FoldX AnalyseComplex output (v1.2-lab-production-fast).

Reads .fxout files and returns interaction energy terms.
No fabricated values. All outputs marked COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def parse_foldx_artifact(artifact_path: str) -> dict[str, Any]:
    """Parse a FoldX AnalyseComplex .fxout file.

    Args:
        artifact_path: Path to .fxout file.

    Returns:
        Dict with status, energy terms, and scientific boundary.
    """
    path = Path(artifact_path)
    if not path.exists():
        return {
            "status": "BLOCKED",
            "error_code": "ARTIFACT_NOT_FOUND",
            "message": f"FoldX artifact not found: {artifact_path}",
        }

    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "status": "FAILED",
            "error_code": "READ_ERROR",
            "message": str(exc),
        }

    # Find the data line (starts with /home or similar PDB path)
    data_line = None
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("Pdb") and not stripped.startswith("-") and "/" in stripped:
            data_line = stripped
            break

    if data_line is None:
        return {
            "status": "FAILED",
            "error_code": "NO_DATA_LINE",
            "message": "Could not find data line in FoldX output.",
        }

    parts = data_line.split("\t")
    # Expected columns after header:
    # Pdb, Group1, Group2, IntraclashesGroup1, IntraclashesGroup2,
    # Interaction Energy, Backbone Hbond, Sidechain Hbond, Van der Waals,
    # Electrostatics, Solvation Polar, Solvation Hydrophobic, VdW clashes, ...
    if len(parts) < 13:
        return {
            "status": "FAILED",
            "error_code": "INSUFFICIENT_COLUMNS",
            "message": f"Expected >=13 columns, got {len(parts)}",
        }

    try:
        interaction_energy = float(parts[5])
        backbone_hbond = float(parts[6])
        sidechain_hbond = float(parts[7])
        vdw = float(parts[8])
        electrostatics = float(parts[9])
        solvation_polar = float(parts[10])
        solvation_hydrophobic = float(parts[11])
        vdw_clashes = float(parts[12])
    except ValueError as exc:
        return {
            "status": "FAILED",
            "error_code": "PARSE_ERROR",
            "message": str(exc),
        }

    return {
        "status": "SUCCEEDED",
        "run_type": "PILOT",
        "prediction_status": "COMPUTATIONAL_INTERACTION_ENERGY_ESTIMATE_ONLY",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "energy_terms": {
            "interaction_energy_kcal_mol": interaction_energy,
            "backbone_hbond": backbone_hbond,
            "sidechain_hbond": sidechain_hbond,
            "van_der_waals": vdw,
            "electrostatics": electrostatics,
            "solvation_polar": solvation_polar,
            "solvation_hydrophobic": solvation_hydrophobic,
            "vdw_clashes": vdw_clashes,
        },
        "interpretation": (
            "Unfavorable interaction energy (positive value suggests poorly relaxed model)"
            if interaction_energy > 0
            else "Favorable interaction energy"
        ),
        "scientific_boundary": {
            "computational_only": True,
            "not_docking_score": True,
            "not_mmgbsa_delta_g": True,
        },
    }
