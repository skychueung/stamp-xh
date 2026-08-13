"""
test_mmgbsa_persistence_guard.py
--------------------------------
Tests for MM-GBSA persistence guard.

Scientific boundary checks:
- Pilot/smoke must NEVER be promoted to official mm_gbsa_delta_g.
- Production must pass ALL criteria before official ΔG is allowed.
- Missing values must fail gracefully (null, not crash).
"""

import json
from pathlib import Path

import pytest

from app.services.mmpbsa_result_parser import MMPBSAParsedResult, parse_mmpbsa_result
from app.services.mmgbsa_persistence_guard import (
    GuardDecision,
    evaluate_mmgbsa_for_production,
    guard_dict,
)


def make_parsed(
    run_type: str = "PILOT",
    convergence_status: str = "PILOT_ONLY",
    frames_used: int = 7,
    delta_total: float = -0.0001,
    status: str = "SUCCESS",
) -> MMPBSAParsedResult:
    """Factory for creating parsed results with specific parameters."""
    result = MMPBSAParsedResult(
        source_file="test.dat",
        run_type=run_type,
        convergence_status=convergence_status,
        frames_used=frames_used,
        pilot_delta_total_kcal_mol=delta_total,
        status=status,
    )
    result.energy_terms["delta"] = {"DELTA_TOTAL": delta_total}
    return result


def test_pilot_result_blocked():
    """Pilot results must never be promoted to official ΔG."""
    parsed = make_parsed(run_type="PILOT", convergence_status="PILOT_ONLY", frames_used=7)
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=0.1, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert decision.convergence_status == "PILOT_ONLY"
    assert "run_type" in decision.checks_failed
    assert "convergence_status" in decision.checks_failed
    assert any("official_mm_gbsa_delta_g remains null" in w for w in decision.warnings)


def test_smoke_result_blocked():
    """Smoke results must never be promoted to official ΔG."""
    parsed = make_parsed(run_type="SMOKE", convergence_status="SMOKE_ONLY", frames_used=1)
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=0.001, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert decision.convergence_status == "SMOKE_ONLY"


def test_production_insufficient_frames_blocked():
    """Production with <200 frames must be blocked."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=50,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=10.0, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert "frame_count" in decision.checks_failed


def test_production_short_trajectory_blocked():
    """Production with <1 ns trajectory must be blocked."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=0.5, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert "trajectory_length" in decision.checks_failed


def test_production_minimal_trajectory_allowed_with_warning():
    """Production with 1-10 ns trajectory is allowed but warns."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=5.0, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is True
    assert decision.official_mm_gbsa_delta_g == pytest.approx(-15.5)
    assert any("below recommended" in w for w in decision.warnings)


def test_production_full_criteria_passed():
    """Production meeting all criteria should allow official ΔG."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=10.0, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is True
    assert decision.official_mm_gbsa_delta_g == pytest.approx(-15.5)
    assert decision.convergence_status == "CONVERGED"
    assert decision.checks_passed["run_type"] is True
    assert decision.checks_passed["convergence_status"] is True
    assert decision.checks_passed["frame_count"] is True
    assert decision.checks_passed["trajectory_length"] is True
    assert decision.checks_passed["mmpbsa_success"] is True
    assert decision.checks_passed["parser_status"] is True
    assert decision.checks_passed["delta_value_present"] is True
    assert not decision.checks_failed


def test_production_mmpbsa_failure_blocked():
    """Production with MMPBSA.py failure must be blocked."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=10.0, mmpbsa_exit_code=1)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert "mmpbsa_success" in decision.checks_failed


def test_production_partial_convergence_allowed():
    """PARTIAL_CONVERGENCE should allow official ΔG if other criteria pass."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="PARTIAL_CONVERGENCE",
        frames_used=250,
        delta_total=-12.3,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=10.0, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is True
    assert decision.official_mm_gbsa_delta_g == pytest.approx(-12.3)


def test_missing_trajectory_length_blocked():
    """Missing trajectory length must block official ΔG."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=-15.5,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=None, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert "trajectory_length" in decision.checks_failed


def test_missing_delta_value_blocked():
    """Missing DELTA TOTAL must block official ΔG."""
    parsed = make_parsed(
        run_type="PRODUCTION",
        convergence_status="CONVERGED",
        frames_used=500,
        delta_total=None,
    )
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=10.0, mmpbsa_exit_code=0)

    assert decision.can_write_official_delta_g is False
    assert decision.official_mm_gbsa_delta_g is None
    assert "delta_value_present" in decision.checks_failed


def test_guard_dict_serializable():
    """Guard decision must be JSON-serializable."""
    parsed = make_parsed(run_type="PILOT", convergence_status="PILOT_ONLY")
    decision = evaluate_mmgbsa_for_production(parsed, trajectory_length_ns=0.1)
    d = guard_dict(decision)

    json_str = json.dumps(d, indent=2)
    assert json_str
    assert d["official_mm_gbsa_delta_g"] is None
    assert d["can_write_official_delta_g"] is False
