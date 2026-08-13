"""CRUD for AuditLogEntry (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from app.models.orm import AuditLogEntry


def create_audit_log(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    user_id: Optional[str] = None,
    before_state: Optional[dict] = None,
    after_state: Optional[dict] = None,
    ip_address: Optional[str] = None,
    session_id: Optional[str] = None,
) -> AuditLogEntry:
    entry = AuditLogEntry(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_state=before_state or {},
        after_state=after_state or {},
        ip_address=ip_address,
        session_id=session_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def list_audit_logs(
    db: Session,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[AuditLogEntry]:
    q = db.query(AuditLogEntry).order_by(AuditLogEntry.timestamp.desc())
    if entity_type:
        q = q.filter(AuditLogEntry.entity_type == entity_type)
    if entity_id:
        q = q.filter(AuditLogEntry.entity_id == entity_id)
    if user_id:
        q = q.filter(AuditLogEntry.user_id == user_id)
    return q.offset(offset).limit(limit).all()
