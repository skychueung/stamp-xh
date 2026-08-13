# STAMP P33J-D1 RFpeptides Detail API 500 — Root Cause & Patch Report

**Task ID:** P33J-D1  
**Scope:** Pure metadata API fix — no model execution, no checkpoint loading, no gate creation, no env/source/runner modification.  
**Date:** 2026-06-28  
**Author:** Kimi Code CLI (Reasonix-audited closure)  

---

## 1. Symptom

`GET /api/v1/models/rfpeptides` returned HTTP 500 with the following traceback (captured on dev stack at port 12823):

```python
AttributeError: 'RFpeptidesAdapter' object has no attribute 'model_entry'
  File ".../backend/app/routers/model_registry.py", line 228, in get_model_endpoint
    model=adapter.model_entry,
```

The sibling endpoints (`/api/v1/models/ppflow`, `/api/v1/models/pepglad`) returned HTTP 200 and correct metadata.

---

## 2. Root Cause

All staging model adapters in `backend/app/services/model_adapters/` inherit from `BaseModelAdapter` except `RFpeptidesAdapter`.

`BaseModelAdapter.__init__` exposes:

```python
self.model_entry = model
self.display_name = ...
self.adapter_id   = ...
```

`RFpeptidesAdapter.__init__` only sets:

```python
self.model_id = model_id
```

When `model_registry.py:228` reads `adapter.model_entry` for the detail response, the attribute is missing and FastAPI raises `AttributeError` → HTTP 500.

The detail endpoint only reads metadata (`adapter.model_entry` and safety flags). It does **not** call `probe()`, `dry_run()`, or `submit()`, so the fix is strictly a metadata-interface alignment and does not alter any model execution path.

---

## 3. Affected File

- `backend/app/services/model_adapters/rfpeptides_adapter.py`

No other files need modification.

---

## 4. Minimal Patch

```diff
--- a/backend/app/services/model_adapters/rfpeptides_adapter.py
+++ b/backend/app/services/model_adapters/rfpeptides_adapter.py
@@ -20,6 +20,8 @@
 from datetime import datetime, timezone
 from pathlib import Path
 from typing import Any
+
+from app.services.target_peptide_model_registry import get_model
 
 MODEL_ROOT = Path("/mnt/sdb/kxc/stamp_models")
 SOURCE_DIR = MODEL_ROOT / "source" / "rfpeptides" / "rfd_macro"
@@ -125,6 +127,9 @@
 
     def __init__(self, model_id: str = "rfpeptides") -> None:
         self.model_id = model_id
+        # Expose the registry model_entry so the unified model detail endpoint
+        # can return metadata without touching any model execution path.
+        self.model_entry = get_model(model_id)
```

### Why this is minimal and safe

- Adds one import and one attribute assignment.
- `get_model()` is the same registry lookup already used by `BaseModelAdapter`; it returns a plain `dict` from `TARGET_PEPTIDE_MODEL_REGISTRY`.
- No changes to `model_registry.py`, `target_peptide_model_registry.py`, env variables, source directories, checkpoints, runners, or scientific parameters.
- `RFpeptidesAdapter.probe()` / `dry_run()` / `submit()` still raise the intended `NotImplementedError` / `RuntimeError`, preserving P33I out-of-scope execution evidence for the RFpeptides model.

---

## 5. Expected Outcome After Patch

```bash
curl -s http://127.0.0.1:12823/api/v1/models/rfpeptides | python -m json.tool
```

Should return HTTP 200 with:

```json
{
  "data": {
    "model": {
      "model_id": "rfpeptides",
      "display_name": "RFpeptides (RFDiffusion/Macro) - staging",
      "adapter_id": "rfpeptides_adapter",
      "status": "pending_probe",
      "safety_state": "P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED",
      "real_run_enabled": false
    },
    "safety_flags": { ... }
  }
}
```

---

## 6. Verification Plan

1. Apply patch to dev backend.
2. Run targeted tests:
   - `pytest tests/test_model_registry.py`
   - `pytest tests/test_p33j_registry_api_ui_governance.py`
3. Hit the live endpoint on `12823` and confirm HTTP 200 + expected governance fields.
4. Confirm `npm run build` still succeeds.
5. Confirm four ports (`12823`, `12824`, `8001`, `8080`) respond 200.
6. Confirm `gate` / model process count / GPU lock count are all zero.

---

## 7. Failure Gates

If any of the following occur, **stop** and do not proceed to closure:

- Patch touches model execution, checkpoint loading, or gate logic.
- Tests fall below the baseline of `36 passed, 3 skipped`.
- Endpoint still returns non-200 after patch.
- `real_run_enabled` is observed as `true` for RFpeptides, PepGLAD, or PPFlow.
- Any new model process or GPU lock appears during verification.
