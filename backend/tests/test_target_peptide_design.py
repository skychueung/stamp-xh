"""Tests for the Targeted Peptide Design Center skeleton."""

from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services import target_peptide_design_service as service


@pytest.fixture()
def temp_design_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    root = tmp_path / "data_dev" / "target_peptide_design"
    monkeypatch.setattr(service, "get_target_peptide_design_root", lambda: root)
    return root


@pytest.fixture()
def test_app(temp_design_root: Path):
    # Ensure the app starts with the actual dev settings, but the service writes into tmp_path.
    return create_app()


@pytest_asyncio.fixture()
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_models_endpoint_returns_registry(async_client: AsyncClient):
    response = await async_client.get("/api/v1/target-peptide-design/models")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert "models" in data
    assert len(data["models"]) == 9
    model_ids = {item["model_id"] for item in data["models"]}
    assert "pepmlm" in model_ids
    assert data["scientific_boundary"]


@pytest.mark.asyncio
async def test_create_job_writes_artifacts_and_planned_status(async_client: AsyncClient, temp_design_root: Path):
    payload = {
        "target_name": "OprF",
        "target_sequence": ">example\nMKTAIAIAIVAA\n",
        "model_id": "PepPrCLIP",
        "peptide_length": 12,
        "num_candidates": 20,
        "notes": "skeleton test",
    }
    response = await async_client.post("/api/v1/target-peptide-design/jobs", json=payload)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    assert data["target_sequence"] == "MKTAIAIAIVAA"
    assert data["status"] == "PLANNED"
    artifact_dir = Path(data["artifact_dir"])
    assert artifact_dir.exists()
    assert artifact_dir.is_dir()
    assert artifact_dir.parts[-3:] == ("target_peptide_design", "jobs", artifact_dir.name)
    assert (artifact_dir / "request.json").exists()
    assert (artifact_dir / "model_status.json").exists()
    assert (artifact_dir / "job_status.json").exists()
    assert (artifact_dir / "candidates.json").exists()
    request_json = (artifact_dir / "request.json").read_text(encoding="utf-8")
    assert "MKTAIAIAIVAA" in request_json
    assert "PepPrCLIP" in request_json
    assert data["scientific_boundary"]


@pytest.mark.asyncio
async def test_create_pepmlm_job_returns_config_required(async_client: AsyncClient):
    payload = {
        "target_name": "OprF",
        "target_sequence": "MKTAAIAIVAA",
        "model_id": "PepMLM",
        "peptide_length": 11,
        "num_candidates": 10,
        "notes": "pepmlm skeleton",
    }
    response = await async_client.post("/api/v1/target-peptide-design/jobs", json=payload)
    assert response.status_code == status.HTTP_201_CREATED, response.text
    data = response.json()["data"]
    assert data["status"] == "CONFIG_REQUIRED"
    assert "PepMLM" in data["message"]
    assert "no model" in data["message"].lower() or "not configured" in data["message"].lower()


@pytest.mark.asyncio
async def test_invalid_target_sequence_returns_422(async_client: AsyncClient):
    payload = {
        "target_name": "OprF",
        "target_sequence": "MKTAX",
        "model_id": "PepPrCLIP",
        "peptide_length": 10,
        "num_candidates": 5,
    }
    response = await async_client.post("/api/v1/target-peptide-design/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "non-standard" in response.text.lower() or "target_sequence" in response.text


@pytest.mark.asyncio
async def test_get_job_returns_expected_fields(async_client: AsyncClient):
    create_resp = await async_client.post(
        "/api/v1/target-peptide-design/jobs",
        json={
            "target_name": "OprF",
            "target_sequence": "MKTAAIAIVAA",
            "model_id": "PepPrCLIP",
            "peptide_length": 11,
            "num_candidates": 5,
        },
    )
    job_id = create_resp.json()["data"]["job_id"]
    response = await async_client.get(f"/api/v1/target-peptide-design/jobs/{job_id}")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["job_id"] == job_id
    assert data["model_id"] == "PepPrCLIP"
    assert data["artifact_dir"].endswith(job_id)
    assert data["scientific_boundary"]
    assert data["message"]


@pytest.mark.asyncio
async def test_candidates_endpoint_returns_empty_array(async_client: AsyncClient):
    create_resp = await async_client.post(
        "/api/v1/target-peptide-design/jobs",
        json={
            "target_name": "OprF",
            "target_sequence": "MKTAAIAIVAA",
            "model_id": "PepPrCLIP",
            "peptide_length": 11,
            "num_candidates": 5,
        },
    )
    job_id = create_resp.json()["data"]["job_id"]
    response = await async_client.get(f"/api/v1/target-peptide-design/jobs/{job_id}/candidates")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()["data"]
    assert data["job_id"] == job_id
    assert data["candidates"] == []
    assert "no real model" in data["note"].lower()
    assert "scientific_boundary" in data
    assert "kd" not in response.text.lower()
    assert "mic" not in response.text.lower()
    assert "mm-gbsa" not in response.text.lower()
    assert "iptm" not in response.text.lower()
    assert "plddt" not in response.text.lower()
