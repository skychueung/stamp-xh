"""P33J governance correction zero-model verification.

This test does not load any checkpoint, import any model runner, or execute any
model. It only reads the registry metadata exposed by the API.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.services import target_peptide_model_registry as registry_module

client = TestClient(app)

_AVAILABLE_SIX = {"pepmlm", "evobind2", "diffpepbuilder", "pepflow", "pephar", "ppflow"}
_RESERVED_PLACEHOLDERS = {"pepglad", "rfpeptides"}
_EXCLUDED = {"pepprclip"}


def test_ppflow_remains_controlled_smoke_verified() -> None:
    response = client.get("/api/v1/models/ppflow")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "controlled_smoke_verified"
    # P33P: stage/readiness_gate advanced to P33O path-repair success; locks preserved.
    assert model["stage"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert model["readiness_gate"] == "P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS"
    assert model["readiness_level"] == "controlled_smoke_verified"
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
    assert "P33H" not in model["evidence_ref"]


def test_pepglad_downgraded_to_out_of_scope_evidence() -> None:
    response = client.get("/api/v1/models/pepglad")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["status"] == "pending_probe"
    assert model["status_reason"] == "p33i_out_of_scope_execution_evidence_preserved"
    assert model["stage"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_gate"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_level"] == "pending_probe"
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_rfpeptides_downgraded_to_out_of_scope_evidence_via_list() -> None:
    # RFpeptides detail endpoint currently fails because RFpeptidesAdapter lacks
    # model_entry; the governance state is verified via the list/status endpoints
    # which read directly from the registry.
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["model_id"]: m for m in response.json()["data"]["models"]}
    model = models["rfpeptides"]
    assert model["status"] == "pending_probe"
    assert model["status_reason"] == "p33i_out_of_scope_execution_evidence_preserved"
    assert model["stage"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_gate"] == "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED"
    assert model["readiness_level"] == "pending_probe"
    assert model["real_run_enabled"] is False
    assert model["execution_locked"] is True
    assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"


def test_model_registry_status_counts_reflect_correction() -> None:
    response = client.get("/api/v1/model-registry/status")
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["count_total"] == 9
    assert data["count_parked"] == 0
    assert data["count_pending_probe"] == 3
    assert data["count_pending_registry"] == 0
    assert set(data["pending_probe_models"]) == {"pepprclip", "pepglad", "rfpeptides"}
    assert "ppflow" not in data["pending_probe_models"]


def test_no_model_returns_controlled_smoke_for_pepglad_rfpeptides() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["model_id"]: m for m in response.json()["data"]["models"]}
    assert models["pepglad"]["status"] != "controlled_smoke_verified"
    assert models["rfpeptides"]["status"] != "controlled_smoke_verified"
    assert models["ppflow"]["status"] == "controlled_smoke_verified"


def test_no_eight_of_eight_completion_claim() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    payload = response.text
    assert "P33H_EIGHT_MODEL_DELIVERY_MANIFEST" not in payload
    assert "P33H_CONTROLLED_SMOKE_DELIVERED" not in payload
    assert "8/8" not in payload


def test_all_models_locked_and_not_experimentally_validated() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    for model in response.json()["data"]["models"]:
        assert model["real_run_enabled"] is False
        assert model["execution_locked"] is True
        assert model["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED"
        assert "NOT_EXPERIMENTALLY_VALIDATED" in model["validation_policy"]


# ---------------------------------------------------------------------------
# P33K product-group UI governance
# ---------------------------------------------------------------------------


def test_product_group_classification() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["model_id"]: m for m in response.json()["data"]["models"]}
    for mid in _AVAILABLE_SIX:
        assert models[mid]["product_group"] == "available_six", mid
    for mid in _RESERVED_PLACEHOLDERS:
        assert models[mid]["product_group"] == "reserved_placeholder", mid
    for mid in _EXCLUDED:
        assert models[mid]["product_group"] == "excluded", mid


def test_ui_selectable_only_for_available_six() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    for model in response.json()["data"]["models"]:
        mid = model["model_id"]
        if mid in _AVAILABLE_SIX:
            assert model["ui_selectable"] is True, mid
            assert model["ui_execution_state"] == "probe_dry_run_available", mid
            assert model["delivery_status"] == "delivered_for_probe_dry_run_ui", mid
        else:
            assert model["ui_selectable"] is False, mid
            if mid in _RESERVED_PLACEHOLDERS:
                assert model["ui_execution_state"] == "locked_placeholder", mid
                assert model["delivery_status"] == "out_of_scope_evidence_preserved", mid
            elif mid in _EXCLUDED:
                assert model["ui_execution_state"] == "excluded", mid
                assert model["delivery_status"] == "blocked_pending_miniclip_license_token", mid


def test_activation_requirements_match_product_group() -> None:
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["model_id"]: m for m in response.json()["data"]["models"]}
    for mid in _AVAILABLE_SIX:
        assert "NEW_EXPLICIT_AUTH_REQUIRED" in models[mid]["activation_requirements"], mid
    for mid in _RESERVED_PLACEHOLDERS:
        assert "NEW_EXPLICIT_AUTH_REQUIRED" in models[mid]["activation_requirements"], mid
        assert "fresh compliant controlled smoke" in models[mid]["activation_requirements"], mid
    assert "MiniCLIP checkpoint" in models["pepprclip"]["activation_requirements"]


def test_status_endpoint_includes_product_group_fields() -> None:
    response = client.get("/api/v1/model-registry/status")
    assert response.status_code == 200
    data = response.json()["data"]
    entries = {m["model_id"]: m for m in data["models"]}
    for mid in _AVAILABLE_SIX:
        assert entries[mid]["product_group"] == "available_six", mid
        assert entries[mid]["ui_selectable"] is True, mid
    for mid in _RESERVED_PLACEHOLDERS:
        assert entries[mid]["product_group"] == "reserved_placeholder", mid
        assert entries[mid]["ui_selectable"] is False, mid
    assert entries["pepprclip"]["product_group"] == "excluded"
    assert entries["pepprclip"]["ui_selectable"] is False


def test_future_activation_fixture_promotes_placeholder_to_available(monkeypatch) -> None:
    """Temporarily override a placeholder model's metadata to available.

    The product-group fields are derived from module-level classification sets,
    so promoting PepGLAD at runtime changes the API response without code edits.
    """
    original_available = set(registry_module._PRODUCT_GROUP_AVAILABLE_SIX)
    original_reserved = set(registry_module._PRODUCT_GROUP_RESERVED_PLACEHOLDER)

    monkeypatch.setattr(
        registry_module,
        "_PRODUCT_GROUP_AVAILABLE_SIX",
        original_available | {"pepglad"},
    )
    monkeypatch.setattr(
        registry_module,
        "_PRODUCT_GROUP_RESERVED_PLACEHOLDER",
        original_reserved - {"pepglad"},
    )

    # Detail endpoint reflects the override
    response = client.get("/api/v1/models/pepglad")
    assert response.status_code == 200
    model = response.json()["data"]["model"]
    assert model["product_group"] == "available_six"
    assert model["ui_selectable"] is True
    assert model["ui_execution_state"] == "probe_dry_run_available"
    assert model["delivery_status"] == "delivered_for_probe_dry_run_ui"
    assert "NEW_EXPLICIT_AUTH_REQUIRED" in model["activation_requirements"]

    # List endpoint reflects the override
    response = client.get("/api/v1/models")
    assert response.status_code == 200
    models = {m["model_id"]: m for m in response.json()["data"]["models"]}
    assert models["pepglad"]["product_group"] == "available_six"
    assert models["pepglad"]["ui_selectable"] is True

    # Status endpoint reflects the override
    response = client.get("/api/v1/model-registry/status")
    assert response.status_code == 200
    entries = {m["model_id"]: m for m in response.json()["data"]["models"]}
    assert entries["pepglad"]["product_group"] == "available_six"
    assert entries["pepglad"]["ui_selectable"] is True
