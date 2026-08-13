"""
STAMP Platform — Pipeline Runs Router (v1.6 P0)

REST API for creating, running, and monitoring automated pipeline executions.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.schemas import ApiResponse
from app.services.pipeline_orchestrator import (
    create_pipeline_run,
    create_pipeline_zip,
    get_pipeline_status,
    list_pipeline_artifacts,
    retry_pipeline_from_step,
    run_pipeline_once,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/pipeline-runs", tags=["Pipeline Runs"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class PipelineRunCreate(BaseModel):
    project_id: str | None = Field(None, description="Optional project ID")
    target_name: str = Field(..., min_length=1, max_length=255)
    target_sequence: str = Field(..., min_length=10, max_length=5000)
    mode: str = Field("run_all", description="'run_all' or 'create_only'")
    top_epitopes: int = Field(20, ge=1, le=100)
    peptides_per_epitope: int = Field(5, ge=1, le=20)
    top_stamp_candidates: int = Field(100, ge=1, le=500)
    # P0 unified-workbench params (minimal backward-compatible addition).
    # Accepted and persisted into pipeline_runs.output_json; the orchestrator is
    # NOT modified (still uses the deterministic curated baseline). Real ML model
    # execution remains gated (REAL_RUN_GATE_CLOSED).
    selected_models: list[str] | None = Field(None, description="Selected targeting-peptide model ids, e.g. ['pepmlm','evobind2']")
    epitope_type: str | None = Field(None, description="'b_cell' or 't_cell'")
    run_mode: str | None = Field(None, description="'auto' or 'semi_auto'")
    epitope_filters: dict[str, Any] | None = Field(None, description="6-layer epitope filter config (recorded only, not yet applied)")


class PipelineRunResponse(BaseModel):
    id: str
    project_id: str | None
    target_name: str
    status: str
    current_step: str
    created_at: str
    updated_at: str
    error_message: str | None


class PipelineRunListResponse(BaseModel):
    items: list[PipelineRunResponse]
    total: int


class PipelineStepSummary(BaseModel):
    step_name: str
    status: str
    started_at: str | None
    finished_at: str | None
    method: str | None
    output_summary: dict[str, Any]


class PipelineStatusResponse(BaseModel):
    run_id: str
    target_name: str
    status: str
    current_step: str
    error_message: str | None
    created_at: str
    updated_at: str
    steps: list[PipelineStepSummary]


class PipelineRetryRequest(BaseModel):
    from_step: str = Field(..., description="Step name to retry from")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiResponse[PipelineRunResponse])
def create_run(
    body: PipelineRunCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Create a new pipeline run. If mode='run_all', start execution in background."""
    run = create_pipeline_run(
        db=db,
        project_id=body.project_id,
        target_name=body.target_name,
        target_sequence=body.target_sequence,
    )

    # Persist unified-workbench request params into the existing output_json
    # JSON column (no schema migration). The orchestrator itself is unchanged.
    if body.selected_models or body.epitope_type or body.run_mode or body.epitope_filters:
        existing = dict(run.output_json or {})
        existing["request"] = {
            "selected_models": body.selected_models,
            "epitope_type": body.epitope_type,
            "run_mode": body.run_mode,
            "epitope_filters": body.epitope_filters,
        }
        run.output_json = existing
        db.commit()
        db.refresh(run)

    if body.mode == "run_all":
        background_tasks.add_task(
            _run_pipeline_bg,
            run.id,
            body.top_epitopes,
            body.peptides_per_epitope,
            body.top_stamp_candidates,
        )

    return ApiResponse.success(data=_run_to_response(run))


@router.get("", response_model=ApiResponse[PipelineRunListResponse])
def list_runs(
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List pipeline runs with optional filtering."""
    from app.models.orm import PipelineRun

    q = db.query(PipelineRun)
    if project_id:
        q = q.filter(PipelineRun.project_id == project_id)
    if status:
        q = q.filter(PipelineRun.status == status)
    total = q.count()
    runs = q.order_by(PipelineRun.created_at.desc()).offset(offset).limit(limit).all()

    return ApiResponse.success(
        data=PipelineRunListResponse(
            items=[_run_to_response(r) for r in runs],
            total=total,
        )
    )


@router.get("/{run_id}", response_model=ApiResponse[PipelineStatusResponse])
def get_run(run_id: str, db: Session = Depends(get_db)):
    """Get full pipeline run status with step details."""
    try:
        status = get_pipeline_status(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse.success(data=PipelineStatusResponse(**status))


@router.get("/{run_id}/steps", response_model=ApiResponse[list[PipelineStepSummary]])
def get_steps(run_id: str, db: Session = Depends(get_db)):
    """Get step list for a pipeline run."""
    try:
        status = get_pipeline_status(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse.success(data=status["steps"])


@router.post("/{run_id}/run", response_model=ApiResponse[PipelineRunResponse])
def run_pipeline(
    run_id: str,
    background_tasks: BackgroundTasks,
    top_epitopes: int = Query(20, ge=1, le=100),
    peptides_per_epitope: int = Query(5, ge=1, le=20),
    top_stamp_candidates: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Trigger pipeline execution for an existing run."""
    from app.models.orm import PipelineRun

    run = db.query(PipelineRun).filter(PipelineRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    if run.status == "RUNNING":
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    background_tasks.add_task(
        _run_pipeline_bg,
        run_id,
        top_epitopes,
        peptides_per_epitope,
        top_stamp_candidates,
    )

    run.status = "RUNNING"
    db.commit()
    db.refresh(run)
    return ApiResponse.success(data=_run_to_response(run))


@router.post("/{run_id}/retry", response_model=ApiResponse[PipelineRunResponse])
def retry_pipeline(
    run_id: str,
    body: PipelineRetryRequest,
    background_tasks: BackgroundTasks,
    top_epitopes: int = Query(20, ge=1, le=100),
    peptides_per_epitope: int = Query(5, ge=1, le=20),
    top_stamp_candidates: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Retry pipeline from a specific step."""
    try:
        run = retry_pipeline_from_step(db, run_id, body.from_step)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    background_tasks.add_task(
        _run_pipeline_bg,
        run_id,
        top_epitopes,
        peptides_per_epitope,
        top_stamp_candidates,
    )
    return ApiResponse.success(data=_run_to_response(run))


@router.get("/{run_id}/artifacts", response_model=ApiResponse[list[dict[str, Any]]])
def list_artifacts(run_id: str):
    """List artifact files for a pipeline run."""
    try:
        files = list_pipeline_artifacts(run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ApiResponse.success(data=files)


@router.get("/{run_id}/report", response_model=ApiResponse[dict[str, Any]])
def get_report(run_id: str):
    """Get pipeline report (JSON and markdown paths)."""
    import os
    from app.services.pipeline_orchestrator import _artifact_dir

    base = _artifact_dir(run_id)
    report_dir = os.path.join(base, "report_export")
    report_json = os.path.join(report_dir, "pipeline_report.json")
    report_md = os.path.join(report_dir, "pipeline_report.md")
    result: dict[str, Any] = {"run_id": run_id}
    if os.path.exists(report_json):
        import json
        with open(report_json, "r", encoding="utf-8") as f:
            result["report_data"] = json.load(f)
    if os.path.exists(report_md):
        with open(report_md, "r", encoding="utf-8") as f:
            result["report_markdown"] = f.read()
    return ApiResponse.success(data=result)


@router.get("/{run_id}/artifacts/download")
def download_artifact(run_id: str, path: str = Query(..., description="Relative artifact path")):
    """Download a single artifact file by relative path."""
    from app.services.pipeline_orchestrator import _artifact_dir

    base = _artifact_dir(run_id)
    file_path = os.path.join(base, path)
    # Security: ensure path is within base directory
    real_base = os.path.realpath(base)
    real_file = os.path.realpath(file_path)
    if not real_file.startswith(real_base + os.sep) and real_file != real_base:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not os.path.isfile(real_file):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        real_file,
        media_type="application/octet-stream",
        filename=os.path.basename(real_file),
    )


@router.get("/{run_id}/download")
def download_artifacts(run_id: str):
    """Download all pipeline artifacts as a zip file."""
    from fastapi.responses import FileResponse

    try:
        zip_path = create_pipeline_zip(run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Artifacts zip not found")

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"pipeline_{run_id}_artifacts.zip",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_to_response(run: Any) -> PipelineRunResponse:
    return PipelineRunResponse(
        id=run.id,
        project_id=run.project_id,
        target_name=run.target_name,
        status=run.status,
        current_step=run.current_step,
        created_at=run.created_at.isoformat() if run.created_at else None,
        updated_at=run.updated_at.isoformat() if run.updated_at else None,
        error_message=run.error_message,
    )


def _run_pipeline_bg(
    run_id: str,
    top_epitopes: int,
    peptides_per_epitope: int,
    top_stamp_candidates: int,
) -> None:
    """Background task wrapper for pipeline execution."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        run_pipeline_once(
            db=db,
            run_id=run_id,
            top_epitopes=top_epitopes,
            peptides_per_epitope=peptides_per_epitope,
            top_stamp_candidates=top_stamp_candidates,
        )
    except Exception:
        logger.exception("Background pipeline run %s failed", run_id)
    finally:
        db.close()
