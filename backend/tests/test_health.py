"""
Tests for the Health Check endpoint.

Covers:
    - GET /health returns 200 with expected payload shape.
    - Response conforms to ApiResponse envelope.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient) -> None:
    """GET /health must return 200 with healthy status and version info.

    The response body follows the unified ApiResponse envelope::

        {
            "code": 200,
            "message": "ok",
            "data": {"status": "healthy", "version": "v0.6d"}
        }

    Args:
        client: Async HTTP test client (from conftest).
    """
    response = await client.get("/health")

    assert response.status_code == 200, (
        f"Expected HTTP 200 from /health, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 200, "ApiResponse.code must be 200"
    assert "message" in body, "ApiResponse must contain 'message' field"
    assert "data" in body, "ApiResponse must contain 'data' field"

    data = body["data"]
    assert isinstance(data, dict), "data field must be a dict"
    assert data.get("status") == "healthy", "Health status must be 'healthy'"
    assert "version" in data, "Health data must include 'version'"
