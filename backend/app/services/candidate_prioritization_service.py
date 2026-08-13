"""STAMP Platform — Candidate Prioritization Service (v0.11-P4).

Decision-support logic for ranking and reviewing peptide candidates.
Does NOT fabricate experimental data, does NOT auto-promote validation status,
and does NOT modify composite_score.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.crud.experimental_validation import (
    list_measurements_by_candidate,
    list_validation_runs_by_candidate,
)
from app.crud.stamp_candidates import (
    get_stamp_candidate,
    list_stamp_candidates_by_project,
    update_stamp_candidate,
)
from app.schemas.stamp import StampCandidateUpdate

# ---------------------------------------------------------------------------
# Priority status rules
# ---------------------------------------------------------------------------

REQUIRED_ACTIVITY_METRICS = {"MIC_ug_ml", "MBC_ug_ml"}
REQUIRED_SAFETY_METRICS = {"hemolysis_percent", "cell_viability_percent", "HC50_ug_ml", "IC50_ug_ml"}

VALID_DECISIONS = {"SHORTLIST", "HOLD", "REJECT", "NEEDS_REPEAT_EXPERIMENT"}


def compute_priority_status(candidate: Any, measurements: list[Any]) -> str:
    """Compute a decision-support priority status from candidate + measurements.

    Rules (decision-support only, not experimental validation):
    - VALIDATION_FAILED          → VALIDATION_FAILED
    - No experimental data       → NEEDS_MORE_DATA
    - Has activity but no safety → NEEDS_MORE_DATA
    - Low MIC + low hemolysis    → READY_FOR_REVIEW
    - High hemolysis/cytotoxicity → SAFETY_CONCERN
    """
    if candidate.validation_status == "VALIDATION_FAILED":
        return "VALIDATION_FAILED"

    metric_names = {m.metric_name for m in measurements if m.value is not None}
    has_activity = bool(metric_names & REQUIRED_ACTIVITY_METRICS)
    has_safety = bool(metric_names & REQUIRED_SAFETY_METRICS)

    if not has_activity and not has_safety:
        return "NEEDS_MORE_DATA"

    if has_activity and not has_safety:
        return "NEEDS_MORE_DATA"

    # Evaluate safety values
    hemolysis_values = [m.value for m in measurements if m.metric_name == "hemolysis_percent" and m.value is not None]
    viability_values = [m.value for m in measurements if m.metric_name == "cell_viability_percent" and m.value is not None]
    ic50_values = [m.value for m in measurements if m.metric_name == "IC50_ug_ml" and m.value is not None]

    safety_concern = False
    if hemolysis_values and max(hemolysis_values) > 50:
        safety_concern = True
    if viability_values and min(viability_values) < 50:
        safety_concern = True
    if ic50_values and min(ic50_values) < 10:
        safety_concern = True

    if safety_concern:
        return "SAFETY_CONCERN"

    # If we have both activity and safety and no safety concern → ready for review
    if has_activity and has_safety:
        return "READY_FOR_REVIEW"

    return "NEEDS_MORE_DATA"


def _extract_computational_summary(candidate: Any) -> dict[str, Any]:
    """Extract computational metrics for display."""
    metrics = candidate.metrics or {}
    sp = metrics.get("structure_prediction") or {}
    iq = metrics.get("interface_quality") or {}
    eq = metrics.get("energy_quality") or {}

    return {
        "pepmlm_source": metrics.get("source") or metrics.get("pepmlm_source") or None,
        "mean_plddt": sp.get("mean_plddt") if sp else None,
        "pdockq": iq.get("pdockq") if iq else None,
        "interaction_energy_kcal_mol": eq.get("interaction_energy_kcal_mol") if eq else None,
    }


def _extract_experimental_summary(measurements: list[Any]) -> dict[str, Any]:
    """Extract best experimental measurement per metric for display."""
    summary: dict[str, Any] = {}
    quality_flags: set[str] = set()

    for m in measurements:
        if m.value is not None:
            # Keep the latest (or best) value per metric
            summary[m.metric_name] = m.value
            quality_flags.add(m.quality_flag)

    # Attach overall quality flag if any failed
    if "FAILED" in quality_flags:
        summary["quality_flag"] = "FAILED"
    elif "WARNING" in quality_flags:
        summary["quality_flag"] = "WARNING"
    elif quality_flags:
        summary["quality_flag"] = "PASS"
    else:
        summary["quality_flag"] = None

    return summary


# ---------------------------------------------------------------------------
# Build project-level prioritization
# ---------------------------------------------------------------------------

def build_project_candidate_prioritization(db: Session, project_id: str) -> dict:
    """Return full prioritization data for a project."""
    candidates = list_stamp_candidates_by_project(db, project_id, limit=1000)

    result_candidates = []
    summary_counts = {
        "candidate_count": len(candidates),
        "ready_for_review": 0,
        "needs_more_data": 0,
        "safety_concern": 0,
        "validation_failed": 0,
        "shortlisted": 0,
        "rejected": 0,
    }

    for c in candidates:
        measurements = list_measurements_by_candidate(db, c.id)
        runs = list_validation_runs_by_candidate(db, c.id)

        priority_status = compute_priority_status(c, measurements)

        # Override with manual decision if present
        decision = None
        decision_data = (c.metrics or {}).get("priority_decision")
        if decision_data and isinstance(decision_data, dict):
            decision = {
                "decision": decision_data.get("decision"),
                "decision_reason": decision_data.get("decision_reason"),
                "reviewer": decision_data.get("reviewer"),
                "reviewed_at": decision_data.get("reviewed_at"),
                "notes": decision_data.get("notes"),
            }
            if decision["decision"] == "SHORTLIST":
                summary_counts["shortlisted"] += 1
            elif decision["decision"] == "REJECT":
                summary_counts["rejected"] += 1

        # Count by priority status
        if priority_status == "READY_FOR_REVIEW":
            summary_counts["ready_for_review"] += 1
        elif priority_status == "NEEDS_MORE_DATA":
            summary_counts["needs_more_data"] += 1
        elif priority_status == "SAFETY_CONCERN":
            summary_counts["safety_concern"] += 1
        elif priority_status == "VALIDATION_FAILED":
            summary_counts["validation_failed"] += 1

        # Compute experimental_priority_score if data exists
        from app.services.experimental_validation_service import compute_candidate_priority
        exp_priority = None
        try:
            priority_resp = compute_candidate_priority(db, c.id)
            exp_priority = priority_resp.experimental_priority_score
        except Exception:
            pass

        result_candidates.append({
            "candidate_id": c.id,
            "sequence": c.full_sequence,
            "composite_score": c.composite_score,
            "experimental_priority_score": exp_priority,
            "priority_status": priority_status,
            "validation_status": c.validation_status,
            "computational_summary": _extract_computational_summary(c),
            "experimental_summary": _extract_experimental_summary(measurements),
            "run_count": len(runs),
            "measurement_count": len(measurements),
            "decision": decision,
        })

    # Sort: shortlist first, then by experimental_priority_score desc, then composite_score desc
    def sort_key(item: dict) -> tuple:
        d = item.get("decision") or {}
        is_shortlisted = 1 if d.get("decision") == "SHORTLIST" else 0
        exp_score = item.get("experimental_priority_score") or 0
        comp_score = item.get("composite_score") or 0
        return (-is_shortlisted, -exp_score, -comp_score)

    result_candidates.sort(key=sort_key)

    return {
        "project_id": project_id,
        "summary": summary_counts,
        "candidates": result_candidates,
    }


# ---------------------------------------------------------------------------
# Save manual priority decision
# ---------------------------------------------------------------------------

def save_candidate_priority_decision(
    db: Session, candidate_id: str, payload: dict
) -> dict:
    """Save a manual review decision into candidate.metrics['priority_decision'].

    Does NOT modify composite_score or validation_status.
    """
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate '{candidate_id}' not found")

    decision = payload.get("decision")
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {VALID_DECISIONS}")

    reason = payload.get("decision_reason", "").strip()
    if not reason:
        raise ValueError("decision_reason is required")

    # Build decision record
    decision_record = {
        "decision": decision,
        "decision_reason": reason,
        "reviewer": payload.get("reviewer") or "anonymous",
        "reviewed_at": datetime.utcnow().isoformat(),
        "manual_override": True,
        "notes": payload.get("notes") or None,
    }

    # Merge into existing metrics
    metrics = dict(candidate.metrics or {})
    metrics["priority_decision"] = decision_record

    update_stamp_candidate(
        db, candidate, StampCandidateUpdate(metrics=metrics)
    )

    return {
        "candidate_id": candidate_id,
        "decision": decision_record,
        "composite_score": candidate.composite_score,
        "validation_status": candidate.validation_status,
    }
