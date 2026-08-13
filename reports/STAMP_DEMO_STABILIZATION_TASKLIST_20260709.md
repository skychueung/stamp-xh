# STAMP 演示前工程止血任务单

生成时间：2026-07-09  
工作副本：`/home/xh/kxc/stamp-v3`  
任务分支：`demo-stabilization-p0p1-tasklist-20260709`  
当前目标：20 号前只做主流程稳定、界面收敛、结果追溯和中文演示，不新增模型，不做大重构。

## 0. 仓库核对结论

### 0.1 Git 状态

- 当前检查分支：原为 `v1.5-md-computation-pilot`，已新建任务分支 `demo-stabilization-p0p1-tasklist-20260709`。
- 最近提交：`f073baa chore(pepglad): patch conda-pack dependency probe`。
- 远端：`origin https://github.com/skychueung/stamp-targeted-peptide-platform.git`。
- 工作区不是干净状态：初查约 `1310` 个 tracked 修改、`397` 个 untracked 条目，包含大量历史报告、运行产物、data_dev/pipeline_runs、模型探针记录等。
- 处理原则：后续修复必须只改演示主链路相关文件，避免清理或回滚历史运行产物。

### 0.2 服务和端口

当前运行服务没有切到 `stamp-v3`，仍在原目录运行：

| 端口 | 进程 | 工作目录 | 说明 |
|---|---|---|---|
| 12823 | `node vite preview` | `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev` | 当前线上/演示前端，不动 |
| 12824 | `uvicorn app.main:app` | `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/backend` | 当前线上/演示后端，不动 |
| 8001 | `uvicorn app.main:app` | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend` | 旧后端/其他版本，不作为本次主线 |

健康检查结果：

- `GET http://127.0.0.1:12824/health` 返回 `200`，`STAMP backend is healthy`。
- `GET http://127.0.0.1:12824/api/health` 返回 `200`。

### 0.3 当前主链路真实状态

前端存在多条并行路线：

- `/targeted-peptide-design` 当前实际渲染 `src/components/p33u/RunConsole.tsx`。
- `/target-design` 渲染 `TargetedPeptideDesignCenterPage.tsx`，包含旧模型中心、P33T 结果中心、P33U RunConsole 等混合内容。
- `/epitope-screening`、`/peptide-generation`、`/final-ranking` 是旧主流程页面，但默认存在 mock/localStorage fallback。
- `/api/v1/pipeline-runs` 是更接近“输入靶蛋白到最终排序”的后端流水线，但前端主入口没有把它包装成清晰演示流程。
- `/api/v1/p33u/run/model` 是当前模型运行控制台入口，能返回 `job_id/run_id/status/gate/provenance`，但 UI 偏开发控制台，且只支持单模型点击，不是汇报型主流程。

### 0.4 模型清单核对

来自 `GET /api/v1/p33u/run/console-matrix`：

| 模型 ID | 演示状态 | 真实含义 | 当前建议 |
|---|---|---|---|
| `pepmlm` | enabled | real-run enabled，已有 D20A 成功证据 | 保留为核心模型 |
| `diffpepbuilder` | enabled | registry-dispatched dev real-run smoke | 保留，但说明为开发烟测 |
| `pephar` | enabled | registry-dispatched dev real-run smoke | 保留，但说明为开发烟测 |
| `evobind2` | enabled | minimal smoke passed, ingested D29 | 保留，但说明 PTM fallback/开发烟测边界 |
| `pepflow` | enabled | artifact-only parser smoke，不是新 forward pass | 若保留，必须标注“历史 artifact 解析” |
| `ppflow` | blocked | no upstream LICENSE，never run | 演示界面隐藏，不显示灰色锁定 |
| `pepprclip` | backlog | roadmap only | 演示界面隐藏 |
| `rfpeptides` | backlog | roadmap only | 演示界面隐藏 |
| `pepglad` | backlog | roadmap only | 演示界面隐藏 |

结论：当前阶段可对外讲的“核心模型入口”最多 5 个，但其中 `pepflow` 不是实时模型生成，只能作为“历史 artifact parser smoke”。如果汇报强调实时生成，建议演示只启用 `pepmlm/diffpepbuilder/pephar/evobind2` 四个，并在报告中说明 PepFlow 暂不作为实时生成模型。

### 0.5 关键风险证据

- `src/pages/FinalRankingPage.tsx` 存在 `mockRankedPeptides` fallback，虽然有标注，但仍可能在无数据时展示 mock 排序。
- `src/pages/EpitopeScreeningPage.tsx` 内置 `mockEpitopeCandidates`，默认 dataSource 可为 `mock`。
- `src/pages/PeptideGenerationPage.tsx` 内置 `mockSelectedEpitope`，无 scan/epitope 时会进入 mock/localStorage fallback。
- `backend/app/services/target_peptide_design_service.py` 明确写有 `No real model was executed in P2.`，旧 `target-peptide-design/jobs` 不能作为演示真实生成入口。
- `src/lib/api/p33t.ts` 调用 `/api/v1/target-design/results`，后端该路由需要登录；未登录直接 `401 Not authenticated`。演示流程若没有稳定登录态，结果中心会失败。
- `/api/v1/pipeline-runs` 已有成功 run：`dcfeea4b-a51f-4963-af3f-1ea2364e6936`，状态 `SUCCEEDED`，目标 `P11311 · ADP1_MYCPN`，可作为 golden demo 候选基础。

## 1. 本次止血范围

### 必须做

- 把演示主流程收敛成一条：靶蛋白输入 -> 表位筛选 -> 用户确认继续 -> 模型生成 -> 评分排序 -> 导出/报告。
- 每次运行必须显示 `run_id/job_id/created_at/input/selected_models/status/error/source_model/score_breakdown`。
- 修复模型切换后结果不变或旧结果残留问题。
- 明确区分实时运行、历史结果、示例数据、mock fallback。
- 中文化核心页面和错误提示。
- 保留 `12823/12824` 当前服务不动，在 `stamp-v3` 副本完成并验证。

### 禁止做

- 不新增模型。
- 不把历史运行结果伪装成实时结果。
- 不删除历史模块，只隐藏演示入口。
- 不大规模重构路由、数据库、模型适配器。
- 不清理海量历史数据产物，避免误伤。

## 2. P0 任务单

### P0-0：建立工作安全线

目标：确保后续修改在副本和分支中完成，可回滚，可对比。

涉及文件/位置：

- `/home/xh/kxc/stamp-v3`
- `reports/`
- git branch `demo-stabilization-p0p1-tasklist-20260709`

任务：

1. 固定后续开发分支，例如 `demo-stabilization-p0p1-fixes-20260709`。
2. 记录当前 dirty worktree 基线，禁止执行 `git reset --hard`、大范围删除、批量格式化。
3. 后续每个 P0 修复单独提交，提交信息包含任务号。
4. 建议先添加 `.git/info/exclude` 或后续单独任务处理运行产物，不在本轮大清理。

验收：

- `git branch --show-current` 显示演示止血分支。
- `git status --short` 中新增修改只集中在主流程文件和报告。

### P0-1：固定 golden demo input，并保证默认示例稳定跑通

目标：至少一个固定示例从输入到结果稳定成功，连续 3 次可复现。

建议 golden demo：

- 名称：`P11311 · ADP1_MYCPN`
- 依据：当前 `/api/v1/pipeline-runs` 已有成功 run `dcfeea4b-a51f-4963-af3f-1ea2364e6936`。
- 需要补齐：在前端示例按钮中固定 target_name、target_sequence、top_epitopes、peptides_per_epitope、top_stamp_candidates。

涉及文件：

- `src/lib/api/pipelineRuns.ts`
- `src/pages/TargetProteinInputPage.tsx`
- `src/pages/PipelineOrchestratorPage.tsx`
- `src/components/p33u/RunConsole.tsx`
- `backend/app/routers/pipeline_runs.py`
- `backend/app/services/pipeline_orchestrator.py`

子任务：

1. 从成功 run 的 artifact 或数据库中提取 golden demo 的完整 `target_sequence`，写入一个明确的 demo preset。
2. 前端提供“载入演示输入”按钮，按钮旁标注“固定演示样例”。
3. 默认示例只调用真实 `/api/v1/pipeline-runs` 或 `/api/v1/p33u/run/model`，不能落到 mock。
4. 失败时显示后端 `error_message/detail/failure_reason`，不要只显示 “API request failed”。
5. 连续运行 3 次，记录 run_id 和状态。

验收：

- 页面显示真实 `run_id`。
- 后端返回 `SUCCEEDED` 或模型 job `succeeded`。
- 至少能看到候选序列和来源模型。
- 失败路径能显示明确错误原因。

测试：

| 测试项 | 输入 | 预期 |
|---|---|---|
| golden demo 创建 | P11311 固定序列 | 返回新 run_id |
| golden demo 运行 1 | 默认参数 | 成功 |
| golden demo 运行 2 | 默认参数 | 成功 |
| golden demo 运行 3 | 默认参数 | 成功 |
| 非法序列 | `ABC123` | 显示 validation error，不转圈假运行 |

### P0-2：修复模型切换后结果不变和旧结果残留

目标：模型选择必须改变后端请求和前端展示，旧结果不能留在新模型上下文中。

涉及文件：

- `src/components/p33u/RunConsole.tsx`
- `src/lib/api/p33u.ts`
- `backend/app/routers/p33u.py`
- `src/components/p33t/P33TResultCenter.tsx`
- `src/lib/api/p33t.ts`

已知情况：

- `RunConsole` 会把 `model_id` 传给 `/api/v1/p33u/run/model`。
- 后端 `run_model` 使用 `req.model_id` 生成 `run_id`，如 `pepmlm_xxx` 或 `{model}_xxx`。
- 前端切换模型时清空 `activeJob/artifacts/error/logs`，但最终候选结果中心和 smoke candidates 仍可能显示历史/烟测数据，造成“切换模型结果不变”的观感。

子任务：

1. 在模型选择区显示“本次运行结果”和“历史/烟测结果”两个分区。
2. `activeJob.result_summary` 必须展示候选序列时附带 `source_model`。
3. 切换模型后清空当前 run 的结果表，同时保留历史区但标注为“历史烟测/非本次运行”。
4. `P33TResultCenter` 的默认 `SOURCE_MODELS` 删除或隐藏 `ppflow`，隐藏 backlog 模型。
5. 如果 `PepFlow` 保留，UI 文案改为“PepFlow 历史 artifact 解析”，不是“生成模型”。
6. 增加前端测试或手动验证：PepMLM 和 PepHAR 运行后 `run_id` 前缀不同、`model_or_scorer` 不同。

验收：

- 选择 PepMLM 后运行，结果显示 `source_model=pepmlm`，`run_id=pepmlm_*`。
- 选择 PepHAR 后运行，结果显示 `source_model=pephar`，`run_id=pephar_*`。
- 未运行新模型前，不展示上一模型的实时结果。
- 历史 smoke candidates 只在“历史/烟测结果”区出现。

### P0-3：统一运行结果可追溯结构

目标：每次运行能回答“谁生成、什么时候、用什么输入、什么模型、什么参数、为什么排序”。

涉及文件：

- `src/lib/api/p33u.ts`
- `src/components/p33u/RunConsole.tsx`
- `backend/app/routers/p33u.py`
- `backend/app/routers/pipeline_runs.py`
- `backend/app/services/pipeline_orchestrator.py`
- `src/lib/api/pipelineRuns.ts`
- `src/components/p33t/P33TResultCenter.tsx`

统一字段要求：

```json
{
  "run_id": "...",
  "job_id": "...",
  "created_at": "...",
  "input_type": "target_sequence|epitope_sequence",
  "input_sequence": "...",
  "uniprot_id": "...",
  "epitope_filter_mode": "...",
  "selected_models": ["pepmlm"],
  "model_name": "PepMLM",
  "model_version": "...",
  "parameters": {},
  "status": "running|succeeded|failed|historical|demo",
  "error_message": null,
  "epitope_candidates": [],
  "peptide_candidates": [],
  "candidate_sequence": "...",
  "candidate_rank": 1,
  "length": 12,
  "charge": 0,
  "hydrophobicity": 0.0,
  "toxicity_score": null,
  "targeting_score": null,
  "final_score": null,
  "score_breakdown": {},
  "source_model": "pepmlm"
}
```

子任务：

1. 后端 `p33u` job 返回 `created_at` alias 或将 `start_time` 映射为 `created_at`。
2. `result_summary` 增加候选列表时，必须包含 `candidate_sequence/source_model/parameters/score_breakdown`。
3. `pipeline_runs` step summary 中现有 `candidates/peptides/final_ranking` 增加统一映射字段，缺失评分显示 `null`。
4. 前端最终表头使用中文展示：运行编号、来源模型、候选序列、长度、电荷、疏水性、综合评分、评分拆解。
5. 缺失真实字段时显示“未计算”，禁止补假数。

验收：

- 页面最终表能看到 `run_id/source_model/candidate_sequence/final_score`。
- 刷新页面后能通过 `run_id` 重新加载同一结果。
- 无真实评分字段时显示“未计算”。

### P0-4：修复结果中心认证和 API 路径风险

目标：演示时最终排序页不能因为未登录或路径不一致而空白。

涉及文件：

- `src/lib/api/p33t.ts`
- `src/components/p33t/P33TResultCenter.tsx`
- `backend/app/routers/p33t.py`
- `src/contexts/AuthContext.tsx`
- `src/App.tsx`

已知证据：

- `GET /api/v1/target-design/results?...` 未登录返回 `401 Not authenticated`。
- 结果中心依赖 `require_active`。

子任务：

1. 明确演示路线是否需要登录。推荐：保留登录，但给演示账号和自动跳转提示。
2. 如果登录态失效，结果中心显示“请先登录以查看可追溯结果”，不要 fallback 到 mock。
3. 确认前端 `API_PREFIX=/api/v1/target-design` 与后端 router prefix 一致。
4. 演示主流程页面应避免无提示地进入未认证结果中心。

验收：

- 未登录访问结果页显示明确中文认证提示。
- 登录后结果页能加载 P33U candidates。
- 不因为 401 而展示 mock 排序。

## 3. P1 任务单

### P1-1：简化首页和左侧菜单

目标：老师第一次看能理解主流程，不被历史模块干扰。

涉及文件：

- `src/components/platform/Sidebar.tsx`
- `src/pages/HomePage.tsx`
- `src/App.tsx`

当前菜单过多：Job Center、System Health、Audit Logs、File Manager、Batch Computation、Production MD、LIMS、EvoBind2、旧版 Filter、Design Center 等。

子任务：

1. 新增 `DEMO_NAV_ITEMS`，只显示：首页、靶蛋白输入、表位筛选、模型生成、候选排序、结果导出/报告。
2. 历史入口保留路由，但从侧栏隐藏。
3. 首页改为“AI 辅助靶向肽设计演示流程”，不要堆模块卡片。
4. 可选：在 URL 或环境变量中保留 admin/debug nav 开关。

验收：

- 左侧菜单不超过 6 个核心入口。
- 旧路由仍可直接访问。
- 首页首屏能看到流程和“开始演示”。

### P1-2：核心界面汉化

涉及文件：

- `src/components/p33u/RunConsole.tsx`
- `src/components/p33t/P33TResultCenter.tsx`
- `src/pages/EpitopeScreeningPage.tsx`
- `src/pages/PeptideGenerationPage.tsx`
- `src/pages/FinalRankingPage.tsx`
- `src/i18n/translations.ts`
- `src/lib/platformText.ts`

子任务：

1. RunConsole 标题改为“靶向肽模型生成”。
2. 按钮汉化：`Run model` -> `运行模型生成`，`Run scorer` -> `运行评分`。
3. 字段汉化：`run_id` -> `运行编号`，`job_id` -> `任务编号`，`source_model` -> `来源模型`。
4. 错误提示汉化，保留英文错误码。
5. 评分字段汉化：长度、电荷、疏水性、靶向评分、毒性/安全性、稳定性、综合评分。

验收：

- 核心演示路径中文可讲。
- 必要英文缩写保留，并有中文解释。
- 后端字段名不变。

### P1-3：表位筛选到模型生成的半自动流程

目标：用户可先看表位结果，再选择是否继续生成靶向肽。

推荐实现路径：优先用现有 `/api/v1/pipeline-runs` 拆步或前端分阶段展示，不重写模型后端。

涉及文件：

- `src/lib/api/pipelineRuns.ts`
- `src/pages/EpitopeScreeningPage.tsx`
- `src/pages/PeptideGenerationPage.tsx`
- `src/components/p33u/RunConsole.tsx`
- `backend/app/routers/pipeline_runs.py`
- `backend/app/services/pipeline_orchestrator.py`

子任务：

1. 表位筛选完成后停在结果页，显示 Top epitopes。
2. 每个表位或整体结果提供“继续生成靶向肽”按钮。
3. 进入模型生成前，显示模型多选：PepMLM、DiffPepBuilder、PepHAR、EvoBind2；PepFlow 如保留则标注历史 artifact parser。
4. 增加“抗平台验证/抗原平台验证”开关；未接通时显示“暂未接通，仅记录选择”。
5. 多模型运行可以先串行触发多个 `/api/v1/p33u/run/model`，记录每个 job_id/run_id。

验收：

- 可以只跑表位筛选，不强制继续。
- 可以选择 1 个或多个模型生成。
- 每个模型结果独立显示来源模型和运行编号。
- 不可用模型不出现在演示界面。

### P1-4：最终排序页展示完整评分拆解

涉及文件：

- `src/components/p33t/P33TResultCenter.tsx`
- `src/pages/FinalRankingPage.tsx`
- `src/lib/finalRankingApi.ts`
- `backend/app/routers/p33t.py`
- `backend/app/routers/p33u.py`
- `backend/app/services/pipeline_orchestrator.py`

展示要求：

A. 6 层表位筛选评分：

- 长度
- 电荷
- 疏水性
- 抗原性或表位相关评分
- 可及性或结构相关评分
- 综合表位评分

B. 5 层靶向肽生成评分：

- 生成模型来源
- 靶向评分
- 毒性/安全性预测
- 稳定性或理化性质评分
- 综合排序评分

子任务：

1. 从 `pipeline_runs` step summary 读取表位字段：`length/net_charge/hydrophobic_ratio/priority_score/surface_accessibility`。
2. 从 `p33t` 或 `p33u d26/d30` 读取模型评分字段。
3. 为每条候选建立 `score_breakdown` 面板。
4. 缺失字段统一显示“未计算”，不要填 0。
5. 支持 100 条结果分页或虚拟列表。

验收：

- 最终排序表不能只显示序列。
- 每条候选能展开评分拆解。
- 后端返回 100 条时前端不卡死、不遮挡数值。

## 4. 建议实施顺序

1. P0-0：创建修复分支和基线报告。
2. P0-1：固定 golden demo，并跑通 3 次。
3. P0-2：修模型切换和旧结果残留。
4. P0-3：统一 run/candidate 追溯字段。
5. P0-4：处理结果中心认证和路径问题。
6. P1-1：隐藏侧栏非演示入口。
7. P1-2：汉化核心路径。
8. P1-3：表位筛选后继续生成。
9. P1-4：最终评分拆解。
10. 全量验收测试和最终报告。

## 5. 验收测试清单

| 编号 | 测试项 | 输入/操作 | 预期结果 | 状态 |
|---|---|---|---|---|
| T01 | 后端健康检查 | `GET /health` 和 `/api/health` | 200 healthy | 待执行于修复后 |
| T02 | 前端构建 | `npm run build` | 构建通过 | 待执行 |
| T03 | golden demo 运行 1 | P11311 默认参数 | 成功，有 run_id | 待执行 |
| T04 | golden demo 运行 2 | 同上 | 成功，有新 run_id | 待执行 |
| T05 | golden demo 运行 3 | 同上 | 成功，有新 run_id | 待执行 |
| T06 | 模型切换 PepMLM -> PepHAR | 分别运行 | run_id/source_model 改变 | 待执行 |
| T07 | 单模型运行 | 只选 PepMLM | 返回候选和来源模型 | 待执行 |
| T08 | 多模型运行 | PepMLM + PepHAR + EvoBind2 | 多个 job/run 可追踪 | 待执行 |
| T09 | 表位筛选单独运行 | 只跑筛选 | 停在表位结果页 | 待执行 |
| T10 | 表位后继续生成 | 点击继续并选择模型 | 进入模型生成并记录 run_id | 待执行 |
| T11 | 最终排序字段展示 | 打开结果页 | 显示 run_id、来源模型、评分拆解 | 待执行 |
| T12 | 页面刷新追溯 | 刷新结果页 | 通过 run_id 恢复同一结果 | 待执行 |
| T13 | 错误参数 | 非法序列/过大 top_k | 明确错误提示，无假动画 | 待执行 |
| T14 | 未登录结果页 | 清除登录态访问 P33T | 中文提示登录，不显示 mock | 待执行 |

## 6. 修改文件建议清单

优先改这些文件：

- `src/components/platform/Sidebar.tsx`
- `src/pages/HomePage.tsx`
- `src/pages/TargetProteinInputPage.tsx`
- `src/pages/EpitopeScreeningPage.tsx`
- `src/pages/PeptideGenerationPage.tsx`
- `src/pages/FinalRankingPage.tsx`
- `src/components/p33u/RunConsole.tsx`
- `src/components/p33t/P33TResultCenter.tsx`
- `src/lib/api/p33u.ts`
- `src/lib/api/pipelineRuns.ts`
- `src/lib/api/p33t.ts`
- `backend/app/routers/p33u.py`
- `backend/app/routers/pipeline_runs.py`
- `backend/app/services/pipeline_orchestrator.py`

尽量不要改这些：

- 模型底层 adapter 大逻辑
- `/mnt/sdb` 模型产物目录
- 历史报告和 data_dev 大量运行产物
- 旧 8001 服务目录
- PPFlow 相关授权/执行逻辑

## 7. 可演示性判断

当前状态：不能直接用于正式录制。

原因：

1. 菜单和入口过多，老师难以判断主流程。
2. 结果中心和旧页面仍有 mock/localStorage fallback。
3. P33U 控制台偏工程调试，不是汇报型流程。
4. 模型状态说明复杂，PepFlow/PPFlow/backlog 容易被误解为可运行模型。
5. P33T 结果中心需要登录态，演示前需固定账号和加载路径。

修完 P0 后：可进行内部彩排录屏。  
修完 P0 + P1 后：可用于 7 月下旬向老师当面演示，但仍应称为“AI 辅助靶向肽设计与候选筛选原型系统”。

## 8. 第一轮执行建议

第一轮只做 3 件事：

1. 固定 golden demo 并跑 3 次。
2. 修模型切换结果追溯，确保来源模型和 run_id 明确。
3. 把演示入口收敛到一个中文主页面，隐藏历史干扰项。

完成后再做评分拆解和多模型批量运行。