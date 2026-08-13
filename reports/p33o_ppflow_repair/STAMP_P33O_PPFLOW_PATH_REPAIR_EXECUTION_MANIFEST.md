# STAMP P33O — PPFlow Invocation-Path Repair Execution Manifest

## User authorization

User instruction: `全力抢修`.

Among the failed models, PPFlow is selected as the lowest-risk repair because:

- P33N failed before model loading only because `./dataset/PPDbench/` was resolved from the artifact directory.
- The official dataset directory exists under the PPFlow source root with 136 sample directories.
- P33G previously completed successfully with the same checkpoint/config using the hardened runner from the source root.

## Repair boundary

- One PPFlow controlled validation attempt.
- Reuse the P33G hardened runner and exact CPU/seed/batch/sample/step limits.
- Change only the invocation path by using the runner's validated `cwd=SOURCE_DIR` behavior.
- No model source, checkpoint, config, dataset, input or scientific-parameter modification.
- No GPU use or GPU-process interference.
- Failure stops P33O; no retry.
- Output remains `NOT_EXPERIMENTALLY_VALIDATED`.

## Frozen execution

| Item | Path | SHA256 |
|---|---|---|
| P33O wrapper | `/home/xh/kxc/stampup/scripts/p33o_ppflow_path_repair_wrapper.sh` | `80bfe3a27e196d78223ccbcc8af04364d27a1c7c31fde5ba4eb2da37ff154ad2` |
| Hardened runner | `/mnt/sdb/kxc/stamp_models/scripts/stamp_ppflow_p33_smoke_runner_v2.py` | `2b11805ced553a38c613571489ba01a592e7b400f4a6a74340dd7f7d430e9d1c` |
| Gate helper | `/mnt/sdb/kxc/stamp_models/scripts/stamp_p33e_gate_helper.py` | `b36ba150ec43502faa0dd832a90d9eeccaf7b18f2f0fe5dc2fe121847244e93e` |
| Config | `/mnt/sdb/kxc/stamp_models/source/ppflow/extracted_p25_install_probe/ppflow-main/configs/test/codesign_ppflow.yml` | `aaf0691414595bf59ed384ca5aacd722040cf853b51f53188b79c15bd14c1db1` |
| Checkpoint | `/mnt/sdb/kxc/stamp_models/checkpoints/ppflow/p25_install_probe/ppflow/pretrained.pt` | `be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d` |

## Parameters

- Device: CPU
- Seed: 2024
- Batch size: 1
- Samples: 1
- Sampling steps: 10
- Wall timeout: 1800 seconds
- Output quota: 50 MiB
- Gate: `/home/xh/kxc/stampup/run_gates/p33e/ppflow/.ppflow_real_run_enabled`
- Artifact: `/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_<timestamp>/`

## Success criteria

- Runner exit code 0.
- Runner manifest `success=true` and `exit_code=0`.
- Non-empty generated PPFlow output files.
- Gate absent after cleanup.
- No residual PPFlow process.

