"""Tests for the Targeted Peptide Design Center model probe endpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.main import create_app
from app.services import target_peptide_model_probe as probe_service


@pytest.fixture()
def temp_probe_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    design_root = tmp_path / "data_dev" / "target_peptide_design"
    probe_root = design_root / "probes"
    models_dir = tmp_path / "models_dev"
    models_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(probe_service, "get_target_peptide_design_root", lambda: design_root)
    monkeypatch.setattr(probe_service, "get_target_peptide_design_probe_root", lambda: probe_root)
    monkeypatch.setattr(probe_service.settings, "target_peptide_models_dir", str(models_dir), raising=False)
    monkeypatch.setattr(probe_service.settings, "pepmlm_model_path", None, raising=False)
    monkeypatch.setattr(probe_service.settings, "pepmlm_hf_model_id", None, raising=False)
    monkeypatch.setattr(probe_service.settings, "pepmlm_allow_download", False, raising=False)
    monkeypatch.setattr(probe_service.settings, "pepmlm_offline_only", True, raising=False)
    monkeypatch.setattr(
        probe_service,
        "_collect_pepmlm_env_probe",
        lambda: {
            "probe_time": "2026-06-02T00:00:00+00:00",
            "status": "DEPENDENCY_MISSING",
            "message": "PepMLM isolated environment dependencies are missing; no inference was executed.",
            "backend_env_status": "DEPENDENCY_MISSING",
            "pepmlm_env_status": "DEPENDENCY_MISSING",
            "pepmlm_env_python": "/opt/stampup/envs/pepmlm/bin/python",
            "pepmlm_env_check_script": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env_check.sh",
            "recommended_runtime_env": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env.sh",
            "python_version": "3.12.3",
            "dependency_status": {
                "torch": {"available": False, "version": None, "error": "torch missing"},
                "transformers": {"available": False, "version": None, "error": "transformers missing"},
                "huggingface_hub": {"available": False, "version": None, "error": "huggingface_hub missing"},
            },
            "cuda_status": {"available": False, "device_count": 0, "devices": [], "torch_cuda_version": None, "current_device": None, "error": None},
            "path_status": {
                "pepmlm_model_path": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "pepmlm_source_path": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "models_dev": {"path": str(models_dir), "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "data_dev_target_peptide_design": {"path": str(design_root), "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
            },
            "config_status": {
                "pepmlm_model_path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M",
                "pepmlm_source_path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm",
                "pepmlm_allow_download": False,
                "pepmlm_offline_only": True,
                "hf_home": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/hf_home",
                "transformers_cache": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/transformers_cache",
                "torch_home": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/torch_cache",
            },
            "writeability": {"models_dev": True, "data_dev_target_peptide_design": True},
            "model_artifacts": {"exists": True, "is_dir": True, "empty": False},
            "source_artifacts": {"exists": True, "is_dir": True, "git_commit": "3169c4920f8c383948e0a5d3a7c8f87e5e7d2436"},
            "scientific_boundary": "Current phase only performs environment probes; no model download or inference was run.",
            "next_action": "Install missing isolated-runtime dependencies first.",
        },
        raising=False,
    )
    return {
        "design_root": design_root,
        "probe_root": probe_root,
        "models_dir": models_dir,
    }


@pytest.fixture()
def test_app(temp_probe_root: dict[str, Path]):
    return create_app()


@pytest_asyncio.fixture()
async def async_client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.mark.asyncio
async def test_models_probe_endpoint_returns_summary(async_client: AsyncClient, temp_probe_root: dict[str, Path]):
    response = await async_client.get("/api/v1/target-peptide-design/models/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["summary"]["total_models"] == 9
    assert data["summary"]["pepmlm_status"]
    assert len(data["probes"]) == 9
    assert temp_probe_root["probe_root"].exists()
    saved_files = list(temp_probe_root["probe_root"].glob("models_probe_*.json"))
    assert saved_files, "expected models probe artifact to be written"


@pytest.mark.asyncio
async def test_pepmlm_probe_endpoint_returns_probe_payload(async_client: AsyncClient, temp_probe_root: dict[str, Path]):
    response = await async_client.get("/api/v1/target-peptide-design/models/pepmlm/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    assert data["status"] in {"CONFIG_REQUIRED", "DEPENDENCY_MISSING", "OFFLINE_ONLY", "smoke_rerun_verified"}
    assert data["scientific_boundary"]
    assert data["next_action"]
    saved_files = list(temp_probe_root["probe_root"].glob("pepmlm_probe_*.json"))
    assert saved_files, "expected PepMLM probe artifact to be written"
    persisted = json.loads(saved_files[0].read_text(encoding="utf-8"))
    assert persisted["model_id"] == "pepmlm"
    assert "candidates" not in persisted


@pytest.mark.asyncio
async def test_unconfigured_pepmlm_probe_reports_config_required(async_client: AsyncClient):
    response = await async_client.get("/api/v1/target-peptide-design/models/PepMLM/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["status"] in {"CONFIG_REQUIRED", "OFFLINE_ONLY", "DEPENDENCY_MISSING"}
    assert data["config_status"]["pepmlm_model_path_configured"] is False
    assert data["config_status"]["pepmlm_hf_model_id_configured"] is False


@pytest.mark.asyncio
async def test_dependency_missing_does_not_crash(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    original_safe_import = probe_service._safe_import_module

    def fake_import(module_name: str):
        if module_name in {"torch", "transformers", "huggingface_hub"}:
            return {"available": False, "version": None, "error": f"{module_name} missing"}
        return original_safe_import(module_name)

    monkeypatch.setattr(probe_service, "_safe_import_module", fake_import)
    response = await async_client.get("/api/v1/target-peptide-design/models/PepMLM/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["status"] == "DEPENDENCY_MISSING"
    assert data["dependency_status"]["torch"]["available"] is False
    assert data["dependency_status"]["transformers"]["available"] is False
    assert data["dependency_status"]["huggingface_hub"]["available"] is False


@pytest.mark.asyncio
async def test_probe_response_does_not_leak_token_or_scientific_metrics(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("HUGGINGFACE_HUB_TOKEN", "super-secret-token")
    response = await async_client.get("/api/v1/target-peptide-design/models/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    body = response.text.lower()
    assert "super-secret-token" not in response.text
    assert "kd" not in body
    assert "mic" not in body
    assert "mm-gbsa" not in body
    assert "iptm" not in body
    assert "plddt" not in body
    assert "rmsd" not in body
    assert "rmsf" not in body


@pytest.mark.asyncio
async def test_probe_payload_has_no_candidates_field(async_client: AsyncClient):
    response = await async_client.get("/api/v1/target-peptide-design/models/PepMLM/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert "candidates" not in data
    assert "candidate" not in data


@pytest.mark.asyncio
async def test_models_probe_reports_isolated_env_metadata(async_client: AsyncClient):
    response = await async_client.get("/api/v1/target-peptide-design/models/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["summary"]["pepmlm_env_check_script"]
    assert data["summary"]["recommended_runtime_env"]
    assert data["summary"]["backend_env_status"] in {"DEPENDENCY_MISSING", "AVAILABLE", "CONFIG_REQUIRED", "GPU_NOT_AVAILABLE", "MODEL_NOT_AVAILABLE", "OFFLINE_ONLY"}


@pytest.mark.asyncio
async def test_pepmlm_probe_reports_isolated_env_fields(async_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        probe_service,
        "_collect_pepmlm_env_probe",
        lambda: {
            "probe_time": "2026-06-02T00:00:00+00:00",
            "status": "AVAILABLE",
            "message": "PepMLM isolated environment probe passed; no real inference was attempted in P6.",
            "backend_env_status": "DEPENDENCY_MISSING",
            "pepmlm_env_status": "AVAILABLE",
            "pepmlm_env_python": "/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python3",
            "pepmlm_env_check_script": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env_check.sh",
            "recommended_runtime_env": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/scripts/ops/stampup_pepmlm_env.sh",
            "dependency_status": {
                "torch": {"available": True, "version": "2.6.0+cu124", "error": None},
                "transformers": {"available": True, "version": "4.57.1", "error": None},
                "huggingface_hub": {"available": True, "version": "0.34.4", "error": None},
            },
            "cuda_status": {"available": True, "device_count": 2, "devices": [{"index": 0, "name": "NVIDIA GeForce RTX 4090"}, {"index": 1, "name": "NVIDIA GeForce RTX 4090"}], "torch_cuda_version": "12.4", "current_device": 0, "error": None},
            "path_status": {
                "pepmlm_model_path": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "pepmlm_source_path": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "models_dev": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
                "data_dev_target_peptide_design": {"path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/target_peptide_design", "exists": True, "is_dir": True, "readable": True, "writable": True, "empty": False},
            },
            "config_status": {
                "pepmlm_model_path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M",
                "pepmlm_source_path": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm",
                "pepmlm_allow_download": False,
                "pepmlm_offline_only": True,
                "hf_home": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/hf_home",
                "transformers_cache": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/transformers_cache",
                "torch_home": "/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/torch_cache",
            },
            "writeability": {"models_dev": True, "data_dev_target_peptide_design": True},
            "model_artifacts": {"exists": True, "is_dir": True, "empty": False},
            "source_artifacts": {"exists": True, "is_dir": True, "git_commit": "3169c4920f8c383948e0a5d3a7c8f87e5e7d2436"},
            "scientific_boundary": "Current phase only performs environment probes; no model download or inference was run.",
            "next_action": "PepMLM isolated runtime is ready; keep inference gated by later workflow approval.",
        },
        raising=False,
    )
    response = await async_client.get("/api/v1/target-peptide-design/models/PepMLM/probe")
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()["data"]
    assert data["status"] == "AVAILABLE"
    assert data["backend_env_status"] == "DEPENDENCY_MISSING"
    assert data["pepmlm_env_status"] == "AVAILABLE"
    assert data["pepmlm_env_python"]
    assert data["pepmlm_env_check_script"].endswith("stampup_pepmlm_env_check.sh")
    assert data["recommended_runtime_env"].endswith("stampup_pepmlm_env.sh")
    assert "candidates" not in data
    assert "Kd" not in response.text
    assert "MM-GBSA" not in response.text
