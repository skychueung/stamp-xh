"""
STAMP Platform — Admin User Management Router (P33V-A1)

Endpoints:
  GET  /api/v1/admin/users
  POST /api/v1/admin/users/{id}/approve
  POST /api/v1/admin/users/{id}/disable
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import require_admin, validate_csrf
from app.database import get_db
from app.models.user import User
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class AdminUserOut(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    status: str
    must_change_password: bool
    failed_login_attempts: int
    locked_until: Optional[datetime]
    created_at: datetime
    approved_at: Optional[datetime]
    approved_by: Optional[str]


class UserListResponse(BaseModel):
    items: List[AdminUserOut]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_user_out(user: User) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        must_change_password=user.must_change_password,
        failed_login_attempts=user.failed_login_attempts,
        locked_until=user.locked_until,
        created_at=user.created_at,
        approved_at=user.approved_at,
        approved_by=user.approved_by,
    )


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------


@router.get(
    "/users",
    response_model=ApiResponse[UserListResponse],
    status_code=status.HTTP_200_OK,
    summary="List all users (admin only)",
)
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    status_filter: Optional[str] = None,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[UserListResponse]:
    """Return all users, optionally filtered by status."""
    query = db.query(User)
    if status_filter in ("pending", "active", "disabled"):
        query = query.filter(User.status == status_filter)
    users = query.order_by(User.created_at.desc()).all()
    return ApiResponse.success(
        data=UserListResponse(items=[_admin_user_out(u) for u in users], total=len(users)),
        message="User list retrieved.",
    )


# ---------------------------------------------------------------------------
# Approve user
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/approve",
    response_model=ApiResponse[AdminUserOut],
    status_code=status.HTTP_200_OK,
    summary="Approve a pending user (admin only)",
)
@limiter.limit("30/minute")
async def approve_user(
    request: Request,
    user_id: str = Path(..., min_length=36, max_length=36),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[AdminUserOut]:
    """Approve a pending user account."""
    validate_csrf(request)
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target.status == "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User is already active.")

    target.status = "active"
    target.approved_at = datetime.now(timezone.utc)
    target.approved_by = admin.id
    db.add(target)
    db.commit()
    db.refresh(target)
    return ApiResponse.success(data=_admin_user_out(target), message="User approved.")


# ---------------------------------------------------------------------------
# Disable user
# ---------------------------------------------------------------------------


@router.post(
    "/users/{user_id}/disable",
    response_model=ApiResponse[AdminUserOut],
    status_code=status.HTTP_200_OK,
    summary="Disable a user account (admin only)",
)
@limiter.limit("30/minute")
async def disable_user(
    request: Request,
    user_id: str = Path(..., min_length=36, max_length=36),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ApiResponse[AdminUserOut]:
    """Disable a user account."""
    validate_csrf(request)
    if admin.id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot disable your own account.")
    target = db.query(User).filter(User.id == user_id).first()
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target.role == "admin" and target.status == "active":
        # Extra guard: prevent disabling the only active admin.
        active_admins = db.query(User).filter(User.role == "admin", User.status == "active").count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot disable the only active admin account.",
            )

    target.status = "disabled"
    db.add(target)
    db.commit()
    db.refresh(target)
    return ApiResponse.success(data=_admin_user_out(target), message="User disabled.")
