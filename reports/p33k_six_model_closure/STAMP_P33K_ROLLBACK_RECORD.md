# STAMP P33K Rollback Record

**Task ID:** P33K  
**Date:** 2026-06-29  
**Backup Directory:** `/home/xh/kxc/stampup/backups/p33k_six_model_closure_20260629_020847`

---

## 1. Pre-Change Baseline

A full project snapshot was taken before applying the P33K registry/API/UI patch:

```bash
rsync -a --delete \
  /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/ \
  /home/xh/kxc/stampup/backups/p33k_six_model_closure_20260629_020847/
```

## 2. Files Modified by P33K

| File | Final SHA256 |
|---|---|
| `backend/app/services/target_peptide_model_registry.py` | `d60531a50296ead75e3e8c2b1d0a3733b17532adc1267d8598110c7d509b37c0` |
| `backend/app/schemas/model_registry.py` | `ba0df95ce53b01aef76291b6be9dc9b7d8aa8249023b25658accd83909182026` |
| `backend/app/routers/model_registry.py` | `6427260d98fb9ad45c2bfd6c05eb73a57d1455940150e927060ef22e08998429` |
| `backend/tests/test_model_registry.py` | `fe374d2f260280eb358c8c14027623f298ae6a49df73e2f9e0367b8f3ecc31ee` |
| `backend/tests/test_p33j_registry_api_ui_governance.py` | `12502904e0fe2eb84ce10bcafd002f7f59c99fac77c9997ce961eccab57c86ba` |
| `src/types/modelRegistry.ts` | `924c4842264cd8b53f2563df51bdad57f90d95d86159279acc77e16167be7818` |
| `src/pages/TargetedPeptideDesignCenterPage.tsx` | `cdae86414feb94dfe0e1009c38dc636522301e38336975935b719e787748175a` |
| `src/components/model-readiness/ModelReadinessOverview.tsx` | `47242623ca282bd070942c1c56eb2d7c067261bb6a67bdfdc9c1f369cc9ac89b` |

## 3. Rollback Procedure

To restore the pre-P33K state:

```bash
# 1. Stop the dev backend
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh

# 2. Restore files from backup
rsync -a --delete \
  /home/xh/kxc/stampup/backups/p33k_six_model_closure_20260629_020847/ \
  /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/

# 3. Rebuild frontend to regenerate dist/
bash -c 'cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev && npm run build'

# 4. Restart dev backend
bash /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/restart_dev_backend_12824.sh

# 5. Verify baseline endpoints
curl -s http://192.168.31.218:12824/api/health
curl -s http://192.168.31.218:12823/ | head
curl -s http://192.168.31.218:8001/api/health
curl -s http://192.168.31.218:8080/ | head
```

## 4. Notes

- Rollback does **not** affect formal services on ports 8001/8080, which were read-only throughout P33K.
- Rollback restores the pre-P33K UI (flat model selector without grouped governance cards).
- No model artifacts, gates, or checkpoint state are touched during rollback.
