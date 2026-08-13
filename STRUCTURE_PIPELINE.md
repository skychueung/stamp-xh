# Peptide Frontend — 结构流水线文档

> 记录候选肽三维结构从预测到前端展示的完整数据流水线。

---

## 流水线总览

```
候选肽序列
    ↓
ColabFold / AlphaFold2
    ↓
PDB 文件 + pLDDT 评分
    ↓
DSSP / STRIDE 二级结构解析
    ↓
helix / sheet / coil 分类
    ↓
structureMetadata.ts（或 structure-metadata.json）
    ↓
Molstar 前端展示（/structure 页面）
```

---

## 各阶段说明

### 1. 候选肽序列输入

- 来源：`/api/predict` 返回的 `ranked_peptides` 中的 `sequence`
- 格式：单字母氨基酸序列，如 `ACDEFGHIKLMNPQRSTVWY`

### 2. 结构预测（ColabFold / AlphaFold2）

- **ColabFold**（推荐）：本地或云端运行，输出 PDB 格式
- **AlphaFold2**：官方实现，精度更高但资源消耗大
- 输出：`.pdb` 文件 + 每个残基的 `pLDDT` 置信度评分（0–100）

### 3. 二级结构解析（DSSP / STRIDE）

- **DSSP**（首选）：`mkdssp` 命令行工具，从 PDB 提取二级结构
- **STRIDE**（备选）：替代方案，输出格式类似
- 输出：每个残基的二级结构类型
  - `H` = α-helix（螺旋）
  - `E` = β-sheet（折叠）
  - `C` = coil / 其他（无规卷曲）

### 4. 元数据生成

将解析结果写入前端可消费的元数据文件：

```typescript
// src/data/structureMetadata.ts
export interface StructureMetadata {
  peptideId: string;
  sequence: string;
  pdbUrl: string;           // PDB 文件路径或 URL
  plddtScores: number[];    // 每残基 pLDDT，长度 = sequence.length
  secondaryStructure: ("H" | "E" | "C")[];  // 每残基二级结构
  source: "colabfold" | "alphafold2";
  predictionDate: string;   // ISO 日期
}
```

或等效 JSON 格式 `structure-metadata.json`。

### 5. 前端展示（Molstar）

- 使用 `molstar` NPM 包嵌入 3D 结构查看器
- 加载 PDB 数据，按二级结构着色：
  - 螺旋（H）→ 蓝色
  - 折叠（E）→ 黄色
  - 卷曲（C）→ 灰色
- pLDDT 以 B-factor 或自定义着色方案展示

---

## 当前状态

| 阶段 | 状态 | 备注 |
|------|------|------|
| ColabFold 预测 | ⚠️ 占位 | 使用示例 PDB，待替换为真实预测结果 |
| DSSP 解析 | ✅ 完成 | `mkdssp` v4.2.2 已安装并验证可用 |
| 元数据生成 | ⏳ 待编写 | `analyze_dssp.py` 待开发 |
| Molstar 展示 | ✅ 完成 | `/structure` 页面已可展示占位 PDB |

---

## 待办事项

详见 `TODO.md`：

1. WSL 安装 DSSP ✅
2. 用真实 ColabFold PDB 替换占位 PDB
3. 编写 `analyze_dssp.py`
4. 自动生成 `structureMetadata.ts` 或 `structure-metadata.json`
5. `rose-four.html` 改造成 `LoadingScreen`
6. 后续接入真实 Linker / STAMP 计算逻辑

---

## 相关文件

| 文件 | 作用 |
|------|------|
| `src/pages/StructureViewerPage.tsx` | Molstar 查看器页面 |
| `src/data/structureMetadata.ts` | 结构元数据（待创建） |
| `public/structures/` | PDB 与 DSSP 文件存放目录 |
| `scripts/analyze_dssp.py` | DSSP 解析脚本（待创建） |

---

*最后更新：2026-04-27*
