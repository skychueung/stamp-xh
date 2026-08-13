# STAMP P33K Registry / API / UI Test Report

**Task ID:** P33K  
**Date:** 2026-06-29  
**Scope:** Zero-model acceptance — backend tests + endpoint checks.

---

## 1. Test Environment

- **Server:** xh-System-Product-Name
- **Project:** `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- **Python:** venv `./backend/.venv/bin/python`
- **Node:** project-local `npm` + `vite`

---

## 2. Backend Test Suite

### 2.1 Command

```bash
./backend/.venv/bin/python -m pytest \
  backend/tests/test_model_registry.py \
  backend/tests/test_p33j_registry_api_ui_governance.py \
  -q
```

### 2.2 Result

```text
41 passed, 3 skipped, 4 warnings in 24.11s
```

### 2.3 Covered Governance Cases (new file)

- `test_product_group_classification`
- `test_ui_selectable_only_for_available_six`
- `test_activation_requirements_match_product_group`
- `test_status_endpoint_includes_product_group_fields`
- `test_future_activation_fixture_promotes_placeholder_to_available`

---

## 3. API Endpoint Checks

| Endpoint | Expected | Actual |
|---|---|---|
| `GET /api/health` (dev 12824) | 200 | 200 |
| `GET /api/model-registry/status` (dev 12824) | 200 + governance fields | 200, all 9 models classified |
| `GET /api/model-registry/models` (dev 12824) | 200 | 200 |
| `GET /` (dev frontend 12823) | 200 | 200 |
| `GET /` (formal frontend 8080) | 200 | 200 |
| `GET /api/health` (formal backend 8001) | 200 | 200 |

### 3.1 Registry Status Payload Verification

The `/api/model-registry/status` response contains exactly 9 models:

- `available_six`: 6 models
- `reserved_placeholder`: 2 models
- `excluded`: 1 model

All entries include the five new governance fields:

- `product_group`
- `ui_selectable`
- `ui_execution_state`
- `activation_requirements`
- `delivery_status`

---

## 4. Frontend Build

### 4.1 Initial Attempt

```bash
npm run build
```

Failed with TS6133:

```text
src/pages/TargetedPeptideDesignCenterPage.tsx(356,9): error TS6133: 'isReserved' is declared but its value is never read.
src/pages/TargetedPeptideDesignCenterPage.tsx(357,9): error TS6133: 'isExcluded' is declared but its value is never read.
```

### 4.2 Minimal Fix

Removed the two unused const declarations in `src/pages/TargetedPeptideDesignCenterPage.tsx`.

### 4.3 Second Attempt

```bash
npm run build
```

Succeeded. `dist/` updated.

---

## 5. Gate / Process / GPU Lock Checks

| Check | Result |
|---|---|
| Gate files | `PASS: no gate files` |
| Target model processes | `PASS: no target model processes` |
| GPU compute apps | VLLM/other services only; no STAMP peptide model compute apps |

---

## 6. Conclusion

All backend tests pass, all six endpoints return 200, the frontend build succeeds, and no model execution artifacts or locks are present. P33K Registry/API/UI closure meets the zero-model acceptance criteria.
