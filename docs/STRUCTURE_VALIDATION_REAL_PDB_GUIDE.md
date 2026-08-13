# Structure Validation — Real PDB Replacement Guide

## 1. PDB 文件存放位置

真实 AlphaFold-Multimer / ColabFold 输出的复合物 PDB 文件应放入：

```
public/structures/
├── mock_complex.pdb       # 当前演示用（可保留作为 fallback）
├── real_complex_001.pdb   # 真实复合物 1
├── real_complex_002.pdb   # 真实复合物 2
└── ...
```

> 放入 `public/` 目录后，Vite 会在构建时自动复制到 `dist/structures/`，前端通过 `/structures/<filename>` 直接访问。

## 2. 前端数据修改点

修改文件：`src/pages/StructureValidationPage.tsx`

### 2.1 复合物 PDB URL

```tsx
<ComplexMolstarViewer
  ref={viewerRef}
  complexPdbUrl="/structures/real_complex_001.pdb"  // ← 修改这里
  targetChainId={mockComplexInfo.targetChainId}     // ← 确认链 ID
  peptideChainId={mockComplexInfo.peptideChainId}   // ← 确认链 ID
  epitopeResidueRange={{ start: 455, end: 465 }}    // ← 确认残基编号
/>
```

### 2.2 结构验证数据

修改 `src/data/platformMockData.ts` 中的以下字段：

| 字段 | 含义 | 来源 |
|------|------|------|
| `complexPdbUrl` | 复合物 PDB 路径 | AlphaFold-Multimer / ColabFold 输出 |
| `targetChainId` | 目标蛋白链 ID | PDB 文件中的 `auth_asym_id` |
| `peptideChainId` | 靶向肽链 ID | PDB 文件中的 `auth_asym_id` |
| `epitopeResidueRange.start` | 表位起始残基编号 | UniProt / PDB 对应编号 |
| `epitopeResidueRange.end` | 表位结束残基编号 | UniProt / PDB 对应编号 |
| `contactResidues` | 界面接触残基对 | FoldX / PyMOL / ChimeraX 分析 |
| `interfaceMetrics.ipTM` | AlphaFold-Multimer 置信度 | AlphaFold 输出 `ranked_0.pdb` 的 JSON |
| `interfaceMetrics.pDockQ` | 对接质量 | pDockQ 脚本计算 |
| `interfaceMetrics.interfaceDeltaG` | 界面结合能 | FoldX / HADDOCK |
| `interfaceMetrics.epitopeContactRatio` | 表位接触比例 | 自定义脚本：接触表位的残基 / 总接触残基 |
| `interfaceMetrics.contactingResidues` | 接触残基数 | 距离 < 5Å 的残基对计数 |
| `interfaceMetrics.distanceToEpitope` | 肽到表位质心距离 | PyMOL / Biopython 计算 |

## 3. 链 ID 要求

### 默认约定

| 链 | 内容 | 默认 ID |
|----|------|---------|
| Chain A | Target Protein（目标蛋白） | `A` |
| Chain B | Targeting Peptide（靶向肽） | `B` |

### 手动指定

如果 PDB 使用其他链 ID（如 `H` / `L`，或 `1` / `2`），需要在以下两处同步修改：

1. `ComplexMolstarViewer` 的 `targetChainId` / `peptideChainId` props
2. `mockComplexInfo` 中的对应字段

```tsx
// 示例：PDB 中目标蛋白为 H 链，肽为 L 链
<ComplexMolstarViewer
  targetChainId="H"
  peptideChainId="L"
/>
```

## 4. 表位残基编号映射

### 关键要求

**表位残基编号必须与 PDB 文件中的 `resSeq`（residue sequence number）严格对应。**

### 编号不一致的常见场景

| 场景 | 问题 | 解决方案 |
|------|------|----------|
| PDB 重新编号 | UniProt 第 453 位 → PDB 第 1 位 | 建立 UniProt-to-PDB 映射表 |
| 缺失 N-端 | PDB 从第 16 位开始 | 所有表位编号减去偏移量 |
| 插入残基 | PDB 有 `100A`, `100B` | 使用 PDB 原始编号 |

### 映射示例

```typescript
// UniProt-to-PDB 映射表（以 SARS-CoV-2 Spike 为例）
const uniprotToPdbMap: Record<number, number> = {
  453: 453,   // 直接对应
  454: 454,
  // ...
  505: 505,
};

// 使用前转换
const pdbStart = uniprotToPdbMap[453];  // 453
const pdbEnd = uniprotToPdbMap[505];    // 505
```

## 5. 真实验证流程

```
Target protein + targeting peptide
    ↓
AlphaFold-Multimer / ColabFold complex prediction
    ↓
生成 ranked_0.pdb（复合物 PDB）
    ↓
计算 contact residues（FoldX / PyMOL / ChimeraX）
    ↓
计算 epitope contact ratio
    ↓
计算 ipTM, pDockQ, interface ΔG
    ↓
更新数据：
  - 后端 API 返回真实值
  - 或更新 platformMockData.ts（演示阶段）
    ↓
前端展示真实结果
```

### 工具链推荐

| 步骤 | 工具 | 输出 |
|------|------|------|
| 复合物预测 | AlphaFold-Multimer v3 | `ranked_*.pdb` + JSON 置信度 |
| 对接优化 | FlexPepDock / HADDOCK | 优化后 PDB |
| 能量计算 | FoldX | `Interaction_Analyze_FoldX.txt` |
| 接触分析 | PyMOL / ChimeraX / PLIP | 残基对列表 |
| 质量评分 | pDockQ | `pdockq.csv` |
| 比例计算 | 自定义 Python 脚本 | epitopeContactRatio |

## 6. 后端 API 接入

当后端就绪后，将 `src/lib/structureValidationApi.ts` 中的 mock Promise 替换为真实 `fetch`：

```typescript
export async function fetchStructureValidationResult(
  candidateId: string
): Promise<StructureValidationResult> {
  const response = await fetch(`/api/structure-validation/${candidateId}`);
  if (!response.ok) throw new Error('Failed to fetch structure validation');
  return response.json();
}
```

当前 mock 接口保留了完整的字段结构，直接替换函数体即可。
