# STAMP P33K Six-Model Product/UI Closure Delivery Manifest

**Task ID:** P33K  
**Title:** STAMP_P33K_SIX_MODEL_PRODUCT_CLOSURE_AND_TWO_PLACEHOLDER_UI  
**Date:** 2026-06-29  
**Server:** xh-System-Product-Name (192.168.31.218)  
**User:** xh  
**Project Root:** `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`

---

## 1. Closure Scope

Deliver product/UI closure for the Targeted Peptide Design Center with:

- **Six available models** selectable from the UI for Probe / Dry-Run:
  1. PepMLM
  2. EvoBind2
  3. DiffPepBuilder
  4. PepFlow
  5. PepHAR
  6. PPFlow
- **Two reserved placeholders** (locked, future activation only):
  - PepGLAD
  - RFpeptides
- **One excluded model** (blocked pending licensed checkpoint):
  - PepPrCLIP

No model execution, checkpoint loading, gate creation, or real-run unlocking was performed.

---

## 2. Final Model Classification (Registry-Driven)

| Model | Product Group | UI Selectable | UI Execution State | Delivery Status |
|---|---|---|---|---|
| PepMLM | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| EvoBind2 | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| DiffPepBuilder | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| PepFlow | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| PepHAR | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| PPFlow | `available_six` | true | `probe_dry_run_available` | `delivered_for_probe_dry_run_ui` |
| PepGLAD | `reserved_placeholder` | false | `locked_placeholder` | `out_of_scope_evidence_preserved` |
| RFpeptides | `reserved_placeholder` | false | `locked_placeholder` | `out_of_scope_evidence_preserved` |
| PepPrCLIP | `excluded` | false | `excluded` | `blocked_pending_miniclip_license_token` |

---

## 3. Modified Files

| File | Purpose | Final SHA256 |
|---|---|---|
| `backend/app/services/target_peptide_model_registry.py` | Derive product group and UI governance fields from classification sets | `d60531a50296ead75e3e8c2b1d0a3733b17532adc1267d8598110c7d509b37c0` |
| `backend/app/schemas/model_registry.py` | Add governance fields to Pydantic schemas | `ba0df95ce53b01aef76291b6be9dc9b7d8aa8249023b25658accd83909182026` |
| `backend/app/routers/model_registry.py` | Expose governance fields in status response | `6427260d98fb9ad45c2bfd6c05eb73a57d1455940150e927060ef22e08998429` |
| `backend/tests/test_model_registry.py` | Existing registry tests baseline | `fe374d2f260280eb358c8c14027623f298ae6a49df73e2f9e0367b8f3ecc31ee` |
| `backend/tests/test_p33j_registry_api_ui_governance.py` | New governance tests | `12502904e0fe2eb84ce10bcafd002f7f59c99fac77c9997ce961eccab57c86ba` |
| `src/types/modelRegistry.ts` | Frontend types for governance fields | `924c4842264cd8b53f2563df51bdad57f90d95d86159279acc77e16167be7818` |
| `src/pages/TargetedPeptideDesignCenterPage.tsx` | One-click grouped model selection + gated run buttons | `cdae86414feb94dfe0e1009c38dc636522301e38336975935b719e787748175a` |
| `src/components/model-readiness/ModelReadinessOverview.tsx` | Grouped readiness cards with placeholder/excluded lock messages | `47242623ca282bd070942c1c56eb2d7c067261bb6a67bdfdc9c1f369cc9ac89b` |

---

## 4. Phase 4 Zero-Model Acceptance Results

### 4.1 Backend Tests

```text
pytest backend/tests/test_model_registry.py backend/tests/test_p33j_registry_api_ui_governance.py -q
41 passed, 3 skipped, 4 warnings in 24.11s
```

Warnings are existing Pydantic class-based `config` deprecations in unrelated routers.

### 4.2 Frontend Build

Initial build failed with TS6133 unused-variable errors:

```text
src/pages/TargetedPeptideDesignCenterPage.tsx(356,9): error TS6133: 'isReserved' is declared but its value is never read.
src/pages/TargetedPeptideDesignCenterPage.tsx(357,9): error TS6133: 'isExcluded' is declared but its value is never read.
```

A minimal TS6133 fix removed the two unused declarations. Re-run succeeded:

```text
vite v7.3.2 building client environment for production...
```

`dist/` was updated.

### 4.3 Service Health

| Endpoint | HTTP Code |
|---|---|
| `http://192.168.31.218:12824/api/health` | 200 |
| `http://192.168.31.218:12824/api/model-registry/status` | 200 |
| `http://192.168.31.218:12823/` | 200 |
| `http://192.168.31.218:8080/` | 200 |
| `http://192.168.31.218:8001/api/health` | 200 |

### 4.4 Gate / Process / GPU Lock

- Gate files: `PASS: no gate files`
- Target model processes: `PASS: no target model processes`
- GPU compute apps are VLLM/other services, not STAMP peptide model processes.

---

## 5. Backup

- **Path:** `/home/xh/kxc/stampup/backups/p33k_six_model_closure_20260629_020847`
- **Scope:** Full project snapshot before patch application.

---

## 6. Rollback Command

```bash
# Stop dev backend first
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh
# Restore from backup
rsync -a --delete /home/xh/kxc/stampup/backups/p33k_six_model_closure_20260629_020847/ /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/
# Rebuild frontend
bash -c 'cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev && npm run build'
# Restart dev backend
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh
```

---

## 7. Delivery Conclusion

P33K product/UI closure is complete. Six models are exposed in the UI as selectable for Probe/Dry-Run. PepGLAD and RFpeptides remain locked placeholders. PepPrCLIP remains excluded. Real-run remains gated by backend `real_run_enabled=false` / `execution_locked=true`. No model was executed, no checkpoint loaded, and no gate was created.

---

## 8. Next Steps

- Future activation of PepGLAD/RFpeptides requires a new P33K+ task, fresh explicit authorization, and a Reasonix GO.
- PepPrCLIP remains blocked until a licensed MiniCLIP checkpoint + HF token are available.
