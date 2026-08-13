# STAMP Platform — Project Context

> 本文件记录项目基本信息、当前功能、路由映射，作为 AI 协作的长期记忆。
> 每次新会话开始时，请先阅读本文件。

---

## 平台全称

**Epitope-guided STAMP / Targeting Peptide Design Platform**
（表位引导的 STAMP / 靶向肽设计平台）

## 版本状态

当前版本：`v0.5-stamp-platform-ui-mvp`
状态：MVP 冻结，前端 UI + Mock 数据完成，等待真实结构数据接入
最后更新：2026-04-28

---

## 核心科研流程

```
Target Protein Input
↓
Epitope & Hotspot Prediction
↓
5-Layer Epitope Screening          ← 筛选"表位"
↓
Recommended Target Epitope
↓
Epitope-conditioned Targeting Peptide Generation  ← "互补"生成，非随机
↓
Targeting Peptide Screening / Optimization        ← 筛选"肽"，区分于上层
↓
Epitope-Peptide Complementarity Scoring
↓
3D Structure Validation            ← 验证肽是否真的结合到筛选出的表位
↓
Final Candidate Ranking
```

---

## 技术栈

| 层级 | 技术 |
|:---|:---|
| 框架 | React 19 + TypeScript 5 |
| 构建 | Vite 7 |
| 样式 | Tailwind CSS 3 |
| 组件库 | shadcn/ui |
| 3D 可视化 | Molstar 5.8.0 |
| 状态管理 | React Hooks（当前）|
| 路由 | React Router v7 |

---

## 关键术语规范

| 术语 | 使用场景 | 禁止替代 |
|:---|:---|:---|
| STAMP | 平台全称、导航、文档 | AMP（旧称）|
| Targeting Peptide | 生成的候选肽 | Peptide（模糊）|
| Epitope | 目标蛋白表位 | Antigen（不准确）|
| Epitope Contact Ratio | 核心验证指标 | Contact Ratio（省略）|
| 5-Layer Epitope Screening | 表位筛选 | 5-Layer Screening（歧义）|
| 5-Layer Peptide Filtering | 肽筛选 | 同上 |

---

## 品牌信息

```
湘湖实验室
XIANGHU LABORATORY
动物疫病疫苗团队
Animal Disease Control and Vaccine Team
```

主色：`#156B98`

---

## 路由映射

| 路由 | 页面组件 | 说明 |
|------|----------|------|
| `/` | `TargetingPeptidePage` | 新平台首页（蓝白科研风格） |
| `/target-protein` | `TargetProteinInputPage` | 目标蛋白输入 |
| `/epitope-screening` | `EpitopeScreeningPage` | 表位预测与筛选 |
| `/peptide-generation` | `PeptideGenerationPage` | 互补肽生成 |
| `/peptide-optimization` | `PeptideOptimizationPage` | 肽优化与筛选 |
| `/structure-validation` | `StructureValidationPage` | 3D 结构验证（门面页） |
| `/final-ranking` | `FinalRankingPage` | 最终候选排序 |
| `/filter` | `PeptideFilterPage` | 旧功能页（肽段筛选流水线） |
| `/demo` | `PeptideFilterPage` | 旧功能页（与 `/filter` 同页） |
| `/structure` | `StructureViewerPage` | 旧功能页（三维结构展示） |

---

## 保留旧功能

| 路由 | 功能 | 状态 |
|:---|:---|:---|
| `/filter` | Legacy Peptide Filter Pipeline | 保留，无新 Layout |
| `/demo` | Legacy Demo Page | 保留，无新 Layout |
| `/structure` | Legacy Structure Viewer | 保留，无新 Layout |
| `/api/predict` | Backend prediction API | 保留，Vite proxy 透传 |

---

## 下一阶段

见 `TODO.md` → `v0.6-real-complex-validation`

---

## 关键文件速查

| 文件 | 作用 |
|------|------|
| `src/App.tsx` | 路由总入口，所有 Route 定义在此 |
| `src/lib/api.ts` | 后端 API 调用封装（`/api/predict`、`/api/health`） |
| `src/lib/structureValidationApi.ts` | 结构验证 API（mock，待接后端） |
| `src/types/platform.ts` | 全平台 TypeScript 类型定义 |
| `src/data/platformMockData.ts` | 全平台 Mock 数据 |
| `tailwind.config.js` | 主题色配置，主色 `#156B98` |
| `docs/STRUCTURE_VALIDATION_REAL_PDB_GUIDE.md` | 真实 PDB 替换指南 |

---

## 项目目录（WSL）

```
/mnt/d/Desktop/靶向肽/github/前端
```

对应 Windows 路径：

```
D:\Desktop\靶向肽\github\前端
```
