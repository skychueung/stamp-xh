"""File Assets Router (v1.2-lab-production-fast)."""

from __future__ import annotations

import io
import os
import tarfile
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.crud.file_assets import create_asset, get_asset, list_assets_by_batch, list_assets_by_job
from app.database import get_db
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/assets", tags=["File Assets"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a file asset",
)
async def create_asset_endpoint(
    job_id: Annotated[Optional[str], Query()] = None,
    candidate_id: Annotated[Optional[str], Query()] = None,
    batch_id: Annotated[Optional[str], Query()] = None,
    file_type: Annotated[str, Query(...)] = "log",
    original_filename: Annotated[str, Query(...)] = "",
    storage_path: Annotated[str, Query(...)] = "",
    size_bytes: Annotated[int, Query(...)] = 0,
    sha256: Annotated[Optional[str], Query()] = None,
    storage_backend: Annotated[str, Query()] = "local_fs",
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Register a file asset in the registry."""
    asset = create_asset(
        db, job_id, candidate_id, batch_id, file_type,
        original_filename, storage_path, size_bytes, sha256, storage_backend,
    )
    return ApiResponse.success(data={
        "asset_id": asset.id,
        "file_type": asset.file_type,
        "storage_path": asset.storage_path,
        "size_bytes": asset.size_bytes,
        "sha256": asset.sha256,
    })


@router.get(
    "/{asset_id}",
    summary="Get asset metadata",
)
async def get_asset_endpoint(
    asset_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Get file asset metadata."""
    asset = get_asset(db, asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    return ApiResponse.success(data={
        "asset_id": asset.id,
        "job_id": asset.job_id,
        "candidate_id": asset.candidate_id,
        "batch_id": asset.batch_id,
        "file_type": asset.file_type,
        "original_filename": asset.original_filename,
        "storage_path": asset.storage_path,
        "size_bytes": asset.size_bytes,
        "sha256": asset.sha256,
        "storage_backend": asset.storage_backend,
        "created_at": asset.created_at.isoformat() if asset.created_at else None,
    })


@router.get(
    "",
    summary="List assets",
)
async def list_assets_endpoint(
    job_id: Annotated[Optional[str], Query()] = None,
    batch_id: Annotated[Optional[str], Query()] = None,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """List assets filtered by job or batch."""
    if job_id:
        assets = list_assets_by_job(db, job_id)
    elif batch_id:
        assets = list_assets_by_batch(db, batch_id)
    else:
        raise HTTPException(status_code=400, detail="Provide job_id or batch_id")
    return ApiResponse.success(data=[
        {
            "asset_id": a.id,
            "file_type": a.file_type,
            "original_filename": a.original_filename,
            "size_bytes": a.size_bytes,
            "sha256": a.sha256,
        }
        for a in assets
    ])


@router.post(
    "/bundles/{batch_id}",
    summary="Create a tar.gz bundle for a batch",
)
async def create_bundle_endpoint(
    batch_id: Annotated[str, Path(...)],
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Create and download a tar.gz bundle of all assets in a batch."""
    assets = list_assets_by_batch(db, batch_id)
    if not assets:
        raise HTTPException(status_code=404, detail="No assets found for batch")

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for asset in assets:
            if os.path.exists(asset.storage_path):
                tar.add(asset.storage_path, arcname=asset.original_filename)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/gzip",
        headers={"Content-Disposition": f'attachment; filename="batch_{batch_id}.tar.gz"'},
    )
