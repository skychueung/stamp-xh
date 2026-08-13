"""
STAMP Demo Overview router (read-only).

Purpose
-------
Provides a single read-only endpoint that serves the "golden run" pipeline data
to the demo mainline (old pages wired to pipeline-runs). This is a 止口
(stop-the-bleeding) measure so the demo shows REAL database data instead of
silently falling back to mock placeholders.

Constraints
-----------
* Read-only. No DB writes, no migrations.
* Uses the existing `engine` (resolves to the configured stamp_database_url,
  which currently points at data_dev/db/stamp_dev.db containing golden run
  dcfeea4b).
* Does NOT touch p33u / p33t / pipeline-runs routers.
* All data is tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.

Endpoint
--------
GET /api/v1/demo/overview?run_id=<auto>&source_model=<all>
"""

from __future__ import annotations

import json
import os
from typing import Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from app.database import engine
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/demo", tags=["Demo"])

PREDICTION_TAG = "COMPUTATIONAL_PREDICTION_ONLY"
VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"

# Pinned golden run for the demo mainline. The shared live stamp_dev.db is
# actively written to, so "auto-pick newest" is unstable (a junk test run can
# win the tiebreak). Pin the curated golden run; fall back to auto-pick only
# if the pinned run is missing. Override via STAMP_GOLDEN_RUN_ID env.
GOLDEN_RUN_ID = os.environ.get(
    "STAMP_GOLDEN_RUN_ID", "dcfeea4b-a51f-4963-af3f-1ea2364e6936"
)


def _parse_metrics(raw: Any) -> dict:
    """stamp_candidates.metrics / epitope_candidates.metrics is a JSON text column."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _truncate(seq: str | None, n: int = 220) -> str:
    if not seq:
        return ""
    return seq if len(seq) <= n else seq[:n] + "…"


def _pick_golden_run(conn) -> dict | None:
    """Auto-select the SUCCEEDED run with the most stamp_candidates (tie-break: newest)."""
    sql = text(
        """
        SELECT pr.id, pr.project_id, pr.target_name, pr.target_sequence,
               pr.status, pr.current_step, pr.created_at
        FROM pipeline_runs pr
        WHERE pr.status = 'SUCCEEDED'
        ORDER BY (
            SELECT COUNT(*) FROM stamp_candidates sc
            WHERE sc.project_id = pr.project_id
        ) DESC, pr.created_at DESC
        LIMIT 1
        """
    )
    row = conn.execute(sql).mappings().first()
    return dict(row) if row else None


def _get_golden_run(conn) -> dict | None:
    """Resolve the demo golden run: pinned GOLDEN_RUN_ID if it exists &
    succeeded, else fall back to auto-pick (most stamp_candidates, newest)."""
    if GOLDEN_RUN_ID:
        run = _get_run(conn, GOLDEN_RUN_ID)
        if run and run.get("status") == "SUCCEEDED":
            return run
    return _pick_golden_run(conn)


def _get_run(conn, run_id: str) -> dict | None:
    sql = text(
        """
        SELECT id, project_id, target_name, target_sequence, status,
               current_step, created_at
        FROM pipeline_runs WHERE id = :rid
        """
    )
    row = conn.execute(sql, {"rid": run_id}).mappings().first()
    return dict(row) if row else None


def _epitope_candidates(conn, project_id: str) -> list[dict]:
    sql = text(
        """
        SELECT ec.id, ec.start, ec.end, ec.sequence, ec.net_charge,
               ec.hydrophobicity, ec.pi, ec.cys_count,
               ec.surface_exposure_score, ec.ranking_score, ec.metrics
        FROM epitope_candidates ec
        JOIN epitope_scans es ON ec.scan_id = es.id
        WHERE es.project_id = :pid
        ORDER BY ec.ranking_score DESC
        """
    )
    rows = conn.execute(sql, {"pid": project_id}).mappings().all()
    out = []
    for r in rows:
        m = _parse_metrics(r.get("metrics"))
        out.append(
            {
                "id": r.get("id"),
                "start": r.get("start"),
                "end": r.get("end"),
                "sequence": r.get("sequence"),
                "net_charge": r.get("net_charge"),
                "hydrophobicity": r.get("hydrophobicity"),
                "pi": r.get("pi"),
                "cys_count": r.get("cys_count"),
                "surface_exposure_score": r.get("surface_exposure_score"),
                "ranking_score": r.get("ranking_score"),
                "accessibility_score": m.get("accessibility_score") or m.get("surface_exposure_score"),
            }
        )
    return out


def _source_models(conn, project_id: str) -> list[dict]:
    sql = text(
        """
        SELECT sgr.generator_name, sgr.generator_version, COUNT(sc.id) AS cnt
        FROM stamp_generation_runs sgr
        LEFT JOIN stamp_candidates sc ON sc.generation_run_id = sgr.id
        WHERE sgr.project_id = :pid
        GROUP BY sgr.generator_name, sgr.generator_version
        ORDER BY cnt DESC
        """
    )
    rows = conn.execute(sql, {"pid": project_id}).mappings().all()
    return [
        {
            "name": r.get("generator_name"),
            "version": r.get("generator_version"),
            "count": int(r.get("cnt") or 0),
        }
        for r in rows
    ]


def _stamp_candidates(conn, project_id: str, source_model: str | None) -> list[dict]:
    base = (
        "SELECT sc.id, sc.full_sequence, sc.targeting_peptide_seq, sc.linker_seq, "
        "sc.composite_score, sc.validation_status, sc.metrics, sc.created_at, "
        "sgr.generator_name AS source_model "
        "FROM stamp_candidates sc "
        "LEFT JOIN stamp_generation_runs sgr ON sc.generation_run_id = sgr.id "
        "WHERE sc.project_id = :pid"
    )
    params: dict[str, Any] = {"pid": project_id}
    if source_model and source_model.lower() != "all":
        base += " AND sgr.generator_name = :sm"
        params["sm"] = source_model
    base += " ORDER BY sc.composite_score DESC LIMIT 100"
    rows = conn.execute(text(base), params).mappings().all()
    out = []
    for r in rows:
        m = _parse_metrics(r.get("metrics"))
        out.append(
            {
                "id": r.get("id"),
                "full_sequence": r.get("full_sequence"),
                "targeting_peptide_seq": r.get("targeting_peptide_seq"),
                "linker_seq": r.get("linker_seq"),
                "composite_score": r.get("composite_score"),
                "length": m.get("total_length") or m.get("length"),
                "net_charge": m.get("net_charge") if m.get("net_charge") is not None else r.get("net_charge"),
                "hydrophobicity": m.get("hydrophobic_ratio") if m.get("hydrophobic_ratio") is not None else m.get("hydrophobicity"),
                "source_model": r.get("source_model"),
                "functional_peptide_source": m.get("functional_peptide_source"),
                "functional_peptide_name": m.get("functional_peptide_name"),
                "linker_type": m.get("linker_type"),
                "validation_status": r.get("validation_status") or VALIDATION_STATUS,
                "created_at": str(r.get("created_at")) if r.get("created_at") else None,
            }
        )
    return out


@router.get("/overview", response_model=ApiResponse[dict])
def demo_overview(
    run_id: str | None = Query(None, description="Pipeline run id; omit to use pinned golden run (dcfeea4b)"),
    source_model: str = Query("all", description="Filter stamp_candidates by generator_name; 'all' returns all"),
) -> ApiResponse[dict]:
    """Return a read-only overview of a pipeline run for the demo mainline.

    Data is REAL database data (not mock). Tagged NOT_EXPERIMENTALLY_VALIDATED.
    """
    with engine.connect() as conn:
        run = _get_run(conn, run_id) if run_id else _get_golden_run(conn)
        if not run:
            return ApiResponse.success(
                data={
                    "data_source": "empty",
                    "run_id": run_id,
                    "message": "No matching pipeline run found.",
                    "epitope_candidate_count": 0,
                    "epitope_candidates": [],
                    "stamp_candidate_count": 0,
                    "source_models": [],
                    "stamp_candidates": [],
                    "selected_source_model": source_model,
                    "validation_status": VALIDATION_STATUS,
                    "prediction_tag": PREDICTION_TAG,
                }
            )

        project_id = run.get("project_id")
        epi = _epitope_candidates(conn, project_id) if project_id else []
        models = _source_models(conn, project_id) if project_id else []
        stam = _stamp_candidates(conn, project_id, source_model) if project_id else []

        data = {
            "data_source": "real_db",
            "run_id": run.get("id"),
            "project_id": project_id,
            "target_name": run.get("target_name"),
            "target_sequence": _truncate(run.get("target_sequence")),
            "target_sequence_length": len(run.get("target_sequence") or ""),
            "status": run.get("status"),
            "current_step": run.get("current_step"),
            "created_at": str(run.get("created_at")) if run.get("created_at") else None,
            "epitope_candidate_count": len(epi),
            "epitope_candidates": epi,
            "stamp_candidate_count": len(stam),
            "stamp_candidate_total_for_run": _stamp_count_total(conn, project_id),
            "source_models": models,
            "stamp_candidates": stam,
            "selected_source_model": source_model,
            "validation_status": VALIDATION_STATUS,
            "prediction_tag": PREDICTION_TAG,
            "disclosure": (
                "Real pipeline-run data from SQLite. Generator is a deterministic "
                "curated baseline, NOT a trained ML model. Computational prediction "
                "only; NOT experimentally validated."
            ),
        }
        return ApiResponse.success(data=data)


def _stamp_count_total(conn, project_id: str) -> int:
    if not project_id:
        return 0
    row = conn.execute(
        text("SELECT COUNT(*) FROM stamp_candidates WHERE project_id = :pid"),
        {"pid": project_id},
    ).first()
    return int(row[0]) if row else 0
