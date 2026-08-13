"""
mmgbsa_persistence_guard.py
----------------------------
Backend guard that prevents smoke/pilot MM-GBSA values from polluting
official production fields.

Rules for writing official mm_gbsa_delta_g:
- run_type == PRODUCTION
- convergence_status in (CONVERGED, PARTIAL_CONVERGENCE)
- frames_used >= 200
- trajectory_length_ns >= 1 (min), recommended >= 10
- MMPBSA completed without error
- scientific boundary validation passed

Always null for:
- SMOKE_ONLY, PILOT_ONLY, NOT_CONVERGED
- Missing frame count
- Missing SEM / convergence evidence
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.services.mmpbsa_result_parser import MMPBSAParsedResult


@dataclass
class GuardDecision:
    can_write_official_delta_g: bool
    official_mm_gbsa_delta_g: Optional[float]
    convergence_status: str
    reason: str
    warnings: List[str] = field(default_factory=list)
    checks_passed: Dict[str, bool] = field(default_factory=dict)
    checks_failed: Dict[str, str] = field(default_factory=dict)


def evaluate_mmgbsa_for_production(
    parsed: MMPBSAParsedResult,
    trajectory_length_ns: Optional[float] = None,
    mmpbsa_exit_code: int = 0,
) -> GuardDecision:
    """
    Evaluate whether a parsed MMPBSA result may be promoted to official production ΔG.

    Args:
        parsed: MMPBSAParsedResult from the parser.
        trajectory_length_ns: Length of the production trajectory in nanoseconds.
        mmpbsa_exit_code: Exit code from MMPBSA.py run (0 = success).

    Returns:
        GuardDecision with can_write_official_delta_g and detailed checks.
    """
    warnings: List[str] = []
    checks_passed: Dict[str, bool] = {}
    checks_failed: Dict[str, str] = {}

    # --- Check 1: Run type ---
    if parsed.run_type == "PRODUCTION":
        checks_passed["run_type"] = True
    else:
        checks_passed["run_type"] = False
        checks_failed["run_type"] = f"Run type is '{parsed.run_type}', not PRODUCTION."
        warnings.append(checks_failed["run_type"])

    # --- Check 2: Convergence status ---
    allowed_convergence = {"CONVERGED", "PARTIAL_CONVERGENCE"}
    if parsed.convergence_status in allowed_convergence:
        checks_passed["convergence_status"] = True
    else:
        checks_passed["convergence_status"] = False
        checks_failed["convergence_status"] = (
            f"Convergence status is '{parsed.convergence_status}'. "
            f"Must be one of {allowed_convergence}."
        )
        warnings.append(checks_failed["convergence_status"])

    # --- Check 3: Frame count ---
    if parsed.frames_used is not None and parsed.frames_used >= 200:
        checks_passed["frame_count"] = True
    else:
        checks_passed["frame_count"] = False
        checks_failed["frame_count"] = (
            f"Frames used ({parsed.frames_used or 'unknown'}) < 200 minimum."
        )
        warnings.append(checks_failed["frame_count"])

    # --- Check 4: Trajectory length ---
    if trajectory_length_ns is not None:
        if trajectory_length_ns >= 10:
            checks_passed["trajectory_length"] = True
        elif trajectory_length_ns >= 1:
            checks_passed["trajectory_length"] = True
            warnings.append(
                f"Trajectory length ({trajectory_length_ns} ns) meets minimum (1 ns) "
                "but is below recommended (10 ns)."
            )
        else:
            checks_passed["trajectory_length"] = False
            checks_failed["trajectory_length"] = (
                f"Trajectory length ({trajectory_length_ns} ns) < 1 ns minimum."
            )
            warnings.append(checks_failed["trajectory_length"])
    else:
        checks_passed["trajectory_length"] = False
        checks_failed["trajectory_length"] = "Trajectory length not provided."
        warnings.append(checks_failed["trajectory_length"])

    # --- Check 5: MMPBSA exit code ---
    if mmpbsa_exit_code == 0:
        checks_passed["mmpbsa_success"] = True
    else:
        checks_passed["mmpbsa_success"] = False
        checks_failed["mmpbsa_success"] = f"MMPBSA.py exited with code {mmpbsa_exit_code}."
        warnings.append(checks_failed["mmpbsa_success"])

    # --- Check 6: Scientific boundary (parser status) ---
    if parsed.status == "SUCCESS":
        checks_passed["parser_status"] = True
    else:
        checks_passed["parser_status"] = False
        checks_failed["parser_status"] = f"Parser status is '{parsed.status}'."
        warnings.append(checks_failed["parser_status"])

    # --- Check 7: Delta value must exist ---
    if parsed.pilot_delta_total_kcal_mol is not None:
        checks_passed["delta_value_present"] = True
    else:
        checks_passed["delta_value_present"] = False
        checks_failed["delta_value_present"] = "No DELTA TOTAL value found in parsed result."
        warnings.append(checks_failed["delta_value_present"])

    # --- Final decision ---
    all_critical_passed = all(
        checks_passed.get(k, False)
        for k in [
            "run_type",
            "convergence_status",
            "frame_count",
            "trajectory_length",
            "mmpbsa_success",
            "parser_status",
            "delta_value_present",
        ]
    )

    if all_critical_passed:
        can_write = True
        official_delta = parsed.pilot_delta_total_kcal_mol
        reason = "All production criteria satisfied. Official mm_gbsa_delta_g may be written."
    else:
        can_write = False
        official_delta = None
        failed_list = ", ".join(checks_failed.keys())
        reason = f"Production criteria NOT satisfied. Failed checks: {failed_list}."
        warnings.append(
            "official_mm_gbsa_delta_g remains null. Result is not suitable for candidate ranking."
        )

    return GuardDecision(
        can_write_official_delta_g=can_write,
        official_mm_gbsa_delta_g=official_delta,
        convergence_status=parsed.convergence_status,
        reason=reason,
        warnings=warnings,
        checks_passed=checks_passed,
        checks_failed=checks_failed,
    )


def guard_dict(decision: GuardDecision) -> Dict[str, Any]:
    """Serialize guard decision to plain dict for JSON output."""
    return {
        "can_write_official_delta_g": decision.can_write_official_delta_g,
        "official_mm_gbsa_delta_g": decision.official_mm_gbsa_delta_g,
        "convergence_status": decision.convergence_status,
        "reason": decision.reason,
        "warnings": decision.warnings,
        "checks_passed": decision.checks_passed,
        "checks_failed": decision.checks_failed,
    }
