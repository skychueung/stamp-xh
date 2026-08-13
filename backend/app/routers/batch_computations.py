"""Batch Computation Router (v1.5-md-computation-pilot).

Provides CRUD and operations for batch compute jobs:
- COLABFOLD / FOLDX / MMGBSA / MIXED / FLEXPEPDOCK

New in v1.5:
- Artifact listing per item
- Log reading (stdout/stderr)
- Batch ZIP download
- Aggregated report endpoint (RMSD/RMSF/Rg, score.sc, ΔG)
"""

from __future__ import annotations

import io
import logging
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm import BatchComputation, BatchComputationItem
from app.crud.batch_computations import (
    create_batch_computation,
    create_batch_item,
    get_batch_computation,
    list_batch_computations,
    list_batch_items,
    update_batch_computation_status,
    cancel_batch_computation,
    update_batch_item_status,
)
from app.models.schemas import ApiResponse
from app.services.batch_compute_runner import dispatch_batch_item, validate_job_params
from app.services.batch_dir_service import ensure_batch_dir, ensure_item_dir, get_item_log_path
from app.services.mmpbsa_result_parser import (
    parse_mmpbsa_result,
    get_mmgbsa_components,
    write_mmgbsa_summary_json,
    write_mmgbsa_components_csv,
)
from app.services.computation_report_export import (
    build_computation_report_data,
    render_computation_report_json,
    render_computation_report_markdown,
    render_computation_report_pdf,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/v1/batch-computations", tags=["Batch Computation"])

VALID_JOB_TYPES = {"COLABFOLD", "FOLDX", "MMGBSA", "MIXED", "FLEXPEPDOCK"}
VALID_ITEM_TYPES = {"COLABFOLD", "FOLDX", "MMGBSA", "FLEXPEPDOCK"}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class BatchComputationCreate(BaseModel):
    project_id: str
    name: str
    job_type: str = Field(..., description="COLABFOLD / FOLDX / MMGBSA / MIXED / FLEXPEPDOCK")
    candidate_ids: list[str] = Field(default_factory=list)
    input_json: dict = Field(default_factory=dict)
    created_by: Optional[str] = None

    @field_validator("job_type")
    @classmethod
    def validate_job_type(cls, v: str) -> str:
        if v.upper() not in VALID_JOB_TYPES:
            raise ValueError(f"job_type must be one of {sorted(VALID_JOB_TYPES)}")
        return v.upper()


class BatchComputationResponse(BaseModel):
    id: str
    project_id: str
    name: str
    job_type: str
    status: str
    artifact_dir: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BatchComputationListResponse(BaseModel):
    items: list[BatchComputationResponse]
    total: int
    limit: int
    offset: int


class BatchItemResponse(BaseModel):
    id: str
    batch_id: str
    candidate_id: Optional[str]
    job_type: str
    status: str
    error_message: Optional[str]
    artifact_dir: Optional[str]
    output_json: Optional[dict]
    created_at: datetime
    started_at: Optional[datetime]
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


class ArtifactFileResponse(BaseModel):
    name: str
    path: str
    size: int
    is_dir: bool
    modified_at: Optional[datetime]


class LogContentResponse(BaseModel):
    stdout: str
    stderr: str
    exists: bool


class BatchReportResponse(BaseModel):
    batch_id: str
    job_type: str
    status: str
    total_items: int
    succeeded_items: int
    failed_items: int
    blocked_items: int
    pending_items: int
    md_results: list[dict]
    flexpepdock_results: list[dict]
    mmgbsa_results: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=BatchComputationResponse, status_code=201)
def create_batch(
    body: BatchComputationCreate,
    db: Session = Depends(get_db),
):
    """Create a new batch computation."""
    artifact_dir = ensure_batch_dir(body.project_id + "_" + body.name.replace(" ", "_"))

    batch = create_batch_computation(
        db,
        project_id=body.project_id,
        name=body.name,
        job_type=body.job_type,
        input_json=body.input_json,
        artifact_dir=artifact_dir,
        created_by=body.created_by,
    )

    for cid in body.candidate_ids:
        item_type = body.job_type if body.job_type != "MIXED" else "COLABFOLD"
        item_dir = ensure_item_dir(batch.id, cid, item_type)
        create_batch_item(
            db,
            batch_id=batch.id,
            project_id=body.project_id,
            candidate_id=cid,
            job_type=item_type,
            input_json=body.input_json,
            artifact_dir=item_dir,
        )

    return batch


@router.get("", response_model=BatchComputationListResponse)
def list_batches(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List batch computations."""
    items, total = list_batch_computations(db, project_id=project_id, status=status, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{batch_id}", response_model=BatchComputationResponse)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Get batch computation details."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return batch


@router.get("/{batch_id}/items", response_model=list[BatchItemResponse])
def get_batch_items(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Get all items in a batch computation."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    return list_batch_items(db, batch_id)


@router.get("/{batch_id}/items/{item_id}/artifacts", response_model=list[ArtifactFileResponse])
def get_item_artifacts(
    batch_id: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """List artifact files for a specific batch item."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    item = db.query(BatchComputationItem).filter(
        BatchComputationItem.id == item_id,
        BatchComputationItem.batch_id == batch_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    artifact_dir = item.artifact_dir
    if not artifact_dir or not Path(artifact_dir).exists():
        return []

    results = []
    for root, dirs, files in os.walk(artifact_dir):
        for d in dirs:
            p = Path(root) / d
            rel = p.relative_to(artifact_dir).as_posix()
            stat = p.stat()
            results.append(ArtifactFileResponse(
                name=d,
                path=rel,
                size=0,
                is_dir=True,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            ))
        for f in files:
            p = Path(root) / f
            rel = p.relative_to(artifact_dir).as_posix()
            stat = p.stat()
            results.append(ArtifactFileResponse(
                name=f,
                path=rel,
                size=stat.st_size,
                is_dir=False,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            ))
    return sorted(results, key=lambda x: (not x.is_dir, x.path))


@router.get("/{batch_id}/items/{item_id}/logs", response_model=LogContentResponse)
def get_item_logs(
    batch_id: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """Read stdout/stderr logs for a batch item."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    item = db.query(BatchComputationItem).filter(
        BatchComputationItem.id == item_id,
        BatchComputationItem.batch_id == batch_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    log_path = get_item_log_path(batch_id, item_id, item.job_type)
    stdout_text = ""
    stderr_text = ""
    exists = False

    if Path(log_path).exists():
        exists = True
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                stdout_text = f.read()
        except Exception as e:
            stdout_text = f"[Error reading log: {e}]"

    stderr_path = str(Path(log_path).with_suffix(".stderr.log"))
    if Path(stderr_path).exists():
        try:
            with open(stderr_path, "r", encoding="utf-8", errors="replace") as f:
                stderr_text = f.read()
        except Exception as e:
            stderr_text = f"[Error reading stderr: {e}]"

    return LogContentResponse(stdout=stdout_text, stderr=stderr_text, exists=exists)


@router.get("/{batch_id}/report", response_model=BatchReportResponse)
def get_batch_report(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Get aggregated report for a batch computation."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = list_batch_items(db, batch_id)
    total = len(items)
    succeeded = sum(1 for i in items if i.status == "SUCCEEDED")
    failed = sum(1 for i in items if i.status == "FAILED")
    blocked = sum(1 for i in items if i.status == "BLOCKED")
    pending = sum(1 for i in items if i.status == "PENDING")

    md_results = []
    flexpepdock_results = []
    mmgbsa_results = []

    for item in items:
        artifact_dir = item.artifact_dir
        dir_exists = artifact_dir and Path(artifact_dir).exists()

        if item.job_type == "FLEXPEPDOCK":
            score_sc = None
            if dir_exists:
                candidates = list(Path(artifact_dir).rglob("score_*.sc"))
                if candidates:
                    score_sc = str(candidates[0].relative_to(artifact_dir))
            flexpepdock_results.append({
                "item_id": item.id,
                "candidate_id": item.candidate_id,
                "status": item.status,
                "score_sc_exists": score_sc is not None,
                "score_sc_path": score_sc,
                "output_json": item.output_json or {},
            })

        elif item.job_type == "MMGBSA":
            dg_file = None
            if dir_exists:
                candidates = (
                    list(Path(artifact_dir).rglob("*FINAL*"))
                    + list(Path(artifact_dir).rglob("*dg*"))
                    + list(Path(artifact_dir).rglob("*delta*"))
                )
                if candidates:
                    dg_file = str(candidates[0].relative_to(artifact_dir))
            mmgbsa_results.append({
                "item_id": item.id,
                "candidate_id": item.candidate_id,
                "status": item.status,
                "dg_file_exists": dg_file is not None,
                "dg_file_path": dg_file,
                "output_json": item.output_json or {},
            })

        elif item.job_type in ("COLABFOLD", "FOLDX"):
            rmsd_file = None
            rmsf_file = None
            rg_file = None
            if dir_exists:
                for p in Path(artifact_dir).rglob("*"):
                    name_lower = p.name.lower()
                    if "rmsd" in name_lower:
                        rmsd_file = str(p.relative_to(artifact_dir))
                    elif "rmsf" in name_lower:
                        rmsf_file = str(p.relative_to(artifact_dir))
                    elif "rg" in name_lower or "gyration" in name_lower or "radius" in name_lower:
                        rg_file = str(p.relative_to(artifact_dir))
            md_results.append({
                "item_id": item.id,
                "candidate_id": item.candidate_id,
                "status": item.status,
                "rmsd_file_exists": rmsd_file is not None,
                "rmsd_file_path": rmsd_file,
                "rmsf_file_exists": rmsf_file is not None,
                "rmsf_file_path": rmsf_file,
                "rg_file_exists": rg_file is not None,
                "rg_file_path": rg_file,
                "output_json": item.output_json or {},
            })

    return BatchReportResponse(
        batch_id=batch_id,
        job_type=batch.job_type,
        status=batch.status,
        total_items=total,
        succeeded_items=succeeded,
        failed_items=failed,
        blocked_items=blocked,
        pending_items=pending,
        md_results=md_results,
        flexpepdock_results=flexpepdock_results,
        mmgbsa_results=mmgbsa_results,
    )


@router.get("/{batch_id}/download")
def download_batch_artifacts(
    batch_id: str,
    format: str = Query("zip", pattern="^(zip|json|csv|md)$"),
    db: Session = Depends(get_db),
):
    """Download batch artifacts as ZIP, or export report as JSON/CSV/Markdown."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = list_batch_items(db, batch_id)

    if format == "zip":
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                if item.artifact_dir and Path(item.artifact_dir).exists():
                    for root, dirs, files in os.walk(item.artifact_dir):
                        for f in files:
                            file_path = Path(root) / f
                            arcname = f"{item.id}/{file_path.relative_to(item.artifact_dir).as_posix()}"
                            zf.write(file_path, arcname)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.zip"},
        )

    elif format == "json":
        import json
        report_data = {
            "batch": {
                "id": batch.id,
                "name": batch.name,
                "job_type": batch.job_type,
                "status": batch.status,
                "artifact_dir": batch.artifact_dir,
            },
            "items": [
                {
                    "id": i.id,
                    "candidate_id": i.candidate_id,
                    "job_type": i.job_type,
                    "status": i.status,
                    "error_message": i.error_message,
                    "artifact_dir": i.artifact_dir,
                    "output_json": i.output_json,
                    "started_at": i.started_at.isoformat() if i.started_at else None,
                    "finished_at": i.finished_at.isoformat() if i.finished_at else None,
                }
                for i in items
            ],
        }
        buffer = io.BytesIO(json.dumps(report_data, indent=2, ensure_ascii=False).encode("utf-8"))
        return StreamingResponse(
            buffer,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.json"},
        )

    elif format == "csv":
        import csv
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["item_id", "candidate_id", "job_type", "status", "error_message", "started_at", "finished_at"])
        for i in items:
            writer.writerow([
                i.id,
                i.candidate_id or "",
                i.job_type,
                i.status,
                i.error_message or "",
                i.started_at.isoformat() if i.started_at else "",
                i.finished_at.isoformat() if i.finished_at else "",
            ])
        buffer.seek(0)
        return StreamingResponse(
            io.BytesIO(buffer.getvalue().encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.csv"},
        )

    elif format == "md":
        lines = [
            f"# Batch Report: {batch.name}",
            "",
            f"- **ID**: {batch.id}",
            f"- **Job Type**: {batch.job_type}",
            f"- **Status**: {batch.status}",
            f"- **Artifact Dir**: {batch.artifact_dir or 'N/A'}",
            "",
            "## Items",
            "",
            "| Item ID | Candidate | Job Type | Status | Error |",
            "|---------|-----------|----------|--------|-------|",
        ]
        for i in items:
            error_short = (i.error_message or "")[:40]
            lines.append(f"| {i.id[:8]}... | {i.candidate_id or '-'} | {i.job_type} | {i.status} | {error_short} |")
        lines.append("")
        lines.append("## Scientific Boundary")
        lines.append("")
        lines.append("Metrics are only shown when real output files exist. No fabricated data.")
        lines.append("")
        content = "\n".join(lines)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/markdown",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}.md"},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.get("/{batch_id}/computation-report")
def get_computation_report(
    batch_id: str,
    format: str = Query("json", pattern="^(json|markdown|md|pdf)$"),
    db: Session = Depends(get_db),
):
    """Download a real computation report for a batch computation.

    Formats:
      - json: structured report data
      - markdown/md: human-readable Markdown
      - pdf: PDF export (placeholder; full tables in future version)
    """
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    report_data = build_computation_report_data(db, batch_id)

    if format in ("json",):
        buffer = io.BytesIO(render_computation_report_json(report_data))
        return StreamingResponse(
            buffer,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_report.json"},
        )

    if format in ("markdown", "md"):
        content = render_computation_report_markdown(report_data)
        buffer = io.BytesIO(content.encode("utf-8"))
        return StreamingResponse(
            buffer,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_report.md"},
        )

    if format == "pdf":
        buffer = io.BytesIO(render_computation_report_pdf(report_data))
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=batch_{batch_id}_report.pdf"},
        )

    raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")


@router.post("/{batch_id}/retry-failed", response_model=ApiResponse[dict])
def retry_failed_items(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Retry all FAILED or BLOCKED items in a batch."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = db.query(BatchComputationItem).filter(
        BatchComputationItem.batch_id == batch_id,
        BatchComputationItem.status.in_(["FAILED", "BLOCKED"]),
    ).all()

    retried = 0
    for item in items:
        item.status = "PENDING"
        item.error_message = None
        item.started_at = None
        item.finished_at = None
        retried += 1

    db.commit()
    return ApiResponse.success(data={"batch_id": batch_id, "retried_count": retried})


@router.post("/{batch_id}/cancel", response_model=BatchComputationResponse)
def cancel_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Cancel a batch computation and all its pending/running items."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")
    if batch.status in ("SUCCEEDED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=422, detail=f"Batch already in terminal state: {batch.status}")

    batch = cancel_batch_computation(db, batch)
    return batch


@router.post("/{batch_id}/dispatch", response_model=ApiResponse[dict])
def dispatch_batch(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """Dispatch all PENDING items in a batch."""
    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    items = db.query(BatchComputationItem).filter(
        BatchComputationItem.batch_id == batch_id,
        BatchComputationItem.status == "PENDING",
    ).all()

    dispatched = 0
    blocked = 0
    failed = 0
    for item in items:
        item = dispatch_batch_item(db, item)
        if item.status == "RUNNING":
            dispatched += 1
        elif item.status == "BLOCKED":
            blocked += 1
        elif item.status == "FAILED":
            failed += 1

    summary = {
        "batch_id": batch_id,
        "total_pending": len(items),
        "dispatched": dispatched,
        "blocked": blocked,
        "failed": failed,
    }
    batch.summary_json = summary
    db.commit()
    return ApiResponse.success(data=summary)


class MmgbsaResultResponse(BaseModel):
    status: str
    source_file: Optional[str] = None
    run_type: Optional[str] = None
    convergence_status: Optional[str] = None
    frames_used: Optional[int] = None
    delta_g_total: Optional[float] = None
    components: dict = Field(default_factory=dict)
    official_mm_gbsa_delta_g: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    decomposition_available: bool = False
    message: Optional[str] = None


@router.get("/{batch_id}/items/{item_id}/mmgbsa-results", response_model=ApiResponse[MmgbsaResultResponse])
def get_mmgbsa_results(
    batch_id: str,
    item_id: str,
    db: Session = Depends(get_db),
):
    """Get parsed MM-GBSA results for a batch item.

    Parses FINAL_RESULTS_MMPBSA.dat from the item's artifact directory.
    Returns 'Not available' if the file does not exist.
    """
    from app.crud.batch_computations import get_batch_item

    batch = get_batch_computation(db, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Batch not found")

    item = get_batch_item(db, item_id)
    if not item or item.batch_id != batch_id:
        raise HTTPException(status_code=404, detail="Item not found in batch")

    if item.job_type != "MMGBSA":
        raise HTTPException(status_code=422, detail="Item is not an MMGBSA job")

    artifact_dir = item.artifact_dir
    if not artifact_dir:
        return ApiResponse.success(data=MmgbsaResultResponse(
            status="NOT_AVAILABLE",
            message="No artifact directory for this item.",
        ))

    # Look for FINAL_RESULTS_MMPBSA.dat (may have suffixes like _PILOT, _PRODUCTION)
    import glob
    dat_files = glob.glob(f"{artifact_dir}/FINAL_RESULTS_MMPBSA*.dat")
    if not dat_files:
        return ApiResponse.success(data=MmgbsaResultResponse(
            status="NOT_AVAILABLE",
            message="FINAL_RESULTS_MMPBSA.dat not found.",
        ))

    dat_path = dat_files[0]
    parsed = parse_mmpbsa_result(dat_path)

    if parsed.status == "BLOCKED":
        return ApiResponse.success(data=MmgbsaResultResponse(
            status="NOT_AVAILABLE",
            message="FINAL_RESULTS_MMPBSA.dat not found.",
        ))

    components = get_mmgbsa_components(parsed)

    # Optionally write outputs to artifact_dir for caching
    try:
        write_mmgbsa_summary_json(parsed, artifact_dir)
        write_mmgbsa_components_csv(parsed, artifact_dir)
    except Exception:
        pass

    return ApiResponse.success(data=MmgbsaResultResponse(
        status=parsed.status,
        source_file=parsed.source_file,
        run_type=parsed.run_type,
        convergence_status=parsed.convergence_status,
        frames_used=parsed.frames_used,
        delta_g_total=components["delta_g_total"],
        components={
            "vdW": components["vdw"],
            "electrostatic": components["electrostatic"],
            "polar_solvation": components["polar_solvation"],
            "nonpolar_solvation": components["nonpolar_solvation"],
        },
        official_mm_gbsa_delta_g=parsed.official_mm_gbsa_delta_g,
        warnings=parsed.warnings,
        decomposition_available=len(parsed.decomposition) > 0,
    ))
