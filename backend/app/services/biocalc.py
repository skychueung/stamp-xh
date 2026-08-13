"""
STAMP Platform — Biophysical Calculation Service

Lightweight sequence-level calculations that can be performed safely
without external binaries.  Heavy calculations (full pI, molecular
dynamics descriptors, etc.) are deferred to a future pipeline.

All functions are pure (no side effects) and operate on strings.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Residue property tables
# ---------------------------------------------------------------------------

# Kyte-Doolittle hydropathy index
KD_HYDROPATHY: Final[dict[str, float]] = {
    "I": 4.5,
    "V": 4.2,
    "L": 3.8,
    "F": 2.8,
    "C": 2.5,
    "M": 1.9,
    "A": 1.8,
    "G": -0.4,
    "T": -0.7,
    "S": -0.8,
    "W": -0.9,
    "Y": -1.3,
    "P": -1.6,
    "H": -3.2,
    "E": -3.5,
    "Q": -3.5,
    "D": -3.5,
    "N": -3.5,
    "K": -3.9,
    "R": -4.5,
}

# pKa values for Henderson-Hasselbalch pI approximation
PKA_NTERM: Final[float] = 9.69
PKA_CTERM: Final[float] = 2.34
PKA_SIDECHAIN: Final[dict[str, float]] = {
    "D": 3.86,  # Asp
    "E": 4.25,  # Glu
    "C": 8.33,  # Cys
    "Y": 10.07,  # Tyr
    "K": 10.79,  # Lys
    "R": 12.48,  # Arg
    "H": 6.0,  # His (approximate)
}

CHARGED_POSITIVE: Final[set[str]] = {"K", "R"}
CHARGED_NEGATIVE: Final[set[str]] = {"D", "E"}


def calculate_length(sequence: str) -> int:
    """Return the number of amino acid residues.

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        Residue count.
    """
    return len(sequence.strip())


def calculate_net_charge_simple(sequence: str) -> float:
    """Compute approximate net charge at pH 7.4 using simple residue counts.

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        Approximate net charge.
    """
    seq = sequence.upper().strip()
    pos = sum(seq.count(aa) for aa in CHARGED_POSITIVE) + 0.5 * seq.count("H")
    neg = sum(seq.count(aa) for aa in CHARGED_NEGATIVE)
    return pos - neg


def calculate_gravy(sequence: str) -> float:
    """Compute Grand Average of Hydropathicity (Kyte-Doolittle).

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        GRAVY score.  Positive = hydrophobic; negative = hydrophilic.
    """
    seq = sequence.upper().strip()
    if not seq:
        return 0.0
    total = sum(KD_HYDROPATHY.get(aa, 0.0) for aa in seq)
    return round(total / len(seq), 3)


def calculate_hydrophobicity_fraction(sequence: str) -> float:
    """Compute the fraction of hydrophobic residues.

    Uses a broad definition: A, V, I, L, M, F, W, Y, G, P.

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        Fraction in [0.0, 1.0].
    """
    HYDROPHOBIC: Final[set[str]] = {"A", "V", "I", "L", "M", "F", "W", "Y", "G", "P"}
    seq = sequence.upper().strip()
    if not seq:
        return 0.0
    count = sum(1 for aa in seq if aa in HYDROPHOBIC)
    return round(count / len(seq), 3)


def calculate_pi_approximate(sequence: str) -> float | None:
    """Approximate isoelectric point using Henderson-Hasselbalch.

    This is a coarse estimate sufficient for ranking; a full
    computational pI (e.g. via BioPython or IPC) will replace it later.

    Args:
        sequence: Uppercase amino acid sequence.

    Returns:
        Approximate pI, or ``None`` if the sequence is empty.
    """
    seq = sequence.upper().strip()
    if not seq:
        return None

    # Bracket search for pH where net charge ≈ 0
    def _net_at_ph(ph: float) -> float:
        charge = 0.0
        # N-terminus
        charge += 1.0 / (1.0 + 10 ** (ph - PKA_NTERM))
        # C-terminus
        charge -= 1.0 / (1.0 + 10 ** (PKA_CTERM - ph))
        # Side chains
        for aa, pka in PKA_SIDECHAIN.items():
            count = seq.count(aa)
            if count == 0:
                continue
            if aa in CHARGED_POSITIVE or aa == "H":
                # Basic residue — contributes positive charge
                charge += count / (1.0 + 10 ** (ph - pka))
            elif aa in CHARGED_NEGATIVE or aa in {"C", "Y"}:
                # Acidic residue — contributes negative charge
                charge -= count / (1.0 + 10 ** (pka - ph))
        return charge

    # Binary search between pH 2 and 12
    lo, hi = 2.0, 12.0
    for _ in range(50):
        mid = (lo + hi) / 2.0
        if _net_at_ph(mid) > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2.0, 2)
