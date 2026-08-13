"""STAMP Platform — Project Results Router (P5-lite P5).

Aggregated read-only endpoints for project-level result queries.
"""

from __future__ import annotations

import io
import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.crud.project_results import (
    get_project_pipeline_results,
    get_project_summary,
    list_generation_runs_by_project,
    list_project_stamp_results,
)
from app.crud.projects import get_project
from app.crud.stamp_candidates import get_stamp_candidate
from app.database import get_db
from app.models.schemas import ApiResponse
from app.schemas import (
    GenerationRunListResponse,
    GenerationRunLite,
    ProjectPipelineResultsResponse,
    ProjectStampResultsResponse,
    ProjectSummaryResponse,
    StampCandidateDetail,
)
from app.services.candidate_report_export import (
    build_candidate_report_data,
    render_candidate_report_csv,
    render_candidate_report_markdown,
    render_candidate_report_pdf,
    render_candidate_report_xlsx,
    validate_report_no_fabricated_metrics,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["Project Results"])
stamp_candidates_router = APIRouter(
    prefix="/api/v1/stamp-candidates", tags=["STAMP Candidates"]
)


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/summary
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/summary",
    status_code=status.HTTP_200_OK,
    summary="Get project overview statistics",
    response_model=ApiResponse[ProjectSummaryResponse],
)
async def project_summary(
    project_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[ProjectSummaryResponse]:
    """Return project overview statistics."""
    summary = get_project_summary(db, project_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return ApiResponse.success(data=ProjectSummaryResponse(**summary))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/pipeline-results
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/pipeline-results",
    status_code=status.HTTP_200_OK,
    summary="Get full pipeline results for a project",
    response_model=ApiResponse[ProjectPipelineResultsResponse],
)
async def project_pipeline_results(
    project_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[ProjectPipelineResultsResponse]:
    """Return full pipeline results including all child entities."""
    results = get_project_pipeline_results(db, project_id)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return ApiResponse.success(data=ProjectPipelineResultsResponse(**results))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/stamp-results
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/stamp-results",
    status_code=status.HTTP_200_OK,
    summary="Get assembled and ranked STAMP candidates",
    response_model=ApiResponse[ProjectStampResultsResponse],
)
async def project_stamp_results(
    project_id: Annotated[str, Path(...)],
    top_k: Annotated[Optional[int], Query(ge=1, le=500)] = None,
    include_metrics: Annotated[bool, Query()] = True,
    db: Session = Depends(get_db),
) -> ApiResponse[ProjectStampResultsResponse]:
    """Return STAMP candidates that have been assembled and ranked.

    Filtered to candidates with composite_score and assembly/ranking metrics.
    Sorted by composite_score descending.
    """
    results = list_project_stamp_results(
        db, project_id, top_k=top_k, include_metrics=include_metrics
    )
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )

    # Build response with optional metrics stripping
    candidates = results["candidates"]
    if not include_metrics:
        # Strip metrics from response
        candidate_dicts = []
        for c in candidates:
            d = StampCandidateDetail.model_validate(c).model_dump()
            d["metrics"] = None
            candidate_dicts.append(d)
        # Reconstruct objects for schema validation
        from app.schemas import StampCandidateDetail as SCD

        candidates = [SCD(**d) for d in candidate_dicts]

    response_data = {
        "project_id": results["project_id"],
        "project_name": results["project_name"],
        "total_count": results["total_count"],
        "returned_count": results["returned_count"],
        "candidates": candidates,
    }
    return ApiResponse.success(data=ProjectStampResultsResponse(**response_data))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/generation-runs
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/generation-runs",
    status_code=status.HTTP_200_OK,
    summary="Get all generation runs for a project",
    response_model=ApiResponse[GenerationRunListResponse],
)
async def project_generation_runs(
    project_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[GenerationRunListResponse]:
    """Return all targeting-peptide generation runs for a project."""
    results = list_generation_runs_by_project(db, project_id)
    if results is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found",
        )
    return ApiResponse.success(data=GenerationRunListResponse(**results))


# ---------------------------------------------------------------------------
# GET /api/v1/stamp-candidates/{candidate_id}
# ---------------------------------------------------------------------------


@stamp_candidates_router.get(
    "/{candidate_id}",
    status_code=status.HTTP_200_OK,
    summary="Get a single STAMP candidate by ID",
    response_model=ApiResponse[StampCandidateDetail],
)
async def stamp_candidate_detail(
    candidate_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[StampCandidateDetail]:
    """Return full details for a single STAMP candidate."""
    candidate = get_stamp_candidate(db, candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"STAMP candidate '{candidate_id}' not found",
        )
    return ApiResponse.success(data=StampCandidateDetail.model_validate(candidate))


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{project_id}/candidate-report
# ---------------------------------------------------------------------------


@router.get(
    "/{project_id}/candidate-report",
    status_code=status.HTTP_200_OK,
    summary="Export candidate validation report (JSON, Markdown, CSV, XLSX, or PDF)",
)
async def project_candidate_report(
    project_id: Annotated[str, Path(...)],
    top_k: Annotated[int, Query(ge=1, le=500)] = 10,
    format: Annotated[str, Query()] = "json",
    db: Session = Depends(get_db),
):
    """Export a candidate report in JSON, Markdown, or CSV format.

    The report includes structure prediction, interface quality (pDockQ),
    and FoldX energy quality metrics with explicit scientific boundary
    declarations.
    """
    # Normalize md -> markdown
    fmt = format.lower()
    if fmt == "md":
        fmt = "markdown"
    valid_formats = {"json", "markdown", "csv", "xlsx", "pdf"}
    if fmt not in valid_formats:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid format '{format}'. Supported: json, markdown/md, csv, xlsx, pdf",
        )

    try:
        report_data = build_candidate_report_data(db, project_id, top_k=top_k)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    # Integrity check: no fabricated metrics
    try:
        validate_report_no_fabricated_metrics(report_data)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    if fmt == "json":
        return ApiResponse.success(data=report_data)

    if fmt == "markdown":
        md = render_candidate_report_markdown(report_data)
        return Response(
            content=md,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="candidate_report_{project_id}.md"'},
        )

    if fmt == "csv":
        csv_content = render_candidate_report_csv(report_data)
        return Response(
            content=csv_content,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="candidate_report_{project_id}.csv"'},
        )

    if fmt == "xlsx":
        xlsx_bytes = render_candidate_report_xlsx(report_data)
        return StreamingResponse(
            io.BytesIO(xlsx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="candidate_report_{project_id}.xlsx"'},
        )

    if fmt == "pdf":
        pdf_bytes = render_candidate_report_pdf(report_data)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="candidate_report_{project_id}.pdf"'},
        )

    # Should never reach here due to format validation above
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Unsupported format: {format}",
    )
