"""P32B controlled-smoke evidence loader for adapters.

Read-only loader for the P32B delivery manifest and per-step manifests.
All paths are locked under /home/xh/kxc/stampup and /mnt/sdb/kxc/stamp_models.
SHA256 verification is fail-closed: any mismatch returns an error dict and
blocks downstream probe status upgrades.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

DELIVERY_MANIFEST_PATH = Path("/home/xh/kxc/stampup/reports/STAMP_P32B_DELIVERY_MANIFEST.json")
STEP_MANIFEST_ROOT = Path("/mnt/sdb/kxc/stamp_models/artifacts/p32b_overnight/p32b_overnight_20260628_82705827")

EXPECTED_DELIVERY_SHA256 = "c755ff61980a8dbeccfec66a5f4cf06275542d59839892cab092fc56a00b2c0c"
EXPECTED_STEP_SHA256: dict[str, str] = {
    "diffpepbuilder": "ccc6a3e0b601dbe69b8e2b8d5f808ade6bfd30f1c9fc42adb7d701f328202581",
    "pepflow": "fc76f5537d1cee88e3e446082d267ac690547861d5c207d0e2941341526708f6",
    "pephar_density": "f6b25b80b023aa160241d0fb92d438ce2ffaf2bc5e97527fa5ff37e47ab98695",
    "pephar_prediction": "43a9e08994fdaccc68974dcb4813ed294830ebeeaa53770ca20ab454bfb652dd",
}


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return ""


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def load_p32b_delivery_manifest() -> dict[str, Any]:
    """Return delivery manifest with SHA verification; fail-closed on error."""
    result: dict[str, Any] = {
        "ok": False,
        "path": str(DELIVERY_MANIFEST_PATH),
        "manifest": None,
        "sha256": None,
        "expected_sha256": EXPECTED_DELIVERY_SHA256,
        "error": None,
    }
    sha = _sha256_file(DELIVERY_MANIFEST_PATH)
    result["sha256"] = sha
    if not sha:
        result["error"] = "delivery_manifest_missing_or_unreadable"
        return result
    if sha.lower() != EXPECTED_DELIVERY_SHA256.lower():
        result["error"] = "delivery_manifest_sha256_mismatch"
        return result
    manifest = _load_json(DELIVERY_MANIFEST_PATH)
    if manifest is None:
        result["error"] = "delivery_manifest_json_invalid"
        return result
    result["manifest"] = manifest
    result["ok"] = True
    return result


def load_p32b_step_manifest(step: str) -> dict[str, Any]:
    """Return per-step manifest with SHA verification; fail-closed on error."""
    expected = EXPECTED_STEP_SHA256.get(step)
    path = STEP_MANIFEST_ROOT / step / "manifest.json"
    result: dict[str, Any] = {
        "ok": False,
        "step": step,
        "path": str(path),
        "manifest": None,
        "sha256": None,
        "expected_sha256": expected,
        "error": None,
    }
    if expected is None:
        result["error"] = "unknown_p32b_step"
        return result
    sha = _sha256_file(path)
    result["sha256"] = sha
    if not sha:
        result["error"] = "step_manifest_missing_or_unreadable"
        return result
    if sha.lower() != expected.lower():
        result["error"] = "step_manifest_sha256_mismatch"
        return result
    manifest = _load_json(path)
    if manifest is None:
        result["error"] = "step_manifest_json_invalid"
        return result
    result["manifest"] = manifest
    result["ok"] = True
    return result


def p32b_evidence_ok(step: str) -> dict[str, Any]:
    """Check delivery + step manifest for a single model step.

    Returns a dict with ok=True only when both manifests exist, SHA match,
    and the step reports status SUCCESS and exit_code 0.
    """
    delivery = load_p32b_delivery_manifest()
    step_manifest = load_p32b_step_manifest(step)
    errors: list[str] = []
    if not delivery["ok"]:
        errors.append(delivery["error"] or "delivery_manifest_failed")
    if not step_manifest["ok"]:
        errors.append(step_manifest["error"] or "step_manifest_failed")
    if step_manifest["ok"]:
        manifest = step_manifest["manifest"] or {}
        if manifest.get("status") != "SUCCESS":
            errors.append("step_status_not_success")
        if manifest.get("exit_code") != 0:
            errors.append("step_exit_code_nonzero")
    return {
        "ok": not errors,
        "delivery_manifest": delivery,
        "step_manifest": step_manifest,
        "errors": errors,
    }
