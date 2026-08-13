"""
STAMP Platform — Rule-Based Targeting Peptide Generator

Generates up to 20 targeting peptide candidates from a selected epitope
using deterministic, biophysically-informed rules (no ML).

Rules:
  - Length 8–15 aa
  - Cys count = 0 (hard filter)
  - Charge complementarity vs source epitope
  - Moderate GRAVY preferred
"""

from __future__ import annotations

import itertools

from app.models.epitope import FilterStatus
from app.models.targeting_peptide import (
    SourceEpitope,
    TargetingPeptideCandidate,
    TargetingPeptideGenerateResponse,
    TargetingPeptideInputSummary,
)
from app.services.biophys import (
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
    disulfide_risk,
    hydrophobicity_class,
)

# ---------------------------------------------------------------------------
# Amino acid pools for charge-complementary design
# ---------------------------------------------------------------------------

NEGATIVE_AA: set[str] = {"D", "E"}
POSITIVE_AA: set[str] = {"K", "R", "H"}
NEUTRAL_AA: set[str] = {
    "A", "G", "I", "L", "M", "N", "P", "Q", "S", "T", "V", "W", "Y", "F",
}
NON_CYS_AA: set[str] = set("ADEFGHIKLMNPQRSTVWY")

# Substitution map: for a given epitope charge sign, which residues to prefer
_SUBSTITUTIONS: dict[str, dict[str, str]] = {
    "positive": {
        # Replace positive/neutral with negative or neutral
        "K": "E", "R": "D", "H": "E",
        "A": "D", "G": "E", "I": "D", "L": "E",
        "M": "D", "N": "E", "P": "D", "Q": "E",
        "S": "D", "T": "E", "V": "D", "W": "E",
        "Y": "D", "F": "E",
    },
    "negative": {
        # Replace negative/neutral with positive or neutral
        "D": "K", "E": "R",
        "A": "K", "G": "R", "I": "K", "L": "R",
        "M": "K", "N": "R", "P": "K", "Q": "R",
        "S": "K", "T": "R", "V": "K", "W": "R",
        "Y": "K", "F": "R",
    },
    "neutral": {
        # Gentle diversification
        "A": "S", "G": "N", "I": "V", "L": "I",
        "M": "L", "N": "Q", "P": "A", "Q": "N",
        "S": "T", "T": "S", "V": "I", "W": "Y",
        "Y": "W", "F": "Y", "D": "N", "E": "Q",
        "K": "R", "R": "K", "H": "N",
    },
}


def _charge_sign(charge: float) -> str:
    if charge > 0.5:
        return "positive"
    if charge < -0.5:
        return "negative"
    return "neutral"


def _remove_cys(seq: str) -> str:
    """Replace cysteine with serine (conservative, no Cys)."""
    return seq.replace("C", "S")


def _substitute_sequence(seq: str, sign: str, variant_index: int = 0) -> str:
    """Apply charge-complementary substitutions with deterministic variation."""
    mapping = _SUBSTITUTIONS[sign]
    result: list[str] = []
    for i, aa in enumerate(seq):
        if aa == "C":
            result.append("S")
        elif aa in mapping:
            # Deterministic: only substitute every Nth residue based on variant_index
            if (i + variant_index) % 2 == 0:
                result.append(mapping[aa])
            else:
                result.append(aa)
        else:
            result.append(aa)
    return "".join(result)


def _generate_pool_candidates(
    epitope_seq: str,
    sign: str,
    count_needed: int,
) -> list[str]:
    """Generate additional candidates from a charge-complementary amino acid pool."""
    if sign == "positive":
        pool = list(NEGATIVE_AA | NEUTRAL_AA)
    elif sign == "negative":
        pool = list(POSITIVE_AA | NEUTRAL_AA)
    else:
        pool = list(NEUTRAL_AA)

    candidates: list[str] = []
    # Use the epitope sequence as a deterministic seed for generating new sequences
    seq_len = len(epitope_seq)
    for idx in range(count_needed):
        length = 8 + (idx % 8)  # lengths 8-15
        new_seq = ""
        for pos in range(length):
            # Deterministic pseudo-random based on epitope sequence and index
            seed = ord(epitope_seq[(pos + idx) % seq_len]) + idx * 7 + pos * 3
            new_seq += pool[seed % len(pool)]
        candidates.append(new_seq)
    return candidates


def _generate_all_candidates(epitope_seq: str, sign: str) -> list[str]:
    """Produce raw candidate sequences (may include duplicates)."""
    raw: list[str] = []
    seq_len = len(epitope_seq)

    # 1. All 8-15 aa windows from the epitope (step 1)
    for wsize in range(8, min(16, seq_len + 1)):
        for start in range(0, seq_len - wsize + 1):
            window = epitope_seq[start : start + wsize]
            window_no_cys = _remove_cys(window)
            raw.append(window_no_cys)
            # Add substituted variant
            raw.append(_substitute_sequence(window_no_cys, sign, variant_index=0))
            raw.append(_substitute_sequence(window_no_cys, sign, variant_index=1))

    # 2. Truncated / extended variants
    for wsize in range(8, 16):
        if wsize <= seq_len:
            continue
        # Extend with complementary pool
        extension = _generate_pool_candidates(epitope_seq, sign, 1)[0][: wsize - seq_len]
        extended = epitope_seq + extension
        raw.append(_remove_cys(extended))

    # 3. Pool-generated candidates to guarantee diversity
    pool_count = max(30, 50 - len(raw))
    raw.extend(_generate_pool_candidates(epitope_seq, sign, pool_count))

    # Deduplicate while preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for s in raw:
        s = s.upper()
        if s not in seen and len(s) >= 8:
            seen.add(s)
            deduped.append(s)

    return deduped


def _score_candidate(
    candidate_charge: float,
    candidate_gravy: float,
    candidate_cys: int,
    candidate_length: int,
    epitope_charge: float,
) -> float:
    """Composite ranking score (higher = better)."""
    # Charge complementarity: prefer opposite charge to epitope
    ideal_charge = -epitope_charge
    charge_diff = abs(candidate_charge - ideal_charge)
    charge_score = max(0.0, 1.0 - charge_diff / 5.0)

    # Length: prefer 10-12
    length_score = max(0.0, 1.0 - abs(candidate_length - 11) / 4.0)

    # GRAVY: near 0 (balanced hydrophilic/hydrophobic)
    gravy_score = max(0.0, 1.0 - abs(candidate_gravy))

    # Cys: must be 0 for full score
    cys_score = 1.0 if candidate_cys == 0 else 0.0

    raw = 0.35 * charge_score + 0.25 * length_score + 0.25 * gravy_score + 0.15 * cys_score
    return round(raw, 4)


def _classify_filter(cys: int, gravy: float, length: int) -> FilterStatus:
    failures = 0
    if cys > 0:
        failures += 1
    if length < 8 or length > 15:
        failures += 1
    if failures > 0:
        return FilterStatus.FAIL
    if gravy > 0.8 or gravy < -1.0:
        return FilterStatus.WARNING
    return FilterStatus.PASS


def generate_targeting_peptides(
    source_epitope: SourceEpitope,
    requested_count: int = 20,
) -> dict:
    """Generate rule-based targeting peptide candidates.

    Returns a plain dict matching TargetingPeptideGenerateResponse shape.
    """
    epitope_seq = source_epitope.sequence.upper().strip()
    epitope_charge = calculate_net_charge(epitope_seq)
    sign = _charge_sign(epitope_charge)

    raw_sequences = _generate_all_candidates(epitope_seq, sign)

    candidates: list[TargetingPeptideCandidate] = []
    for idx, seq in enumerate(raw_sequences):
        if len(seq) < 8 or len(seq) > 15:
            continue
        cys = count_cys(seq)
        if cys > 0:
            continue
        nc = calculate_net_charge(seq)
        pi = calculate_pi(seq)
        gravy = calculate_gravy(seq)
        score = _score_candidate(nc, gravy, cys, len(seq), epitope_charge)
        filt = _classify_filter(cys, gravy, len(seq))

        note = f"Designed for charge complementarity against {epitope_charge:+.1f} epitope ({sign})"

        candidates.append(
            TargetingPeptideCandidate(
                candidate_id=f"tp_{idx + 1:03d}",
                source_epitope_id=source_epitope.candidate_id,
                sequence=seq,
                length=len(seq),
                net_charge=nc,
                pI=pi,
                GRAVY=gravy,
                cys_count=cys,
                complementarity_note=note,
                filter_status=filt,
                ranking_score=score,
            )
        )

    # Sort by ranking score descending
    candidates.sort(key=lambda c: c.ranking_score, reverse=True)

    # Take top requested_count
    top_candidates = candidates[:requested_count]

    # Reassign sequential candidate IDs after sorting
    for i, c in enumerate(top_candidates):
        c.candidate_id = f"tp_{i + 1:03d}"

    # If we still don't have enough, pad with pool-generated (should not happen often)
    if len(top_candidates) < requested_count:
        needed = requested_count - len(top_candidates)
        extra = _generate_pool_candidates(epitope_seq, sign, needed)
        for i, seq in enumerate(extra):
            seq = _remove_cys(seq).upper()
            if len(seq) < 8:
                seq = seq + "A" * (8 - len(seq))
            if len(seq) > 15:
                seq = seq[:15]
            cys = count_cys(seq)
            if cys > 0:
                seq = seq.replace("C", "S")
            nc = calculate_net_charge(seq)
            pi = calculate_pi(seq)
            gravy = calculate_gravy(seq)
            score = _score_candidate(nc, gravy, 0, len(seq), epitope_charge)
            filt = _classify_filter(0, gravy, len(seq))
            top_candidates.append(
                TargetingPeptideCandidate(
                    candidate_id=f"tp_{len(top_candidates) + 1:03d}",
                    source_epitope_id=source_epitope.candidate_id,
                    sequence=seq,
                    length=len(seq),
                    net_charge=nc,
                    pI=pi,
                    GRAVY=gravy,
                    cys_count=0,
                    complementarity_note=note,
                    filter_status=filt,
                    ranking_score=score,
                )
            )

    summary = TargetingPeptideInputSummary(
        source_epitope_id=source_epitope.candidate_id,
        source_sequence=epitope_seq,
        source_length=len(epitope_seq),
        source_net_charge=epitope_charge,
        source_target_name=source_epitope.target_name,
        source_species=source_epitope.species,
        requested_count=requested_count,
    )

    return TargetingPeptideGenerateResponse(
        code=200,
        message="success",
        mode="RULE_BASED_TARGETING_PEPTIDE_GENERATION",
        validation_status="NOT_EXPERIMENTALLY_VALIDATED",
        input_summary=summary,
        candidates=top_candidates,
    ).model_dump()
