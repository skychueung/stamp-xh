# STAMP P33J-D1 RFpeptides Detail API Patch — Rollback Plan

**Rollback trigger:** any verification failure, unintended model-execution side effect, or user/reviewer stop order.  
**Rollback authority:** Kimi Code CLI under active goal P33J-D1.  
**Estimated rollback time:** < 30 seconds.  

## 1. Backup Artifacts

| Artifact | Local Path | SHA256 |
|----------|------------|--------|
| Original `rfpeptides_adapter.py` | `C:/Users/33319/.kimi-code/sessions/rfpeptides_adapter_before.py` | `2ed88dec51fff0c05f042f340797a3666397114cc22a54d744dbc38555f677f0` |
| Proposed patched file | `C:/Users/33319/.kimi-code/sessions/rfpeptides_src_rfpeptides_adapter.py` | `61b570f984dc336fce1bd721006969f4073e21afe588f59aa4b123df9131e4d3` |
| Patch diff | `C:/Users/33319/.kimi-code/sessions/STAMP_P33J_D1_RFPEPTIDES_DETAIL_API_PROPOSED_PATCH.diff` | `920884abf2ede3df114f1922f660369134541cb392bccdecdb7fedea9a96dcb5` |

## 2. Rollback Commands

From project root on the dev server (`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`):

```bash
# 1. Restore the original file from the local backup
scp -i ~/.ssh/stamp_xh_218 -o StrictHostKeyChecking=no \
  "C:/Users/33319/.kimi-code/sessions/rfpeptides_adapter_before.py" \
  xh@192.168.31.218:/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend/app/services/model_adapters/rfpeptides_adapter.py

# 2. Verify SHA256 matches the before manifest
ssh -i ~/.ssh/stamp_xh_218 xh@192.168.31.218 \
  "sha256sum /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend/app/services/model_adapters/rfpeptides_adapter.py"

# Expected output:
# 2ed88dec51fff0c05f042f340797a3666397114cc22a54d744dbc38555f677f0  .../rfpeptides_adapter.py

# 3. Restart only the FastAPI dev backend (no model process restart needed)
cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend
bash scripts/restart_dev_backend.sh

# 4. Confirm the endpoint returns 500 again (pre-patch state)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:12823/api/v1/models/rfpeptides
# Expected: 500
```

## 3. Rollback Success Criteria

- SHA256 of server file matches `2ed88dec51fff0c05f042f340797a3666397114cc22a54d744dbc38555f677f0`.
- `GET /api/v1/models/rfpeptides` returns HTTP 500 (restores pre-patch symptom).
- No model processes spawned, no GPU lock held, no gate created.
- Tests return to pre-patch baseline (`36 passed, 3 skipped`, with the RFpeptides detail test failing/skipped as before).

## 4. Rollback Failure Escalation

If file restore cannot complete or SHA mismatch persists:

1. Stop all backend restart attempts.
2. Preserve both local and server copies.
3. Escalate to user/manual review before any further mutation.
