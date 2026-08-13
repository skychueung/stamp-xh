# STAMP-XH 五模型统一执行：阶段验收记录（2026-08-14）

## 1. 本阶段判定

- 五模型统一注册、统一持久化任务状态机、统一 JSONL 日志、隔离产物目录、独立 worker、取消/超时/重启恢复与标准结果结构已经进入同一执行主干。
- PepMLM、EvoBind2、PepHAR、PepFlow 已分别使用真实 checkpoint 连续执行 seed 41/42/43，结果为 **12/12 SUCCEEDED**。
- PepPrCLIP 的 3 次真实生成/排序仍按 15 次总分母计入最终验收；本文件不把历史产物、probe 或 fixture 测试计为本轮真实生成。

## 2. PepMLM 真实连续运行证据

固定输入：`MKKLLPTAAAGLLLLAAQPAMA`；肽长 12；设备 `cuda:1`。

| seed | job_id | 状态 | 候选 | 运行时长 |
|---:|---|---|---|---:|
| 41 | `d364acfe-b715-4874-a620-1350dd58c68b` | SUCCEEDED | `EELVVLAALLAR` | 5.322s |
| 42 | `366b6d5f-79bd-4cfa-b558-040c65e996fc` | SUCCEEDED | `QSVLLAAAAALG` | 5.363s |
| 43 | `9dc52ffb-1313-475f-8334-91b6f829bee7` | SUCCEEDED | `QVVLVLLLQLAG` | 5.336s |

Checkpoint SHA256：`e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668`

机器可读记录：`reports/pepmlm_real_3x_results.json`。三个任务均生成 request、runner log、CSV、JSON 和 manifest；任务结束后 GPU lock 与 busy 标记已清理。

## 3. 自动化验证

| 验证 | 结果 |
|---|---|
| 本地 focused pytest | 14 passed / 19.03s |
| 服务器 focused pytest | 14 passed / 18.98s |
| 前端 TypeScript + Vite build | passed（3600 modules） |
| ESLint | passed |

## 3.1 新增真实运行摘要

| 模型 | seed 41 | seed 42 | seed 43 | checkpoint SHA256 |
|---|---|---|---|---|
| EvoBind2 | `HGPNMQICVADR` | `EGVITPQFDFMV` | `DWACWQHVTGEC` | `f95e453e6a290ddf317ba1c9698d53fa110cf007ea979b0eae43e6ad38b4e364` |
| PepHAR | `PPAVVAAPPVVV` | `PVPPPPAPPVAI` | `PPVPGPAPAVVP` | `06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15` |
| PepFlow | `EWEDIKEIWAEEWPNEVNPHES` | `ENEENCWDHWPEEFPESNEPTP` | `DMEPTDDWEGSIIASNEINFEE` | `80ef4d7a07eddd877067859b5df95c50833cb72c40ef10d6ff5aa1263f0dba21` |

机器可读记录：

- `reports/evobind2_real_3x_results.json`
- `reports/pephar_real_3x_results.json`
- `reports/pepflow_real_3x_results.json`

## 4. 本阶段新增修复

1. GPU 文件锁升级为原子 `O_EXCL` 创建，锁记录含 owner、PID、创建时间与 TTL，并兼容旧锁格式。
2. 异步 API 只负责持久化入队，由独立 worker 领取，避免把长 GPU 推理绑在 FastAPI `BackgroundTasks` 生命周期。
3. 修复 run_id 查询未过滤其他任务的问题。
4. 结果加载兼容 EvoBind2/PepHAR 常见的 `metrics.csv` 与 `test.csv`。
5. 前端模型状态切换到 `/api/v1/models/production/status` 的五模型真实文件探测，不再展示旧的静态门禁文案。

## 5. 剩余最终验收项

- PepPrCLIP：官方 Quickstart 已核实“ESM 高斯扰动生成 + MiniCLIP 排序”的完整生成路径；服务器当前 4.83GB `PepPrCLIP.zip` 经归档目录核验仅含实验原始数据，不含 MiniCLIP checkpoint。官方 Hugging Face 仓库列出的 24.6MB checkpoint/weight archive 受访问确认控制，服务器账户尚未持有该资产。
- 完成五模型组合、并发、取消、超时、服务重启、前端浏览器截图、12973 部署与最终 15/15 报告。
