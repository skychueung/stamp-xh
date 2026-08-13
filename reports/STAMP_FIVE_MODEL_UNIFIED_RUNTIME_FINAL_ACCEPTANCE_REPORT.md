# STAMP-XH 五模型统一运行最终验收报告

- 验收时间：2026-08-14（Australia/Sydney）
- 目标仓库：[skychueung/stamp-xh](https://github.com/skychueung/stamp-xh)
- 分支：`fix/five-model-unified-runtime`
- 本报告对应 HEAD：`f86b534`
- 独立部署：`http://100.75.69.36:12973`（Tailscale），后端 `12974`
- **FINAL VERDICT: PARTIAL**

## 1. 执行摘要

统一注册、API、数据库任务、worker、状态机、JSONL 日志、GPU 锁、产物隔离、取消、超时、崩溃恢复和浏览器界面已落地。PepMLM、EvoBind2、PepHAR、PepFlow 完成 12/12 次真实 checkpoint 推理；总分母为 15，本轮实际 **12/15**。PepPrCLIP 官方 MiniCLIP 权重位于需确认许可的 Hugging Face gated 仓库，服务器未配置该资产，因此其 3 次真实推理仍为空缺。官方论文同时说明完整代码需经非商业研究许可获取。[官方模型仓库](https://huggingface.co/ubiquitx/pepprclip/tree/main)｜[论文与数据声明](https://pmc.ncbi.nlm.nih.gov/articles/PMC11291000/)

## 2. 根因与修复

| 根因 | 修复结果 |
|---|---|
| 注册层只有静态 accepted，执行层未统一 | 五模型统一 `submit/status/cancel/collect_artifacts/normalize_result`；真实子进程由数据库 worker 调度 |
| worker 领取竞态、首次运行后的锁/标记风险 | 条件 UPDATE 原子领取；GPU lock 与 busy marker 统一 `finally` 清理 |
| 服务重启遗留 RUNNING | API 启动与 worker 启动扫描，写入 `RECOVERING → QUEUED` 后仅领取一次 |
| 前端 POST 缺 Cookie/CSRF | fetch client 统一 credentials 与 CSRF header |
| Pipeline 长期 QUEUED | 12973 独立栈加入 durable pipeline worker，并限制交互候选数为 10 |
| Pipeline 仍消费确定性基线 | 直接消费统一模型任务的真实 candidates，并保留 source model |

## 3. 五模型矩阵

| 模型 | 运行探测 | Checkpoint SHA256 | 真实连续运行 | 判定 |
|---|---|---|---:|---|
| pepmlm | ready | `e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668` | 3/3 | PASS |
| pepprclip | checkpoint_missing | — | 0/3 | OPEN |
| evobind2 | ready | `f95e453e6a290ddf317ba1c9698d53fa110cf007ea979b0eae43e6ad38b4e364` | 3/3 | PASS |
| pephar | ready | `06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15` | 3/3 | PASS |
| pepflow | ready | `80ef4d7a07eddd877067859b5df95c50833cb72c40ef10d6ff5aa1263f0dba21` | 3/3 | PASS |

说明：PepHAR 与 PepFlow 的 runner 确实加载并执行真实 checkpoint；当前输入桥接使用项目自带历史结构 fixture。它们尚未把任意 `target_sequence` 自动转换成各自所需结构输入，此项保留为输入语义差距。

## 4. 连续真实运行

| 模型 | seed 41 | seed 42 | seed 43 | 结果 |
|---|---|---|---|---|
| PepMLM | SUCCEEDED | SUCCEEDED | SUCCEEDED | 3/3 |
| PepPrCLIP | checkpoint_missing | checkpoint_missing | checkpoint_missing | 0/3 |
| EvoBind2 | SUCCEEDED | SUCCEEDED | SUCCEEDED | 3/3 |
| PepHAR | SUCCEEDED | SUCCEEDED | SUCCEEDED | 3/3 |
| PepFlow | SUCCEEDED | SUCCEEDED | SUCCEEDED | 3/3 |

逐任务 job ID、时长、候选和 checkpoint 指纹见 `reports/*_real_3x_results.json`。12 次均有非空结果 JSON、runner log、候选或结构产物；结束后锁与 busy 目录为空。

## 5. 组合、并发与控制面验收

- 五模型组合 run：`models_632ed8c58ced46fe`，五个子任务全部创建；PepMLM/EvoBind2/PepHAR/PepFlow 成功，PepPrCLIP 以明确 `RUNNER_COMMAND_MISSING` 失败，总状态 `PARTIAL`，其余四份结果均保留。
- 组合日志：51 条，包含五个 model_id，日志未混淆；具备领取、探测、推理、状态、锁获取/释放事件。
- 不同模型任务：观察到 `[RUNNING, QUEUED]` 后依次 `SUCCEEDED`，资源不足真实排队。
- 同模型双任务：观察到 `[RUNNING, QUEUED] → [SUCCEEDED, RUNNING] → [SUCCEEDED, SUCCEEDED]`。
- 运行中取消：job `8085f59c-40c8-4133-8ad7-b42b6795c6a0` 进入 `CANCELLED`，锁/标记清理。
- 超时：job `a04be744-4f47-4c9b-a818-7a3350b46502` 在 1 秒测试阈值进入 `TIMED_OUT`，随后恢复常规 worker。
- worker 崩溃恢复：job `9c845225-d954-4091-b5c0-e98fed931b7a` 日志含 `STATE_RECOVERING → STATE_QUEUED → WORKER_CLAIMED`，最终 `SUCCEEDED`。

## 6. API、日志与浏览器

- `/api/health`：200。
- `/api/v1/models/production/status`：恰好五模型，四 ready、一 checkpoint_missing。
- 统一提交、状态、run 汇总、日志筛选、产物列表/下载、取消均实测。
- 浏览器登录后真实创建 Pipeline，run `c54b50f3-547c-427f-93fc-5d695a089678` 最终 `SUCCEEDED`；刷新后状态、步骤、日志和结果从后端恢复。
- 五模型选择的浏览器 Pipeline，run `62b5cba1-76e3-409a-be2c-98e52279fbb4` 最终 `SUCCEEDED`：四个 ready 模型结果完整保留，PepPrCLIP 以 `checkpoint_missing` 警告呈现，不再抹除其余结果。
- 页面新增模型子任务控制台：逐模型状态、进度、开始/结束信息、结构化事件日志、错误 JSON、取消按钮和真实产物下载。
- 截图：`output/playwright/five-model-runtime-12973.png`、`output/playwright/pepmlm-live-run-succeeded-12973.png`、`output/playwright/unified-model-job-console-12973.png`、`output/playwright/partial-five-model-pipeline-12973.png`。

## 7. 自动化测试

| 命令 | 结果 |
|---|---|
| Linux `pytest -q backend/tests` | **1678 passed, 3 skipped, 0 failed**, 302.38s |
| `npm run lint` | PASS |
| `npm run build` | PASS，3600 modules transformed |
| Pipeline focused tests | 20 passed |

首次全量测试暴露服务器 venv 未按 `backend/requirements.txt` 安装 numpy/pdfminer.six；补齐已声明依赖后，原 3 项失败单独复测 3/3、全量复测全绿。

## 8. 部署与回滚

启动：`bash scripts/start-unified-runtime-12973.sh`。运行数据在 `/home/xh/kxc/runtime/five-model-unified`，PID/日志在 `/home/xh/kxc/run/stamp-five-model`。脚本仅管理本独立栈的 12973/12974、model worker、pipeline worker。回滚时终止这四个 PID，并切换到前一提交后重跑脚本；数据库与 artifacts 保留。

## 9. 最终验收表

| 验收项 | 目标 | 实际结果 | 证据 | 判定 |
|---|---:|---:|---|---|
| 五模型注册 | 5/5 | 5/5 | production/status | PASS |
| 五模型真实适配器 | 5/5 | 5/5 接口；4/5 资产就绪 | registry + probe | PARTIAL |
| 五模型真实生成 | 5/5 | 4/5 | 12 个真实 job | PARTIAL |
| 连续运行 | 15/15 | 12/15 | `*_real_3x_results.json` | PARTIAL |
| 五模型组合任务 | 1/1 | 1/1 子任务创建，4 成功 1 资产失败 | combined JSON | PARTIAL |
| 并发任务 | 通过 | 串行 GPU 排队通过 | concurrency JSON | PASS |
| 失败后再运行 | 通过 | 通过 | 自动化测试 | PASS |
| 重启恢复 | 通过 | RECOVERING 后成功 | restart JSON | PASS |
| 结构化日志 | 5/5 | 5/5 | 组合 run 51 条 | PASS |
| 前端日志展示 | 通过 | 通过 | 浏览器截图 | PASS |
| 产物隔离 | 通过 | 独立 run/model/job 路径 | artifact manifests | PASS |
| GPU锁清理 | 100% | 100%，审计为空 | server audit | PASS |
| 后端测试 | 全部通过 | 1678 passed / 3 skipped | pytest log | PASS |
| 前端构建 | 通过 | 通过 | Vite build | PASS |
| GitHub推送 | 完成 | 分支已推送 | GitHub branch | PASS |

## 10. 开放差距与收口条件

1. 在 Hugging Face 接受 PepPrCLIP 许可并取得 `weights-20240131T125328Z-001.zip`，配置 `STAMP_PEPPRCLIP_*`，记录 SHA256，执行 seeds 41/42/43；届时连续运行可由 12/15 提升至 15/15。
2. 为 PepHAR/PepFlow 增加目标相关 receptor/complex 预处理，使结构 fixture 转为请求级输入。
3. 服务器 Node 升至 Vite 7 推荐版本；对 5.27 MB 主 chunk 做路由级拆包，并处理 npm audit 报告。

**FINAL VERDICT: PARTIAL**
