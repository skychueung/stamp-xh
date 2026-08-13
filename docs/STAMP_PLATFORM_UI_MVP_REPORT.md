# STAMP Platform UI — MVP 验收报告

> 版本：v0.5-stamp-platform-ui-mvp  
> 日期：2026-04-28  
> 状态：✅ MVP 冻结，文档收口完成

---

## 1. 执行摘要

本项目已将原有 **Peptide Filter Pipeline** 前端，升级为 **Epitope-guided STAMP / Targeting Peptide Design Platform**（表位引导的 STAMP / 靶向肽设计平台）完整科研流程 UI。

本轮升级共新增 **23 个文件**，修改 **3 个文件**，在零破坏旧功能的前提下，完成了 6 个新页面、9 步流程条、3D 结构验证门面页、互补生成模块、以及真实 PDB 替换基础设施。

---

## 2. 9 步科研流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  ① Target Protein Input  →  ② Epitope Prediction  →  ③ 5-Layer Epitope    │
│     Screening  →  ④ Recommended Target Epitope  →  ⑤ AI Targeting Peptide │
│     Generation  →  ⑥ 5-Layer Peptide Filtering  →  ⑦ Epitope-Peptide      │
│     Complementarity  →  ⑧ Structure Prediction & Docking  →  ⑨ Top       │
│     Candidate Targeting Peptides                                           │
└─────────────────────────────────────────────────────────────────────────────┘
```

| 步骤 | 页面 | 核心功能 |
|:---|:---|:---|
| 1 | `/target-protein` | 目标蛋白序列 / UniProt / PDB 输入 |
| 2-4 | `/epitope-screening` | 表位预测、5 层筛选、推荐目标表位 |
| 5 | `/peptide-generation` | 基于表位的互补肽生成、Complementarity Panel |
| 6-7 | `/peptide-optimization` | 靶向肽筛选 / 优化、可开发性过滤 |
| 8 | `/structure-validation` | 3D 复合物验证、Molstar Viewer、Contact Ratio |
| 9 | `/final-ranking` | Top 候选排序、导出决策 |

---

## 3. 页面功能验收清单

### 3.1 `/target-protein`
- [x] Protein Sequence / UniProt ID / PDB CIF 三种输入方式 Tabs
- [x] 蛋白名称、物种、目标类型、序列、感兴趣区域、备注字段
- [x] Target Summary 卡片（Length / TM Helices / Domain Count / Signal Peptide）
- [x] Recommended Checks 卡片
- [x] Load Example / Run Epitope Prediction / Reset 按钮

### 3.2 `/epitope-screening`
- [x] 蛋白线性图（Extracellular Domain / Epitope Hotspot / Functional Site / TM）
- [x] Candidate Epitope Table（17 列，横向滚动）
- [x] 5-Layer Epitope Screening 卡片
- [x] New Critical Indicators 卡片（Surface / Function / Specificity / Disorder / Flexibility）
- [x] Recommended Target Epitope 卡片（Select / View Details / View Epitope in 3D / Surface Exposure Preview）

### 3.3 `/peptide-generation`
- [x] Selected Target Epitope 信息展示
- [x] **Epitope-Peptide Complementarity Panel**（5 项 ScoreBar + 0.87 Pre-score）
- [x] Generation Settings（Model / Count / Length / Charge / Hydrophobicity / Diversity / Temperature / Top-k / Seed）
- [x] Generated Targeting Peptides Table（13 列 + Preview Binding Pose / Send to Structure Validation）
- [x] Epitope-Peptide Design Rules
- [x] Generation Summary

### 3.4 `/peptide-optimization`
- [x] Selected Epitope + Lead Targeting Peptide 双卡片
- [x] Optimization Controls（Strategy / Rounds / Mutation Rate / Weights）
- [x] **Targeting Peptide Screening / Developability Filtering**（5 层基础 + 9 项可开发性）
- [x] Before vs After Optimization 表格
- [x] Top Optimized Peptides 卡片（Validate in 3D / Predict Complex）

### 3.5 `/structure-validation` ⭐ 门面页
- [x] 顶部 6 张指标卡（ipTM / pDockQ / ΔG / Contact Ratio / Contacts / Confidence）
- [x] **20/60/20 三栏布局**
- [x] 中间：**真实 Molstar Complex Viewer**（540px，非 placeholder）
- [x] 四色图例：Target(灰) / Epitope(橙) / Peptide(青) / Contacts(红)
- [x] 8 个交互按钮（Show/Hide/Highlight/Reset/Download/Snapshot）
- [x] **Epitope Binding Validation 判断卡**（Contact Ratio 大数字 + Pass/Warning/Fail）
- [x] **Interface Contact Map**（8 行，4 种接触类型标签）
- [x] **Off-epitope Binding Warning**（自动判断，ratio < 0.75 显示红色横幅）
- [x] Top Validated Complexes 表格（View / Download）

### 3.6 `/final-ranking`
- [x] 顶部统计卡（Total / Passed / Top Score / Recommended）
- [x] Top 1/2/3 卡片（View 3D Complex / Download PDB / Export Snapshot）
- [x] Top Targeting Peptides 表格（20 列完整指标）
- [x] Export & Decision Support（CSV / PDF / Send to Team / Mark for Synthesis）
- [x] Ranking Weights（Epitope / Complementarity / Developability / Specificity / Validation）

---

## 4. 3D 验证页面深度说明

### 4.1 Molstar Complex Viewer
- **组件路径**：`src/components/structure/ComplexMolstarViewer.tsx`
- **技术**：直接操作 Molstar Plugin API（非 placeholder wrapper）
- **暴露接口**：`loadPdbUrl` / `loadPdbData` / `showLayer` / `hideLayer` / `highlightEpitope` / `resetView` / `exportSnapshot`
- **图层颜色**：
  - Target Protein：`#CCCCCC` (cartoon)
  - Selected Epitope：`#F59E0B` (ball-and-stick)
  - Targeting Peptide：`#06B6D4` (ball-and-stick)

### 4.2 Mock PDB
- **路径**：`public/structures/mock_complex.pdb`
- **生成器**：`src/utils/mockPdbGenerator.ts`
- **内容**：Chain A = 21 残基 α-helix（表位 455-465，B-factor=50）；Chain B = 7 残基靶向肽
- **用途**：UI 演示，后续替换为真实 AlphaFold-Multimer 输出

### 4.3 真实 PDB 替换路径
- **指南**：`docs/STRUCTURE_VALIDATION_REAL_PDB_GUIDE.md`
- **API 占位**：`src/lib/structureValidationApi.ts`
- **类型预留**：`src/types/platform.ts` → `StructureValidationData` / `LoadOptions`

---

## 5. 文件清单

### 5.1 新增文件（23 个）

| # | 路径 | 说明 |
|:---|:---|:---|
| 1 | `src/types/platform.ts` | 全平台类型定义 |
| 2 | `src/layouts/PlatformLayout.tsx` | 统一布局（Sidebar + Main + Footer） |
| 3 | `src/components/platform/PipelineProgress.tsx` | 9 步流程条 |
| 4 | `src/components/platform/MetricCard.tsx` | 指标卡片 |
| 5 | `src/components/platform/ScoreBar.tsx` | 评分进度条 |
| 6 | `src/components/platform/InfoBanner.tsx` | 信息横幅 |
| 7 | `src/components/platform/DataTableShell.tsx` | 表格外壳（横向滚动） |
| 8 | `src/components/platform/SectionCard.tsx` | 区块卡片 |
| 9 | `src/components/platform/SequenceBadge.tsx` | 氨基酸序列徽章 |
| 10 | `src/components/platform/StatusPill.tsx` | 状态标签 |
| 11 | `src/components/structure/ComplexMolstarViewer.tsx` | Molstar 复合物查看器 |
| 12 | `src/components/structure/InterfaceContactMap.tsx` | 界面接触地图 |
| 13 | `src/components/structure/EpitopeBindingValidationCard.tsx` | 表位结合验证卡 |
| 14 | `src/pages/TargetProteinInputPage.tsx` | 目标蛋白输入页 |
| 15 | `src/pages/EpitopeScreeningPage.tsx` | 表位筛选页 |
| 16 | `src/pages/PeptideGenerationPage.tsx` | 肽生成页 |
| 17 | `src/pages/PeptideOptimizationPage.tsx` | 肽优化页 |
| 18 | `src/pages/StructureValidationPage.tsx` | 结构验证页 |
| 19 | `src/pages/FinalRankingPage.tsx` | 最终排序页 |
| 20 | `src/lib/structureValidationApi.ts` | 结构验证 API（mock） |
| 21 | `docs/STRUCTURE_VALIDATION_REAL_PDB_GUIDE.md` | 真实 PDB 替换指南 |
| 22 | `src/data/platformMockData.ts` | 全平台 Mock 数据 |
| 23 | `src/utils/mockPdbGenerator.ts` | Mock PDB 生成器 |

### 5.2 修改文件（3 个）

| 路径 | 修改内容 |
|:---|:---|
| `src/App.tsx` | 新增 6 条路由，新旧 Layout 隔离 |
| `src/components/platform/Sidebar.tsx` | 导航菜单更新为 12 项 |
| `package.json` | 版本标记为 v0.5.0 |

---

## 6. 截图存档

截图存放于 `docs/report_screenshots/`：

| 页面 | 文件 | 分辨率 |
|:---|:---|:---|
| `/structure-validation` | `structure-validation.png` | 1814×2675 |
| `/peptide-generation` | `peptide-generation.png` | 1784×4399 |
| `/peptide-optimization` | `peptide-optimization.png` | 1784×3474 |
| `/final-ranking` | `final-ranking.png` | 1784×1366 |
| `/epitope-screening` | `epitope-screening.png` | 1784×4190 |

---

## 7. 已知问题

| 问题 | 影响 | 优先级 |
|:---|:---|:---|
| molstar chunk size > 500KB warning | 不影响构建和运行 | 低 |
| a11y snapshot 在 Molstar 页面超时 | screenshot 工具正常，a11y snapshot 作为替代验证 | 低 |
| 右侧 20% 面板中 Interface Contact Map 被截断 | 完整版在页面下方单独展示，不影响功能 | 低 |

---

## 8. 下一阶段

见 `TODO.md` → **v0.6-real-complex-validation**

核心目标：将 Mock complex structure 替换为真实 AlphaFold-Multimer / ColabFold 预测结果。

关键任务：
1. 真实目标蛋白 PDB 接入
2. 真实靶向肽序列接入
3. AlphaFold-Multimer 复合物预测
4. 结构质量过滤（ipTM > 0.7, pDockQ > 0.23）
5. 界面接触分析
6. Epitope Contact Ratio 真实计算
7. 界面能量计算（FoldX / Rosetta）
8. 后端 API 实现
9. 前端 mock → 真实 API 替换

---

*报告生成：2026-04-28*
