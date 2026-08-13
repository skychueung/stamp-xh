# STAMP P33O PPFlow 路径抢修成功报告

- 日期：2026-06-29 CST
- 任务：P33O PPFlow 独立调用路径修复与单次受控验证
- 最终 Gate：`P33O_PPFLOW_PATH_REPAIR_REAL_RUN_SUCCESS`
- 验证标记：`NOT_EXPERIMENTALLY_VALIDATED`

## 一句话结论

P33N PPFlow 失败不是模型、checkpoint 或数据损坏，而是从 artifact 目录启动官方程序时，相对路径 `./dataset/PPDbench/` 解析错误。P33O 复用已在 P33G 成功的 hardened runner，以绝对数据路径与临时 config 完成了一次 CPU 受控执行：exit 0，133 个样本目录，404 个文件，用时 588.46 秒。

## 修复范围

- 未修改 PPFlow source、checkpoint、官方 config 或科学参数。
- 仅修复启动路径与运行工作目录契约。
- 仅发起一次 P33O 尝试，无自动或手工重试。
- 使用 CPU，未终止、抢占或修改现有 GPU 任务。

## 执行结果

| 项目 | 结果 |
|---|---|
| Artifact | `/mnt/sdb/kxc/stamp_models/artifacts/ppflow/p33o_ppflow_path_repair_20260629_063127/` |
| Runner | `stamp_ppflow_p33_smoke_runner_v2.py --mode submit` |
| Device | CPU |
| Exit code | `0` |
| Manifest success | `true` |
| Elapsed | `588.4605281352997s` |
| 样本目录 | `133` |
| 文件数 | `404` |
| Artifact 字节数 | `4,408,281` |
| Gate 清理 | P33O 结束后 absent |
| 目标残留进程 | `0` |

## 冻结资产

| 资产 | SHA256 |
|---|---|
| PPFlow runner | `2b11805ced553a38c613571489ba01a592e7b400f4a6a74340dd7f7d430e9d1c` |
| Gate helper | `b36ba150ec43502faa0dd832a90d9eeccaf7b18f2f0fe5dc2fe121847244e93e` |
| Official config | `aaf0691414595bf59ed384ca5aacd722040cf853b51f53188b79c15bd14c1db1` |
| Checkpoint | `be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d` |
| P33O wrapper | `80bfe3a27e196d78223ccbcc8af04364d27a1c7c31fde5ba4eb2da37ff154ad2` |
| P33O execution manifest | `1c3cfe85a35989f4deef44305186eb1683336c2900a9e5c43e24c8e0729ec307` |
| Result manifest | `6d14f2f56f927d5130099d88e3993534a8662b88e43394cbc36de93a5a006a00` |
| Status | `3ffca90345575290cf9fccfbfb3997799631c7834e5f1a94c0e7f520c18628d8` |
| Runner log | `a4d59f8b14fac8d3789f453ef45e0713ef4a968e17abcab6f6b7d7a8d6b70770` |

## 最终安全状态

- P33O/PPFlow 目标进程：0。
- P33O 使用的 PPFlow gate：absent。
- P33N 旧 gate 证据仍保留，未删除或篡改。
- `12823/12824/8001/8080`：全部 HTTP 200。
- GPU 上原有 VLLM/Python 进程未受影响；P33O 未使用 GPU。

## 产品语义

本次结果证明 PPFlow 在冻结资产与受控路径下可完成计算执行，但不代表实验验证、临床有效性或自动解锁网页 Real Run。如需推送 Registry/UI 状态，应在独立收口任务中引用本报告与 SHA 证据。
