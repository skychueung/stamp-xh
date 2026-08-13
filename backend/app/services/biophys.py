"""
STAMP Platform — Biophysics Calculation Service

Pure functions for sequence-level biophysical properties:
  - GRAVY (Kyte-Doolittle)
  - net_charge (pH 7.0 with explicit pKa values)
  - pI (binary search pH 0–14)
  - Cys count / disulfide risk

All functions are pure and operate on uppercase amino acid strings.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Valid amino acids
# ---------------------------------------------------------------------------

VALID_AA: Final[set[str]] = set("ACDEFGHIKLMNPQRSTVWY")

# ---------------------------------------------------------------------------
# Kyte-Doolittle hydropathy index
# ---------------------------------------------------------------------------

KD_HYDROPATHY: Final[dict[str, float]] = {
    "I": 4.5, "V": 4.2, "L": 3.8, "F": 2.8, "C": 2.5,
    "M": 1.9, "A": 1.8, "G": -0.4, "T": -0.7, "S": -0.8,
    "W": -0.9, "Y": -1.3, "P": -1.6, "H": -3.2, "E": -3.5,
    "Q": -3.5, "D": -3.5, "N": -3.5, "K": -3.9, "R": -4.5,
}

# ---------------------------------------------------------------------------
# pKa values (pH 7.0 net charge and pI computation)
# ---------------------------------------------------------------------------

PKA_NTERM: Final[float] = 9.69
PKA_CTERM: Final[float] = 2.34

PKA_SIDECHAIN: Final[dict[str, float]] = {
    "D": 3.86,   # Asp
    "E": 4.25,   # Glu
    "C": 8.33,   # Cys
    "Y": 10.07,  # Tyr
    "H": 6.00,   # His
    "K": 10.53,  # Lys
    "R": 12.48,  # Arg
}

# Positively charged at neutral pH (besides N-term)
BASIC_RESIDUES: Final[set[str]] = {"K", "R", "H"}
# Negatively charged at neutral pH (besides C-term)
ACIDIC_RESIDUES: Final[set[str]] = {"D", "E", "C", "Y"}


# ---------------------------------------------------------------------------
# Sequence validation
# ---------------------------------------------------------------------------


def validate_sequence(sequence: str) -> str:
    """Return uppercase stripped sequence or raise ValueError for illegal chars."""
    seq = sequence.upper().strip()
    if not seq:
        raise ValueError("sequence must not be empty")
    invalid = [c for c in seq if c not in VALID_AA]
    if invalid:
        unique = sorted(set(invalid))
        raise ValueError(
            f"Sequence contains illegal characters: {', '.join(unique)}. "
            f"Only standard amino acids allowed."
        )
    return seq


# ---------------------------------------------------------------------------
# GRAVY — Kyte-Doolittle
# ---------------------------------------------------------------------------


def calculate_gravy(sequence: str) -> float:
    """Grand Average of Hydropathicity using Kyte-Doolittle index.

    Positive = hydrophobic; negative = hydrophilic.
    """
    seq = sequence.upper().strip()
    if not seq:
        return 0.0
    total = sum(KD_HYDROPATHY.get(aa, 0.0) for aa in seq)
    return round(total / len(seq), 3)


# ---------------------------------------------------------------------------
# Net charge at pH 7.0
# ---------------------------------------------------------------------------


def calculate_net_charge(sequence: str, ph: float = 7.0) -> float:
    """Net charge at given pH using Henderson-Hasselbalch with explicit pKa values.

    pH defaults to 7.0 per the P0 specification.
    """
    seq = sequence.upper().strip()
    if not seq:
        return 0.0

    charge = 0.0

    # N-terminus (positive when protonated)
    charge += 1.0 / (1.0 + 10 ** (ph - PKA_NTERM))

    # C-terminus (negative when deprotonated)
    charge -= 1.0 / (1.0 + 10 ** (PKA_CTERM - ph))

    # Side chains
    for aa in seq:
        pka = PKA_SIDECHAIN.get(aa)
        if pka is None:
            continue
        if aa in BASIC_RESIDUES:
            # Basic: positive when protonated (pH < pKa)
            charge += 1.0 / (1.0 + 10 ** (ph - pka))
        elif aa in ACIDIC_RESIDUES:
            # Acidic / Cys/Tyr: negative when deprotonated (pH > pKa)
            charge -= 1.0 / (1.0 + 10 ** (pka - ph))

    return round(charge, 3)


# ---------------------------------------------------------------------------
# pI — binary search pH 0–14
# ---------------------------------------------------------------------------


def calculate_pi(sequence: str) -> float:
    """Isoelectric point via binary search in [0, 14].

    Finds pH where net_charge ≈ 0 within 1e-6 tolerance.
    """
    seq = sequence.upper().strip()
    if not seq:
        return 7.0

    lo, hi = 0.0, 14.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        nc = calculate_net_charge(seq, ph=mid)
        if abs(nc) < 1e-6:
            return round(mid, 2)
        if nc > 0:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2.0, 2)


# ---------------------------------------------------------------------------
# Cysteine / Disulfide risk
# ---------------------------------------------------------------------------


def count_cys(sequence: str) -> int:
    """Count cysteine residues."""
    return sequence.upper().count("C")


def disulfide_risk(cys_count: int) -> str:
    """Classify disulfide risk based on cysteine count.

    0 Cys → "none"
    1 Cys → "single_cys"
    >=2 Cys → "potential_disulfide"
    """
    if cys_count == 0:
        return "none"
    if cys_count == 1:
        return "single_cys"
    return "potential_disulfide"


# ---------------------------------------------------------------------------
# Hydrophobicity class
# ---------------------------------------------------------------------------


def hydrophobicity_class(gravy: float) -> str:
    """Classify based on GRAVY score."""
    if gravy > 0.5:
        return "hydrophobic"
    if gravy < -0.5:
        return "hydrophilic"
    return "neutral"
