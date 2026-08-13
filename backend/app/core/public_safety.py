"""Public release safety guards for risky unauthenticated endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.core.config import settings

_DISABLED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def _disabled(capability: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            f"{capability} is disabled by the public-demo safety defaults. "
            "Set PUBLIC_DEMO_MODE=false and enable the matching ENABLE_* "
            "environment variable only in a trusted local deployment."
        ),
    )


def write_endpoints_enabled() -> bool:
    return (not settings.public_demo_mode) and settings.enable_write_endpoints


def compute_endpoints_enabled() -> bool:
    return (not settings.public_demo_mode) and settings.enable_compute_endpoints


def file_asset_registration_enabled() -> bool:
    return (not settings.public_demo_mode) and settings.enable_file_asset_registration


def require_file_asset_registration_enabled() -> None:
    if not file_asset_registration_enabled():
        raise _disabled("File asset registration")


def create_disabled_router(prefix: str, tag: str, capability: str) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    async def disabled_endpoint() -> None:
        raise _disabled(capability)

    router.add_api_route("", disabled_endpoint, methods=_DISABLED_METHODS, include_in_schema=False)
    router.add_api_route("/{path:path}", disabled_endpoint, methods=_DISABLED_METHODS, include_in_schema=False)
    return router
