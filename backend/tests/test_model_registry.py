"""Tests for the unified Model Registry API and adapters (P4A)."""

from __future__ import annotations


import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

P3B_JOB_ID = "b8ab6d11-5762-4bdf-a9db-6d30602637fd"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def compute_enabled_client(monkeypatch) -> TestClient:
    """Client with compute endpoints enabled for artifact tests."""
    from app.core import public_safety

    monkeypatch.setattr(public_safety.settings, "public_demo_mode", False)
    monkeypatch.setattr(public_safety.settings, "enable_compute_endpoints", True)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Registry listing
# ---------------------------------------------------------------------------


def test_list_models_returns_registry() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    data = response.json()["data"]
    model_ids = {m["model_id"] for m in data["models"]}
    assert "evobind2" in model_ids
    assert "pepmlm" in model_ids
    assert "pepprclip" in model_ids
    assert "rfpeptides" in model_ids
    assert "pepflow" in model_ids
    assert "pepglad" in model_ids
    assert "diffpepbuilder" in model_ids
    assert "ppflow" in model_ids
    assert "pephar" in model_ids
    assert data["scientific_boundary"]


def test_list_models_pepmlm_parked_and_8_model_track_statuses() -> None:
    response = client.get("/api/v1/models")
    data = response.json()["data"]
    statuses = {m["model_id"]: m["status"] for m in data["models"]}
    assert statuses["pepmlm"] == "smoke_rerun_verified"
    assert statuses["evobind2"] == "controlled_smoke_verified"
    assert statuses["pepprclip"] == "pending_probe"
    assert statuses["pepglad"] == "pending_probe"
    assert statuses["diffpepbuilder"] == "controlled_smoke_verified"
    assert statuses["pepflow"] == "controlled_smoke_verified"
    assert statuses["pephar"] == "controlled_smoke_verified"
    assert statuses["rfpeptides"] == "pending_probe"
    # Every model carries a status_reason in P0
    for m in data["models"]:
        assert m.get("status_reason") is not None
        assert len(m["status_reason"]) > 0


def test_model_registry_status_endpoint() -> None:
    response = client.get("/api/v1/model-registry/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count_total"] == 9
    # P30D: PepMLM moved from parked to smoke_rerun_verified
    assert data["count_parked"] == 0
    # P3B/P32B: EvoBind2/DiffPepBuilder/PepFlow/PepHAR are controlled_smoke_verified, not pending_probe
    assert data["count_pending_probe"] == 3
    assert data["count_pending_registry"] == 0
    assert "pepmlm" not in data["parked_models"]
    assert set(data["pending_probe_models"]) == {"pepprclip", "pepglad", "rfpeptides"}
    assert data["pending_registry_models"] == []


# ---------------------------------------------------------------------------
# Model detail
# ---------------------------------------------------------------------------


def test_get_evobind2_metadata() -> None:
    response = client.get("/api/v1/models/evobind2")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["model_id"] == "evobind2"
    assert model["display_name"] == "EvoBind2"
    assert model["supports_probe"] is True
    assert model["supports_dry_run"] is True
    assert model["supports_structure_output"] is True
    assert model["real_run_enabled"] is False
    assert "pdb" in model["output_artifact_types"]


def test_get_evobind2_metadata_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/evobind2")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    # P33: EvoBind2 promoted from pending_probe to controlled_smoke_verified based on P3B/P3C evidence
    assert model["status"] == "controlled_smoke_verified"
    assert model["status_reason"] == "p3b_real_smoke_verified_gate_closed"
    assert model["stage"] == "P3B_CONTROLLED_SMOKE_OK"
    assert model["adapter_id"] == "evobind2"
    assert model["supports_probe"] is True
    assert model["supports_dry_run"] is True
    assert model["supports_real_run"] is False
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert model["readiness_level"] == "controlled_smoke_verified"
    assert model["blocker_code"] == "REAL_RUN_GATE_CLOSED"
    assert "EVOBIND2_P3B_REAL_SMOKE_RUN_CONTROLLED_EXECUTION_REPORT.md" in model["evidence_ref"]


def test_get_pepmlm_metadata_smoke_rerun_verified() -> None:
    response = client.get("/api/v1/models/pepmlm")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    # P30D: PepMLM is now smoke_rerun_verified
    assert model["status"] == "smoke_rerun_verified"
    assert model["status_reason"] == "p30b_smoke_rerun_verified_gate_closed"
    assert model["supports_probe"] is True
    assert model["supports_dry_run"] is True
    assert model["supports_real_run"] is True
    assert model["real_run_enabled"] is False


def test_get_pepglad_metadata_pending_probe_ready_for_real_run_gate() -> None:
    response = client.get("/api/v1/models/pepglad")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "pending_probe"
    assert model["status_reason"] == "p33i_out_of_scope_execution_evidence_preserved"
    assert model["stage"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_gate"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_level"] == "pending_probe"
    assert model["execution_locked"] is True
    assert model["real_run_enabled"] is False
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert model["supports_probe"] is True
    assert model["supports_dry_run"] is True


def test_get_diffpepbuilder_metadata_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/diffpepbuilder")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "controlled_smoke_verified"
    assert model["status_reason"] == "p32b_controlled_smoke_verified"
    assert model["adapter_id"] == "diffpepbuilder"
    assert model["supports_probe"] is True
    assert model["supports_dry_run"] is True
    assert model["supports_real_run"] is False
    assert model["real_run_enabled"] is False
    assert model["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert model["execution_locked"] is True


def test_get_pepflow_metadata_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/pepflow")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "controlled_smoke_verified"
    assert model["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_get_pephar_metadata_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/pephar")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "controlled_smoke_verified"
    assert model["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_p32b_models_evidence_ref_and_last_verified_at() -> None:
    response = client.get("/api/v1/models")
    data = response.json()["data"]
    models = {m["model_id"]: m for m in data["models"]}
    for mid in ("diffpepbuilder", "pephar"):
        model = models[mid]
        assert model["readiness_gate"] == "P32B_THREE_MODEL_CONTROLLED_EXECUTION_DELIVERED"
        assert model["readiness_level"] == "controlled_smoke_verified"
        assert model["blocker_code"] == "REAL_RUN_GATE_CLOSED"
        assert model["next_authorization"] == "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION"
        assert model["evidence_ref"] == "STAMP_P32B_DELIVERY_MANIFEST.json"
        assert model["last_verified_at"] == "2026-06-27T19:14:29+00:00"
        assert model["execution_locked"] is True
        assert model["real_run_enabled"] is False


def test_p33p_ppflow_evidence_ref_and_last_verified_at() -> None:
    response = client.get("/api/v1/models")
    data = response.json()["data"]
    models = {m["model_id"]: m for m in data["models"]}
    model = models["ppflow"]
    # P33P: stage/evidence_ref updated to P33O path-repair success; lock invariants preserved.
    assert model["stage"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert model["readiness_gate"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert model["readiness_level"] == "controlled_smoke_verified"
    assert model["blocker_code"] == "REAL_RUN_GATE_CLOSED"
    assert model["next_authorization"] == "NEW_EXPLICIT_AUTH_REQUIRED_FOR_ANY_FUTURE_EXECUTION"
    assert "STAMP_P33O_PPFLOW_PATH_REPAIR_SUCCESS_REPORT.md" in model["evidence_ref"]
    assert model["execution_locked"] is True
    assert model["real_run_enabled"] is False
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_p33p_ppflow_evidence_endpoint_returns_structured_metadata() -> None:
    response = client.get("/api/v1/models/ppflow/evidence")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "ppflow"
    assert data["stage"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert data["execution_locked"] is True
    assert data["real_run_enabled"] is False
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    # P33Q unified contract: availability + stats + artifacts (no raw evidence sub-object).
    assert data["availability"] == "available"
    assert data["supports_real_run"] is False
    stats = data["stats"]
    assert stats["exit_code"] == 0
    assert stats["sample_dirs"] == 133
    assert stats["file_count"] == 404
    assert stats["artifact_bytes"] == 4408281
    artifacts = {a["id"]: a for a in data["artifacts"]}
    assert artifacts["success_report"]["sha256"] == (
        "8f6519e85ce6f7936794ed5d580fe2c7ef52dadff6c6643770d19c0eb873f293"
    )
    assert artifacts["result_manifest"]["sha256"] == (
        "6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00"
    )
    assert set(data["downloadable_ids"]) == {
        "success_report",
        "execution_manifest",
        "result_manifest",
        "status",
    }


def test_get_unknown_model_returns_404() -> None:
    response = client.get("/api/v1/models/does_not_exist")
    assert response.status_code == 404


def test_get_model_rejects_traversal() -> None:
    response = client.get("/api/v1/models/../etc/passwd")
    assert response.status_code in (400, 404, 405)


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


def test_probe_evobind2_returns_available() -> None:
    response = client.get("/api/v1/models/evobind2/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "evobind2"
    assert data["status"] in ("AVAILABLE", "DEGRADED", "UNAVAILABLE")
    assert data["adapter_id"] == "evobind2"
    assert data["safety_flags"]["executed_model"] is False
    assert data["safety_flags"]["computational_prediction_only"] is True


def test_probe_placeholder_and_pepmlm() -> None:
    # PepMLM P5A: probe performs read-only env/weight checks
    response = client.get("/api/v1/models/pepmlm/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    assert data["status"] == "smoke_rerun_verified"
    assert data["adapter_id"] == "pepmlm"
    assert data["safety_flags"]["executed_model"] is False

    # RFpeptides P33: adapter staged, real execution still blocked
    response = client.get("/api/v1/models/rfpeptides/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "rfpeptides"
    assert data["status"] in ("not_connected", "planned", "disabled", "pending_registry", "pending_probe", "available_for_probe", "blocked")
    assert data["safety_flags"]["executed_model"] is False

    # PepPrCLIP P6A: probe is enabled but weights are missing, so status is
    # PROBED/INSTALLED/DEGRADED rather than a placeholder disabled state.
    response = client.get("/api/v1/models/pepprclip/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepprclip"
    assert data["status"] in ("PROBED", "INSTALLED", "DEGRADED", "UNAVAILABLE")
    assert data["safety_flags"]["executed_model"] is False
    assert data["detail"].get("weights_available") is False


def test_probe_diffpepbuilder_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/diffpepbuilder/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "diffpepbuilder"
    assert data["status"] == "controlled_smoke_verified"
    assert data["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert data["safety_flags"]["executed_model"] is False


def test_probe_pepflow_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/pepflow/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepflow"
    assert data["status"] == "controlled_smoke_verified"
    assert data["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert data["safety_flags"]["executed_model"] is False


def test_probe_pephar_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/pephar/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pephar"
    assert data["status"] == "controlled_smoke_verified"
    assert data["stage"] == "P32B_CONTROLLED_SMOKE_OK"
    assert data["safety_flags"]["executed_model"] is False


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------


def test_dry_run_evobind2_plans_without_execution() -> None:
    payload = {
        "target_sequence": ">target\nMKTAYIAKQRQIK",
        "peptide_length": 10,
        "model_name": "model_1_ptm",
        "max_recycles": 1,
        "num_iterations": 1,
        "dry_run": True,
    }
    response = client.post("/api/v1/models/evobind2/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "evobind2"
    assert data["status"] in ("READY", "BLOCKED")
    assert data["safety_flags"]["executed_model"] is False
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    if data["status"] == "READY":
        assert data["command_preview"]


def test_dry_run_pepmlm_ready_placeholders_disabled() -> None:
    payload = {
        "target_sequence": ">target\nMKTAYIAKQRQIK",
        "peptide_length": 10,
    }
    # PepMLM P5A: dry-run plans without execution
    response = client.post("/api/v1/models/pepmlm/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    assert data["status"] in ("READY", "BLOCKED")
    assert data["safety_flags"]["executed_model"] is False
    if data["status"] == "READY":
        assert data["command_preview"]
        assert "NOT_EXPERIMENTALLY_VALIDATED" in data["validation_status"]

    for mid in ("rfpeptides",):
        response = client.post(f"/api/v1/models/{mid}/dry-run", json=payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "BLOCKED"
        assert data["blocked_reasons"]
        assert data["safety_flags"]["executed_model"] is False

    # PepPrCLIP P6A: dry-run plans without execution and returns a command preview.
    response = client.post("/api/v1/models/pepprclip/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepprclip"
    assert data["status"] in ("READY", "BLOCKED")
    assert data["safety_flags"]["executed_model"] is False
    if data["status"] == "READY":
        assert data["command_preview"]
        assert "NOT_EXPERIMENTALLY_VALIDATED" in data["validation_status"]



# ---------------------------------------------------------------------------
# Pending registry skeleton blocked responses (STAMP_6 P1)
# ---------------------------------------------------------------------------

PENDING_REGISTRY_MODELS = []


def test_pending_registry_models_listed_with_probe_support() -> None:
    response = client.get("/api/v1/model-registry/status")
    assert response.status_code == 200
    data = response.json()["data"]
    status_map = {m["model_id"]: m for m in data["models"]}
    for mid in PENDING_REGISTRY_MODELS:
        assert status_map[mid]["status"] == "pending_registry"
        assert status_map[mid]["supports_probe"] is True
        assert status_map[mid]["supports_dry_run"] is True


@pytest.mark.parametrize("mid", PENDING_REGISTRY_MODELS)
def test_probe_pending_registry_returns_blocked(mid: str) -> None:
    response = client.get(f"/api/v1/models/{mid}/probe")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == mid
    assert data["status"] == "pending_registry"
    assert data["probe_status"] == "blocked"
    assert data["available"] is False
    assert data["actionable"] is False
    assert data["runs_model"] is False
    assert data["generates_candidates"] is False
    assert data["experimental_validation"] is False
    assert data["stage"] == "P1_SKELETON"
    assert data["safety_flags"]["executed_model"] is False
    assert data["safety_flags"]["computational_prediction_only"] is True


@pytest.mark.parametrize("mid", PENDING_REGISTRY_MODELS)
def test_dry_run_pending_registry_returns_blocked(mid: str) -> None:
    payload = {
        "target_sequence": ">target\nMKTAYIAKQRQIK",
        "peptide_length": 10,
    }
    response = client.post(f"/api/v1/models/{mid}/dry-run", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == mid
    assert data["status"] == "BLOCKED"
    assert data["dry_run_status"] == "blocked"
    assert data["available"] is False
    assert data["actionable"] is False
    assert data["runs_model"] is False
    assert data["generates_candidates"] is False
    assert data["experimental_validation"] is False
    assert data["stage"] == "P1_SKELETON"
    assert data["blocked_reasons"]
    assert data["command_preview"] is None
    assert data["safety_flags"]["executed_model"] is False
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


@pytest.mark.parametrize("mid", PENDING_REGISTRY_MODELS)
def test_submit_pending_registry_returns_blocked(mid: str) -> None:
    payload = {
        "target_sequence": ">target\nMKTAYIAKQRQIK",
        "peptide_length": 10,
    }
    response = client.post(f"/api/v1/models/{mid}/submit", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == mid
    assert data["status"] == "BLOCKED"
    assert data["blocked_reasons"]
    assert data["run_id"] is None
    assert data["safety_flags"]["executed_model"] is False
    assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------


def test_list_artifacts_evobind2_p3b(compute_enabled_client: TestClient) -> None:
    response = compute_enabled_client.get(f"/api/v1/models/evobind2/jobs/{P3B_JOB_ID}/artifacts")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "evobind2"
    assert data["job_id"] == P3B_JOB_ID
    names = {a["name"] for a in data["artifacts"]}
    assert "pdb" in names or "metrics_csv" in names or data["artifacts"] == []
    for artifact in data["artifacts"]:
        assert "/home/" not in artifact["path"]
        if artifact["exists"]:
            assert artifact["size_bytes"] >= 0


def test_list_artifacts_pepmlm_unknown_job_empty() -> None:
    response = client.get("/api/v1/models/pepmlm/jobs/123/artifacts")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["model_id"] == "pepmlm"
    assert data["status"] in ("unknown", "disabled")
    # Adapter lists expected artifact slots with exists=False for unknown jobs
    assert all(a["exists"] is False for a in data["artifacts"])
    for artifact in data["artifacts"]:
        assert "/home/" not in artifact["path"]


# ---------------------------------------------------------------------------
# Real-run remains blocked
# ---------------------------------------------------------------------------


def test_evobind2_submit_blocked_via_adapter() -> None:
    from app.services.model_adapters import EvoBind2Adapter
    from app.schemas.model_registry import ModelDryRunPayload

    adapter = EvoBind2Adapter("evobind2")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        peptide_length=10,
        model_name="model_1_ptm",
    )
    result = adapter.submit(payload)
    assert result.status == "BLOCKED"
    assert result.safety_flags.executed_model is False


def test_placeholder_submit_blocked() -> None:
    from app.services.model_adapters import PlaceholderAdapter
    from app.schemas.model_registry import ModelDryRunPayload

    adapter = PlaceholderAdapter("pepmlm")
    payload = ModelDryRunPayload(
        target_sequence=">target\nMKTAYIAKQRQIK",
        peptide_length=10,
    )
    result = adapter.submit(payload)
    assert result.status == "BLOCKED"


# ---------------------------------------------------------------------------
# Traversal / safety
# ---------------------------------------------------------------------------


def test_model_id_traversal_rejected_in_probe() -> None:
    response = client.get("/api/v1/models/..%2Fetc%2Fpasswd/probe")
    assert response.status_code in (400, 404, 405)


def test_model_id_traversal_rejected_in_dry_run() -> None:
    response = client.post(
        "/api/v1/models/..%2Fetc%2Fpasswd/dry-run",
        json={"target_sequence": "MKT"},
    )
    assert response.status_code in (400, 404, 405)


def test_all_models_carry_validation_policy() -> None:
    response = client.get("/api/v1/models")
    data = response.json()["data"]
    for model in data["models"]:
        assert "NOT_EXPERIMENTALLY_VALIDATED" in model["validation_policy"]
        assert model["real_run_enabled"] is False
