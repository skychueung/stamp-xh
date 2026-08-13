# P33U-D19A UI Fix Visual Acceptance Report

Final Gate: `P33U_D19A_FIVE_MODEL_UI_VISUALLY_ACCEPTED`

## Root cause and fix

The earlier D19A change updated `/target-design`, while the visible navigation entry and reported screenshot used `/targeted-peptide-design`. The latter continued rendering the legacy nine-model registry and raw probe summary.

`src/pages/TargetedPeptideDesignPage.tsx` was corrected on the dev copy so the real visible route now renders the five-model product structure.

## Visual acceptance

- Top KPI: Available Models 5 / Blocked Models 1 / Backlog Models 3.
- Runnable list: PepMLM, DiffPepBuilder, PepHAR, PepFlow, EvoBind2 only.
- PPFlow appears only in the blocked card with `License Blocked`, the required reason, and disabled Run.
- PepPrCLIP, RFpeptides, and PepGLAD appear only inside the collapsed Roadmap / Backlog and advanced audit views.
- Model selector contains exactly five options and defaults to `PepMLM` (`value=pepmlm`).
- Model Probe shows Available 5 / Blocked 1 / Backlog 3; `Total registered: 9` is secondary audit text.
- Backend Env shows the three product messages and does not expose `DEPENDENCY_MISSING` as a visible status.
- Both details sections are closed by default.

Screenshots:

- `06_任务单/KimiCode/p33u_d19a_model_ui_cleanup/P33U_D19A_UI_FIX_KPI.png` — `b2c0e9f0b1610a534524882aebd3ab6bd3a00cf296c46ba5646dbe2907c5e07a`
- `06_任务单/KimiCode/p33u_d19a_model_ui_cleanup/P33U_D19A_UI_FIX_MODELS.png` — `de6ad43ba5c3c8ee0db5489f1c30906bd08ac6871b1078d7c2dfcae3bf8ebbae`
- `06_任务单/KimiCode/p33u_d19a_model_ui_cleanup/P33U_D19A_UI_FIX_PROBE.png` — `53958c2bdc4b6b65e7980082a65482a2cc3438444b0e753d9468ce20375685eb`

## Build and runtime

- `npm run build`: PASS; 3590 modules transformed.
- Source SHA256: `97468a4688da8cc80052038fb580eedac6fc06e5522ecf01707d0db740fa8456`.
- Frontend 12823 restarted with the project script; new PID `3860979`; HTTP 200.
- Backend 12824 was not restarted; HTTP 200.
- Formal 8080/8001 remained HTTP 200 and were not restarted; production backend PID remained `3074240`.

## Safety boundary

No model run, PPFlow execution, checkpoint load, GPU call, dependency install, or formal-environment write occurred.

