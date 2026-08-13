# STAMP P33K Six-Model UI Activation Report

**Task ID:** P33K  
**Date:** 2026-06-29  
**Scope:** Frontend product/UI closure only — no model execution.

---

## 1. Activation Model

The UI now derives model groupings and permissions from backend Registry fields rather than hard-coded lists. The canonical source of truth is `backend/app/services/target_peptide_model_registry.py`:

- `_PRODUCT_GROUP_AVAILABLE_SIX`
- `_PRODUCT_GROUP_RESERVED_PLACEHOLDER`
- `_PRODUCT_GROUP_EXCLUDED`

These sets drive:

- `product_group`
- `ui_selectable`
- `ui_execution_state`
- `activation_requirements`
- `delivery_status`

---

## 2. UI Changes

### 2.1 Model Selection Panel (`TargetedPeptideDesignCenterPage.tsx`)

Replaced the single flat `<select>` with grouped one-click model cards:

- **可用模型 (6)** — PepMLM, EvoBind2, DiffPepBuilder, PepFlow, PepHAR, PPFlow
- **预留占位 (2)** — PepGLAD, RFpeptides
- **已排除 (1)** — PepPrCLIP

Clicking a card:

1. Sets `selectedModelId`
2. Resets the form via `getDefaultFormForModel`
3. Persists `?model=...` in the URL
4. Refreshes the Run/Deliver panel based on the selected model's governance fields

### 2.2 Real-Run Gating

Real-run button remains disabled unless:

```ts
selectedModel.real_run_enabled === true && selectedModel.execution_locked === false
```

For all nine models, the backend continues to return `real_run_enabled=false` and `execution_locked=true`, so the real-run UI path remains locked.

### 2.3 Placeholder / Excluded Lock Messages

`ModelReadinessOverview.tsx` now groups readiness cards by `product_group`:

- Reserved placeholders show: `需新授权与 Reasonix GO`
- Excluded models show: `缺少授权 checkpoint`

---

## 3. URL Persistence

The selected model is reflected in the query string (`?model=pepmlm`), allowing refresh/reload without losing selection.

---

## 4. Future Activation Fixture

A backend test (`test_future_activation_fixture_promotes_placeholder_to_available`) verifies that monkeypatching a placeholder model into `available_six` correctly updates its governance fields. This ensures PepGLAD/RFpeptides can be promoted without UI code changes once a new compliant controlled smoke is completed and authorized.

---

## 5. Build Verification

`npm run build` succeeded after the TS6133 minimal fix. The production `dist/` contains the updated UI.

---

## 6. Conclusion

The UI now supports one-click switching across all nine registry models, with clear visual grouping and backend-gated execution locks. Six models are selectable for Probe/Dry-Run; two placeholders and one excluded model are correctly locked with explanatory messaging.
