"""Audit Log Router (v1.2-lab-production-fast)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.crud.audit_logs import list_audit_logs
from app.database import get_db
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/audit-log", tags=["Audit Log"])


@router.get(
    "",
    summary="Query audit log entries",
)
async def list_audit_log_endpoint(
    entity_type: Annotated[Optional[str], Query()] = None,
    entity_id: Annotated[Optional[str], Query()] = None,
    user_id: Annotated[Optional[str], Query()] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
) -> ApiResponse[list[dict]]:
    """Query audit log entries with filters. Append-only; no modification endpoints."""
    entries = list_audit_logs(db, entity_type=entity_type, entity_id=entity_id,
                              user_id=user_id, limit=limit, offset=offset)
    return ApiResponse.success(data=[
        {
            "event_id": e.id,
            "timestamp": e.timestamp.isoformat() if e.timestamp else None,
            "user_id": e.user_id,
            "action": e.action,
            "entity_type": e.entity_type,
            "entity_id": e.entity_id,
            "before_state": e.before_state,
            "after_state": e.after_state,
            "ip_address": e.ip_address,
            "session_id": e.session_id,
        }
        for e in entries
    ])
