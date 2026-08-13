"""
STAMP Platform — Authentication Router (P33V-A1)

Endpoints:
  POST /api/v1/auth/register
  POST /api/v1/auth/login
  POST /api/v1/auth/logout
  GET  /api/v1/auth/me
  POST /api/v1/auth/change-password
"""

from __future__ import annotations

import os

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.core.limiter import limiter
from app.core.security import (
    SESSION_COOKIE_NAME,
    clear_session,
    create_session,
    hash_password,
    require_active,
    validate_csrf,
    validate_password_strength,
    validate_username,
    verify_password,
)
from app.database import get_db
from app.models.user import User
from app.models.schemas import ApiResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

FAILED_LOGIN_LOCKOUT_ATTEMPTS = 5
FAILED_LOGIN_LOCKOUT_MINUTES = 15
_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=512)
    email: Optional[str] = Field(None, max_length=255)

    @field_validator("username")
    @classmethod
    def check_username(cls, v: str) -> str:
        if not validate_username(v):
            raise ValueError("Username must be 3-32 characters, alphanumeric, hyphen, or underscore.")
        return v


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=512)


class UserMeOut(BaseModel):
    id: str
    username: str
    email: Optional[str]
    role: str
    status: str
    must_change_password: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generic_register_error() -> HTTPException:
    """Prevent username enumeration by returning the same message."""
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Registration failed. Please check your input and try again.",
    )


_LOGIN_FAILURE_MSG = "Invalid username or password."


def _admin_approval_required() -> bool:
    """Return whether registrations should wait for explicit admin approval.

    Development and default deployments allow immediate login. Deployments
    that need the legacy approval workflow can opt in with
    STAMP_REQUIRE_ADMIN_APPROVAL=true.
    """
    return os.environ.get("STAMP_REQUIRE_ADMIN_APPROVAL", "false").strip().lower() in _TRUE_VALUES


def _record_login_failure(db: Session, user: User) -> None:
    user.failed_login_attempts += 1
    if user.failed_login_attempts >= FAILED_LOGIN_LOCKOUT_ATTEMPTS:
        user.locked_until = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=FAILED_LOGIN_LOCKOUT_MINUTES)
    db.add(user)
    db.commit()


def _reset_login_failure(db: Session, user: User) -> None:
    if user.failed_login_attempts != 0 or user.locked_until is not None:
        user.failed_login_attempts = 0
        user.locked_until = None
        db.add(user)
        db.commit()


def _user_me(user: User) -> UserMeOut:
    return UserMeOut(
        id=user.id,
        username=user.username,
        email=user.email,
        role=user.role,
        status=user.status,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit(os.environ.get("STAMP_REGISTER_RATE_LIMIT", "3/hour"))
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[dict]:
    """Create a user that is active by default or pending in opt-in approval mode."""
    if db.query(User).filter(User.username == payload.username).first():
        raise _generic_register_error()
    if payload.email and db.query(User).filter(User.email == payload.email).first():
        raise _generic_register_error()

    ok, msg = validate_password_strength(payload.password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    approval_required = _admin_approval_required()
    initial_status = "pending" if approval_required else "active"
    registered_at = datetime.now(timezone.utc)

    user = User(
        username=payload.username,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role="user",
        status=initial_status,
        must_change_password=False,
        approved_at=None if approval_required else registered_at,
        approved_by=None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Registration never inherits an existing browser session. The user signs
    # in explicitly after registration, whether active or pending.
    clear_session(response, request)

    message = (
        "Registration successful. Waiting for administrator approval."
        if approval_required
        else "Registration successful. You can now sign in."
    )

    return ApiResponse.success(
        data={
            "id": user.id,
            "username": user.username,
            "status": user.status,
            "approval_required": approval_required,
            "message": message,
        },
        message=message,
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=ApiResponse[UserMeOut],
    status_code=status.HTTP_200_OK,
    summary="Log in with username and password",
)
@limiter.limit(os.environ.get("STAMP_LOGIN_RATE_LIMIT", "5/minute"))
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
) -> ApiResponse[UserMeOut]:
    """Authenticate and set HttpOnly session cookies."""
    user = db.query(User).filter(User.username == payload.username).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_LOGIN_FAILURE_MSG,
        )

    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to failed login attempts.",
        )

    if not verify_password(payload.password, user.password_hash):
        _record_login_failure(db, user)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=_LOGIN_FAILURE_MSG,
        )

    if user.status == "disabled":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled. Please contact an administrator.",
        )

    if user.status == "pending":
        if _admin_approval_required():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is waiting for administrator approval.",
            )

        # Compatibility path for accounts created under the former default-
        # pending policy. A correct password activates the account when the
        # deployment is not running in explicit approval mode.
        user.status = "active"
        user.approved_at = datetime.now(timezone.utc)
        user.approved_by = None
        db.add(user)
        db.commit()
        db.refresh(user)

    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is unavailable. Please contact an administrator.",
        )

    _reset_login_failure(db, user)
    create_session(response, user.id, request)

    return ApiResponse.success(data=_user_me(user), message="Login successful.")


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@router.post(
    "/logout",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Log out the current user",
)
@limiter.limit(os.environ.get("STAMP_LOGOUT_RATE_LIMIT", "30/minute"))
async def logout(
    request: Request,
    response: Response,
) -> ApiResponse[dict]:
    """Clear session cookies. Requires CSRF token."""
    validate_csrf(request)
    if request.cookies.get(SESSION_COOKIE_NAME):
        clear_session(response, request)
    return ApiResponse.success(data={}, message="Logged out successfully.")


# ---------------------------------------------------------------------------
# Me
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=ApiResponse[UserMeOut],
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
)
async def me(user: User = Depends(require_active)) -> ApiResponse[UserMeOut]:
    """Return the current user's profile."""
    return ApiResponse.success(data=_user_me(user), message="Authenticated.")


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@router.post(
    "/change-password",
    response_model=ApiResponse[UserMeOut],
    status_code=status.HTTP_200_OK,
    summary="Change the current user's password",
)
@limiter.limit(os.environ.get("STAMP_CHANGE_PASSWORD_RATE_LIMIT", "10/minute"))
async def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest,
    user: User = Depends(require_active),
    db: Session = Depends(get_db),
) -> ApiResponse[UserMeOut]:
    """Change password after verifying the current password."""
    validate_csrf(request)

    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect.",
        )

    ok, msg = validate_password_strength(payload.new_password)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    db.add(user)
    db.commit()

    # Rotate session after password change.
    create_session(response, user.id, request)

    return ApiResponse.success(data=_user_me(user), message="Password changed successfully.")
