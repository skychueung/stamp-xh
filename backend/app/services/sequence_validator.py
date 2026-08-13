"""
STAMP Platform — Sequence Validation Service

Validates amino acid sequences, checks for illegal characters, and
computes lightweight sequence properties (length, charge from residue
counts).  Heavy biophysical calculations (pI, GRAVY, hydrophobicity
fraction) are intentionally deferred to a future pipeline.
"""

from __future__ import annotations

import re
from typing import Final

from app.core.exceptions import InvalidSequenceError

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Standard 20 amino acids + common non-canonical (U=Sec, O=Pyl)
VALID_AA: Final[set[str]] = set(
    "ACDEFGHIKLMNPQRSTVWY"
)

# Charged residues at pH ~7.4
POSITIVE: Final[set[str]] = {"K", "R", "H"}
NEGATIVE: Final[set[str]] = {"D", "E"}

# Hydrophobic residues (for future hydrophobicity_fraction)
HYDROPHOBIC: Final[set[str]] = {"A", "V", "I", "L", "M", "F", "W", "Y", "G", "P"}

LINKER_SEQUENCE: Final[str] = "EAAAK"
LINKER_LENGTH: Final[int] = 5

TERMINAL_MOD: Final[str] = "-NH2"


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------


def validate_sequence(sequence: str, context: str = "sequence") -> str:
    """Check that *sequence* contains only valid amino acid characters.

    Args:
        sequence: Amino acid string (uppercase recommended).
        context: Human-readable context for error messages.

    Returns:
        The cleaned (uppercase, stripped) sequence.

    Raises:
        InvalidSequenceError: If illegal characters are found.
    """
    seq = sequence.upper().strip()
    if not seq:
        raise InvalidSequenceError(f"{context} is empty.")
    illegal = [ch for ch in seq if ch not in VALID_AA]
    if illegal:
        raise InvalidSequenceError(
            f"{context} contains illegal character(s): {set(illegal)}"
        )
    return seq


def clean_sequence(raw: str) -> tuple[str, str | None, str | None]:
    """Remove non-amino-acid characters and return metadata.

    Args:
        raw: Raw sequence potentially containing illegal chars.

    Returns:
        Tuple of (clean_sequence, illegal_char_found, illegal_char_position).
        The position is a comma-separated 1-based index string.
    """
    raw_upper = raw.upper().strip()
    illegal_chars: list[str] = []
    illegal_positions: list[int] = []
    cleaned_chars: list[str] = []

    for idx, ch in enumerate(raw_upper, start=1):
        if ch in VALID_AA:
            cleaned_chars.append(ch)
        else:
            illegal_chars.append(ch)
            illegal_positions.append(idx)

    clean = "".join(cleaned_chars)
    found = "".join(set(illegal_chars)) if illegal_chars else None
    pos = ",".join(str(p) for p in illegal_positions) if illegal_positions else None
    return clean, found, pos


def compute_net_charge(sequence: str) -> float:
    """Compute approximate net charge at physiological pH.

    Uses a simple residue-count heuristic:
        +1 for each K, R
        +0.5 for each H (partial protonation)
        -1 for each D, E

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        Approximate net charge.
    """
    seq = sequence.upper()
    positive = sum(seq.count(aa) for aa in POSITIVE)
    negative = sum(seq.count(aa) for aa in NEGATIVE)
    # Histidine contributes +0.5 on average at pH 7.4
    his = seq.count("H")
    return positive + 0.5 * his - negative


def compute_gravy(sequence: str) -> float:
    """Compute Grand Average of Hydropathicity (GRAVY) using the
    Kyte-Doolittle scale.

    This is a lightweight local calculation; the full biophysical
    pipeline may eventually replace it.

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        GRAVY score (more positive = more hydrophobic).
    """
    # Kyte-Doolittle hydropathy index (simplified)
    kd: dict[str, float] = {
        "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
        "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "S": -0.8,
        "W": -0.9, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
        "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5,
    }
    seq = sequence.upper()
    if not seq:
        return 0.0
    total = sum(kd.get(aa, 0.0) for aa in seq)
    return round(total / len(seq), 3)


def assemble_stamp_sequence(
    tp_sequence: str,
    amp_sequence: str,
    linker: str = LINKER_SEQUENCE,
    terminal_mod: str = TERMINAL_MOD,
) -> tuple[str, str]:
    """Concatenate TP + Linker + AMP and produce both raw and display forms.

    Args:
        tp_sequence: Clean targeting peptide sequence.
        amp_sequence: Clean AMP sequence.
        linker: Linker sequence (default ``EAAAK``).
        terminal_mod: C-terminal modification (default ``-NH2``).

    Returns:
        Tuple of (raw_full_sequence, display_full_sequence).
    """
    tp = tp_sequence.upper().strip()
    amp = amp_sequence.upper().strip()
    raw = f"{tp}{linker}{amp}"
    display = f"{tp}-{linker}-{amp}{terminal_mod}"
    return raw, display
