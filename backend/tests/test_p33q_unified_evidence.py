"""P33Q unified six-model evidence & safe-download verification.

Zero-model test: no checkpoint load, no model runner import, no model execution.
Exercises the unified /evidence metadata + whitelisted download endpoints for
all six available_six models, the two reserved_placeholder models, and the
excluded model. Verifies per-model whitelist, containment, no traversal, no
unknown id, SHA256 re-check (409), and containment escape (403).
"""

from __future__ import annotations

import hashlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import model_registry as router_module

client = TestClient(app)

# Expected downloadable ids per six-model (truthful, on-disk-verified).
_EXPECTED_IDS = {
    "ppflow": {"success_report", "execution_manifest", "result_manifest", "status"},
    "pepmlm": {"success_report", "status", "reasonix_review", "artifacts_index"},
    "evobind2": {"p3b_report", "p3c_report"},
    "diffpepbuilder": {"delivery_manifest", "result_manifest"},
    "pepflow": {"delivery_manifest", "result_manifest"},
    "pephar": {"delivery_manifest", "result_manifest"},
}
_SIX = list(_EXPECTED_IDS.keys())
_PLACEHOLDERS = ["pepglad", "rfpeptides"]
_EXCLUDED = ["pepprclip"]


def test_all_six_models_return_unified_evidence() -> None:
    for mid in _SIX:
        response = client.get(f"/api/v1/models/{mid}/evidence")
        assert response.status_code == 200, mid
        data = response.json()["data"]
        assert data["model_id"] == mid, mid
        assert data["validation_status"] == "NOT_EXPERIMENTALLY_VALIDATED", mid
        assert data["execution_locked"] is True, mid
        assert data["real_run_enabled"] is False, mid
        assert data["availability"] in ("available", "partial"), mid
        assert set(data["downloadable_ids"]) == _EXPECTED_IDS[mid], mid
        # artifacts must mirror downloadable_ids and never expose a server path
        assert {a["id"] for a in data["artifacts"]} == _EXPECTED_IDS[mid], mid
        for a in data["artifacts"]:
            assert "path" not in a, a
            assert a["sha256"] and len(a["sha256"]) == 64, a


def test_placeholders_and_excluded_have_no_downloadable_evidence() -> None:
    for mid in _PLACEHOLDERS + _EXCLUDED:
        response = client.get(f"/api/v1/models/{mid}/evidence")
        assert response.status_code == 200, mid
        data = response.json()["data"]
        assert data["availability"] == "unavailable", mid
        assert data["downloadable_ids"] == [], mid
        assert data["artifacts"] == [], mid


def test_each_six_model_evidence_downloads_and_sha_matches() -> None:
    for mid in _SIX:
        meta = client.get(f"/api/v1/models/{mid}/evidence").json()["data"]
        for a in meta["artifacts"]:
            response = client.get(f"/api/v1/models/{mid}/evidence/{a['id']}/download")
            assert response.status_code == 200, f"{mid}/{a['id']}"
            actual = hashlib.sha256(response.content).hexdigest()
            assert actual == a["sha256"], f"{mid}/{a['id']} sha mismatch"


def test_unknown_evidence_id_rejected_per_model() -> None:
    for mid in _SIX:
        response = client.get(f"/api/v1/models/{mid}/evidence/unknown_id/download")
        assert response.status_code == 404, mid


def test_traversal_evidence_id_rejected_per_model() -> None:
    for mid in _SIX:
        for bad in ("..", "../etc/passwd", "..\\etc\\passwd", "foo/bar"):
            response = client.get(f"/api/v1/models/{mid}/evidence/{bad}/download")
            assert response.status_code in (400, 404), f"{mid}/{bad}"


def test_placeholder_evidence_download_not_available() -> None:
    for mid in _PLACEHOLDERS + _EXCLUDED:
        response = client.get(f"/api/v1/models/{mid}/evidence/any_id/download")
        assert response.status_code == 404, mid


def test_sha_mismatch_yields_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Corrupt the expected SHA for pepmlm/status; download must refuse (409)."""
    real = router_module._EVIDENCE_WHITELIST["pepmlm"]["status"]["sha256"]
    monkeypatch.setitem(
        router_module._EVIDENCE_WHITELIST["pepmlm"]["status"],
        "sha256",
        "0" * 64,
    )
    try:
        response = client.get("/api/v1/models/pepmlm/evidence/status/download")
        assert response.status_code == 409
    finally:
        monkeypatch.setitem(router_module._EVIDENCE_WHITELIST["pepmlm"]["status"], "sha256", real)


def test_containment_escape_yields_403(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point a pepmlm evidence entry at a real file outside pepmlm's allowed
    roots; download must refuse with 403 (containment), not serve the file."""
    import pathlib

    # A real file that exists but is NOT under /home/xh/kxc/stampup/reports.
    outside = pathlib.Path("/home/xh/kxc/stampup/reports_p33p/STAMP_P33P_FINAL_DELIVERY_MANIFEST.md")
    if not outside.exists():
        pytest.skip("outside-root fixture file not present")
    real_path = router_module._EVIDENCE_WHITELIST["pepmlm"]["status"]["path"]
    real_sha = router_module._EVIDENCE_WHITELIST["pepmlm"]["status"]["sha256"]
    monkeypatch.setitem(router_module._EVIDENCE_WHITELIST["pepmlm"]["status"], "path", str(outside))
    monkeypatch.setitem(
        router_module._EVIDENCE_WHITELIST["pepmlm"]["status"],
        "sha256",
        hashlib.sha256(outside.read_bytes()).hexdigest(),
    )
    try:
        response = client.get("/api/v1/models/pepmlm/evidence/status/download")
        assert response.status_code == 403
    finally:
        monkeypatch.setitem(router_module._EVIDENCE_WHITELIST["pepmlm"]["status"], "path", real_path)
        monkeypatch.setitem(router_module._EVIDENCE_WHITELIST["pepmlm"]["status"], "sha256", real_sha)


def test_no_model_execution_surface_in_evidence_paths() -> None:
    """Static guard: evidence whitelist paths must not reference checkpoints,
    model weights, or anything that would imply execution."""
    forbidden = (".pt", ".pth", ".ckpt", ".safetensors", "checkpoint", "torch.load")
    for mid, entries in router_module._EVIDENCE_WHITELIST.items():
        for eid, entry in entries.items():
            p = entry["path"].lower()
            for bad in forbidden:
                assert bad not in p, f"{mid}/{eid} path references {bad}: {entry['path']}"
