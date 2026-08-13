"""
STAMP Platform — Authentication & Session Security (P33V-A1)

Provides:
  - bcrypt password hashing/verification
  - signed session cookies (itsdangerous)
  - CSRF double-submit cookie helpers
  - FastAPI dependencies for current user, active user, admin user
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request, Response, status
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.core.config import settings
from app.database import SessionLocal
from app.models.user import User

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SESSION_COOKIE_NAME: str = "stamp_session"
CSRF_COOKIE_NAME: str = "stamp_csrf"
SESSION_MAX_AGE_SECONDS: int = 24 * 60 * 60  # 24 hours


def _get_secret_key() -> str:
    """Return a stable secret key; warn if falling back to an insecure default."""
    key = os.environ.get("STAMP_SECRET_KEY") or getattr(settings, "secret_key", None)
    if not key:
        # Fallback only for dev. In production this must be set explicitly.
        key = "dev-insecure-fallback-secret-do-not-use-in-production"
    if getattr(settings, "environment", "development").lower() == "production":
        settings.validate_runtime_security()
    return key


_secret_key: str = _get_secret_key()
_session_serializer = URLSafeTimedSerializer(_secret_key, salt="stamp-session-v1")
_csrf_serializer = URLSafeTimedSerializer(_secret_key, salt="stamp-csrf-v1")

# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash a plaintext password with bcrypt."""
    if len(plain) > 512:
        raise ValueError("Password too long")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Cookie policy helpers
# ---------------------------------------------------------------------------


def _is_secure_cookie(request: Request | None = None) -> bool:
    """Use Secure cookies when the request is HTTPS or explicitly enabled."""
    if request is not None:
        forwarded_proto = request.headers.get("x-forwarded-proto", "")
        if forwarded_proto.lower() == "https":
            return True
    return os.environ.get("STAMP_COOKIE_SECURE", "").lower() in ("1", "true", "yes")


def _same_site() -> str:
    return os.environ.get("STAMP_COOKIE_SAMESITE", "Lax")


def _set_cookie(
    response: Response,
    name: str,
    value: str,
    *,
    httponly: bool,
    request: Request | None = None,
) -> None:
    response.set_cookie(
        name,
        value,
        httponly=httponly,
        secure=_is_secure_cookie(request),
        samesite=_same_site(),
        max_age=SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def create_session(response: Response, user_id: str, request: Request | None = None) -> None:
    """Set the HttpOnly session cookie and a matching CSRF cookie."""
    session_token = _session_serializer.dumps({"user_id": user_id})
    csrf_token = _csrf_serializer.dumps({"user_id": user_id})
    _set_cookie(response, SESSION_COOKIE_NAME, session_token, httponly=True, request=request)
    _set_cookie(response, CSRF_COOKIE_NAME, csrf_token, httponly=False, request=request)


def clear_session(response: Response, request: Request | None = None) -> None:
    """Remove session and CSRF cookies."""
    kwargs = {
        "path": "/",
        "secure": _is_secure_cookie(request),
        "samesite": _same_site(),
    }
    response.delete_cookie(SESSION_COOKIE_NAME, httponly=True, **kwargs)
    response.delete_cookie(CSRF_COOKIE_NAME, httponly=False, **kwargs)


def read_session_cookie(request: Request) -> Optional[dict]:
    """Verify and decode the session cookie. Returns None if invalid/expired."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        data = _session_serializer.loads(token, max_age=SESSION_MAX_AGE_SECONDS)
        if not isinstance(data, dict) or "user_id" not in data:
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def validate_csrf(request: Request) -> None:
    """Validate CSRF double-submit token for state-changing requests."""
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    header_token = request.headers.get("x-csrf-token") or request.headers.get("X-CSRF-Token")
    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing.",
        )
    try:
        cookie_data = _csrf_serializer.loads(cookie_token, max_age=SESSION_MAX_AGE_SECONDS)
        header_data = _csrf_serializer.loads(header_token, max_age=SESSION_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token invalid or expired.",
        )
    if cookie_data.get("user_id") != header_data.get("user_id"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch.",
        )


# ---------------------------------------------------------------------------
# User lookup dependencies
# ---------------------------------------------------------------------------


def get_current_user(request: Request) -> User:
    """FastAPI dependency: return the currently authenticated user or 401."""
    session = read_session_cookie(request)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Cookie"},
        )
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == session["user_id"]).first()
    finally:
        db.close()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated.",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def require_active(user: User = Depends(get_current_user)) -> User:
    """Require the current user to be active (approved and not disabled)."""
    if user.status != "active":
        if user.status == "pending":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account pending approval.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled.",
        )
    if user.locked_until and user.locked_until > datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account temporarily locked due to failed login attempts.",
        )
    return user


def require_admin(user: User = Depends(require_active)) -> User:
    """Require the current active user to have admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )
    return user


# ---------------------------------------------------------------------------
# Safe username / password validation
# ---------------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\-]{3,32}$")


def validate_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(username))


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    return True, ""
