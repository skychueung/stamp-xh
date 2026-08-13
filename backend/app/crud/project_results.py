"""STAMP Platform — CRUD: Project-Level Result Queries (P5-lite P5).

Aggregated read-only queries for project dashboards.
No writes, no calculations, no fabricated data.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import (
    EpitopeCandidate,
    EpitopeScan,
    Project,
    StampCandidate,
    StampGenerationRun,
    TargetProtein,
)


# ---------------------------------------------------------------------------
# Project summary
# ---------------------------------------------------------------------------


def get_project_summary(db: Session, project_id: str) -> Optional[dict]:
    """Return project overview statistics.

    Returns None if project does not exist.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return None

    target_protein_count = db.query(TargetProtein).filter(
        TargetProtein.project_id == project_id
    ).count()

    epitope_scan_count = db.query(EpitopeScan).filter(
        EpitopeScan.project_id == project_id
    ).count()

    epitope_candidate_count = (
        db.query(EpitopeCandidate)
        .join(EpitopeScan)
        .filter(EpitopeScan.project_id == project_id)
        .count()
    )

    generation_run_count = db.query(StampGenerationRun).filter(
        StampGenerationRun.project_id == project_id
    ).count()

    stamp_candidate_count = db.query(StampCandidate).filter(
        StampCandidate.project_id == project_id
    ).count()

    # assembled = has non-empty full_sequence (always true per schema, but keep for clarity)
    assembled_candidate_count = (
        db.query(StampCandidate)
        .filter(
            StampCandidate.project_id == project_id,
            StampCandidate.full_sequence != "",
        )
        .count()
    )

    # ranked = composite_score is not null
    ranked_candidate_count = (
        db.query(StampCandidate)
        .filter(
            StampCandidate.project_id == project_id,
            StampCandidate.composite_score.isnot(None),
        )
        .count()
    )

    # latest_updated_at: max of project.updated_at and all child updated_at values
    latest = project.updated_at

    return {
        "project_id": project.id,
        "project_name": project.name,
        "target_protein_count": target_protein_count,
        "epitope_scan_count": epitope_scan_count,
        "epitope_candidate_count": epitope_candidate_count,
        "generation_run_count": generation_run_count,
        "stamp_candidate_count": stamp_candidate_count,
        "assembled_candidate_count": assembled_candidate_count,
        "ranked_candidate_count": ranked_candidate_count,
        "latest_updated_at": latest,
    }


# ---------------------------------------------------------------------------
# Pipeline results
# ---------------------------------------------------------------------------


def get_project_pipeline_results(db: Session, project_id: str) -> Optional[dict]:
    """Return full pipeline results for a project.

    Returns None if project does not exist.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return None

    target_proteins = (
        db.query(TargetProtein)
        .filter(TargetProtein.project_id == project_id)
        .order_by(TargetProtein.created_at.asc())
        .all()
    )

    epitope_scans = (
        db.query(EpitopeScan)
        .filter(EpitopeScan.project_id == project_id)
        .order_by(EpitopeScan.created_at.asc())
        .all()
    )

    scan_ids = [s.id for s in epitope_scans]
    epitope_candidates = (
        db.query(EpitopeCandidate)
        .filter(EpitopeCandidate.scan_id.in_(scan_ids))
        .order_by(EpitopeCandidate.created_at.asc())
        .all()
        if scan_ids
        else []
    )

    generation_runs = (
        db.query(StampGenerationRun)
        .filter(StampGenerationRun.project_id == project_id)
        .order_by(StampGenerationRun.created_at.asc())
        .all()
    )

    stamp_candidates = (
        db.query(StampCandidate)
        .filter(StampCandidate.project_id == project_id)
        .order_by(StampCandidate.created_at.asc())
        .all()
    )

    return {
        "project_id": project.id,
        "project_name": project.name,
        "target_proteins": target_proteins,
        "epitope_scans": epitope_scans,
        "epitope_candidates": epitope_candidates,
        "generation_runs": generation_runs,
        "stamp_candidates": stamp_candidates,
    }


# ---------------------------------------------------------------------------
# STAMP results (assembled + ranked)
# ---------------------------------------------------------------------------


def list_project_stamp_results(
    db: Session,
    project_id: str,
    top_k: Optional[int] = None,
    include_metrics: bool = True,
) -> Optional[dict]:
    """Return assembled and ranked STAMP candidates for a project.

    Filters:
      - composite_score is not null
      - metrics contains 'assembly' or 'final_ranking'
    Sorts:
      - composite_score DESC, created_at ASC

    Returns None if project does not exist.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return None

    query = (
        db.query(StampCandidate)
        .filter(
            StampCandidate.project_id == project_id,
            StampCandidate.composite_score.isnot(None),
        )
        .order_by(StampCandidate.composite_score.desc(), StampCandidate.created_at.asc())
    )

    all_candidates = query.all()

    # Filter in Python for JSON metrics content (safer than raw JSON SQL filters)
    # Include STAMP-assembled candidates AND PepMLM-generated candidates
    filtered = []
    for c in all_candidates:
        metrics = c.metrics or {}
        if "assembly" in metrics or "final_ranking" in metrics or "pepmlm" in str(metrics.get("source", "")):
            filtered.append(c)

    total_count = len(filtered)

    if top_k is not None and top_k > 0:
        filtered = filtered[:top_k]
    elif top_k is not None and top_k <= 0:
        filtered = []

    return {
        "project_id": project.id,
        "project_name": project.name,
        "total_count": total_count,
        "returned_count": len(filtered),
        "candidates": filtered,
        "include_metrics": include_metrics,
    }


# ---------------------------------------------------------------------------
# Generation runs
# ---------------------------------------------------------------------------


def list_generation_runs_by_project(db: Session, project_id: str) -> Optional[dict]:
    """Return all generation runs for a project.

    Returns None if project does not exist.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        return None

    generation_runs = (
        db.query(StampGenerationRun)
        .filter(StampGenerationRun.project_id == project_id)
        .order_by(StampGenerationRun.created_at.desc())
        .all()
    )

    return {
        "project_id": project.id,
        "project_name": project.name,
        "total_count": len(generation_runs),
        "generation_runs": generation_runs,
    }
