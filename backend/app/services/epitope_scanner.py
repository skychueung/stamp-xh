"""
STAMP Platform — Epitope Scanner Service

15 aa sliding window scanner that computes biophysical properties for
every window and ranks them by a composite scoring function.
"""

from __future__ import annotations

from app.models.epitope import (
    DisulfideRisk,
    EpitopeCandidate,
    EpitopeScanFilters,
    FilterStatus,
)
from app.services.biophys import (
    calculate_gravy,
    calculate_net_charge,
    calculate_pi,
    count_cys,
    disulfide_risk,
    hydrophobicity_class,
)


def _classify_filter(
    net_charge: float,
    pI: float,
    gravy: float,
    cys: int,
    filters: EpitopeScanFilters,
) -> FilterStatus:
    """Determine filter status based on user-specified thresholds."""
    failures = 0
    warnings = 0

    if net_charge < filters.min_charge or net_charge > filters.max_charge:
        failures += 1
    if pI < filters.min_pI or pI > filters.max_pI:
        failures += 1
    if gravy > filters.max_gravy:
        warnings += 1
    if cys > filters.max_cys:
        failures += 1

    if failures > 0:
        return FilterStatus.FAIL
    if warnings > 0:
        return FilterStatus.WARNING
    return FilterStatus.PASS


def _ranking_score(net_charge: float, pI: float, gravy: float, cys: int) -> float:
    """Composite ranking score (higher = better candidate).

    Prefers:
      - Moderate charge (-2 to +4)
      - pI near 7.0
      - GRAVY near 0 (balanced)
      - Low cysteine count
    """
    charge_score = max(0.0, 1.0 - abs(net_charge) / 5.0)
    pi_score = max(0.0, 1.0 - abs(pI - 7.0) / 4.0)
    gravy_score = max(0.0, 1.0 - abs(gravy))
    cys_score = 1.0 if cys == 0 else 0.5 if cys == 1 else 0.0

    raw = 0.25 * charge_score + 0.25 * pi_score + 0.25 * gravy_score + 0.25 * cys_score
    return round(raw, 4)


def _risk_notes(
    net_charge: float,
    pI: float,
    gravy: float,
    cys: int,
    ds_risk: str,
) -> str | None:
    """Generate human-readable risk notes."""
    notes: list[str] = []
    if ds_risk == "potential_disulfide":
        notes.append("Potential disulfide bond formation risk")
    elif ds_risk == "single_cys":
        notes.append("Single cysteine: potential aggregation risk")
    if gravy > 0.8:
        notes.append("Highly hydrophobic: solubility concern")
    if abs(net_charge) > 4:
        notes.append("High net charge: may affect specificity")
    if pI < 4.0 or pI > 10.0:
        notes.append("Extreme pI: stability concern")
    return "; ".join(notes) if notes else None


def _recommendation_reason(
    rank: int,
    net_charge: float,
    pI: float,
    cys: int,
    filter_status: FilterStatus,
) -> str:
    """Generate a brief recommendation reason."""
    if filter_status == FilterStatus.FAIL:
        return "Fails filtering criteria"
    if rank == 1:
        return "Top-ranked candidate with balanced biophysical properties"
    if cys == 0:
        return "Cysteine-free; good stability profile"
    if cys == 1:
        return "Acceptable single cysteine; monitor disulfide risk"
    return "Moderate candidate; consider further optimization"


def scan_epitopes(
    sequence: str,
    target_name: str = "Unknown",
    species: str = "Unknown",
    window_size: int = 15,
    top_k: int = 20,
    filters: EpitopeScanFilters | None = None,
) -> dict:
    """Run 15 aa sliding window scan over the full target protein sequence.

    Args:
        sequence: Uppercase amino acid sequence.
        target_name: Human-readable target name.
        species: Source species.
        window_size: Sliding window size (default 15).
        top_k: Number of top candidates to return.
        filters: Optional filter thresholds.

    Returns:
        Dict matching EpitopeScanResponse structure.
    """
    if filters is None:
        filters = EpitopeScanFilters()

    seq = sequence.upper().strip()
    seq_len = len(seq)

    if seq_len < window_size:
        return {
            "code": 200,
            "message": "Sequence shorter than window size — no windows generated",
            "mode": "REAL_BIOPHYSICS_SLIDING_WINDOW",
            "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
            "input_summary": {
                "target_name": target_name,
                "species": species,
                "sequence_length": seq_len,
                "window_size": window_size,
                "total_windows": 0,
            },
            "filtering_summary": {
                "total_windows": 0,
                "passed": 0,
                "warning": 0,
                "failed": 0,
                "returned": 0,
            },
            "candidates": [],
        }

    total_windows = seq_len - window_size + 1
    candidates: list[EpitopeCandidate] = []

    for start in range(total_windows):
        end = start + window_size
        window_seq = seq[start:end]

        length_val = window_size
        nc = calculate_net_charge(window_seq, ph=7.0)
        pi_val = calculate_pi(window_seq)
        gravy_val = calculate_gravy(window_seq)
        cys = count_cys(window_seq)
        ds_risk = disulfide_risk(cys)
        h_class = hydrophobicity_class(gravy_val)
        fs = _classify_filter(nc, pi_val, gravy_val, cys, filters)
        score = _ranking_score(nc, pi_val, gravy_val, cys)

        candidates.append(
            EpitopeCandidate(
                candidate_id=f"epi_{start + 1}_{end}",
                start=start + 1,
                end=end,
                sequence=window_seq,
                length=length_val,
                net_charge=nc,
                pI=pi_val,
                GRAVY=gravy_val,
                cys_count=cys,
                disulfide_risk=ds_risk,
                hydrophobicity_class=h_class,
                filter_status=fs,
                ranking_score=score,
                risk_notes=_risk_notes(nc, pi_val, gravy_val, cys, ds_risk),
                recommendation_reason="",  # filled after sorting
            )
        )

    # Sort by ranking score descending
    candidates.sort(key=lambda c: c.ranking_score, reverse=True)

    # Assign rank-based recommendation reasons
    for i, c in enumerate(candidates):
        c.recommendation_reason = _recommendation_reason(
            i + 1, c.net_charge, c.pI, c.cys_count, c.filter_status
        )

    # Top-K
    top = candidates[:top_k]

    passed = sum(1 for c in top if c.filter_status == FilterStatus.PASS)
    warning = sum(1 for c in top if c.filter_status == FilterStatus.WARNING)
    failed = sum(1 for c in top if c.filter_status == FilterStatus.FAIL)

    return {
        "code": 200,
        "message": "Epitope scan completed",
        "mode": "REAL_BIOPHYSICS_SLIDING_WINDOW",
        "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
        "input_summary": {
            "target_name": target_name,
            "species": species,
            "sequence_length": seq_len,
            "window_size": window_size,
            "total_windows": total_windows,
        },
        "filtering_summary": {
            "total_windows": total_windows,
            "passed": passed,
            "warning": warning,
            "failed": failed,
            "returned": len(top),
        },
        "candidates": [c.model_dump() for c in top],
    }
