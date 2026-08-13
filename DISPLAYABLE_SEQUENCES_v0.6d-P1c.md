# v0.6d-P1c 当前可展示序列清单

**导出日期**: 2026-04-28  

**服务器**: 192.168.31.218:8088  

**版本**: v0.6d-P1c Demo-compatible  


---


## 1. Peptide Filter Pipeline 可展示候选肽

**说明**：以下序列来自 Demo-compatible `/api/predict`，为 **OprF 历史预计算示例数据**，不是实时 BepiPred3/ESM 推理结果。所有肽段已按 priority_score 降序排列。


| Rank | 序列 | 长度 | 净电荷 (pH 7.4) | GRAVY | pI | Priority Score | Disulfide 风险 | 排名原因 |
|---:|:---|---:|---:|---:|---:|---:|:---|:---|
| 1 | `NPRRH` | 5 | 0.761 | -3.46 | 12.0 | 39.1112 | none | 无明显二硫键优势，但疏水性表现较好 |
| 2 | `GHVTKSAHT` | 9 | 1.7235 | -0.7667 | 8.7642 | 37.7844 | none | 无明显二硫键优势，但电荷表现较好 |
| 3 | `NPRRHP` | 6 | 0.761 | -3.15 | 12.0 | 37.0916 | none | 无明显二硫键优势，但疏水性表现较好 |
| 4 | `PRRHP` | 5 | 0.761 | -3.08 | 12.0 | 36.6356 | none | 无明显二硫键优势，但疏水性表现较好 |
| 5 | `RYGNNHR` | 7 | 0.7589 | -2.9857 | 10.835 | 32.8456 | none | 无明显二硫键优势，但疏水性表现较好 |
| 6 | `FNPRRH` | 6 | 0.761 | -2.4167 | 12.0 | 32.3144 | none | 无明显二硫键优势，但疏水性表现较好 |
| 7 | `FNPRRHP` | 7 | 0.761 | -2.3 | 12.0 | 31.5542 | none | 无明显二硫键优势，但疏水性表现较好 |
| 8 | `RYGNNHRG` | 8 | 0.7589 | -2.6625 | 10.835 | 30.7401 | none | 无明显二硫键优势，但疏水性表现较好 |
| 9 | `GNNHR` | 5 | 0.761 | -3.02 | 9.7565 | 30.2338 | none | 无明显二硫键优势，但疏水性表现较好 |
| 10 | `NNHRG` | 5 | 0.761 | -3.02 | 9.7565 | 30.2338 | none | 无明显二硫键优势，但疏水性表现较好 |


**筛选规则说明**：
- 硬筛选：Net Charge > 0，GRAVY < 0，pI 在范围内，Cys 数量可控，Disulfide Risk 不过高
- 软排序权重：Disulfide (0.4) > Charge (0.25) > Hydrophobicity (0.2) > pI (0.15)
- 所有数据为历史 post-screen-ranking 输出，仅用于演示五层筛选流程。

---


## 2. One-click STAMP Demo 三段式序列

**说明**：以下序列为 **STAMP Demo 组装结果**，由最佳 PepMLM 候选肽 + EAAAK 刚性 Linker + P4 AMP  killing domain 拼接而成。状态为 `NOT_EXPERIMENTALLY_VALIDATED`。


| 组件 | 名称 | 氨基酸序列 | 长度 (aa) |
|:---|:---|:---|---:|
| 靶向肽 (Targeting Peptide) | OPRF_0029 | `DATAAAALAALG` | 12 |
| 刚性连接肽 (Linker) | EAAAK | `EAAAK` | 5 |
| 杀菌域 (AMP / Killing Domain) | P4 | `FSRFLRRVRRYRPKISFNLEPFFKF` | 25 |
| **完整 STAMP** | **stamp_oprf_0029** | **`DATAAAALAALG-EAAAK-FSRFLRRVRRYRPKISFNLEPFFKF-NH2`** | **42** |


**架构说明**：
- N-端 [靶向肽] — [EAAAK 刚性 Linker] — [P4 AMP] C-端
- 末端修饰：`-NH2`（C-端酰胺化）
- 靶向肽来源：PepMLM 条件生成，最低 PPL 候选 OPRF_0029
- AMP 来源：优先文库 P4（priority=HIGH，cosmetic preservative screening）

---


## 3. 演示边界与汇报口径

### ✅ 可以展示

- 五层筛选流程界面与候选肽段排序结果
- STAMP 三段式分子组装结果
- PepMLM 靶向肽候选列表
- AMP 优先文库数据

### ❌ 不可宣称

- ~~"BepiPred 3.0 已实时集成"~~ — 当前为预计算示例数据
- ~~"ESM-1b 实时编码已上线"~~ — fair-esm 未安装
- ~~"实验验证数据已产生"~~ — 所有 experimental 字段为 None
- ~~"结构预测评分已计算"~~ — pDockQ/ipTM/pLDDT 为 None
- ~~"MIC/MBC 已测定"~~ — 无湿实验数据

### 推荐演示话术

> "当前展示的是 STAMP 平台的 v0.6d-P1c 演示版本。前端可完整展示从目标蛋白输入到表位筛选、再到肽段生成和 STAMP 嵌合肽组装的全流程界面。其中 STAMP 组装为真实计算逻辑，而表位筛选当前使用预计算的历史示例数据来演示五层过滤与排序效果。真实 BepiPred3/ESM 后端资产已通过审计找回，将在后续版本以 Sidecar 方式接入。"

---

*文档结束*