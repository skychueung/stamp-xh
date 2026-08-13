"""Tests for the target-design workflow dry-run skeleton (P7A/P7C)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.security import require_active
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_download_dependency():
    """Exercise the whitelist behind the production authentication gate."""
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


def test_target_design_dry_run_returns_plan() -> None:
    response = client.post("/api/v1/workflows/target-design/dry-run", json=BASE_PAYLOAD)
    assert response.status_code == 200
    data = response.json()["data"]

    assert data["workflow_type"] == "target-design"
    assert data["status"] == "BLOCKED_WITH_NOTES"
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert "MiniCLIP checkpoint missing" in " ".join(data["blocked_reasons"])
    assert data["safety_flags"]["executed_model"] is False
    assert data["safety_flags"]["computational_prediction_only"] is True

    steps = data["steps"]
    assert len(steps) == 4
    assert steps[0]["model_id"] == "pepmlm"
    assert steps[1]["model_id"] == "pepprclip"
    assert steps[2]["model_id"] == "evobind2"
    assert steps[3]["model_id"] == "molstar"
    assert steps[0]["status"] == "READY"
    assert steps[1]["status"] == "READY"
    assert steps[1]["blocked_reason"] == (
        "BLOCKED_LICENSE_OR_TOKEN_REQUIRED: MiniCLIP checkpoint missing"
    )
    assert "output/ranking.csv" in steps[1]["expected_artifacts"]
    assert steps[2]["status"] == "BLOCKED"
    assert "Real execution is gated" in steps[2]["message"]
    assert steps[3]["status"] == "READY"

    expected = data["expected_artifacts"]
    assert "pepmlm/output/candidate_sequences.csv" in expected
    assert "pepprclip/output/ranking.csv" in expected
    assert "evobind2/output/unrelaxed_true.pdb" in expected
    assert "manifest/workflow_lineage.json" in expected
    assert "logs/workflow.log" in expected

    assert data["prior_artifacts_referenced"]["pepmlm_p5c_job_id"] == (
        "db47863a-501b-435a-840c-254376798251"
    )
    references = data["artifact_references"]
    assert any(
        item["artifact_name"] == "candidate_sequences.csv" and item["status"] == "Exists"
        for item in references
    )
    assert any(
        item["artifact_name"] == "ranking.csv"
        and item["status"] == "Blocked"
        and "BLOCKED_LICENSE_OR_TOKEN_REQUIRED" in item["reason"]
        for item in references
    )
    assert any(
        item["artifact_name"] == "unrelaxed_true.pdb" and item["status"] == "Exists"
        for item in references
    )


def test_target_design_dry_run_rejects_unsupported_models() -> None:
    payload = {**BASE_PAYLOAD, "generator_model": "rfpeptides"}
    response = client.post("/api/v1/workflows/target-design/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "BLOCKED_WITH_NOTES"
    assert any("rfpeptides" in reason for reason in data["blocked_reasons"])


def test_target_design_dry_run_rejects_short_sequence() -> None:
    payload = {**BASE_PAYLOAD, "target_sequence": ""}
    response = client.post("/api/v1/workflows/target-design/dry-run", json=payload)
    assert response.status_code == 422


def test_target_design_dry_run_persists_latest_result() -> None:
    """P7C: the dry-run result is persisted and retrievable as 'latest'."""
    response = client.post("/api/v1/workflows/target-design/dry-run", json=BASE_PAYLOAD)
    assert response.status_code == 200
    workflow_id = response.json()["data"]["workflow_id"]

    latest = client.get("/api/v1/workflows/target-design/reports/latest.json")
    assert latest.status_code == 200
    report = latest.json()
    assert report["workflow_id"] == workflow_id
    assert report["dry_run"] is True

    specific = client.get(f"/api/v1/workflows/target-design/reports/{workflow_id}.json")
    assert specific.status_code == 200
    assert specific.json()["workflow_id"] == workflow_id


def test_workflow_artifact_download_whitelist() -> None:
    """P7C: only whitelisted Exists artifacts can be downloaded."""
    for ref, expected_name in [
        ("p5c-candidates-csv", "P5C_candidate_sequences.csv"),
        ("p5c-candidates-json", "P5C_candidate_sequences.json"),
        ("p3b-pdb", "P3B_unrelaxed_true.pdb"),
    ]:
        response = client.get(f"/api/v1/workflows/target-design/artifacts/{ref}/download")
        assert response.status_code == 200, f"{ref} should be downloadable"
        disposition = response.headers.get("content-disposition", "")
        assert expected_name in disposition


def test_workflow_artifact_download_rejects_blocked_refs() -> None:
    """P7C: blocked / expected artifact refs are not served."""
    for ref in ["pepprclip-ranking-csv", "workflow-lineage-json", "ranking.csv", "scores.json"]:
        response = client.get(f"/api/v1/workflows/target-design/artifacts/{ref}/download")
        assert response.status_code == 404, f"{ref} should not be downloadable"


def test_workflow_artifact_download_rejects_path_traversal() -> None:
    """P7C: path traversal attempts are rejected."""
    for ref in ["../etc/passwd", "p5c-candidates-csv/../../etc/passwd", "..%2F..%2Fetc%2Fpasswd"]:
        response = client.get(f"/api/v1/workflows/target-design/artifacts/{ref}/download")
        assert response.status_code in (400, 404)


def test_workflow_report_export_latest_markdown() -> None:
    """P7C: Markdown report export works for the latest dry-run."""
    response = client.post("/api/v1/workflows/target-design/dry-run", json=BASE_PAYLOAD)
    assert response.status_code == 200
    workflow_id = response.json()["data"]["workflow_id"]

    md = client.get("/api/v1/workflows/target-design/reports/latest.md")
    assert md.status_code == 200
    assert "text/markdown" in md.headers.get("content-type", "")
    body = md.text
    assert workflow_id in body
    assert "dry-run" in body.lower()
    assert "MiniCLIP checkpoint missing" in body


def test_workflow_report_export_404_for_unknown_workflow() -> None:
    """P7C: exporting a non-existent workflow returns 404."""
    response = client.get("/api/v1/workflows/target-design/reports/does-not-exist.json")
    assert response.status_code == 404

    response = client.get("/api/v1/workflows/target-design/reports/does-not-exist.md")
    assert response.status_code == 404
