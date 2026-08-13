# P33U-D19-A Model UI Cleanup and Enable Report

Final Gate: `P33U_D19A_FIVE_MODEL_UI_ENABLED`

## Result

- Available 5: PepMLM, DiffPepBuilder, PepHAR, PepFlow, EvoBind2.
- Blocked 1: PPFlow (`blocked_license`; no upstream LICENSE / authorization unclear).
- Backlog 3: PepPrCLIP, RFpeptides, PepGLAD.
- Only five closed models are selectable; default is PepMLM.
- PepFlow is shown as a closed 22aa deviation and excluded from 12aa main ranking.
- Legacy six-model Run panels were removed. Run controls are hidden; future enablement requires dev only, auth, no PPFlow, no 8001/8080, GPU warning, run_id + gate JSON.
- Closed models show View candidates / evidence / scoring / wet-lab plan.
- All result areas retain `COMPUTATIONAL_PREDICTION_ONLY / NOT_EXPERIMENTALLY_VALIDATED`.
- Blocked/backlog direct API adapter resolution is forced through a zero-execution placeholder.

## Acceptance

- `GET /api/v1/models`: `available_models=5`, `blocked_models=1`, `backlog_models=3`, with exact ID lists.
- Frontend `npm run build`: PASS (3590 modules).
- Python router/service/schema compile: PASS.
- Built bundle contains 5/1/3 labels, PPFlow license reason, and safety-gate wording.
- 12823/12824 restarted and healthy; 8080/8001 remain HTTP 200 and were not restarted. Production backend PID remained `3074240`.
- Browser reached `/login`, confirming auth protection; no credentials were submitted.

## Safety / rollback

No model run, PPFlow execution, checkpoint load, GPU call, evidence deletion, D8-D18 bundle deletion, formal-environment write, or 8001/8080 restart occurred.

Rollback backup: `/home/xh/kxc/stampup/backups/p33u_d19a_20260705_020241`

Source SHA256: page `aa36ce8d...`, readiness `1ec425f9...`, TS types `8b0dee6b...`, router `68b0c6cc...`, registry service `10c384a8...`, schema `50c5d4f7...`.
