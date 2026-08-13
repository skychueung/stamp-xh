# STAMP Platform — Development Roadmap

> 按优先级排序的任务清单。

---

## 下一阶段：v0.8

待完成：
- [ ] 接入真实靶向肽生成模型（PepMLM / CreoPep / Fair-ESM）
- [ ] 接入结构验证计算结果（AlphaFold-Multimer / ColabFold / FoldX / FlexPepDock）
- [ ] 建立候选肽数据库持久化层
- [ ] 完善 GitHub Actions 或自动化部署流程
- [ ] 补充更多后端单元测试与接口文档

---

## v0.7-P1a Epitope Parameterization & Flow ✅ 已完成（2026-05-06）

P1a 表位筛选参数化与候选表位流转已实现。

### 已完成
- [x] /target-protein Scan Parameters 面板（6 个参数控件）
- [x] /epitope-screening 显示本次扫描参数
- [x] CSV 导出（候选表 + 元数据）
- [x] 候选表位 → /peptide-generation 流转（"Send to Peptide Gen" 按钮）
- [x] localStorage key: `stamp.selectedEpitope.v0.7`
- [x] /peptide-generation 显示真实选中表位 + mock 回退
- [x] pytest 101 passed
- [x] npm run build 0 errors

---

## v0.7-real-backend-integration ✅ 已完成（2026-05-06）

P0 最小真实后端闭环已实现。

### 已完成
- [x] POST /api/v1/epitope/scan — 真实后端 API
- [x] 15 aa sliding window 扫描（68 aa OprF → 54 窗口）
- [x] GRAVY / net_charge / pI / Cys / disulfide_risk 真实计算
- [x] 前端 TargetProteinInputPage 调用真实 API
- [x] 前端 EpitopeScreeningPage 优先展示真实结果
- [x] mode = REAL_BIOPHYSICS_SLIDING_WINDOW
- [x] validation_status = NOT_EXPERIMENTALLY_VALIDATED
- [x] pytest 101 passed
- [x] npm run build 0 errors

---

## v0.5.1-i18n-home-global ✅ 已冻结（2026-04-28）

前端 UI MVP + 首页级 i18n 完成。

### 已完成
- [x] 轻量级全局 i18n 系统（Context + localStorage，零外部依赖）
- [x] 中文 / English 一键切换（LanguageToggle 组件）
- [x] Home 页面完整双语（标题、副标题、模块卡片、特性说明、按钮）
- [x] Sidebar 导航双语（12 项菜单实时切换）
- [x] Pipeline Progress 双语（9 步流程标签实时切换）
- [x] 6 平台页面标题双语（TargetProtein / EpitopeScreening / PeptideGeneration / PeptideOptimization / StructureValidation / FinalRanking）

---

## v0.5.2-full-page-i18n-polish 🔄 阶段一完成，阶段二可选

### 阶段一 ✅ 已完成（2026-04-28）

- [x] 页面大标题/副标题全量 i18n（6 页面）
- [x] SectionCard 标题/副标题 i18n（重点页面）
- [x] 按钮文案 i18n（主要操作按钮）
- [x] 表格列名 i18n（peptide-generation 13 列）
- [x] StatusPill 状态标签 i18n（5 页面生效）
- [x] 设计规则描述 i18n
- [x] 生成概览/优化对比 i18n

### 阶段二 ⏸️ 可选（有国际汇报需求时启动）

- [ ] 表格列名补全（epitope-screening 15 列 / final-ranking 20+ 列）
- [ ] 小标签硬编码清理（`2nd Structure:` / `Charge Pattern:` 等）
- [ ] InfoBanner message 全量 i18n
- [ ] 空状态提示 i18n（No data / Loading / Error）
- [ ] 科学术语统一表（Scientific Terms Glossary）
- [ ] 双语截图归档（`docs/report_screenshots/i18n/`）
- [ ] 国际版汇报素材导出

### 启动条件

- 有国际会议/合作汇报需求
- 或 v0.6-real-complex-validation 完成后统一打磨

### 建议

优先启动 v0.6-real-complex-validation 真实结构数据接入。i18n 阶段二作为并行可选任务，有需求时随时补全。

---

## v0.6-real-complex-validation 🔄 下一阶段

### 目标
将 Mock complex structure 替换为真实 AlphaFold-Multimer / ColabFold 预测结果。

### 任务清单

#### 1. 真实目标蛋白数据接入
- [ ] 从 `/target-protein` 页面获取真实 UniProt ID 或 PDB ID
- [ ] 下载真实目标蛋白结构（AlphaFold DB 或实验 PDB）
- [ ] 解析并验证结构质量（pLDDT / resolution）

#### 2. 真实靶向肽序列接入
- [ ] 从 `/peptide-generation` 获取 AI 生成的候选肽序列
- [ ] 或从 `/peptide-optimization` 获取优化后的 Top 肽
- [ ] 序列格式标准化（FASTA，单字母氨基酸）

#### 3. 复合物结构预测
- [ ] 准备 AlphaFold-Multimer 输入：
  - sequence 1: target protein（或仅表位区域 + 周围残基）
  - sequence 2: targeting peptide
- [ ] 运行 AlphaFold-Multimer v2.3+ 或 ColabFold
- [ ] 参数设置：`model_preset=multimer`, `num_recycles=3`, `stop_at_score=100`
- [ ] 输出：`ranked_0.pdb`, `ranked_1.pdb`, `ranking_debug.json`

#### 4. 结构质量过滤
- [ ] 提取 ipTM（interface predicted TM-score）
- [ ] 计算 pDockQ（protein-protein docking quality）
- [ ] 阈值过滤：`ipTM > 0.7` AND `pDockQ > 0.23`

#### 5. 界面接触分析
- [ ] 解析复合物 PDB，提取两条链坐标
- [ ] 计算肽残基与表位残基的欧氏距离矩阵
- [ ] 识别接触对：`< 5.0Å`（或更严格 `< 4.5Å`）
- [ ] 分类接触类型：hydrophobic / electrostatic / hydrogen-bond / van-der-waals

#### 6. Epitope Contact Ratio 真实计算
```python
# 伪代码
def calculate_epitope_contact_ratio(complex_pdb, epitope_range, peptide_chain):
    epitope_residues = get_residues(complex_pdb, chain='A', range=epitope_range)
    peptide_residues = get_residues(complex_pdb, chain=peptide_chain)
    
    contacts = []
    for p_res in peptide_residues:
        for e_res in epitope_residues:
            dist = min_distance(p_res.atoms, e_res.atoms)
            if dist < 5.0:
                contacts.append((p_res, e_res, dist))
    
    peptide_residues_in_contact = set(p for p, e, d in contacts)
    return len(peptide_residues_in_contact) / len(peptide_residues)
```

#### 7. 界面能量计算
- [ ] FoldX `AnalyseComplex` 或 `Interface`
- [ ] Rosetta `InterfaceAnalyzer`
- [ ] 提取 `interface_delta_G`

#### 8. 后端 API 实现
- [ ] `POST /api/structure-validation/submit` — 提交计算任务
- [ ] `GET /api/structure-validation/:taskId/status` — 查询进度
- [ ] `GET /api/structure-validation/:taskId/result` — 获取结果
- [ ] 结果格式匹配 `src/lib/structureValidationApi.ts` 的 `StructureValidationResult`

#### 9. 前端数据替换
- [ ] 替换 `src/lib/structureValidationApi.ts` 中的 mock Promise 为真实 `fetch`
- [ ] 更新 `src/data/platformMockData.ts` 为真实数据或 API 驱动
- [ ] 验证 `/structure-validation` 页面显示真实 3D 结构、真实指标、真实 Contact Map

---

## 历史归档

### v0.5-stamp-platform-ui-mvp
- 前端 UI MVP 完成，Mock 数据驱动，3D 展示基础设施就绪
- 见 CHANGELOG.md

### v0.4-real-colabfold-structures
- 用真实 ColabFold / AlphaFold2 预测结构替换占位 PDB
- 见 CHANGELOG.md

### v0.3-structure-viewer-toolchain
- 新增 `/structure` 三维结构展示页面
- 接入 Mol* Viewer（Molstar）
- 完成 PDB → DSSP → metadata → 前端展示闭环

### v0.2-platform-ui
- 完成蓝白科研风格平台首页 (`/`)
- 配置 Tailwind 主题色 `xh-primary: #156B98`

### v0.1-filter-pipeline
- 初始项目搭建（Vite + React + TypeScript + Tailwind）
- 实现肽段筛选流水线页面 `/filter`
- 集成 `/api/predict` 后端调用

---

*最后更新：2026-04-28*
