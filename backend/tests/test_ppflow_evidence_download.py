"""P33P PPFlow safe evidence download zero-model verification.

This test does not load any checkpoint, import any model runner, or execute any
model. It only exercises the read-only evidence metadata + whitelisted download
endpoints and asserts the safety contract (whitelist, no traversal, no symlink
escape, no unknown id, SHA256 verification).

P33Q update: the evidence contract is now unified across all six models, so
pepmlm is no longer 404 — it returns its own evidence bundle. The ppflow-only
safety assertions below remain valid.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_WANT_SHA = {
    "success_report": "8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293",
    "execution_manifest": "1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307",
    "result_manifest": "6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00",
    "status": "3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8",
}


def test_evidence_metadata_returns_structured_block() -> None:
    response = client.get("/api/v1/models/ppflow/evidence")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "ppflow"
    assert data["stage"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert data["execution_locked"] is True
    assert data["real_run_enabled"] is False
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert set(data["downloadable_ids"]) == set(_WANT_SHA.keys())


def test_each_whitelisted_evidence_downloads_and_sha_matches() -> None:
    import hashlib

    for evidence_id, want_sha in _WANT_SHA.items():
        response = client.get(f"/api/v1/models/ppflow/evidence/{evidence_id}/download")
        assert response.status_code == 200, evidence_id
        actual_sha = hashlib.sha256(response.content).hexdigest()
        assert actual_sha == want_sha, f"{evidence_id} sha mismatch"


def test_traversal_evidence_id_rejected() -> None:
    for bad in ("..", "../etc/passwd", "..\\etc\\passwd", "foo/bar"):
        response = client.get(f"/api/v1/models/ppflow/evidence/{bad}/download")
        assert response.status_code in (400, 404), bad


def test_unknown_evidence_id_rejected() -> None:
    response = client.get("/api/v1/models/ppflow/evidence/unknown_id/download")
    assert response.status_code == 404


def test_pepmlm_evidence_now_available_unified() -> None:
    """P33Q: pepmlm now exposes a unified evidence bundle (no longer 404)."""
    response = client.get("/api/v1/models/pepmlm/evidence")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    assert data["availability"] == "available"
    assert "success_report" in data["downloadable_ids"]
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    # pepmlm evidence download now works too
    dl = client.get("/api/v1/models/pepmlm/evidence/success_report/download")
    assert dl.status_code == 200


def test_unknown_model_evidence_not_found() -> None:
    response = client.get("/api/v1/models/unknown_model_xyz/evidence")
    assert response.status_code == 404
