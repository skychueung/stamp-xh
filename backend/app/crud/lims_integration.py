"""CRUD for IntegrationConfig (LIMS / ELN).

v1.2-lab-production-fast — P6 REAL_API_READY framework.
"""

from __future__ import annotations


from sqlalchemy.orm import Session

from app.models.orm import IntegrationConfig


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

def create_integration_config(
    db: Session,
    *,
    integration_type: str,
    name: str,
    base_url: str | None = None,
    auth_mode: str = "token",
    token_secret_ref: str | None = None,
    field_mapping_json: dict | None = None,
    enabled: bool = False,
    test_mode: bool = True,
) -> IntegrationConfig:
    """Create a new LIMS/ELN integration config.

    Status defaults to CONFIG_REQUIRED because no real credentials are verified at creation.
    """
    config = IntegrationConfig(
        integration_type=integration_type,
        name=name,
        base_url=base_url,
        auth_mode=auth_mode,
        token_secret_ref=token_secret_ref,
        field_mapping_json=field_mapping_json or {},
        enabled=enabled,
        test_mode=test_mode,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------

def get_integration_config(db: Session, config_id: str) -> IntegrationConfig | None:
    """Get a single integration config by ID."""
    return db.query(IntegrationConfig).filter(IntegrationConfig.id == config_id).first()


def list_integration_configs(
    db: Session,
    *,
    integration_type: str | None = None,
    enabled: bool | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[IntegrationConfig], int]:
    """List integration configs with optional filters."""
    query = db.query(IntegrationConfig)
    if integration_type:
        query = query.filter(IntegrationConfig.integration_type == integration_type)
    if enabled is not None:
        query = query.filter(IntegrationConfig.enabled == enabled)

    total = query.count()
    results = query.order_by(IntegrationConfig.created_at.desc()).offset(offset).limit(limit).all()
    return results, total


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

def update_integration_config(
    db: Session,
    config: IntegrationConfig,
    **updates: object,
) -> IntegrationConfig:
    """Apply partial updates to an integration config.

    Guards: status must never be set to SYNC_SUCCEEDED via generic update.
    Only test_sync_connection() or a real sync loop may transition to SYNC_SUCCEEDED.
    """
    forbidden = {"status", "last_sync_at", "last_error"}
    for key, value in updates.items():
        if key in forbidden:
            continue
        if hasattr(config, key):
            setattr(config, key, value)
    db.commit()
    db.refresh(config)
    return config


def set_config_status(
    db: Session,
    config: IntegrationConfig,
    *,
    status: str,
    last_error: str | None = None,
) -> IntegrationConfig:
    """Explicitly set status (and optionally last_error) on a config.

    Allowed statuses: CONFIG_REQUIRED, REAL_API_READY, TEST_FAILED, SYNC_SUCCEEDED, SYNC_FAILED.
    """
    allowed = {
        "CONFIG_REQUIRED",
        "REAL_API_READY",
        "TEST_FAILED",
        "SYNC_SUCCEEDED",
        "SYNC_FAILED",
    }
    if status not in allowed:
        raise ValueError(f"Invalid status '{status}'. Must be one of {allowed}")
    config.status = status
    config.last_error = last_error
    config.last_sync_at = None
    db.commit()
    db.refresh(config)
    return config


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

def delete_integration_config(db: Session, config: IntegrationConfig) -> None:
    """Hard-delete an integration config."""
    db.delete(config)
    db.commit()
