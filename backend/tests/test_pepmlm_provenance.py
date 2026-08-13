from __future__ import annotations

import json

from app.services.model_adapters import pepmlm_adapter


def test_pepmlm_manifest_contains_reproducibility_provenance(tmp_path, monkeypatch):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.safetensors").write_bytes(b"checkpoint-fixture")
    monkeypatch.setattr(pepmlm_adapter, "PEPMLM_MODEL_PATH", model_dir)

    paths = {
        "output_dir": tmp_path / "output",
        "manifest_dir": tmp_path / "manifest",
    }
    paths["output_dir"].mkdir()
    pepmlm_adapter._relocate_manifests(
        paths,
        "run-1",
        "MKTAYIAKQRQISFVKSHFSRQ",
        12,
        3,
        "cuda",
        42,
    )

    manifest = json.loads((paths["manifest_dir"] / "manifest_post.json").read_text())
    assert manifest["model_id"] == "pepmlm"
    assert manifest["model_version"] == "PepMLM-650M"
    assert len(manifest["checkpoint_sha256"]) == 64
    assert len(manifest["input_hash"]) == 64
    assert manifest["seed"] == 42
    assert manifest["run_completed"] is True
