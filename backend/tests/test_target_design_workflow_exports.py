"""Extended safety tests for workflow export/download endpoints (P7D).

Covers path traversal, blocked/expected artifacts, and attempts to download
forbidden files (weights, secrets, databases) through the workflow and model
registry artifact endpoints.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_active
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_download_dependency():
    """Exercise download rejection rules after satisfying the auth gate."""
    app.dependency_overrides[require_active] = lambda: object()
    yield
    app.dependency_overrides.pop(require_active, None)


BASE_PAYLOAD = {
    "target_sequence": "MKTIIALSYIFCLVFADYKDDDDK",
    "generator_model": "pepmlm",
    "ranker_model": "pepprclip",
    "structure_model": "evobind2",
    "num_candidates": 3,
    "peptide_length": 12,
    "top_k": 3,
    "dry_run": True,
}

P5C_JOB_ID = "db47863a-501b-435a-840c-254376798251"
P3B_JOB_ID = "b8ab6d11-5762-4bdf-a9db-6d30602637fd"


# ---------------------------------------------------------------------------
# Workflow report export safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "workflow_id",
    [
        "../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "..\\..\\windows\\system32\\drivers\\etc\\hosts",
        "latest%2F..%2Fetc%2Fpasswd",
    ],
)
def test_workflow_report_rejects_path_traversal(workflow_id: str) -> None:
    """Any traversal-like workflow_id must not reach the filesystem."""
    response = client.get(f"/api/v1/workflows/target-design/reports/{workflow_id}.json")
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Workflow artifact download safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "artifact_ref",
    [
        "../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "p5c-candidates-csv/../../etc/passwd",
        "p5c-candidates-csv/..%2F..%2Fetc%2Fpasswd",
        "ranking.csv",
        "scores.json",
        "workflow-lineage-json",
        ".env",
        "config.env",
        "app.db",
        "database.sqlite",
        "model.safetensors",
        "pytorch_model.bin",
        "canonical_miniclip_4-22-23.ckpt",
    ],
)
def test_workflow_artifact_download_rejects_forbidden_refs(artifact_ref: str) -> None:
    """Only whitelisted, existing artifact refs may be downloaded."""
    response = client.get(f"/api/v1/workflows/target-design/artifacts/{artifact_ref}/download")
    assert response.status_code in (400, 404), f"{artifact_ref} returned {response.status_code}"


def test_workflow_artifact_download_does_not_expose_absolute_paths() -> None:
    """Passing an absolute artifact path must not be interpreted as a ref."""
    response = client.get(
        "/api/v1/workflows/target-design/artifacts/"
        "%2Fhome%2Fxh%2Fkxc%2Fstampup%2Fstamp-targeted-peptide-platform-target-design-dev%2F.env"
        "/download"
    )
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Model registry artifact download safety
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "artifact_name",
    [
        "../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "/etc/passwd",
        "candidate_sequences.csv/../../etc/passwd",
        ".env",
        "config.env",
        "app.db",
        "database.sqlite",
        "model.safetensors",
        "pytorch_model.bin",
        "canonical_miniclip_4-22-23.ckpt",
    ],
)
def test_model_registry_artifact_download_rejects_forbidden_names(artifact_name: str) -> None:
    """Artifact names with separators or pointing to weights/secrets/DB are rejected."""
    response = client.get(
        f"/api/v1/models/pepmlm/jobs/{P5C_JOB_ID}/artifacts/{artifact_name}/download"
    )
    assert response.status_code in (400, 404)


@pytest.mark.parametrize(
    "model_id",
    ["../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "/etc/passwd", "pepmlm/../etc/passwd"],
)
def test_model_registry_rejects_model_id_traversal(model_id: str) -> None:
    """Model ID path traversal is rejected across endpoints."""
    response = client.get(f"/api/v1/models/{model_id}")
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# MiniCLIP checkpoint is not downloadable
# ---------------------------------------------------------------------------


def test_miniclip_checkpoint_not_exposed_via_workflow() -> None:
    """The MiniCLIP checkpoint path is not a whitelisted workflow artifact."""
    response = client.get(
        "/api/v1/workflows/target-design/artifacts/canonical_miniclip_4-22-23.ckpt/download"
    )
    assert response.status_code in (400, 404)


def test_miniclip_checkpoint_not_exposed_via_model_registry() -> None:
    """The MiniCLIP checkpoint path is not a valid PepPrCLIP artifact download."""
    response = client.get(
        "/api/v1/models/pepprclip/jobs/dry-run-placeholder/artifacts/"
        "canonical_miniclip_4-22-23.ckpt/download"
    )
    assert response.status_code in (400, 404)


# ---------------------------------------------------------------------------
# Existing artifacts remain downloadable
# ---------------------------------------------------------------------------


def test_p5c_csv_still_downloadable() -> None:
    response = client.get("/api/v1/workflows/target-design/artifacts/p5c-candidates-csv/download")
    assert response.status_code == 200
    assert "P5C_candidate_sequences.csv" in response.headers.get("content-disposition", "")


def test_p3b_pdb_still_downloadable() -> None:
    response = client.get("/api/v1/workflows/target-design/artifacts/p3b-pdb/download")
    assert response.status_code == 200
    assert "P3B_unrelaxed_true.pdb" in response.headers.get("content-disposition", "")
