"""
STAMP Platform — Final Ranking Service (v0.7-P1e)

Heuristic composite scoring for STAMP candidates.

IMPORTANT — SCIENTIFIC BOUNDARY:
  - This module uses ONLY biophysical properties computed directly from
    the amino-acid sequence (length, net_charge, pI, GRAVY, cys_count).
  - NO machine-learning predictions (MIC, MBC, hemolysis, toxicity).
  - NO structural modelling metrics (ipTM, pDockQ, ΔG, docking_score).
  - The composite score is a HEURISTIC weighted sum for ranking convenience
    and does NOT predict antimicrobial efficacy or binding affinity.
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Heuristic weights — explicitly labelled and version-locked
# ---------------------------------------------------------------------------

HEURISTIC_WEIGHTS_V0_7: Final[dict[str, float]] = {
    "length": 0.20,
    "net_charge": 0.25,
    "pI": 0.20,
    "GRAVY": 0.20,
    "cys_count": 0.15,
}

# Ideal values used for Gaussian-like deviation scoring
_IDEAL_LENGTH: Final[float] = 35.0
_IDEAL_NET_CHARGE_ABS: Final[float] = 5.0
_IDEAL_pI: Final[float] = 8.5
_IDEAL_GRAVY: Final[float] = -0.2

# Tolerance scales (larger = more forgiving)
_LENGTH_SCALE: Final[float] = 30.0
_CHARGE_SCALE: Final[float] = 10.0
_pI_SCALE: Final[float] = 7.5
_GRAVY_SCALE: Final[float] = 1.5

# ---------------------------------------------------------------------------
# Sub-score helpers
# ---------------------------------------------------------------------------


def _score_length(length: int) -> float:
    """Score based on deviation from ideal length (~35 aa)."""
    deviation = abs(length - _IDEAL_LENGTH) / _LENGTH_SCALE
    return max(0.0, 1.0 - deviation)


def _score_net_charge(charge: float) -> float:
    """Score based on deviation from ideal absolute net charge (~5)."""
    deviation = abs(abs(charge) - _IDEAL_NET_CHARGE_ABS) / _CHARGE_SCALE
    return max(0.0, 1.0 - deviation)


def _score_pi(pi: float) -> float:
    """Score based on deviation from ideal pI (~8.5)."""
    deviation = abs(pi - _IDEAL_pI) / _pI_SCALE
    return max(0.0, 1.0 - deviation)


def _score_gravy(gravy: float) -> float:
    """Score based on deviation from ideal GRAVY (~-0.2)."""
    deviation = abs(gravy - _IDEAL_GRAVY) / _GRAVY_SCALE
    return max(0.0, 1.0 - deviation)


def _score_cys(cys_count: int) -> float:
    """Score cysteine count: 0 or 2 = best; 1 = acceptable; >2 = penalised."""
    if cys_count == 0 or cys_count == 2:
        return 1.0
    if cys_count == 1:
        return 0.7
    if cys_count == 3:
        return 0.4
    return max(0.0, 1.0 - (cys_count - 2) * 0.3)


def _compute_composite_score(candidate: dict) -> float:
    """Compute heuristic composite score for a single candidate."""
    s_len = _score_length(candidate["length"])
    s_charge = _score_net_charge(candidate["net_charge"])
    s_pi = _score_pi(candidate["pI"])
    s_gravy = _score_gravy(candidate["GRAVY"])
    s_cys = _score_cys(candidate["cys_count"])

    weights = HEURISTIC_WEIGHTS_V0_7
    score = (
        weights["length"] * s_len
        + weights["net_charge"] * s_charge
        + weights["pI"] * s_pi
        + weights["GRAVY"] * s_gravy
        + weights["cys_count"] * s_cys
    )
    return round(min(1.0, max(0.0, score)), 3)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_final_ranking(candidates: list[dict]) -> dict:
    """Rank STAMP candidates using the v0.7 heuristic composite score.

    Returns a plain dict matching FinalRankingComputeResponse shape.
    """
    ranked = []
    for c in candidates:
        score = _compute_composite_score(c)
        ranked.append(
            {
                "candidate_id": c["candidate_id"],
                "full_sequence": c["full_sequence"],
                "targeting_peptide": c["targeting_peptide"],
                "linker": c["linker"],
                "amp": c["amp"],
                "length": c["length"],
                "net_charge": c["net_charge"],
                "pI": c["pI"],
                "GRAVY": c["GRAVY"],
                "cys_count": c["cys_count"],
                "composite_score": score,
                "mode": c.get("mode", "REAL_STAMP_ASSEMBLY_V0_7"),
                "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
                "created_at": c.get("created_at"),
            }
        )

    # Sort descending by composite score
    ranked.sort(key=lambda x: x["composite_score"], reverse=True)

    return {
        "code": 200,
        "message": "success",
        "mode": "HEURISTIC_FINAL_RANKING_V0_7",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "total_candidates": len(ranked),
        "ranked_candidates": ranked,
        "ranking_methodology": {
            "description": (
                "Heuristic composite score based solely on sequence-derived "
                "biophysical properties. This is NOT a prediction of antimicrobial "
                "efficacy, binding affinity, or developability."
            ),
            "weights": HEURISTIC_WEIGHTS_V0_7,
            "ideal_values": {
                "length": _IDEAL_LENGTH,
                "net_charge_absolute": _IDEAL_NET_CHARGE_ABS,
                "pI": _IDEAL_pI,
                "GRAVY": _IDEAL_GRAVY,
            },
            "scoring_method": "Gaussian deviation from ideal values, weighted sum, clamped to [0,1].",
            "experimental_validation": "None. All candidates are NOT_EXPERIMENTALLY_VALIDATED.",
            "excluded_metrics": [
                "MIC",
                "MBC",
                "hemolysis",
                "toxicity",
                "ipTM",
                "pDockQ",
                "docking_score",
                "delta_G",
            ],
        },
    }
