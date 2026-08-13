"""STAMP Platform — Complex Prediction Input Preparation (v0.10-P6g).

Generates multi-chain FASTA and prediction manifests for
target-protein + candidate-peptide complex structure prediction
(AlphaFold-Multimer / ColabFold complex mode).

Current stage: INPUT_PREPARATION_ONLY.
No real AlphaFold-Multimer execution, no pDockQ, no delta_G, no docking_score.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STANDARD_AA = set("ACDEFGHIKLMNPQRSTVWY")
FORBIDDEN_AA = set("UOBZJX")

TARGET_MIN_LEN = 30
TARGET_MAX_LEN = 5000
PEPTIDE_MIN_LEN = 5
PEPTIDE_MAX_LEN = 80

REQUIRED_VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
REQUIRED_PREDICTION_STATUS = "COMPUTATIONAL_COMPLEX_PREDICTION_INPUT_ONLY"


class ComplexInputError(ValueError):
    """Raised when complex prediction input fails validation."""

    pass


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_protein_sequence(sequence: str) -> None:
    """Validate a target protein sequence.

    Rules:
      - Must be non-empty.
      - Only standard 20 amino acids allowed.
      - No U, O, B, Z, J, X.
      - Length must be within TARGET_MIN_LEN..TARGET_MAX_LEN.
    """
    if not sequence:
        raise ComplexInputError("Target protein sequence is empty")

    seq = sequence.upper().strip()
    if not seq:
        raise ComplexInputError("Target protein sequence is empty after stripping")

    forbidden_found = [aa for aa in seq if aa in FORBIDDEN_AA]
    if forbidden_found:
        raise ComplexInputError(
            f"Target sequence contains forbidden residues: {set(forbidden_found)}"
        )

    non_standard = [aa for aa in seq if aa not in STANDARD_AA]
    if non_standard:
        raise ComplexInputError(
            f"Target sequence contains non-standard residues: {set(non_standard)}"
        )

    if len(seq) < TARGET_MIN_LEN:
        raise ComplexInputError(
            f"Target sequence too short: {len(seq)} aa (minimum {TARGET_MIN_LEN})"
        )
    if len(seq) > TARGET_MAX_LEN:
        raise ComplexInputError(
            f"Target sequence too long: {len(seq)} aa (maximum {TARGET_MAX_LEN})"
        )


def validate_peptide_sequence(sequence: str) -> None:
    """Validate a candidate peptide sequence.

    Rules:
      - Must be non-empty.
      - Only standard 20 amino acids allowed.
      - No U, O, B, Z, J, X.
      - Length must be within PEPTIDE_MIN_LEN..PEPTIDE_MAX_LEN.
    """
    if not sequence:
        raise ComplexInputError("Peptide sequence is empty")

    seq = sequence.upper().strip()
    if not seq:
        raise ComplexInputError("Peptide sequence is empty after stripping")

    forbidden_found = [aa for aa in seq if aa in FORBIDDEN_AA]
    if forbidden_found:
        raise ComplexInputError(
            f"Peptide sequence contains forbidden residues: {set(forbidden_found)}"
        )

    non_standard = [aa for aa in seq if aa not in STANDARD_AA]
    if non_standard:
        raise ComplexInputError(
            f"Peptide sequence contains non-standard residues: {set(non_standard)}"
        )

    if len(seq) < PEPTIDE_MIN_LEN:
        raise ComplexInputError(
            f"Peptide sequence too short: {len(seq)} aa (minimum {PEPTIDE_MIN_LEN})"
        )
    if len(seq) > PEPTIDE_MAX_LEN:
        raise ComplexInputError(
            f"Peptide sequence too long: {len(seq)} aa (maximum {PEPTIDE_MAX_LEN})"
        )


# ---------------------------------------------------------------------------
# FASTA generation
# ---------------------------------------------------------------------------


def build_multimer_fasta(
    target_sequence: str,
    peptide_sequence: str,
    *,
    target_chain_id: str = "A",
    peptide_chain_id: str = "B",
    target_name: str = "target",
    peptide_name: str = "candidate_peptide",
) -> str:
    """Generate a ColabFold-compatible multimer FASTA string for complex prediction.

    ColabFold interprets a single FASTA record with ':' in the sequence line as a
    complex (heteromer). Two separate records would be treated as independent queries.
    """
    validate_protein_sequence(target_sequence)
    validate_peptide_sequence(peptide_sequence)

    target_seq = target_sequence.upper().strip()
    peptide_seq = peptide_sequence.upper().strip()

    # Validate chain IDs are simple single characters (A-Z)
    if not re.fullmatch(r"[A-Z]", target_chain_id):
        raise ComplexInputError(
            f"target_chain_id must be a single uppercase letter A-Z, got {target_chain_id!r}"
        )
    if not re.fullmatch(r"[A-Z]", peptide_chain_id):
        raise ComplexInputError(
            f"peptide_chain_id must be a single uppercase letter A-Z, got {peptide_chain_id!r}"
        )
    if target_chain_id == peptide_chain_id:
        raise ComplexInputError(
            f"target_chain_id and peptide_chain_id must differ, both are {target_chain_id!r}"
        )

    header = f"{target_name}_chain_{target_chain_id}|{peptide_name}_chain_{peptide_chain_id}"
    return f">{header}\n{target_seq}:{peptide_seq}\n"


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------


def build_complex_prediction_manifest(
    target_sequence: str,
    peptide_sequence: str,
    *,
    target_chain_id: str = "A",
    peptide_chain_id: str = "B",
    target_name: str = "target",
    peptide_name: str = "candidate_peptide",
    candidate_id: str | None = None,
    job_id: str | None = None,
) -> dict[str, Any]:
    """Build a manifest dict describing the complex prediction input.

    This manifest is purely descriptive. It does NOT contain pDockQ, delta_G,
    or docking_score. It explicitly marks the stage as input preparation only.
    """
    validate_protein_sequence(target_sequence)
    validate_peptide_sequence(peptide_sequence)

    fasta_content = build_multimer_fasta(
        target_sequence=target_sequence,
        peptide_sequence=peptide_sequence,
        target_chain_id=target_chain_id,
        peptide_chain_id=peptide_chain_id,
        target_name=target_name,
        peptide_name=peptide_name,
    )

    return {
        "job_type": "complex_structure_prediction",
        "stage": "input_preparation_only",
        "prediction_type": "complex_structure_prediction_input_only",
        "validation_status": REQUIRED_VALIDATION_STATUS,
        "prediction_status": REQUIRED_PREDICTION_STATUS,
        "metrics_are_real": False,
        "target": {
            "name": target_name,
            "chain_id": target_chain_id,
            "sequence_length": len(target_sequence.upper().strip()),
            "sequence": target_sequence.upper().strip(),
        },
        "peptide": {
            "name": peptide_name,
            "chain_id": peptide_chain_id,
            "sequence_length": len(peptide_sequence.upper().strip()),
            "sequence": peptide_sequence.upper().strip(),
        },
        "chain_mapping": {
            target_chain_id: "target",
            peptide_chain_id: "peptide",
        },
        "fasta_content": fasta_content,
        "forbidden_metrics": {
            "pDockQ": None,
            "delta_G": None,
            "docking_score": None,
        },
        "candidate_id": candidate_id,
        "source_job_id": job_id,
    }
