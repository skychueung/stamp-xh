from app.services.production_model_registry import MODEL_IDS, ProductionModelRegistry


def test_registry_contains_exactly_five_models(monkeypatch, tmp_path):
    monkeypatch.setenv("STAMP_MODEL_HOME", str(tmp_path))
    registry = ProductionModelRegistry()
    statuses = registry.probe_all()
    assert tuple(item["model_id"] for item in statuses) == MODEL_IDS
    assert len(statuses) == 5
    assert all(item["state"] in {"registered", "dependency_missing", "checkpoint_missing", "ready", "busy"} for item in statuses)


def test_adapter_contract_and_truthful_probe(monkeypatch, tmp_path):
    monkeypatch.setenv("STAMP_MODEL_HOME", str(tmp_path))
    adapter = ProductionModelRegistry().get("pepmlm")
    assert adapter.probe()["missing"]
    assert adapter.validate_input({"target_sequence": "ACDEFGHIKLMNPQ"}) == []
    assert adapter.validate_input({"target_sequence": "BAD*"})
    assert adapter.estimate_resources({"target_sequence": "A" * 100})["gpu_count"] == 1
    assert adapter.run({"target_sequence": "A" * 20})["status"] == "blocked"
    assert adapter.normalize_result({"candidates": []})["model_id"] == "pepmlm"
