"""Tests for Resource Probe Service and /health/resources endpoint."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.services.resource_probe import probe_resources


def test_probe_resources_returns_expected_shape():
    """probe_resources() must return a dict with all required keys."""
    data = probe_resources()
    assert "status" in data
    assert "gpus" in data
    assert "cpu" in data
    assert "ram" in data
    assert "disk" in data
    assert "gpu_lock" in data
    assert "blocked_reasons" in data
    assert isinstance(data["gpus"], list)
    assert isinstance(data["cpu"], dict)
    assert isinstance(data["ram"], dict)
    assert isinstance(data["disk"], dict)
    assert isinstance(data["gpu_lock"], dict)


def test_probe_resources_gpu_lock_integration():
    """probe_resources() must reflect GPU lock state accurately."""
    lock_path = Path(tempfile.gettempdir()) / "test_stamp_gpu_probe.lock"
    if lock_path.exists():
        lock_path.unlink()

    with patch("app.services.resource_probe.probe_gpu_lock_status") as mock_lock:
        mock_lock.return_value = {"locked": False, "holder": None, "held_since_seconds": None}
        data = probe_resources()
        assert data["gpu_lock"]["locked"] is False

        mock_lock.return_value = {"locked": True, "holder": "job-123", "held_since_seconds": 12.3}
        data = probe_resources()
        assert data["gpu_lock"]["locked"] is True
        assert data["gpu_lock"]["holder"] == "job-123"
        assert data["status"] == "blocked"
        assert any("GPU lock" in r for r in (data["blocked_reasons"] or []))


def test_probe_resources_blocked_when_gpu_mem_high():
    """When GPU memory usage exceeds threshold, status should be blocked."""
    fake_gpu = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 4090",
            "memory_used_mb": 23000,
            "memory_total_mb": 24564,
            "memory_free_mb": 1564,
            "utilization_percent": 95,
        }
    ]
    with patch("app.services.resource_probe._run_nvidia_smi", return_value=fake_gpu):
        with patch("app.services.resource_probe.probe_gpu_lock_status") as mock_lock:
            mock_lock.return_value = {"locked": False, "holder": None, "held_since_seconds": None}
            data = probe_resources()
            assert data["status"] == "blocked"
            assert any("GPU 0 memory" in r for r in (data["blocked_reasons"] or []))


def test_probe_resources_blocked_when_ram_high():
    """When RAM usage exceeds threshold, status should be blocked."""
    fake_ram = {
        "total_mb": 64000.0,
        "used_mb": 60000.0,
        "free_mb": 4000.0,
        "utilization_percent": 93.75,
    }
    with patch("app.services.resource_probe._read_ram_usage", return_value=fake_ram):
        with patch("app.services.resource_probe._run_nvidia_smi", return_value=[]):
            with patch("app.services.resource_probe.probe_gpu_lock_status") as mock_lock:
                mock_lock.return_value = {"locked": False, "holder": None, "held_since_seconds": None}
                data = probe_resources()
                assert data["status"] == "blocked"
                assert any("RAM usage" in r for r in (data["blocked_reasons"] or []))


def test_probe_resources_healthy_when_all_clear():
    """When all resources are within limits, status should be healthy."""
    fake_gpu = [
        {
            "index": 0,
            "name": "NVIDIA GeForce RTX 4090",
            "memory_used_mb": 1000,
            "memory_total_mb": 24564,
            "memory_free_mb": 23564,
            "utilization_percent": 5,
        },
        {
            "index": 1,
            "name": "NVIDIA GeForce RTX 4090",
            "memory_used_mb": 500,
            "memory_total_mb": 24564,
            "memory_free_mb": 24064,
            "utilization_percent": 2,
        },
    ]
    fake_cpu = {"cores": 16, "load_1min": 2.0, "utilization_percent": 12.5}
    fake_ram = {"total_mb": 64000.0, "used_mb": 16000.0, "free_mb": 48000.0, "utilization_percent": 25.0}
    fake_disk = {"total_gb": 500.0, "used_gb": 100.0, "free_gb": 400.0, "utilization_percent": 20.0}

    with patch("app.services.resource_probe._run_nvidia_smi", return_value=fake_gpu):
        with patch("app.services.resource_probe._read_cpu_load", return_value=fake_cpu):
            with patch("app.services.resource_probe._read_ram_usage", return_value=fake_ram):
                with patch("app.services.resource_probe._read_disk_usage", return_value=fake_disk):
                    with patch("app.services.resource_probe.probe_gpu_lock_status") as mock_lock:
                        mock_lock.return_value = {"locked": False, "holder": None, "held_since_seconds": None}
                        data = probe_resources()
                        assert data["status"] == "healthy"
                        assert data["blocked_reasons"] is None
                        assert len(data["gpus"]) == 2
                        assert data["gpus"][0]["name"] == "NVIDIA GeForce RTX 4090"


@pytest.mark.asyncio
async def test_health_resources_endpoint(client: AsyncClient) -> None:
    """GET /health/resources must return 200 with expected payload shape."""
    with patch("app.routers.health.probe_resources") as mock_probe:
        mock_probe.return_value = {
            "status": "healthy",
            "gpus": [
                {
                    "index": 0,
                    "name": "NVIDIA GeForce RTX 4090",
                    "memory_used_mb": 1000,
                    "memory_total_mb": 24564,
                    "memory_free_mb": 23564,
                    "utilization_percent": 5,
                },
                {
                    "index": 1,
                    "name": "NVIDIA GeForce RTX 4090",
                    "memory_used_mb": 500,
                    "memory_total_mb": 24564,
                    "memory_free_mb": 24064,
                    "utilization_percent": 2,
                },
            ],
            "cpu": {"cores": 16, "load_1min": 2.0, "utilization_percent": 12.5},
            "ram": {"total_mb": 64000.0, "used_mb": 16000.0, "free_mb": 48000.0, "utilization_percent": 25.0},
            "disk": {"total_gb": 500.0, "used_gb": 100.0, "free_gb": 400.0, "utilization_percent": 20.0},
            "gpu_lock": {"locked": False, "holder": None, "held_since_seconds": None},
            "blocked_reasons": None,
        }
        response = await client.get("/health/resources")

    assert response.status_code == 200, (
        f"Expected HTTP 200 from /health/resources, got {response.status_code}"
    )

    body = response.json()
    assert body.get("code") == 200, "ApiResponse.code must be 200"
    assert "data" in body, "ApiResponse must contain 'data' field"

    data = body["data"]
    assert isinstance(data, dict), "data field must be a dict"
    assert data.get("status") == "healthy"
    assert len(data.get("gpus", [])) == 2
    assert data["gpus"][0]["name"] == "NVIDIA GeForce RTX 4090"
    assert data["gpu_lock"]["locked"] is False


@pytest.mark.asyncio
async def test_health_resources_endpoint_blocked(client: AsyncClient) -> None:
    """GET /health/resources must return BLOCKED when resources are insufficient."""
    with patch("app.routers.health.probe_resources") as mock_probe:
        mock_probe.return_value = {
            "status": "blocked",
            "gpus": [],
            "cpu": {"cores": 16, "load_1min": 20.0, "utilization_percent": 125.0},
            "ram": {"total_mb": 64000.0, "used_mb": 60000.0, "free_mb": 4000.0, "utilization_percent": 93.75},
            "disk": {"total_gb": 500.0, "used_gb": 100.0, "free_gb": 400.0, "utilization_percent": 20.0},
            "gpu_lock": {"locked": False, "holder": None, "held_since_seconds": None},
            "blocked_reasons": ["CPU load 125.0% exceeds threshold", "RAM usage 93.75% exceeds threshold"],
        }
        response = await client.get("/health/resources")

    assert response.status_code == 200
    body = response.json()
    data = body["data"]
    assert data.get("status") == "blocked"
    assert isinstance(data.get("blocked_reasons"), list)
    assert len(data["blocked_reasons"]) == 2
