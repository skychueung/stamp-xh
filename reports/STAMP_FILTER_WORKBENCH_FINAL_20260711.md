# STAMP /filter Workbench Refactor — Final Delivery Report

- **Date:** 2026-07-11
- **Task:** STAMP `/filter` 全自动 / 半自动 统一工作台重构收尾
- **Repo root (remote):** `/home/xh/kxc/stamp-v3`
- **Verdict:** `CONFIG_RECORDED_ONLY_NOT_APPLIED`
  （前端接线 + 后端持久化完成；orchestrator 尚未消费这三个字段）
- **Scientific boundary:** `NOT_EXPERIMENTALLY_VALIDATED` / `COMPUTATIONAL_PREDICTION_ONLY` 保留；Golden Run 继续固定；全部 5 个 ML 模型仍 `REAL_RUN_GATE_CLOSED`。

---

## 1. Branch

```
demo-stabilization-p0p1-tasklist-20260709
```

## 2. HEAD

```
f073baa
```

## 3. 修改文件列表（本轮 7 个，待外科式暂存）

| # | 文件 | git 状态 | 变更量 |
|---|---|---|---|
| 1 | `src/pages/PipelineOrchestratorPage.tsx` | M (tracked) | +1008 |
| 2 | `src/pages/TargetProteinInputPage.tsx` | M (tracked) | 867 行 (±) |
| 3 | `src/components/platform/Sidebar.tsx` | M (tracked) | 185 行 (±) |
| 4 | `src/lib/api/pipelineRuns.ts` | M (tracked) | +91 |
| 5 | `src/lib/sequenceHash.ts` | ?? (new / untracked) | 新增文件 |
| 6 | `backend/app/routers/pipeline_runs.py` | M (tracked) | +358 |
| 7 | `reports/STAMP_FILTER_WORKBENCH_FINAL_20260711.md` | ?? (new) | 本报告 |

tracked 文件合计：**2029 insertions / 480 deletions**（`git diff --stat` 口径，5 个 tracked 文件）。
`src/lib/sequenceHash.ts` 与本报告为未跟踪新文件，需 `git add` 显式纳入。

工作树存在大量历史 dirty / untracked 文件（CHANGELOG、README、DEV_RULES、多 backend 文件、dist 等），本轮**不碰**，仅外科式暂存上述 7 个。

---

## 4. /filter 页面结构

文件：`src/pages/PipelineOrchestratorPage.tsx`（默认导出 `PipelineOrchestratorPage`，路由 `/filter`）。

- **Golden Run 固定**：`const GOLDEN_RUN_ID = 'dcfeea4b-a51f-4963-af3f-1ea2364e6936'`（line 46），共享 live DB 抖动时仍回钉到该 golden run。
- **统一工作台**（line 251 注释：`全自动 / 半自动设计 统一工作台`）：
  - 顶部标题「全自动 / 半自动设计」（line 514）。
  - 模式切换 `['auto','semi_auto']`（line 520），分别配 `Zap` / `FlaskConical` 图标与文案「全自动模式」/「半自动模式」（line 530）。
  - 模式说明：auto = 目标蛋白→表位筛选→靶向肽生成→优化→结构验证→最终排序（自动连续）；semi_auto = 先运行表位筛选、确认候选表位后再继续生成靶向肽（line 534）。
- **目标蛋白输入卡**：序列输入框（line 621）、上传入口（line 663）、标准氨基酸集合 `STANDARD_AA`（line 109）。
- **参数卡**：
  - 表位类型选择 `b_cell / t_cell`（line 726）。
  - 靶向肽生成模型多选（line 739-747，`MODEL_DEFS`），默认 `['pepmlm']`。
  - 运行模式 `auto / semi_auto`（line 258、520-526）。
- **预览卡**（line 793-799）：当前模式、表位类型、已选模型、可运行模型（真实 ML，门禁关闭）、暂不可运行模型——均以 `PreviewRow` 诚实展示，`warn` 标注门禁关闭。
- **执行按钮**：`startRun('auto')`（line 833，全自动）/ `startRun('semi_auto')`（line 837，进入半自动流程）。
- **半自动分支**（line 464-465）：提交后跳到表位筛选，供用户审阅候选表位再继续。
- **结果区**：`StepResultCard`（line 181）+ 步骤状态卡（line 873）+ 结果表 `ResultTable`（line 148）。

旧页面 `TargetProteinInputPage.tsx`（`/target-protein`）保留为「目标蛋白输入（旧版）」，未被删除。

---

## 5. digest 根因与修复

文件：`src/lib/sequenceHash.ts`（新增）。

**根因**：原 target-protein 流程使用 `crypto.subtle.digest('SHA-256', ...)`。Web Crypto 的 `crypto.subtle` **仅在 secure context（HTTPS 或 localhost）可用**。STAMP 预览通过纯 HTTP 提供在 LAN/Tailscale IP（`http://100.75.69.36:12833`），不是 secure context，因此 `window.crypto.subtle` 为 `undefined`，调用 `crypto.subtle.digest(...)` 抛错 `Cannot read properties of undefined (reading 'digest')`。

**修复**：`sequenceHash(sequence)`
- secure context → Web Crypto SHA-256，取前 16 hex 字符；
- 非 secure context（HTTP 非 localhost）→ 同步非密码学回退 `cyrb53`，取前 16 hex 字符；
- 该 hash 仅作短去重 / 索引键（16 hex），**非安全用途**，非密码学回退可接受且已显式标注（`hasWebCryptoSubtle()` 可查询能力）。

---

## 6. selected_models / epitope_type / run_mode 前端接线

**类型与 API**（`src/lib/api/pipelineRuns.ts`）：
```ts
export interface PipelineRunCreate {
  project_id?: string;
  target_name: string;
  target_sequence: string;
  mode?: 'run_all' | 'create_only';
  // ...既有字段...
  selected_models?: string[];          // 新增
  epitope_type?: 'b_cell' | 't_cell';  // 新增
  run_mode?: 'auto' | 'semi_auto';     // 新增
}
// pipelineRunsApi.create(data) -> POST /pipeline-runs，body 含三字段
```

**页面状态与提交**（`src/pages/PipelineOrchestratorPage.tsx`）：
- `runMode`（line 258，默认 `'auto'`）、`epitopeType`（line 271，默认 `'b_cell'`）、`selectedModels`（line 272，默认 `['pepmlm']`）。
- `startRun(mode)`（line 438）提交体（line 453-455）：
```ts
selected_models: selectedModels,
epitope_type: epitopeType,
run_mode: mode,   // mode 为 'auto' | 'semi_auto'
```

> 注意：`body.mode`（`run_all`/`create_only`，是否触发后台 pipeline）与新增的 `run_mode`（`auto`/`semi_auto`，工作台模式语义）是两个不同字段。

---

## 7. 三字段持久化证据

后端 `backend/app/routers/pipeline_runs.py` `PipelineRunCreate` 新增三字段（`extra='ignore'` 兜底，不会 422）；`create_run` 端点在创建 run 后，将三字段写入 `pipeline_runs.output_json["request"]` 并 `db.commit()`（无论 `mode` 是否 `run_all` 都执行持久化）。

**验证证据**（清理前捕获，测试 run `20b4ae73-e669-4e6c-8023-aceabe3eb700`，`mode=create_only`）：
- POST `200`，返回 `run_id=20b4ae73-...`，`status=PENDING`。
- GET `/pipeline-runs/{run_id}` `200`，8 个 step 全 `PENDING`（未执行）。
- 直接读 DB `pipeline_runs.output_json`：
```json
{"request":{"selected_models":["pepmlm","evobind2"],"epitope_type":"b_cell","run_mode":"semi_auto","epitope_filters":null}}
```

| 字段 | 期望 | 实际 | 结果 |
|---|---|---|---|
| selected_models | ["pepmlm","evobind2"] | ["pepmlm","evobind2"] | PASS |
| epitope_type | b_cell | b_cell | PASS |
| run_mode | semi_auto | semi_auto | PASS |

> 该测试 run 已在本轮清理步骤删除（见 §13）。证据为删除前真实捕获。

---

## 8. CONFIG_RECORDED_ONLY_NOT_APPLIED 科学边界

- `backend/app/services/pipeline_orchestrator.py` 的 `run_pipeline_once(db, run_id, top_epitopes, peptides_per_epitope, top_stamp_candidates)` 签名**不含**三字段；函数体只读 `run.status`，**从不读 `run.output_json["request"]`**。
- 全 backend 仅 `pipeline_runs.py` 的持久化块**写入** `output_json["request"]`，**无任何代码读回**消费。
- `grep selected_models|epitope_type|run_mode|epitope_filters` 在 orchestrator 中**零匹配**。
- 结论：三字段已成功记录到 `pipeline_runs.output_json["request"]`，但 pipeline 行为当前**不受其影响** → **CONFIG_RECORDED_ONLY_NOT_APPLIED**。
- 全部 5 个 ML 模型仍 `REAL_RUN_GATE_CLOSED`；Golden Run 继续固定为 `dcfeea4b-a51f-4963-af3f-1ea2364e6936`。

---

## 9. 尚未接通的真实能力（下一阶段）

统一记录为下一阶段任务，**本轮不做**：

> **P2_PIPELINE_CONFIG_APPLICATION_AND_REAL_MODEL_ROUTING**

- `pipeline_orchestrator.py` 实际消费 `selected_models` / `epitope_type` / `run_mode`；
- 真实 ML 模型调度（按 `selected_models` 路由）；
- T 细胞 MHC 预测（`epitope_type='t_cell'` 分支）；
- 六层筛选后端执行；
- 半自动后端 gating（`run_mode='semi_auto'` 在表位筛选后暂停待人审）；
- AMPGen / STAMP 原模型不动。

---

## 10. build 结果

命令：`npm run build` = `tsc -b && vite build`（远程 `/home/xh/kxc/stamp-v3`）。

```
✓ built in 7.90s
```

- TypeScript 编译（`tsc -b`）通过（无类型错误，否则 `vite build` 不会执行）。
- Vite 生产构建成功。
- 仅有预存的 chunk 体积告警（`index-*.js` > 500 kB），**非失败**，与本轮改动无关。

---

## 11. 12823 / 12824 / 12825 / 12833 / 8001 PID

| 端口 | 服务 | PID | 说明 |
|---|---|---|---|
| 12823 | node (live dev 前端) | 3485293 | 未触碰 |
| 12824 | python (live dev 后端) | 3485237 | 未触碰 |
| 12825 | python (独立预览后端) | 2088107 | 本轮早前重启后的新 PID，稳定 |
| 12833 | node (独立预览前端, vite preview) | 2049651 | 已重启并验证 HTTP 200 |
| 8001 | python3 (production 后端) | 3074240 | 未触碰 |

（`ss -ltnp` 实测，2026-07-11）

---

## 12. Golden Run 不变证据

- Golden Run ID：`dcfeea4b-a51f-4963-af3f-1ea2364e6936`
- status：`SUCCEEDED`
- target：`P11311 · ADP1_MYCPN`
- `total_runs`：`4` → 清理后回到 `3`（见 §13）
- Golden Run 行本轮**未修改**。

---

## 13. 测试 run 已清理证据

清理本轮创建的测试 run（无 DELETE API，`grep delete` 在 `pipeline_runs.py` 零命中 → 走最小 DB 事务）：

- run_id（精确匹配）：`20b4ae73-e669-4e6c-8023-aceabe3eb700`
- target：`field_persistence_test_12825`（断言匹配）
- status：`PENDING`（断言匹配）
- 事务：删除 `pipeline_steps` 中 `pipeline_run_id = TEST_ID` 的行 → 删除 `pipeline_runs` 该行 → `commit`。
- 结果：
  - `STEPS_BEFORE = 8`，`DELETED_STEP_ROWS = 8`
  - `TEST_RUN_AFTER_DELETE = None`
  - `TOTAL_RUNS = 3`（4 → 3，回到基线）
  - `GOLDEN_ID = dcfeea4b-...`，`GOLDEN_STATUS = SUCCEEDED`，`GOLDEN_TARGET = P11311 · ADP1_MYCPN`
- 未删除任何其他 run；未触碰 Golden Run；未运行真实计算；未改 DB schema（仅 DELETE 已有行）。

---

## 14. 浏览器验收地址

独立预览前端（12833，HTTP 非 secure context，故触发 §5 的 digest 回退路径，正好覆盖验证）：

- Tailscale：`http://100.75.69.36:12833/filter`
- LAN（如在 192.168.31.x 网段）：`http://192.168.31.218:12833/filter`

后端预览（12825）：`http://100.75.69.36:12825`（health: `{"status":"healthy","service":"stamp-backend","version":"0.6.0"}`）。

验收要点：/filter 页面 全自动/半自动 切换、表位类型、模型多选、预览卡、提交后 run 创建（三字段落库）、digest 不再报错。

---

## 15. 回滚方式

本轮**尚未 commit**（等待浏览器验收）。如需回滚，因改动未提交，直接还原工作树即可：

**A. 5 个 tracked 文件**（已有 `.filter_orig_20260711` 备份）：
```bash
cd /home/xh/kxc/stamp-v3
# 方式 1：从本轮备份还原
cp src/pages/PipelineOrchestratorPage.tsx.filter_orig_20260711   src/pages/PipelineOrchestratorPage.tsx
cp src/pages/TargetProteinInputPage.tsx.filter_orig_20260711     src/pages/TargetProteinInputPage.tsx
cp src/components/platform/Sidebar.tsx.filter_orig_20260711      src/components/platform/Sidebar.tsx
cp src/lib/api/pipelineRuns.ts.filter_orig_20260711              src/lib/api/pipelineRuns.ts
cp backend/app/routers/pipeline_runs.py.filter_orig_20260711     backend/app/routers/pipeline_runs.py
# 方式 2（等价，未提交故还原到 HEAD）
git restore src/pages/PipelineOrchestratorPage.tsx src/pages/TargetProteinInputPage.tsx \
  src/components/platform/Sidebar.tsx src/lib/api/pipelineRuns.ts backend/app/routers/pipeline_runs.py
```

**B. 新增文件**（`sequenceHash.ts`、本报告，untracked）：
```bash
rm -f src/lib/sequenceHash.ts
rm -f reports/STAMP_FILTER_WORKBENCH_FINAL_20260711.md   # 如不保留报告
```

**C. 若已暂存但未 commit**：
```bash
git restore --staged src/pages/PipelineOrchestratorPage.tsx src/lib/sequenceHash.ts \
  src/pages/TargetProteinInputPage.tsx src/lib/api/pipelineRuns.ts \
  src/components/platform/Sidebar.tsx backend/app/routers/pipeline_runs.py \
  reports/STAMP_FILTER_WORKBENCH_FINAL_20260711.md
```
然后执行 A + B。

**D. 12825 后端**：若回滚 `pipeline_runs.py` 后需让旧 schema 重新生效，重启 12825（旧 PID 2341447 → 新 PID 2088107 为本轮重启；回滚后再次重启即可，命令同本轮：`cd backend && nohup ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 12825`）。12823/12824/12833/8001 不需要重启。

回滚不影响 Golden Run、live dev（12823/12824）、production（8001）。

---

## 附：外科式 commit 准备（待用户浏览器验收通过后执行）

- 暂存**仅**上述 7 个文件（`git add` 逐个，**禁止 `git add -A` / `git add .`**）。
- 提交前校验：`git diff --cached --stat` / `git diff --cached --name-only` / `git status --short`，确认暂存区只含 7 个文件、不含 `*.filter_orig_20260711` / dist / 其他历史 dirty。
- 建议 commit message：
  ```
  feat(filter): redesign automated and semi-automated STAMP workbench
  ```
- **不 push。**
