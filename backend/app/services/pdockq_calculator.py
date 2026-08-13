"""STAMP Platform — pDockQ Calculator (v0.10-P6j).

Computes pDockQ from real interface features parsed by P6i.

Formula (Bryant et al., 2022):
    x = average_interface_plddt * ln(number_of_interface_contacts)
    pDockQ = L / (1 + exp(-k * (x - x0))) + b

Parameters:
    L = 0.724
    x0 = 152.611
    k = 0.052
    b = 0.018

Current stage: INTERFACE_QUALITY_PREDICTION_ONLY.
NO delta_G, NO docking_score.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

L_PARAM = 0.724
X0_PARAM = 152.611
K_PARAM = 0.052
B_PARAM = 0.018

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_INTERFACE_QUALITY_PREDICTION_ONLY"


class PDockQError(ValueError):
    """Raised when pDockQ calculation cannot proceed."""

    pass


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------


def calculate_pdockq(
    interface_contact_count: int | float,
    interface_residue_plddt_mean: float,
) -> float:
    """Compute pDockQ from interface contact count and mean interface pLDDT.

    Args:
        interface_contact_count: Number of residue-residue contacts at the interface.
        interface_residue_plddt_mean: Mean pLDDT of interface residues.

    Returns:
        pDockQ score in the range [0, 1].

    Raises:
        PDockQError: If inputs are invalid (non-positive contact count,
            missing pLDDT, out-of-range pLDDT).
    """
    # Validate contact count
    if interface_contact_count is None:
        raise PDockQError("interface_contact_count is required, got None")

    try:
        contacts = float(interface_contact_count)
    except (TypeError, ValueError) as exc:
        raise PDockQError(
            f"interface_contact_count must be numeric, got {interface_contact_count!r}"
        ) from exc

    if contacts <= 0:
        raise PDockQError(
            f"interface_contact_count must be > 0, got {contacts}"
        )

    # Validate pLDDT
    if interface_residue_plddt_mean is None:
        raise PDockQError("interface_residue_plddt_mean is required, got None")

    try:
        plddt = float(interface_residue_plddt_mean)
    except (TypeError, ValueError) as exc:
        raise PDockQError(
            f"interface_residue_plddt_mean must be numeric, got {interface_residue_plddt_mean!r}"
        ) from exc

    if plddt < 0:
        raise PDockQError(
            f"interface_residue_plddt_mean must be >= 0, got {plddt}"
        )
    if plddt > 100:
        raise PDockQError(
            f"interface_residue_plddt_mean must be <= 100, got {plddt}"
        )

    # Compute x
    x = plddt * math.log(contacts)

    # Sigmoid
    pdockq = L_PARAM / (1.0 + math.exp(-K_PARAM * (x - X0_PARAM))) + B_PARAM

    # Clamp to [0, 1] to guard against numerical edge cases
    pdockq = max(0.0, min(1.0, pdockq))

    return pdockq


# ---------------------------------------------------------------------------
# Interface quality builder
# ---------------------------------------------------------------------------


def build_interface_quality(
    parser_result: dict[str, Any],
    *,
    input_complex_structure_file: str = "complex_unrelaxed.pdb",
    interface_parser_commit: str = "605031f",
) -> dict[str, Any]:
    """Build a complete interface_quality metrics dict from P6i parser output.

    Computes pDockQ and assembles provenance, input features, and
    scientific-integrity metadata.

    Args:
        parser_result: Output dict from parse_complex_interface().
        input_complex_structure_file: Path to the input complex PDB.
        interface_parser_commit: Git commit hash of the interface parser.

    Returns:
        Structured interface_quality dict ready for persistence.

    Raises:
        PDockQError: If required fields are missing or invalid.
    """
    if not parser_result.get("interface_parser_ran"):
        raise PDockQError("interface_parser_ran is false; cannot compute pDockQ")

    iface_summary = parser_result.get("interface_summary", {})
    contact_count = iface_summary.get("interface_contact_count")
    plddt_mean = iface_summary.get("interface_residue_plddt_mean")

    pdockq = calculate_pdockq(contact_count, plddt_mean)

    # Compute x for provenance
    x_value = plddt_mean * math.log(contact_count) if contact_count and plddt_mean is not None else None

    return {
        "source": "colabfold_complex_interface_parser",
        "algorithm": "pDockQ",
        "algorithm_version": "original_sigmoid_bryant_2022",
        "metrics_are_real": True,
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "chain_mapping": parser_result.get("chain_mapping", {"A": "target", "B": "peptide"}),
        "input_features": {
            "interface_contact_count": contact_count,
            "interface_residue_plddt_mean": plddt_mean,
            "x_value": x_value,
            "distance_cutoff_angstrom": iface_summary.get("distance_cutoff_angstrom"),
        },
        "pdockq": pdockq,
        "pae_interface_mean": iface_summary.get("pae_interface_mean"),
        "interface_residue_count_A": iface_summary.get("interface_residue_count_A"),
        "interface_residue_count_B": iface_summary.get("interface_residue_count_B"),
        "provenance": {
            "input_complex_structure_file": input_complex_structure_file,
            "interface_parser_commit": interface_parser_commit,
            "calculator_formula": "pDockQ = L/(1+exp(-k*(x-x0)))+b",
            "parameters": {
                "L": L_PARAM,
                "x0": X0_PARAM,
                "k": K_PARAM,
                "b": B_PARAM,
            },
        },
        "forbidden_metrics": {
            "delta_G": None,
            "docking_score": None,
        },
    }
