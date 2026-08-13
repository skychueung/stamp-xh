# STAMP P33L — EvoBind2 Failed, Execution Stopped, No Retry

## Final Gate

`P33L_EVOBIND2_FAILED_STOPPED_NO_RETRY`

## Authorization

- Authorized manifest SHA256: `2410eb59b0eea6310394bd02f66f9152f0609f39c452bd724ee472026e55d24a`
- User authorized a fresh isolated execution state after acknowledging the earlier unauthorized test-manifest PepMLM execution.
- Fixed order: PepMLM → EvoBind2 → DiffPepBuilder → PepFlow → PepHAR → PPFlow.
- Policy: one authorized attempt per model; any failure stops the chain; no automatic or manual retry.

## Pre-authorization evidence preservation

The old test-manifest state, closed gates and artifacts were preserved without deletion before the authorized session:

- Gate/state archive: `/home/xh/kxc/stampup/backups/p33l_pre_auth_archive_20260629_054557/run_gates_p33l`
- Artifact archive: `/mnt/sdb/kxc/stamp_models/artifacts/p33l_pre_auth_archive_20260629_054557`
- The old execution remains out-of-scope evidence and was not retroactively authorized.

## Authorized execution results

| Order | Model | Result | Job ID | Evidence |
|---:|---|---|---|---|
| 1 | PepMLM | SUCCESS | `p33l_pepmlm_29dc1839c8854048` | exit 0; three real candidates; manifest and artifact SHA validated |
| 2 | EvoBind2 | FAILED | `p33l_evobind2_6ec56e45a7464e9b` | exit 1; `ModuleNotFoundError: No module named 'alphafold'` |
| 3 | DiffPepBuilder | SKIPPED_DUE_TO_PRIOR_FAILURE | — | Not started |
| 4 | PepFlow | SKIPPED_DUE_TO_PRIOR_FAILURE | — | Not started |
| 5 | PepHAR | SKIPPED_DUE_TO_PRIOR_FAILURE | — | Not started |
| 6 | PPFlow | SKIPPED_DUE_TO_PRIOR_FAILURE | — | Not started |

## PepMLM success evidence

- Artifact: `/mnt/sdb/kxc/stamp_models/artifacts/p33l/p33l_pepmlm_29dc1839c8854048`
- Run manifest SHA256: `e709ee7cebcf943ff1518ccc525b354ebfb2de5cfde3cd2367d84ea8a1d04413`
- Artifact SHA manifest SHA256: `d25667b71de59d4bf2ebbed97c162ee88b18c3afd5bd7e6f71404772a22ecd33`
- Candidate CSV SHA256: `2088a6e838b0683687bda7f1bc920e2291abfe6c3012ffad5fdea3936375479a`
- The output is computational only and remains `NOT_EXPERIMENTALLY_VALIDATED`.

## EvoBind2 failure evidence

- Artifact: `/mnt/sdb/kxc/stamp_models/artifacts/p33l/p33l_evobind2_6ec56e45a7464e9b`
- Run manifest SHA256: `1bba55733594591e435f87ce2c1449bae977ff4f814a4b508a78aa6c4b8a7453`
- Artifact SHA manifest SHA256: `5ff81ff8f555485210af4b750bfc5ec140020738154ae20245d4ef63e2d790e5`
- Failure log SHA256: `1846507f922e86c62965e3401ced7408bb48d59db1e68c90300b22e8d248f816`
- Exact error:

```text
ModuleNotFoundError: No module named 'alphafold'
```

The failure occurred during the import of `alphafold.common.protein` before model inference began. No retry was attempted, and the environment was not repaired in P33L.

## Control-plane note

After the PepMLM success, the initial EvoBind2 submission was rejected before job creation because the state implementation stored both `running` and `succeeded` events for the same PepMLM job and interpreted the earlier event as failure. The raw state and HTTP 409 response were preserved. The state was normalized to one final record for the same job without changing model code, checkpoint, input or artifact. EvoBind2 was then submitted exactly once and failed for the missing `alphafold` module described above.

## Final safety state

- PepMLM gate: closed.
- EvoBind2 gate: closed.
- P33L GPU lock: absent.
- Target model processes: none.
- Dev backend was safely restarted without `P33L_AUTHORIZED_MANIFEST_SHA`; `/api/v1/p33l/authorized` returns `authorized=false`, so the UI Real Run path is locked again.
- Ports `12823/12824/8001/8080`: HTTP 200 on their proper health/root endpoints.
- Persistent state SHA256: `8e49d12c09cdcfc9407b7c3c67cb8ad1a76857f33c2bf56d2b8f23342dd677d6`.
- User authorization evidence SHA256: `52601939c15598560caac9a74833d69f40c77db1298575d06e164b02e36a8369`.

## Prohibited continuation

P33L is stopped. EvoBind2 must not be repaired and retried within P33L, and the four skipped models must not be started under this task. Any continuation requires a new task, a new frozen manifest and new explicit authorization.
