"""P33L one-click real-run API router.

Provides four endpoints, all gated by the P33L-Authorized-Manifest-SHA header:
  POST /api/v1/p33l/real-run
  GET  /api/v1/p33l/jobs/{job_id}
  POST /api/v1/p33l/jobs/{job_id}/cancel
  GET  /api/v1/p33l/jobs/{job_id}/download/{file_path:path}

The router never runs a model unless the manifest SHA matches the env var set
at dev backend startup.  It delegates all execution to P33LOrchestrator.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.services.p33l import P33LOrchestrator, safe_relative_path
from app.services.p33l.config import ordered_model_ids

router = APIRouter(prefix="/api/v1/p33l", tags=["p33l"])

# Global orchestrator keyed by manifest SHA.
_orchestrators: dict[str, P33LOrchestrator] = {}


def _authorized_manifest_sha() -> str | None:
    return os.environ.get("P33L_AUTHORIZED_MANIFEST_SHA")


def _get_orchestrator(manifest_sha: str) -> P33LOrchestrator:
    if manifest_sha not in _orchestrators:
        _orchestrators[manifest_sha] = P33LOrchestrator(manifest_sha=manifest_sha)
    return _orchestrators[manifest_sha]


def _is_authorized(manifest_sha: str) -> bool:
    expected = _authorized_manifest_sha()
    return expected is not None and expected == manifest_sha


class RealRunRequest(BaseModel):
    model_id: str
    input: dict = {}


@router.post("/real-run")
async def p33l_real_run(
    req: RealRunRequest,
    p33l_manifest_sha: str = Header(..., alias="P33L-Authorized-Manifest-SHA"),
) -> JSONResponse:
    """Create and start a P33L real-run job for the next allowed model."""
    if not _is_authorized(p33l_manifest_sha):
        raise HTTPException(status_code=403, detail="P33L manifest SHA not authorized")

    orch = _get_orchestrator(p33l_manifest_sha)
    try:
        job = orch.create_job(req.model_id, req.input)
        # Run synchronously within the request; in production this would be a worker task.
        orch.run_job(job, req.input)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Internal error: {exc}")

    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "data": {
                "job_id": job.job_id,
                "model_id": job.model_id,
                "status": job.status,
                "run_dir": job.run_dir,
            },
        },
    )


@router.get("/jobs/{job_id}")
async def p33l_job_status(
    job_id: str,
    p33l_manifest_sha: str = Header(..., alias="P33L-Authorized-Manifest-SHA"),
) -> JSONResponse:
    """Return the current status of a P33L job."""
    if not _is_authorized(p33l_manifest_sha):
        raise HTTPException(status_code=403, detail="P33L manifest SHA not authorized")

    orch = _get_orchestrator(p33l_manifest_sha)
    job = orch.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(status_code=200, content={"code": 200, "data": job.to_dict()})


@router.post("/jobs/{job_id}/cancel")
async def p33l_cancel_job(
    job_id: str,
    p33l_manifest_sha: str = Header(..., alias="P33L-Authorized-Manifest-SHA"),
) -> JSONResponse:
    """Cancel a running P33L job by its recorded PID."""
    if not _is_authorized(p33l_manifest_sha):
        raise HTTPException(status_code=403, detail="P33L manifest SHA not authorized")

    orch = _get_orchestrator(p33l_manifest_sha)
    try:
        job = orch.cancel_job(job_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Cancel failed: {exc}")

    return JSONResponse(status_code=200, content={"code": 200, "data": job.to_dict()})


@router.get("/jobs/{job_id}/download/{file_path:path}", response_model=None)
async def p33l_download(
    job_id: str,
    file_path: str,
    p33l_manifest_sha: str = Header(None, alias="P33L-Authorized-Manifest-SHA"),
    manifest_sha: str = None,
):
    """Download a file from the job run directory with whitelist checks.

    The manifest SHA may be supplied either via the P33L-Authorized-Manifest-SHA
    header or as a manifest_sha query parameter (needed for plain <a> downloads).
    """
    effective_sha = p33l_manifest_sha or manifest_sha
    if not effective_sha or not _is_authorized(effective_sha):
        raise HTTPException(status_code=403, detail="P33L manifest SHA not authorized")

    orch = _get_orchestrator(p33l_manifest_sha)
    job = orch.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    run_dir = job.run_dir
    try:
        abs_path = safe_relative_path(run_dir, file_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not os.path.isfile(abs_path):
        raise HTTPException(status_code=404, detail="File not found")

    # For failed jobs, restrict downloads to logs/ and manifest/
    if job.status != "succeeded":
        rel = Path(abs_path).relative_to(Path(run_dir).resolve()).as_posix()
        if not (rel.startswith("logs/") or rel.startswith("manifest/")):
            raise HTTPException(
                status_code=403,
                detail="Failed jobs only allow log and manifest downloads",
            )

    return FileResponse(abs_path)


@router.get("/authorized")
async def p33l_authorized() -> JSONResponse:
    """Return whether P33L real runs are authorized on this backend.

    If authorized, the manifest SHA is exposed so the frontend can include it
    in subsequent P33L-Authorized-Manifest-SHA headers. The SHA itself is the
    user-facing authorization token; it is not a backend secret.
    """
    sha = _authorized_manifest_sha()
    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "data": {
                "authorized": sha is not None and sha != "",
                "manifest_sha": sha,
            },
        },
    )


@router.get("/status")
async def p33l_status(
    p33l_manifest_sha: str = Header(..., alias="P33L-Authorized-Manifest-SHA"),
) -> JSONResponse:
    """Return the P33L session status without running anything."""
    if not _is_authorized(p33l_manifest_sha):
        raise HTTPException(status_code=403, detail="P33L manifest SHA not authorized")

    orch = _get_orchestrator(p33l_manifest_sha)
    completed = []
    failed = None
    for model_id in ordered_model_ids():
        attempts = orch.state.get_attempts(model_id)
        if attempts:
            last = attempts[-1]
            if last.get("status") == "succeeded":
                completed.append(model_id)
            else:
                failed = model_id
                break

    return JSONResponse(
        status_code=200,
        content={
            "code": 200,
            "data": {
                "authorized": True,
                "completed_models": completed,
                "failed_model": failed,
                "next_model": orch._next_allowed_model(),
                "total_jobs": len(orch.jobs),
            },
        },
    )
