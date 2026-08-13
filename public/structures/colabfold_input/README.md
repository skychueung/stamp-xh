# ColabFold 输入说明

## 文件

- `candidates.fasta` — 候选肽序列，用于 ColabFold / AlphaFold2 结构预测

## 当前状态

序列尚未填入真实候选肽，当前为占位符：

| ID | 序列 | 状态 |
|----|------|------|
| candidate_1 | REPLACE_WITH_REAL_CANDIDATE_1_SEQUENCE | 待替换 |
| candidate_2 | REPLACE_WITH_REAL_CANDIDATE_2_SEQUENCE | 待替换 |
| candidate_3 | REPLACE_WITH_REAL_CANDIDATE_3_SEQUENCE | 待替换 |

真实序列应从 `/api/predict` 返回的 `ranked_peptides` 中提取，或从实验数据中选取。

## ColabFold 使用步骤

### 1. 本地运行（推荐，如有 GPU）

```bash
# 进入 ColabFold 环境（conda / venv）
colabfold_batch \
  candidates.fasta \
  ./colabfold_output \
  --num-models 3 \
  --num-recycle 3 \
  --model-type alphafold2_ptm
```

### 2. Google Colab（无本地 GPU）

1. 打开 [ColabFold Notebook](https://colab.research.google.com/github/sokrypton/ColabFold/blob/main/AlphaFold2.ipynb)
2. 上传 `candidates.fasta`
3. 运行所有 cell，下载输出的 `ranked_*.pdb`

## 输出处理

ColabFold 会为每条序列生成多个 PDB 文件（`ranked_0.pdb` 为最佳模型）。

需要将其重命名为项目约定的文件名，并放入 `public/structures/`：

| 原始输出 | 重命名为 |
|----------|----------|
| `candidate_1_ranked_0.pdb` 或 `ranked_0.pdb` | `candidate_1.pdb` |
| `candidate_2_ranked_0.pdb` 或 `ranked_0.pdb` | `candidate_2.pdb` |
| `candidate_3_ranked_0.pdb` 或 `ranked_0.pdb` | `candidate_3.pdb` |

重命名后替换到：

```
public/structures/
```

## 替换后自动化处理

1. **重新运行 DSSP** — 在 WSL 中执行：

   ```bash
   cd /mnt/d/Desktop/靶向肽/github/前端/public/structures
   mkdssp candidate_1.pdb candidate_1.dssp
   mkdssp candidate_2.pdb candidate_2.dssp
   mkdssp candidate_3.pdb candidate_3.dssp
   ```

2. **更新元数据** — 运行脚本自动生成：

   ```bash
   cd /mnt/d/Desktop/靶向肽/github/前端
   python3 scripts/structure/analyze_dssp.py \
     --pdb-dir public/structures \
     --output public/structures/structure-metadata.json \
     --keep-dssp
   ```

3. **构建验证** — 重新构建前端：

   ```bash
   npm run build
   ```

4. **页面验证** — 访问 `/structure`，确认：
   - Molstar 正确加载 3D 结构
   - pLDDT 评分显示正常
   - helix/sheet/coil 比例非 100% coil

## 占位文件备份

原始占位 PDB 与 DSSP 输出已备份至：

```
public/structures/archive_placeholder/
```

如需回滚，从备份目录复制回来即可。

---

*最后更新：2026-04-27*
