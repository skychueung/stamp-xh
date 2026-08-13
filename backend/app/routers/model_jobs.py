"""Unified five-model job API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm import Job
from app.models.schemas import ApiResponse
from app.services.unified_model_runtime import (
    MODEL_JOB_PREFIX,
    cancel_model_job,
    list_job_artifacts,
    process_model_job,
    read_job_logs,
    resolve_job_artifact,
    submit_model_job,
)

router = APIRouter(prefix="/api/v1", tags=["Production model jobs"])


def _job(db: Session, job_id: str) -> Job:
    job = db.query(Job).filter(Job.id == job_id, Job.job_type.like(f"{MODEL_JOB_PREFIX}%")).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Model job not found")
    return job


def _response(job: Job) -> dict[str, Any]:
    meta = job.input_json or {}
    return {
        "job_id": job.id,
        "run_id": meta.get("run_id"),
        "model_id": meta.get("model_id"),
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
        "error": job.error_json,
        "result": job.output_json,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }


@router.post("/models/{model_id}/jobs")
def submit(model_id: str, body: dict[str, Any],
           sync: bool = Query(False), db: Session = Depends(get_db)):
    try:
        payload = dict(body.get("payload") or body)
        job = submit_model_job(db, model_id, payload, project_id=str(body.get("project_id", "production_models")),
                               run_id=body.get("run_id"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if sync:
        process_model_job(db, job)
    return ApiResponse.success(data=_response(job))


@router.post("/model-runs")
def submit_combined(body: dict[str, Any], db: Session = Depends(get_db)):
    selected = list(body.get("selected_models") or [])
    if not selected:
        raise HTTPException(status_code=422, detail="selected_models is required")
    run_id = str(body.get("run_id") or "") or None
    jobs = []
    for model_id in selected:
        job = submit_model_job(db, model_id, body, project_id=str(body.get("project_id", "production_models")), run_id=run_id)
        run_id = (job.input_json or {}).get("run_id")
        jobs.append(job)
    return ApiResponse.success(data={"run_id": run_id, "jobs": [_response(job) for job in jobs]})


@router.get("/jobs/{job_id}/model-status")
def status(job_id: str, db: Session = Depends(get_db)):
    return ApiResponse.success(data=_response(_job(db, job_id)))


@router.get("/model-jobs/{job_id}")
def model_job(job_id: str, db: Session = Depends(get_db)):
    """Unambiguous canonical status endpoint for unified model jobs."""
    return ApiResponse.success(data=_response(_job(db, job_id)))


@router.get("/jobs/{job_id}")
def canonical_job(job_id: str, db: Session = Depends(get_db)):
    """Canonical unified status endpoint required by the production API contract."""
    return ApiResponse.success(data=_response(_job(db, job_id)))


@router.post("/jobs/{job_id}/model-cancel")
def cancel(job_id: str, db: Session = Depends(get_db)):
    return ApiResponse.success(data=_response(cancel_model_job(db, _job(db, job_id))))


@router.get("/jobs/{job_id}/logs")
def logs(job_id: str, after_id: int = Query(0, ge=0), limit: int = Query(200, ge=1, le=2000),
         level: str | None = None, model_id: str | None = None, db: Session = Depends(get_db)):
    job = _job(db, job_id)
    return ApiResponse.success(data={"job_id": job.id, "records": read_job_logs(job, after_id=after_id, limit=limit, level=level, model_id=model_id)})


@router.get("/jobs/{job_id}/artifacts")
def artifacts(job_id: str, db: Session = Depends(get_db)):
    job = _job(db, job_id)
    return ApiResponse.success(data={"job_id": job.id, "artifacts": list_job_artifacts(job)})


@router.get("/jobs/{job_id}/artifacts/download")
def download_artifact(job_id: str, path: str = Query(...), db: Session = Depends(get_db)):
    job = _job(db, job_id)
    try:
        artifact = resolve_job_artifact(job, path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Artifact not found") from exc
    return FileResponse(artifact, filename=artifact.name)


@router.get("/runs/{run_id}/jobs")
def run_jobs(run_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.job_type.like(f"{MODEL_JOB_PREFIX}%")).order_by(Job.created_at).all()
    return ApiResponse.success(data={"run_id": run_id, "jobs": [_response(job) for job in jobs if (job.input_json or {}).get("run_id") == run_id]})


@router.get("/runs/{run_id}")
def run_status(run_id: str, db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.job_type.like(f"{MODEL_JOB_PREFIX}%")).order_by(Job.created_at).all()
    matched = [job for job in jobs if (job.input_json or {}).get("run_id") == run_id]
    if not matched:
        raise HTTPException(status_code=404, detail="Model run not found")
    states = {job.status for job in matched}
    if states <= {"SUCCEEDED"}:
        aggregate = "SUCCEEDED"
    elif states & {"RUNNING", "PREFLIGHT", "POSTPROCESSING"}:
        aggregate = "RUNNING"
    elif states & {"CREATED", "QUEUED", "RECOVERING"}:
        aggregate = "QUEUED"
    elif states <= {"CANCELLED"}:
        aggregate = "CANCELLED"
    else:
        aggregate = "PARTIAL"
    return ApiResponse.success(data={"run_id": run_id, "status": aggregate,
                                     "jobs": [_response(job) for job in matched]})


@router.get("/runs/{run_id}/logs")
def run_logs(run_id: str, after_id: int = Query(0, ge=0), limit: int = Query(500, ge=1, le=5000),
             level: str | None = None, model_id: str | None = None,
             db: Session = Depends(get_db)):
    jobs = db.query(Job).filter(Job.job_type.like(f"{MODEL_JOB_PREFIX}%")).order_by(Job.created_at).all()
    records = []
    for job in jobs:
        if (job.input_json or {}).get("run_id") != run_id:
            continue
        records.extend(read_job_logs(job, after_id=after_id, limit=limit, level=level, model_id=model_id))
    records.sort(key=lambda record: (record.get("timestamp", ""), record.get("job_id", ""), record.get("id", 0)))
    return ApiResponse.success(data={"run_id": run_id, "records": records[:limit]})
