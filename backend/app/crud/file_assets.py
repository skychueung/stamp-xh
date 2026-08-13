"""CRUD for FileAsset (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import FileAsset


def create_asset(db: Session, job_id: Optional[str], candidate_id: Optional[str],
                 batch_id: Optional[str], file_type: str, original_filename: str,
                 storage_path: str, size_bytes: int, sha256: Optional[str] = None,
                 storage_backend: str = "local_fs") -> FileAsset:
    asset = FileAsset(
        job_id=job_id,
        candidate_id=candidate_id,
        batch_id=batch_id,
        file_type=file_type,
        original_filename=original_filename,
        storage_path=storage_path,
        size_bytes=size_bytes,
        sha256=sha256,
        storage_backend=storage_backend,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


def get_asset(db: Session, asset_id: str) -> Optional[FileAsset]:
    return db.query(FileAsset).filter(FileAsset.id == asset_id).first()


def list_assets_by_job(db: Session, job_id: str) -> list[FileAsset]:
    return db.query(FileAsset).filter(FileAsset.job_id == job_id).all()


def list_assets_by_batch(db: Session, batch_id: str) -> list[FileAsset]:
    return db.query(FileAsset).filter(FileAsset.batch_id == batch_id).all()
