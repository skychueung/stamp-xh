"""LIMS / ELN integration router.

v1.2-lab-production-fast — P6 REAL_API_READY framework.

All endpoints treat the integration as a configuration object.
- No simulated/fake data is ever returned as if it came from a real LIMS/ELN.
- test_sync_connection() performs a basic connectivity test against base_url.
  If base_url is missing or the server is unreachable, status stays TEST_FAILED.
- SYNC_SUCCEEDED is only reached after a successful real sync or test connection.
- CONFIG_REQUIRED means the user still needs to fill in base_url / token.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud.lims_integration import (
    create_integration_config,
    delete_integration_config,
    get_integration_config,
    list_integration_configs,
    set_config_status,
    update_integration_config,
)

logger = logging.getLogger("stamp")

router = APIRouter(prefix="/api/integrations", tags=["Integration Config (LIMS/ELN)"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class IntegrationConfigCreate(BaseModel):
    integration_type: str = Field(..., description="LIMS or ELN")
    name: str = Field(..., description="Display name")
    base_url: Optional[str] = Field(None, description="Root API URL (no trailing slash)")
    auth_mode: str = Field(default="token")
    token_secret_ref: Optional[str] = Field(None, description="Env var or vault path holding the secret")
    field_mapping_json: dict = Field(default_factory=dict)
    enabled: bool = False
    test_mode: bool = True

    @field_validator("integration_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v.upper() not in {"LIMS", "ELN"}:
            raise ValueError("integration_type must be LIMS or ELN")
        return v.upper()

    @field_validator("auth_mode")
    @classmethod
    def validate_auth(cls, v: str) -> str:
        if v not in {"token", "oauth2", "basic"}:
            raise ValueError("auth_mode must be token, oauth2, or basic")
        return v


class IntegrationConfigUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    auth_mode: Optional[str] = None
    token_secret_ref: Optional[str] = None
    field_mapping_json: Optional[dict] = None
    enabled: Optional[bool] = None
    test_mode: Optional[bool] = None


class IntegrationConfigResponse(BaseModel):
    id: str
    integration_type: str
    name: str
    base_url: Optional[str]
    auth_mode: str
    token_secret_ref: Optional[str]
    field_mapping_json: dict
    status: str
    last_sync_at: Optional[datetime]
    last_error: Optional[str]
    enabled: bool
    test_mode: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationConfigListResponse(BaseModel):
    items: list[IntegrationConfigResponse]
    total: int
    limit: int
    offset: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=IntegrationConfigResponse, status_code=201)
def post_integration(
    body: IntegrationConfigCreate,
    db: Session = Depends(get_db),
):
    """Create a new LIMS/ELN integration config."""
    config = create_integration_config(
        db,
        integration_type=body.integration_type,
        name=body.name,
        base_url=body.base_url,
        auth_mode=body.auth_mode,
        token_secret_ref=body.token_secret_ref,
        field_mapping_json=body.field_mapping_json,
        enabled=body.enabled,
        test_mode=body.test_mode,
    )
    return config


@router.get("", response_model=IntegrationConfigListResponse)
def list_integrations(
    integration_type: Optional[str] = Query(None),
    enabled: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List integration configs."""
    items, total = list_integration_configs(
        db,
        integration_type=integration_type,
        enabled=enabled,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{config_id}", response_model=IntegrationConfigResponse)
def get_integration(
    config_id: str,
    db: Session = Depends(get_db),
):
    """Get a single integration config."""
    config = get_integration_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration config not found")
    return config


@router.patch("/{config_id}", response_model=IntegrationConfigResponse)
def patch_integration(
    config_id: str,
    body: IntegrationConfigUpdate,
    db: Session = Depends(get_db),
):
    """Partial update of an integration config.

    Does NOT allow direct status modification — use test_sync_connection or
    set_status endpoints instead.
    """
    config = get_integration_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration config not found")

    updates = body.model_dump(exclude_unset=True)
    config = update_integration_config(db, config, **updates)

    # If base_url and token_secret_ref are both present, auto-transition to REAL_API_READY.
    if config.status == "CONFIG_REQUIRED" and config.base_url and config.token_secret_ref:
        config = set_config_status(db, config, status="REAL_API_READY")

    return config


@router.delete("/{config_id}", status_code=204)
def delete_integration(
    config_id: str,
    db: Session = Depends(get_db),
):
    """Delete an integration config."""
    config = get_integration_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration config not found")
    delete_integration_config(db, config)


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

@router.post("/{config_id}/test-sync", response_model=IntegrationConfigResponse)
def test_sync_connection(
    config_id: str,
    db: Session = Depends(get_db),
):
    """Test connectivity to the configured LIMS/ELN API.

    - If base_url is missing → status stays CONFIG_REQUIRED.
    - If token_secret_ref is missing → status stays REAL_API_READY (user must provide).
    - If HTTP GET to base_url succeeds (2xx) → REAL_API_READY (or TEST_FAILED if non-2xx).
    - If request raises → TEST_FAILED, error logged.

    No fake data is ever returned as a sync result.
    """
    config = get_integration_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration config not found")

    if not config.base_url:
        config = set_config_status(
            db, config, status="CONFIG_REQUIRED", last_error="base_url is required for test"
        )
        return config

    # Resolve token (for now, treat token_secret_ref as env-var name — production uses vault)
    token: str | None = None
    if config.token_secret_ref:
        import os
        token = os.environ.get(config.token_secret_ref)

    headers: dict[str, str] = {}
    if token and config.auth_mode == "token":
        headers["Authorization"] = f"Bearer {token}"

    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(config.base_url, headers=headers)
    except Exception as exc:
        logger.warning("Integration %s test connection failed: %s", config_id, exc)
        config = set_config_status(
            db, config, status="TEST_FAILED", last_error=f"Connection error: {exc}"
        )
        return config

    if resp.status_code < 200 or resp.status_code >= 300:
        config = set_config_status(
            db,
            config,
            status="TEST_FAILED",
            last_error=f"HTTP {resp.status_code}: {resp.text[:200]}",
        )
        return config

    # Real success
    config = set_config_status(db, config, status="REAL_API_READY", last_error=None)
    config.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(config)
    return config


@router.post("/{config_id}/set-status", response_model=IntegrationConfigResponse)
def set_integration_status(
    config_id: str,
    status: str,
    db: Session = Depends(get_db),
):
    """Explicitly set config status (for admin / recovery)."""
    config = get_integration_config(db, config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Integration config not found")
    try:
        config = set_config_status(db, config, status=status)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return config
