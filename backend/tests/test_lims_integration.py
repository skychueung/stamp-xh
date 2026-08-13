"""Tests for LIMS/ELN IntegrationConfig (P6 REAL_API_READY framework).

v1.2-lab-production-fast
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import create_app

TEST_DB_URL = "sqlite:///:memory:"
_test_engine = create_engine(
    TEST_DB_URL, echo=False, future=True, connect_args={"check_same_thread": False}, poolclass=StaticPool
)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=_test_engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_test_engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=_test_engine)


@pytest.fixture
def test_app(db_session):
    Base.metadata.create_all(bind=db_session.bind)
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest_asyncio.fixture
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
def lims_config_payload():
    return {
        "integration_type": "LIMS",
        "name": "Test LIMS",
        "base_url": "https://example-lims.local/api/v1",
        "auth_mode": "token",
        "token_secret_ref": "TEST_LIMS_TOKEN",
        "field_mapping_json": {"sample_id": "external_sample_id"},
        "enabled": False,
        "test_mode": True,
    }


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_lims_config(async_client: AsyncClient, lims_config_payload: dict):
    resp = await async_client.post("/api/integrations", json=lims_config_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["integration_type"] == "LIMS"
    assert data["name"] == "Test LIMS"
    assert data["status"] == "CONFIG_REQUIRED"  # default until verified
    assert data["enabled"] is False
    assert data["test_mode"] is True
    assert "id" in data


@pytest.mark.asyncio
async def test_create_eln_config(async_client: AsyncClient):
    payload = {
        "integration_type": "ELN",
        "name": "Test ELN",
        "base_url": "https://example-eln.local",
        "auth_mode": "oauth2",
        "enabled": True,
    }
    resp = await async_client.post("/api/integrations", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["integration_type"] == "ELN"
    assert data["auth_mode"] == "oauth2"


@pytest.mark.asyncio
async def test_create_invalid_type(async_client: AsyncClient):
    resp = await async_client.post("/api/integrations", json={"integration_type": "INVALID", "name": "X"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_invalid_auth_mode(async_client: AsyncClient):
    resp = await async_client.post(
        "/api/integrations",
        json={"integration_type": "LIMS", "name": "X", "auth_mode": "digest"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List / Get
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_and_get_integration(async_client: AsyncClient, lims_config_payload: dict):
    create_resp = await async_client.post("/api/integrations", json=lims_config_payload)
    created = create_resp.json()

    # list
    list_resp = await async_client.get("/api/integrations")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert list_data["total"] >= 1
    ids = {item["id"] for item in list_data["items"]}
    assert created["id"] in ids

    # get single
    get_resp = await async_client.get(f"/api/integrations/{created['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == created["id"]


@pytest.mark.asyncio
async def test_get_not_found(async_client: AsyncClient):
    resp = await async_client.get(f"/api/integrations/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_patch_integration(async_client: AsyncClient, lims_config_payload: dict):
    create_resp = await async_client.post("/api/integrations", json=lims_config_payload)
    cid = create_resp.json()["id"]

    resp = await async_client.patch(f"/api/integrations/{cid}", json={"name": "Updated LIMS"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Updated LIMS"
    # Status should transition to REAL_API_READY because base_url + token_secret_ref present
    assert data["status"] == "REAL_API_READY"


@pytest.mark.asyncio
async def test_patch_does_not_override_status_directly(async_client: AsyncClient, lims_config_payload: dict):
    """Generic PATCH must not allow direct status tampering."""
    create_resp = await async_client.post("/api/integrations", json=lims_config_payload)
    cid = create_resp.json()["id"]

    resp = await async_client.patch(f"/api/integrations/{cid}", json={"status": "SYNC_SUCCEEDED"})
    assert resp.status_code == 200
    data = resp.json()
    # Status should remain what it was, because 'status' is ignored by generic update
    assert data["status"] != "SYNC_SUCCEEDED"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_delete_integration(async_client: AsyncClient, lims_config_payload: dict):
    create_resp = await async_client.post("/api/integrations", json=lims_config_payload)
    cid = create_resp.json()["id"]

    del_resp = await async_client.delete(f"/api/integrations/{cid}")
    assert del_resp.status_code == 204

    get_resp = await async_client.get(f"/api/integrations/{cid}")
    assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test sync connection
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_test_sync_no_base_url(async_client: AsyncClient, lims_config_payload: dict):
    """If base_url is missing, test-sync should leave status as CONFIG_REQUIRED."""
    payload = {**lims_config_payload, "base_url": None, "token_secret_ref": None}
    create_resp = await async_client.post("/api/integrations", json=payload)
    cid = create_resp.json()["id"]

    resp = await async_client.post(f"/api/integrations/{cid}/test-sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "CONFIG_REQUIRED"
    assert "base_url is required" in (data["last_error"] or "")


@pytest.mark.asyncio
async def test_test_sync_unreachable(async_client: AsyncClient, lims_config_payload: dict):
    """Unreachable URL → TEST_FAILED. No fake success."""
    payload = {
        **lims_config_payload,
        "base_url": "http://localhost:59999/unreachable",
        "token_secret_ref": "FAKE_TOKEN",
    }
    create_resp = await async_client.post("/api/integrations", json=payload)
    cid = create_resp.json()["id"]

    resp = await async_client.post(f"/api/integrations/{cid}/test-sync")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "TEST_FAILED"
    assert data["last_error"] is not None


# ---------------------------------------------------------------------------
# Admin set-status
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_status_endpoint(async_client: AsyncClient, lims_config_payload: dict):
    create_resp = await async_client.post("/api/integrations", json=lims_config_payload)
    cid = create_resp.json()["id"]

    resp = await async_client.post(f"/api/integrations/{cid}/set-status", params={"status": "SYNC_FAILED"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "SYNC_FAILED"

    resp2 = await async_client.post(f"/api/integrations/{cid}/set-status", params={"status": "INVALID"})
    assert resp2.status_code == 422


# ---------------------------------------------------------------------------
# Filtered list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_filter_by_type(async_client: AsyncClient, lims_config_payload: dict):
    await async_client.post("/api/integrations", json=lims_config_payload)
    eln_payload = {
        "integration_type": "ELN",
        "name": "ELN Config",
        "base_url": "https://eln.local",
        "auth_mode": "token",
    }
    await async_client.post("/api/integrations", json=eln_payload)

    resp = await async_client.get("/api/integrations?integration_type=LIMS")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["integration_type"] == "LIMS"


@pytest.mark.asyncio
async def test_list_filter_by_enabled(async_client: AsyncClient):
    payload = {"integration_type": "LIMS", "name": "Enabled LIMS", "enabled": True}
    await async_client.post("/api/integrations", json=payload)

    resp = await async_client.get("/api/integrations?enabled=true")
    assert resp.status_code == 200
    data = resp.json()
    for item in data["items"]:
        assert item["enabled"] is True
