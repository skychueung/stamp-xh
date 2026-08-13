"""STAMP Platform — pDockQ Readiness Audit (v0.10-P6f).

Audits whether a structure prediction result has the necessary inputs for
pDockQ (or comparable interface-quality) computation.

pDockQ requires a protein-protein complex with at least two chains and
interface-level geometric/contact features. Current LocalColabFold monomer
runs do NOT provide these inputs.

This module:
  1. Evaluates available structure prediction outputs.
  2. Lists missing inputs required for pDockQ.
  3. Explicitly rejects any fallback/mock/default pDockQ values.
  4. Designs the future data contract for interface_quality metrics.

DO NOT use this module to compute or fabricate pDockQ values.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required inputs for pDockQ / interface-quality scoring
# ---------------------------------------------------------------------------

REQUIRED_INTERFACE_INPUTS = [
    "complex_pdb_or_cif",
    "chain_pair_interface_contacts",
    "interface_residue_plddt",
    "complex_chain_mapping",
    "pae_matrix_or_interface_confidence",
    "binding_interface_geometry",
]

OPTIONAL_BUT_RECOMMENDED_INPUTS = [
    "interface_sasa",
    "hbond_count_at_interface",
    "salt_bridge_count_at_interface",
    "hydrophobic_contact_count",
]

# ---------------------------------------------------------------------------
# Audit function
# ---------------------------------------------------------------------------


def audit_pdockq_readiness(structure_prediction_metrics: dict[str, Any]) -> dict[str, Any]:
    """Audit whether structure prediction metrics are ready for pDockQ.

    Args:
        structure_prediction_metrics: The dict written to
            stamp_candidate.metrics["structure_prediction"].

    Returns:
        Audit report dict with keys:
          - pdockq_ready (bool): False for monomer / incomplete inputs.
          - reason (str): Human-readable explanation.
          - available_inputs (list[str]): Inputs that are present.
          - missing_inputs (list[str]): Inputs needed for pDockQ.
          - recommendation (str): Actionable recommendation.
          - is_monomer (bool): True if the run appears to be monomer.
          - has_complex_structure (bool): True if a multi-chain PDB/CIF exists.
          - forbidden_metrics_detected (dict[str, Any]): Any non-null forbidden
            metrics found in the input (should be empty for clean data).
    """
    available: list[str] = []
    missing: list[str] = []
    forbidden_detected: dict[str, Any] = {}

    # 1. Check for forbidden metrics that should NEVER be present
    forbidden = structure_prediction_metrics.get("forbidden_metrics", {})
    for key in ("pDockQ", "delta_G", "docking_score"):
        val = forbidden.get(key) if isinstance(forbidden, dict) else None
        if val is not None:
            forbidden_detected[key] = val

    # Also check top-level (should not happen, but defensive)
    for key in ("pDockQ", "delta_G", "docking_score"):
        if key in structure_prediction_metrics and structure_prediction_metrics[key] is not None:
            forbidden_detected[key] = structure_prediction_metrics[key]

    # 2. Determine if this is a monomer run
    iptm = structure_prediction_metrics.get("iptm")
    mean_plddt = structure_prediction_metrics.get("mean_plddt")
    ptm = structure_prediction_metrics.get("ptm")

    # Monomer heuristic: iptm is null AND ptm is present (AlphaFold2-ptm model)
    is_monomer = iptm is None and ptm is not None

    # 3. Check available structure-level inputs
    if mean_plddt is not None and isinstance(mean_plddt, (int, float)):
        available.append("mean_plddt")
    if ptm is not None:
        available.append("ptm")
    if iptm is not None:
        available.append("iptm")

    structure_file = structure_prediction_metrics.get("structure_file")
    has_pdb = bool(structure_file) and str(structure_file).endswith(".pdb")
    has_cif = bool(structure_file) and str(structure_file).endswith(".cif")

    if has_pdb or has_cif:
        available.append("complex_pdb_or_cif")
    else:
        missing.append("complex_pdb_or_cif")

    # 4. Check for interface-level inputs (none are present in current outputs)
    for key in REQUIRED_INTERFACE_INPUTS[1:]:  # skip complex_pdb_or_cif already checked
        missing.append(key)

    # 5. Determine readiness
    has_complex_structure = not is_monomer and (has_pdb or has_cif)
    pdockq_ready = has_complex_structure and len(missing) == 0

    if forbidden_detected:
        reason = (
            "Forbidden metrics detected in structure_prediction data: "
            f"{list(forbidden_detected.keys())}. "
            "pDockQ cannot be computed from fabricated or premature values."
        )
    elif is_monomer:
        reason = (
            "Current structure prediction is a monomer run (iptm is null, ptm is present). "
            "pDockQ requires a multi-chain protein-peptide complex with interface contacts. "
            "Monomer pLDDT and pTM are global structure-quality metrics, not interface-quality metrics."
        )
    elif not has_complex_structure:
        reason = (
            "No multi-chain complex structure file (PDB/CIF) is available. "
            "pDockQ requires a parsed complex with at least two chains."
        )
    else:
        reason = (
            "Multi-chain complex structure is available, but interface-level features "
            "(contacts, geometry, chain mapping, PAE matrix) are missing. "
            "These must be extracted from the complex before pDockQ can be computed."
        )

    recommendation = (
        "Do not compute or display pDockQ until real interface-level features are parsed "
        "from a multi-chain protein-peptide complex. "
        "Current metrics (mean_plddt, ptm, iptm) should be displayed under 'Structure Prediction' only. "
        "When interface-quality tools are integrated, create a separate 'Interface Quality' section."
    )

    return {
        "pdockq_ready": pdockq_ready,
        "reason": reason,
        "available_inputs": available,
        "missing_inputs": missing,
        "recommendation": recommendation,
        "is_monomer": is_monomer,
        "has_complex_structure": has_complex_structure,
        "forbidden_metrics_detected": forbidden_detected,
    }


# ---------------------------------------------------------------------------
# Future data contract design (document-only, not activated in P6f)
# ---------------------------------------------------------------------------

INTERFACE_QUALITY_CONTRACT: dict[str, Any] = {
    "source": "future_pdockq_postprocess",
    "metrics_are_real": True,
    "pdockq": None,
    "interface_contacts_count": None,
    "interface_residue_count": None,
    "chain_pair": None,
    "pae_interface_mean": None,
    "validation_status": "COMPUTATIONAL_INTERFACE_PREDICTION_ONLY",
    "not_experimentally_validated": True,
    "provenance": {
        "input_pdb_or_cif": None,
        "parser_version": None,
        "algorithm": None,
    },
}


def get_interface_quality_contract() -> dict[str, Any]:
    """Return the future data contract for interface-quality metrics.

    This is a design document. It is NOT written to the database in P6f.
    """
    return dict(INTERFACE_QUALITY_CONTRACT)
