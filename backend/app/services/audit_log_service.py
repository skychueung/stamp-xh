"""Audit log service for recording significant system events (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.crud.audit_logs import create_audit_log


def log_job_submit(db: Session, job_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="SUBMIT", entity_type="job", entity_id=job_id, user_id=user_id)


def log_job_start(db: Session, job_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="UPDATE", entity_type="job", entity_id=job_id,
                     user_id=user_id, before_state={"status": "PENDING"}, after_state={"status": "RUNNING"})


def log_job_success(db: Session, job_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="UPDATE", entity_type="job", entity_id=job_id,
                     user_id=user_id, before_state={"status": "RUNNING"}, after_state={"status": "SUCCEEDED"})


def log_job_failed(db: Session, job_id: str, error_json: dict, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="UPDATE", entity_type="job", entity_id=job_id,
                     user_id=user_id, before_state={"status": "RUNNING"}, after_state={"status": "FAILED", "error": error_json})


def log_job_retry(db: Session, original_id: str, new_id: str, submitted_by: Optional[str] = None) -> None:
    create_audit_log(db, action="RETRY", entity_type="job", entity_id=original_id,
                     user_id=submitted_by, after_state={"new_job_id": new_id})


def log_job_cancel(db: Session, job_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="CANCEL", entity_type="job", entity_id=job_id, user_id=user_id)


def log_artifact_registered(db: Session, asset_id: str, job_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="CREATE", entity_type="asset", entity_id=asset_id,
                     user_id=user_id, after_state={"job_id": job_id})


def log_export(db: Session, report_type: str, report_id: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="EXPORT", entity_type="report", entity_id=report_id,
                     user_id=user_id, after_state={"report_type": report_type})


def log_lims_sync(db: Session, sync_id: str, status: str, user_id: Optional[str] = None) -> None:
    create_audit_log(db, action="SYNC", entity_type="integration", entity_id=sync_id,
                     user_id=user_id, after_state={"status": status})
