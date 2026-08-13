"""Target-design workflow router (P7A/P7C).

Provides a dry-run planning endpoint for the multi-model workflow:
PepMLM -> PepPrCLIP -> EvoBind2 -> Molstar.

P7C additions:
  - GET /target-design/reports/{workflow_id}.json
  - GET /target-design/reports/{workflow_id}.md
  - GET /target-design/artifacts/{artifact_ref}/download
"""
from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from app.core.security import require_active
from fastapi.responses import FileResponse, PlainTextResponse

from app.models.schemas import ApiResponse
from app.schemas.model_registry import (
    TargetDesignWorkflowPayload,
    TargetDesignWorkflowResult,
)
from app.services.target_design_workflow_registry import (
    DOWNLOADABLE_ARTIFACT_FILENAMES,
    build_target_design_dry_run,
    generate_workflow_json_report,
    generate_workflow_markdown_report,
    load_workflow_result,
    resolve_workflow_artifact_path,
)

router = APIRouter(prefix="/api/v1/workflows", tags=["Workflows"])


def _safe_workflow_id(workflow_id: str) -> str:
    """Allow alphanumeric, hyphen, underscore, and the special value 'latest'."""
    normalized = workflow_id.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow ID cannot be empty.",
        )
    if normalized == "latest":
        return normalized
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid workflow ID.",
        )
    return normalized


def _safe_artifact_ref(artifact_ref: str) -> str:
    """Validate artifact_ref is a simple whitelisted identifier."""
    normalized = artifact_ref.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Artifact reference cannot be empty.",
        )
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid artifact reference.",
        )
    return normalized


@router.post(
    "/target-design/dry-run",
    status_code=status.HTTP_200_OK,
    summary="Plan a target-design workflow dry-run",
    response_model=ApiResponse[TargetDesignWorkflowResult],
)
async def target_design_dry_run(
    payload: TargetDesignWorkflowPayload,
) -> ApiResponse[TargetDesignWorkflowResult]:
    """Plan the full target-design workflow without executing any model."""
    result = build_target_design_dry_run(payload)
    return ApiResponse.success(
        data=result,
        message="Target-design workflow dry-run planned",
    )


@router.get(
    "/target-design/reports/{workflow_id}.json",
    status_code=status.HTTP_200_OK,
    summary="Export a workflow dry-run report as JSON",
)
async def export_workflow_json_report(
    workflow_id: Annotated[str, Path(...)],
) -> PlainTextResponse:
    """Export a JSON dry-run report for the given workflow_id.

    Use ``workflow_id=latest`` to retrieve the most recently planned dry-run.
    """
    normalized = _safe_workflow_id(workflow_id)
    result = load_workflow_result(normalized)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow dry-run result '{workflow_id}' not found.",
        )
    report = generate_workflow_json_report(result)
    return PlainTextResponse(
        content=json.dumps(report, indent=2, ensure_ascii=False),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{result.workflow_id}_dryrun_report.json"'
        },
    )


@router.get(
    "/target-design/reports/{workflow_id}.md",
    status_code=status.HTTP_200_OK,
    summary="Export a workflow dry-run report as Markdown",
)
async def export_workflow_markdown_report(
    workflow_id: Annotated[str, Path(...)],
) -> PlainTextResponse:
    """Export a Markdown dry-run report for the given workflow_id.

    Use ``workflow_id=latest`` to retrieve the most recently planned dry-run.
    """
    normalized = _safe_workflow_id(workflow_id)
    result = load_workflow_result(normalized)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow dry-run result '{workflow_id}' not found.",
        )
    report = generate_workflow_markdown_report(result)
    return PlainTextResponse(
        content=report,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{result.workflow_id}_dryrun_report.md"'
        },
    )


@router.get(
    "/target-design/artifacts/{artifact_ref}/download",
    status_code=status.HTTP_200_OK,
    summary="Download a whitelisted workflow artifact",
    response_class=FileResponse,
    dependencies=[Depends(require_active)],
)
async def download_workflow_artifact(
    artifact_ref: Annotated[str, Path(...)],
) -> FileResponse:
    """Download a whitelisted artifact referenced by the workflow lineage.

    Allowed ``artifact_ref`` values:
      - ``p5c-candidates-csv``  → P5C PepMLM candidate_sequences.csv
      - ``p5c-candidates-json`` → P5C PepMLM candidate_sequences.json
      - ``p3b-pdb``             → P3B EvoBind2 unrelaxed_true.pdb
    """
    normalized = _safe_artifact_ref(artifact_ref)
    path = resolve_workflow_artifact_path(normalized)
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artifact '{artifact_ref}' is not available for download.",
        )

    filename = DOWNLOADABLE_ARTIFACT_FILENAMES.get(normalized, path.name)
    return FileResponse(
        path=str(path),
        filename=filename,
        media_type="application/octet-stream",
    )
