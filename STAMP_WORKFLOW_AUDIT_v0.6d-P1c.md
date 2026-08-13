# STAMP 平台工作流审计报告

**审计日期**: 2026-04-30  
**审计执行**: Hermes Agent (via stamp-platform Skill)  
**审计复核**: Hermes Agent  
**项目路径**: `D:\Desktop\靶向肽\github\前端\` (WSL: `/mnt/d/Desktop/靶向肽/github/前端/`)  
**平台版本**: v0.6d-P1c  
**服务器**: 192.168.31.218:8088 (amp-xh.cn)  
**审计标准**: STAMP Platform Skill v1.0.0 — GO/NO-GO Gates 1–5

---

## 1. 执行摘要

| 项目 | 结论 |
|------|------|
| **整体 GO/NO-GO** | ⚠️ **CONDITIONAL GO** — 演示兼容版可用，真实科学计算后端未完成 |
| **关键发现** | 1. PepMLM-650M GPU 生成 ✅ 真实跑通；2. `/api/predict` 为预计算 DEMO 数据，非实时 BepiPred3；3. 结构验证全为 MOCK_PLACEHOLDER；4. STAMP 组装后端 ✅ 真实可用 |
| **风险等级** | **MEDIUM-HIGH** — 演示数据与真实计算界限清晰，但结构验证和实验验证完全缺失 |

---

## 2. 9 步流水线覆盖审计

| Step | 模块 | 状态 | 数据标记 | 审计结论 | 备注 |
|:----:|------|:----:|:--------:|:---------|------|
| 1 | **Target Protein Input** | ⚠️ | `DEMO_COMPATIBLE` | 前端界面可用，但输入后无真实 UniProt/PDB 解析 | 使用 SARS-CoV-2 Spike 作为 mock 示例 |
| 2 | **Epitope & Hotspot Prediction** | ❌ | `MOCK_PLACEHOLDER` | **未接入真实 BepiPred3 / ESM** | `/api/predict` 返回预计算数据，非实时推理 |
| 3 | **5-Layer Epitope Screening** | ⚠️ | `DEMO_COMPATIBLE` | 筛选逻辑代码存在，但基于预计算数据 | 5 层指标展示正确，数据源为历史 ranked_peptides |
| 4 | **Recommended Target Epitope** | ⚠️ | `DEMO_COMPATIBLE` | 推荐界面可用，非真实 BepiPred3 输出 | 展示的是预筛选后的示例数据 |
| 5 | **PepMLM Target-conditioned Generation** | ✅ | `REAL_MODEL_OUTPUT` + `NOT_EXPERIMENTALLY_VALIDATED` | **真实 GPU 运行完成** | 1000 候选，61.4s，2×RTX 4090，Ala 37.5% 偏差已记录 |
| 6 | **Peptide Screening (5-Layer + 9 Metrics)** | ✅ | `REAL_MODEL_OUTPUT` | **真实筛选完成** | Pass 659 / Warning 340 / Fail 0 |
| 7 | **Complementarity Scoring** | ⚠️ | `DEMO_COMPATIBLE` | 启发式评分，非真实对接 | 前端展示互补性面板，基于电荷/疏水性模式 |
| 8 | **3D Structure Validation** | ❌ | `MOCK_PLACEHOLDER` | **完全未实现真实后端** | `structureValidationApi.ts` 为纯 mock；无 AlphaFold-Multimer 后端 |
| 9 | **Final Candidate Ranking** | ⚠️ | `DEMO_COMPATIBLE` | 排名界面可用，基于预计算/静态数据 | 无真实结构验证权重参与 |

**状态图例**: ✅ 已实现 | ⚠️ 部分实现 / Demo 兼容 | ❌ 未实现

---

## 3. 模块真实性详细审计

### 3.1 Step 1: Target Protein Input

| 检查项 | 结果 |
|--------|------|
| 前端输入界面 | ✅ 可用 (`/target-protein`) |
| 真实 UniProt 下载 | ❌ 未实现 |
| 真实 PDB 解析 | ❌ 未实现 |
| 序列验证 (标准氨基酸) | ⚠️ 前端有基础验证，无后端严格校验 |
| **数据标记** | `DEMO_COMPATIBLE` |

**审计结论**: 界面层完成，无真实数据源接入。用户输入的序列仅用于前端展示和传递给 `/api/predict` 的 DEMO 响应。

---

### 3.2 Step 2: Epitope & Hotspot Prediction (BepiPred3 / ESM)

| 检查项 | 结果 |
|--------|------|
| BepiPred3 模型文件 (`.pt`) | ❌ 未找到 |
| ESM-2 / fair-esm 安装 | ❌ 未在 requirements.txt 中 |
| 实时推理 API | ❌ 未实现 |
| Sidecar (127.0.0.1:5001) 代码 | ✅ 存在 (`legacy_predict.py`) |
| Sidecar 实际运行 | ❌ 未启动 (默认 `_PREDICT_MODE = "demo"`) |
| `/api/predict` 返回数据 | ⚠️ 预计算历史数据 (10 条 ranked peptides) |
| **数据标记** | `DEMO_COMPATIBLE` / `MOCK_PLACEHOLDER` |

**关键证据**:
```python
# backend/app/routers/legacy_predict.py 第 30 行
_PREDICT_MODE: str = "demo"  # 默认 demo 模式，非 sidecar
```

**审计结论**: BepiPred3 / ESM 推理能力**代码层面保留**（Sidecar 代理逻辑完整），但**当前未启用**。所有 `/api/predict` 返回的数据均为预计算的历史 post-screen-ranking 输出，标记为 `DEMO_COMPATIBLE`。这是 v0.6d-P1c 的**设计决策**（演示稳定性优先），但必须在汇报中明确区分。

---

### 3.3 Step 3–4: 5-Layer Epitope Screening & Recommended Epitope

| 检查项 | 结果 |
|--------|------|
| 5 层筛选逻辑代码 | ✅ 存在 (前端 + 后端) |
| 表面暴露性 (RSA) | ⚠️ 基于预计算数据 |
| 功能相关性 | ⚠️ 基于预计算数据 |
| 特异性 (BLAST) | ❌ 未实现 |
| 紊乱度/柔性 | ⚠️ 基于预计算数据 |
| 保守性 | ⚠️ 基于预计算数据 |
| **数据标记** | `DEMO_COMPATIBLE` |

**审计结论**: 筛选框架完整，但数据源为预计算示例。无真实 BLASTp 宿主蛋白组比对。

---

### 3.4 Step 5: PepMLM Target-conditioned Generation ⭐

| 检查项 | 结果 |
|--------|------|
| 生成脚本 | ✅ `generate_oprf_1000.py` (11,531 bytes) |
| GPU 运行日志 | ✅ `PEPMLM_GPU_GENERATION_REPORT.md` |
| 模型加载 | ✅ TianlaiChen/PepMLM-650M，本地缓存 |
| 生成模式 | ✅ `OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING` |
| 解码策略 | ✅ `top_k_sampling_on_full_mask` |
| 目标序列设置 | ✅ Pseudomonas_OprF (61 aa) |
| 输出文件 | ✅ 1000/100/50 候选 JSON + CSV |
| 去重验证 | ✅ 1000 生成 → 999 唯一 |
| 耗时 | ✅ 61.4 秒 |
| **数据标记** | `REAL_MODEL_OUTPUT` + `NOT_EXPERIMENTALLY_VALIDATED` |

**已知偏差审计**:

| 偏差项 | 实测值 | Skill 阈值 | 状态 |
|--------|--------|:----------:|:----:|
| Ala 占比 | 37.5% | > 25% | 🔴 **超标** |
| GRAVY > 0.5 | 38% (19/50) | > 30% | 🔴 **超标** |
| 3-aa 前缀多样性 | 20 / 50 | << 总数 | 🔴 **偏低** |

**审计结论**: PepMLM 生成**真实完成**，所有输出正确标记。但存在已知的 650M 模型偏差（Ala 过表达、GRAVY 漂移、低多样性），已在报告中记录。**可用于 BepiPred3 输入池或进一步筛选，不可直接用于展示/结构验证。**

---

### 3.5 Step 6: Peptide Screening (5-Layer + 9 Metrics)

| 检查项 | 结果 |
|--------|------|
| 5 层基础筛选 | ✅ 代码实现 |
| 9 项可开发性指标 | ✅ 代码实现 |
| Pass/Warning/Fail 分级 | ✅ 659 / 340 / 0 |
| 优先级评分公式 | ✅ 存在 |
| **数据标记** | `REAL_MODEL_OUTPUT` |

**审计结论**: 筛选逻辑**真实可用**，基于 PepMLM 真实输出计算。但 `pI`、`GRAVY-full`、`hydrophobicity_fraction` 等部分指标在 STAMP 组装时设为 `None`（v0.6d 已知限制）。

---

### 3.6 Step 7: Complementarity Scoring

| 检查项 | 结果 |
|--------|------|
| 互补性评分面板 | ✅ 前端展示 |
| 静电互补 | ⚠️ 启发式（电荷符号相反 = 高分） |
| 疏水性互补 | ⚠️ 启发式 |
| 形状互补 | ❌ 无结构数据 |
| 序列反平行匹配 | ⚠️ 启发式 |
| 预测结合评分 (ΔG) | ❌ 无对接软件 |
| **数据标记** | `DEMO_COMPATIBLE` |

**审计结论**: 互补性评分为**启发式近似**，非真实分子对接结果。必须在汇报中明确说明。

---

### 3.7 Step 8: 3D Structure Validation ❌

| 检查项 | 结果 |
|--------|------|
| AlphaFold-Multimer 后端 | ❌ 未实现 |
| ColabFold 输出目录 | ❌ `colabfold_output/` 为空 |
| ipTM 计算 | ❌ 无 |
| pDockQ 计算 | ❌ 无 |
| Epitope Contact Ratio | ❌ 无 |
| 结构验证 API | ❌ 纯 mock (`structureValidationApi.ts`) |
| mock_complex.pdb | ⚠️ 存在，标记为 mock |
| 真实 AMP 单体结构 | ⚠️ 102 个 `.cif` 文件存在 (`real_amp_monomers/`) |
| **数据标记** | `MOCK_PLACEHOLDER` |

**关键证据**:
```typescript
// src/lib/structureValidationApi.ts 第 6-9 行
/**
 * Structure Validation API 返回的完整结果。
 * 当前为 mock 实现，后续替换为真实后端调用。
 */

// 第 52-81 行: 返回固定 mock 数据，包括 ipTM=0.87, pDockQ=0.78 (虚构值)
```

**审计结论**: 结构验证为**完全未实现的真实后端**。`structureValidationApi.ts` 明确标注为 "mock 实现"，返回的 ipTM/pDockQ/接触残基均为**硬编码的虚构值**。`real_amp_monomers/` 目录有 102 个 `.cif` 文件，但无证据表明它们来自真实的 AlphaFold 运行（无 `ranking_debug.json`，无 `iptm` 文件）。

**⚠️ 严重警告**: 如果任何汇报声称 "结构验证已完成" 或 "ipTM/pDockQ 已计算"，将触发 **NO-GO Gate 5**。

---

### 3.8 Step 9: Final Candidate Ranking

| 检查项 | 结果 |
|--------|------|
| 排名界面 | ✅ 前端可用 |
| 加权评分公式 | ⚠️ 代码存在，但结构验证权重为 0（因无真实数据） |
| 候选列表展示 | ⚠️ 基于静态/预计算数据 |
| **数据标记** | `DEMO_COMPATIBLE` |

**审计结论**: 排名框架可用，但缺乏真实结构验证和实验验证数据支撑。当前排名主要基于可开发性评分和启发式互补性。

---

## 4. 数据真实性标记审计

### 4.1 标记使用合规性

| 标记 | 使用位置 | 合规性 |
|------|----------|:------:|
| `REAL_MODEL_OUTPUT` | PepMLM 生成报告、GPU 日志 | ✅ 正确 |
| `DEMO_COMPATIBLE` | `/api/predict` 响应、`/filter` 页面 | ✅ 正确 |
| `MOCK_PLACEHOLDER` | 结构验证 API、未实现功能 | ✅ 正确 |
| `NOT_EXPERIMENTALLY_VALIDATED` | 所有候选肽、STAMP 组装输出 | ✅ 正确 |
| `LITERATURE_BASED` | 目标蛋白示例 (SARS-CoV-2 Spike) | ✅ 正确 |

### 4.2 禁止行为检查

| 检查项 | 结果 |
|--------|------|
| 伪造 MIC 值 | ✅ 未发现 |
| 伪造 ΔG / 结合亲和力 | ✅ 未发现 |
| 伪造 ipTM / pDockQ / pLDDT | ✅ 未发现（但 mock 数据存在，已标记） |
| 将 DEMO 数据伪装为实验验证 | ✅ 未发现 |
| 移除 `NOT_EXPERIMENTALLY_VALIDATED` 标签 | ✅ 未发现 |

**审计结论**: 数据真实性标记体系**执行良好**。所有 mock/demo 数据均有明确标签，无伪造实验数据行为。

---

## 5. GO / NO-GO 审计结论

### 5.1 逐条 Gate 审计

| Gate | 规则 | 审计结果 | 状态 |
|:----:|------|----------|:----:|
| **1** | 禁止伪造实验数据 | 未发现伪造 MIC/ΔG/ipTM/pDockQ | ✅ **PASS** |
| **2** | Mock 数据必须明确标记 | 所有 mock/demo 均有 `DEMO_COMPATIBLE`/`MOCK_PLACEHOLDER` | ✅ **PASS** |
| **3** | 模型运行日志强制要求 | PepMLM 有完整 GPU 日志；BepiPred3 未运行（合理） | ✅ **PASS** |
| **4** | PepMLM 输出审计 | Ala 37.5% 超标已记录；GRAVY 38% 超标已记录；多样性 20/50 偏低已记录 | ⚠️ **PASS WITH WARNINGS** |
| **5** | 结构验证审计 | 完全无真实结构验证；mock ipTM/pDockQ 已明确标记 | ❌ **NO-GO FOR STRUCTURE CLAIMS** |

### 5.2 综合判定

| 场景 | 判定 | 理由 |
|------|:----:|------|
| **前端演示 / 界面验收** | ✅ **GO** | v0.6d-P1c 演示兼容版功能完整，服务稳定 |
| **PepMLM 候选库生成** | ✅ **GO** | 真实 GPU 运行，输出正确标记，可用于下游筛选 |
| **STAMP 嵌合肽组装** | ✅ **GO** | 后端真实计算，EAAAK 连接逻辑正确，无伪造数据 |
| **表位预测 (BepiPred3)** | ❌ **NO-GO** | 未接入真实模型，所有输出为预计算 DEMO 数据 |
| **结构验证 (AlphaFold-Multimer)** | ❌ **NO-GO** | 完全未实现，所有指标为 MOCK |
| **实验验证 (MIC/溶血)** | ❌ **NO-GO** | 无任何湿实验数据 |
| **整体科学声明** | ⚠️ **CONDITIONAL GO** | 仅可声明"演示兼容版可用"，不可声明"真实计算流水线完成" |

---

## 6. 关键发现与风险

### 6.1 高风险项

1. **结构验证完全缺失**: Step 8 是 STAMP 平台的核心科学断言（"肽段与表位在 3D 空间中结合"），但当前无任何真实结构预测能力。mock 数据中的 ipTM=0.87、pDockQ=0.78 为**虚构值**，若被误用将构成科学不端。

2. **BepiPred3 未接入**: 表位预测是流水线起点，当前使用预计算数据。虽然 Sidecar 代理代码保留，但默认未启用。

3. **PepMLM 模型偏差**: Ala 37.5%（vs 自然 7.5%）、GRAVY>0.5 占 38%、低多样性。若直接用于展示而不加警示，可能误导用户。

### 6.2 中风险项

1. **互补性评分为启发式**: 非真实对接结果，但前端展示可能让用户误以为是预测结合亲和力。

2. **部分生物物理指标为 None**: STAMP 组装时 `pI`、`GRAVY-full`、`hydrophobicity_fraction` 未计算。

### 6.3 低风险项

1. **DEMO 标注清晰**: 所有演示数据均有明确 `DEMO_COMPATIBLE` 和 `NOT_EXPERIMENTALLY_VALIDATED` 标记。
2. **汇报口径文档化**: `SEAL_v0.6d-P1c_FINAL.md` 明确列出了"可以说的"和"不可以说的"。

---

## 7. 下一步行动建议

### 7.1 立即行动（阻塞性）

| 优先级 | 行动 | 负责人 | 验收标准 |
|:------:|------|--------|----------|
| P0 | **结构验证后端实现** | KimiCode + Hermes | AlphaFold-Multimer 或 ColabFold 后端接入；真实 `ranked_0.pdb` + `ranking_debug.json` 输出；ipTM/pDockQ 真实计算 |
| P0 | **BepiPred3 Sidecar 启用** | KimiCode | `_PREDICT_MODE = "sidecar"` 可切换；127.0.0.1:5001 真实响应；失败时透明降级到 demo |
| P1 | **PepMLM 偏差缓解** | Hermes 审计 | 生成时增加多样性约束（top_k ≥ 10）；筛选时 Ala% > 25% 自动降级；GRAVY > 0.5 加警示 |

### 7.2 短期行动（1–2 周）

| 优先级 | 行动 | 负责人 |
|:------:|------|--------|
| P1 | 真实 UniProt/PDB 解析后端 | KimiCode |
| P1 | BLASTp 宿主蛋白组比对 | KimiCode |
| P2 | 互补性评分对接集成 (AutoDock Vina / HADDOCK) | KimiCode |
| P2 | 完整生物物理指标计算 (pI, GRAVY-full) | KimiCode |

### 7.3 中期行动（1–2 月）

| 优先级 | 行动 | 负责人 |
|:------:|------|--------|
| P2 | 湿实验验证设计 (MIC, 溶血, 细胞毒性) | 实验团队 |
| P2 | AMPGen 集成 | KimiCode |
| P3 | ESM-2 conditioned 生成探索 | 研究团队 |

---

## 8. 汇报口径（审计后修订版）

### ✅ 可以说的

> "STAMP 平台 v0.6d-P1c 演示兼容版已部署，前端可完整展示从目标蛋白输入 → 表位筛选 → 肽段生成 → STAMP 组装的全流程界面。PepMLM-650M GPU 生成已真实跑通（1000 候选，61.4s）。STAMP 嵌合肽组装后端为真实计算。所有数据均标记 `NOT_EXPERIMENTALLY_VALIDATED` 或 `DEMO_COMPATIBLE`。"

### ❌ 不可以说的

> ~~"真实 BepiPred3 已集成并实时运行"~~  
> ~~"结构验证已完成，ipTM/pDockQ 已计算"~~  
> ~~"分子对接评分已得出"~~  
> ~~"候选肽已通过实验验证"~~  
> ~~"PepMLM 输出可直接用于临床候选"~~（Ala 偏差未解决前）

### 推荐话术

> "当前为 v0.6d-P1c 演示兼容版本，核心亮点是 PepMLM 真实 GPU 生成和 STAMP 后端真实组装。表位筛选和结构验证为演示数据，用于流程展示。真实 BepiPred3 / ESM Sidecar 代码已保留，结构验证后端是下一个优先里程碑。所有输出均带有科学严谨性标记。"

---

## 9. 关键文件证据清单

| 文件路径 | 用途 | 审计状态 |
|----------|------|----------|
| `pepmlm_oprf_1000_candidates.json` | PepMLM 真实生成输出 | ✅ 真实，标记正确 |
| `PEPMLM_GPU_GENERATION_REPORT.md` | GPU 运行日志 | ✅ 完整，包含偏差记录 |
| `backend/app/routers/legacy_predict.py` | `/api/predict` 路由 | ⚠️ 默认 demo 模式，sidecar 代码保留 |
| `backend/app/routers/stamp.py` | STAMP 组装 API | ✅ 真实计算，无伪造数据 |
| `backend/app/routers/pepmlm.py` | PepMLM 候选查询 API | ✅ 真实数据加载 |
| `src/lib/structureValidationApi.ts` | 结构验证 API | ❌ 纯 mock，已明确标注 |
| `src/data/platformMockData.ts` | 前端 mock 数据 | ✅ 明确为 mock |
| `SEAL_v0.6d-P1c_FINAL.md` | 封口文档 | ✅ 明确区分 demo/real |
| `public/structures/mock_complex.pdb` | Mock 复合物结构 | ✅ 文件名含 "mock" |
| `public/structures/real_amp_monomers/` | AMP 单体结构 | ⚠️ 102 个 .cif，来源待验证 |
| `TODO.md` | 开发路线图 | ✅ v0.6 任务 27.7% 完成 |

---

## 10. 审计签核

| 角色 | 签核 | 日期 |
|------|:----:|------|
| Hermes 审计 | ✅ | 2026-04-30 |
| 数据真实性 | ✅ | 无伪造发现 |
| 科学严谨性 | ⚠️ | 结构验证缺失，需优先补齐 |
| 汇报口径合规 | ✅ | 与 SEAL 文档一致 |

---

*本报告由 Hermes Agent 根据 stamp-platform Skill v1.0.0 自动生成。所有结论基于文件系统审计，未运行湿实验验证。*
