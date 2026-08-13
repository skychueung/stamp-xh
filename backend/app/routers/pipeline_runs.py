"""
STAMP Platform — Pipeline Runs Router (v1.6 P0)

REST API for creating, running, and monitoring automated pipeline executions.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.limiter import limiter
from app.core.security import require_active, validate_csrf
from app.models.user import User
from app.models.schemas import ApiResponse
from app.services.pipeline_orchestrator import (
    create_pipeline_run,
    create_pipeline_zip,
    get_pipeline_status,
    list_pipeline_artifacts,
    read_pipeline_log,
    retry_pipeline_from_step,
)
from app.services.pipeline_artifacts import resolve_artifact
from app.workers.pipeline_worker import enqueue_pipeline

router = APIRouter(prefix="/api/v1/pipeline-runs", tags=["Pipeline Runs"])


def _owned_run(db: Session, run_id: str, user: User):
    from app.models.orm import PipelineRun

    query = db.query(PipelineRun).filter(PipelineRun.id == run_id)
    if user.role != "admin":
        query = query.filter(PipelineRun.created_by == user.id)
    run = query.first()
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline run not found")
    return run


def _csrf(request: Request) -> None:
    validate_csrf(request)


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


class PipelineLogRecord(BaseModel):
    timestamp: str | None
    level: str
    run_id: str
    step: str | None
    model_id: str | None = None
    request_id: str | None = None
    message: str
    exception_trace: str | None = None


class PipelineLogResponse(BaseModel):
    run_id: str
    records: list[PipelineLogRecord]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=ApiResponse[PipelineRunResponse])
@limiter.limit(os.environ.get("STAMP_PIPELINE_CREATE_RATE_LIMIT", "10/minute"))
def create_run(
    request: Request,
    body: PipelineRunCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Create a new pipeline run. If mode='run_all', start execution in background."""
    if body.project_id:
        from app.models.orm import Project

        project_query = db.query(Project).filter(Project.id == body.project_id)
        if user.role != "admin":
            project_query = project_query.filter(Project.owner_id == user.id)
        if project_query.first() is None:
            raise HTTPException(status_code=404, detail="Project not found")
    run = create_pipeline_run(
        db=db,
        project_id=body.project_id,
        target_name=body.target_name,
        target_sequence=body.target_sequence,
        created_by=user.id,
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
        run = enqueue_pipeline(
            db,
            run,
            top_epitopes=body.top_epitopes,
            peptides_per_epitope=body.peptides_per_epitope,
            top_stamp_candidates=body.top_stamp_candidates,
        )

    return ApiResponse.success(data=_run_to_response(run))


@router.get("", response_model=ApiResponse[PipelineRunListResponse])
def list_runs(
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    """List pipeline runs with optional filtering."""
    from app.models.orm import PipelineRun

    q = db.query(PipelineRun)
    if user.role != "admin":
        q = q.filter(PipelineRun.created_by == user.id)
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
def get_run(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_active)):
    """Get full pipeline run status with step details."""
    try:
        _owned_run(db, run_id, user)
        status = get_pipeline_status(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse.success(data=PipelineStatusResponse(**status))


@router.get("/{run_id}/steps", response_model=ApiResponse[list[PipelineStepSummary]])
def get_steps(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_active)):
    """Get step list for a pipeline run."""
    try:
        _owned_run(db, run_id, user)
        status = get_pipeline_status(db, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return ApiResponse.success(data=status["steps"])


@router.get("/{run_id}/logs", response_model=ApiResponse[PipelineLogResponse])
def get_run_logs(
    run_id: str,
    tail: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    """Return durable execution events for one pipeline run."""

    _owned_run(db, run_id, user)
    return ApiResponse.success(
        data=PipelineLogResponse(run_id=run_id, records=read_pipeline_log(run_id, tail=tail))
    )


@router.post("/{run_id}/run", response_model=ApiResponse[PipelineRunResponse])
@limiter.limit(os.environ.get("STAMP_PIPELINE_RUN_RATE_LIMIT", "10/minute"))
def run_pipeline(
    request: Request,
    run_id: str,
    top_epitopes: int = Query(20, ge=1, le=100),
    peptides_per_epitope: int = Query(5, ge=1, le=20),
    top_stamp_candidates: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Trigger pipeline execution for an existing run."""

    run = _owned_run(db, run_id, user)
    if run.status == "RUNNING":
        raise HTTPException(status_code=409, detail="Pipeline is already running")
    if run.status == "SUCCEEDED":
        raise HTTPException(status_code=409, detail="Pipeline already succeeded; create a new run or use retry")

    run = enqueue_pipeline(
        db,
        run,
        top_epitopes=top_epitopes,
        peptides_per_epitope=peptides_per_epitope,
        top_stamp_candidates=top_stamp_candidates,
    )
    return ApiResponse.success(data=_run_to_response(run))


@router.post("/{run_id}/retry", response_model=ApiResponse[PipelineRunResponse])
@limiter.limit(os.environ.get("STAMP_PIPELINE_RETRY_RATE_LIMIT", "10/minute"))
def retry_pipeline(
    request: Request,
    run_id: str,
    body: PipelineRetryRequest,
    top_epitopes: int = Query(20, ge=1, le=100),
    peptides_per_epitope: int = Query(5, ge=1, le=20),
    top_stamp_candidates: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Retry pipeline from a specific step."""
    try:
        _owned_run(db, run_id, user)
        run = retry_pipeline_from_step(db, run_id, body.from_step)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    run = enqueue_pipeline(
        db,
        run,
        top_epitopes=top_epitopes,
        peptides_per_epitope=peptides_per_epitope,
        top_stamp_candidates=top_stamp_candidates,
    )
    return ApiResponse.success(data=_run_to_response(run))


@router.post("/{run_id}/cancel", response_model=ApiResponse[PipelineRunResponse])
@limiter.limit(os.environ.get("STAMP_PIPELINE_CANCEL_RATE_LIMIT", "20/minute"))
def cancel_pipeline(
    request: Request,
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
    _: None = Depends(_csrf),
):
    """Request cooperative cancellation; queued runs stop immediately."""
    run = _owned_run(db, run_id, user)
    if run.status in {"SUCCEEDED", "FAILED", "CANCELLED"}:
        return ApiResponse.success(data=_run_to_response(run))
    metadata = dict(run.output_json or {})
    queue = dict(metadata.get("queue") or {})
    queue["cancel_requested"] = True
    queue["cancel_requested_at"] = __import__("datetime").datetime.now(
        __import__("datetime").timezone.utc
    ).isoformat()
    if run.status == "QUEUED":
        queue["state"] = "cancelled"
        run.status = "CANCELLED"
    metadata["queue"] = queue
    run.output_json = metadata
    db.commit()
    db.refresh(run)
    from app.services.pipeline_artifacts import mark_manifest_status

    mark_manifest_status(run.id, run.status)
    return ApiResponse.success(data=_run_to_response(run))


@router.get("/{run_id}/artifacts", response_model=ApiResponse[list[dict[str, Any]]])
def list_artifacts(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_active)):
    """List artifact files for a pipeline run."""
    try:
        _owned_run(db, run_id, user)
        files = list_pipeline_artifacts(run_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return ApiResponse.success(data=files)


@router.get("/{run_id}/report", response_model=ApiResponse[dict[str, Any]])
def get_report(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_active)):
    """Get pipeline report (JSON and markdown paths)."""
    import os
    from app.services.pipeline_orchestrator import _artifact_dir

    _owned_run(db, run_id, user)
    base = _artifact_dir(run_id)
    report_dir = os.path.join(base, "steps", "report_export", "artifacts")
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
def download_artifact(
    run_id: str,
    path: str = Query(..., description="Relative artifact path"),
    db: Session = Depends(get_db),
    user: User = Depends(require_active),
):
    """Download a single artifact file by relative path."""
    _owned_run(db, run_id, user)
    try:
        real_file = resolve_artifact(run_id, path)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        str(real_file),
        media_type="application/octet-stream",
        filename=os.path.basename(real_file),
    )


@router.get("/{run_id}/download")
def download_artifacts(run_id: str, db: Session = Depends(get_db), user: User = Depends(require_active)):
    """Download all pipeline artifacts as a zip file."""
    from fastapi.responses import FileResponse

    _owned_run(db, run_id, user)
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
