# v0.6d-P1c Demo-compatible `/api/predict` 封存报告

**封存日期**: 2026-04-28  
**封存执行**: KimiCode  
**复核判定**: Hermes — GO  
**方案**: C（Demo-compatible 兼容层）  
**风险等级**: 最低  

---

## 1. 修改文件清单

### 后端（2 个文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/routers/legacy_predict.py` | **新增** | Demo-compatible `/api/health` + `/api/predict`，返回预计算历史数据，明确标注 DEMO_COMPATIBLE / NOT_EXPERIMENTALLY_VALIDATED |
| `backend/app/main.py` | **修改** | 注册 `legacy_predict` router |

### 前端（3 个文件）

| 文件 | 操作 | 说明 |
|------|------|
| `src/pages/PeptideFilterPage.tsx` | **修改** | 顶部添加琥珀色 Demo Mode banner |
| `src/components/hero/HeroSection.tsx` | **修改** | 标题加 "(Demo)"，描述加 "当前为预计算示例数据演示模式" |
| `src/components/status/ApiWarmupBanner.tsx` | **修改** | warming 状态文案改为 "运行示例表位筛选流程 / Running Demo Filter" |

---

## 2. 服务器 curl 验证结果

### 2.1 GET `/api/health`

```bash
curl -s http://127.0.0.1:8088/api/health | python3 -m json.tool
```

```json
{
    "status": "ok",
    "service": "legacy-peptide-filter-demo",
    "mode": "demo-compatible"
}
```

✅ **HTTP 200** — 前端 `checkApiHealth()` 的 `res.ok` 检查通过。

### 2.2 POST `/api/predict`

```bash
curl -s -X POST http://127.0.0.1:8088/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"name":"OprF_Demo","sequence":"MKKTAIAIAIVAAGVATVQAATAEQVNTLKGNVAAGAANLNETTSGVQNYTQFDFNLDKES"}'
```

**返回摘要**:
```
success: True
retained: 10
dropped: 45
mode: DEMO_COMPATIBLE
top1: NPRRH (priority=39.1112)
validation_status: NOT_EXPERIMENTALLY_VALIDATED
```

✅ **HTTP 200**，返回 10 条预计算 ranked peptides，含完整五层筛选字段（charge, hydrophobicity, pI, cysteine, disulfide）。

### 2.3 GET `/api/v1/stamp/demo-one`

```bash
curl -s http://127.0.0.1:8088/api/v1/stamp/demo-one
```

```
candidate_id: stamp_oprf_0029
validation_status: NOT_EXPERIMENTALLY_VALIDATED
target_molecule: Pseudomonas aeruginosa OprF
```

✅ **HTTP 200**，STAMP 核心端点未受影响。

### 2.4 POST `/api/v1/stamp/build`

```bash
curl -s -X POST http://127.0.0.1:8088/api/v1/stamp/build \
  -H 'Content-Type: application/json' \
  -d '{"candidate_id":"OPRF_0029"}'
```

```
candidate_id: stamp_oprf_0029
validation_status: NOT_EXPERIMENTALLY_VALIDATED
```

✅ **HTTP 200**，STAMP build 端点未受影响。

---

## 3. 浏览器验收结果

### 3.1 `/filter` 页面

| 检查项 | 结果 |
|--------|------|
| Demo Mode banner 显示 | ✅ 琥珀色顶部条，含 "Demo Mode" label 和中文说明 |
| 标题标注 (Demo) | ✅ "Peptide Filter Pipeline (Demo)" |
| Run Prediction 按钮 | ✅ 可点击 |
| 点击后 API 调用 | ✅ `GET /api/health [200]`, `POST /api/predict [200]` |
| 结果展示 | ✅ 结果面板展示候选肽段列表 |
| 控制台错误 | ✅ 无 |

### 3.2 `/demo` 页面

| 检查项 | 结果 |
|--------|------|
| Demo Mode banner 显示 | ✅ |
| 标题标注 (Demo) | ✅ |
| Run Prediction 按钮 | ✅ 可点击 |
| 点击后 API 调用 | ✅ `GET /api/health [200]`, `POST /api/predict [200]` |
| 结果展示 | ✅ |
| 控制台错误 | ✅ 无 |

### 3.3 `/peptide-generation` 页面（STAMP 回归）

| 检查项 | 结果 |
|--------|------|
| 一键 STAMP 示例按钮 | ✅ "运行单候选全流程" 可点击 |
| API 调用 | ✅ `GET /api/v1/stamp/demo-one [200]` |
| 控制台错误 | ✅ 无 |

---

## 4. 代码审查：无伪造实验/结构指标

### 4.1 `legacy_predict.py` 审查

| 检查项 | 结果 |
|--------|------|
| 文件头注释声明 demo-compatible | ✅ 第 9-12 行 |
| 声明 "no real BepiPred 3.0 or ESM inference" | ✅ 第 10-11 行 |
| `api_predict` docstring 声明 "No real BepiPred 3.0 or ESM computation" | ✅ 第 321 行 |
| 返回 `mode: DEMO_COMPATIBLE` | ✅ 第 346 行 |
| 返回 `validation_status: NOT_EXPERIMENTALLY_VALIDATED` | ✅ 第 347 行 |
| 返回 `note` 明确说明 precomputed demo data | ✅ 第 348 行 |
| 无 `MIC` / `MBC` / `hemolysis` 字段 | ✅ |
| 无 `pDockQ` / `ipTM` / `pLDDT` / `ΔG` 字段 | ✅ |
| 无 `docking_score` / `binding_affinity` 字段 | ✅ |

### 4.2 前端审查

| 检查项 | 结果 |
|--------|------|
| PeptideFilterPage Demo Mode banner | ✅ |
| HeroSection (Demo) 标注 | ✅ |
| ApiWarmupBanner Demo 文案 | ✅ |
| 无 "实验验证" / "已验证" 等误导性文案 | ✅ |

---

## 5. 当前可演示功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| `/filter` 页面表位筛选流程 | ✅ 可演示 | 点击 Run Prediction → 返回 10 条预计算候选肽段 |
| `/demo` 页面表位筛选流程 | ✅ 可演示 | 同上 |
| 五层筛选结果展示 | ✅ 可演示 | Length, Charge, Hydrophobicity, pI, Cysteine/Disulfide |
| 候选肽段排序与评分 | ✅ 可演示 | priority_score, disulfide_score, charge_score 等 |
| STAMP One-click Demo | ✅ 可演示 | `/api/v1/stamp/demo-one` 返回 stamp_oprf_0029 |
| STAMP Build | ✅ 可演示 | `/api/v1/stamp/build` 可组装完整 STAMP |
| PepMLM 候选展示 | ✅ 可演示 | 静态 JSON 数据 |
| AMP 文库展示 | ✅ 可演示 | 静态 JSON 数据 |

---

## 6. 当前不可宣称功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 实时 BepiPred 3.0 表位预测 | ❌ 未接入 | 返回预计算数据，非实时 ESM+FFNN 推理 |
| 真实 ESM-1b 编码 | ❌ 未接入 | fair-esm 未安装，模型未加载 |
| 真实 BepiPred3 模型推理 | ❌ 未接入 | bp3/BP3Models/*.pt 未加载 |
| 实验验证数据 (MIC/MBC) | ❌ 无 | 所有 experimental 字段为 None |
| 结构预测 (pDockQ/ipTM/pLDDT) | ❌ 无 | 所有 structure 字段为 False/None |
| 分子对接评分 (ΔG) | ❌ 无 | mock_scores 全部为 None |
| GPU 加速推理 | ❌ 不适用 | 演示数据不涉及计算 |

---

## 7. 验收标准检查

| # | 标准 | 验证方式 | 状态 |
|---|------|---------|------|
| 1 | 服务器 `/api/health` 正常 | curl 测试 | ✅ |
| 2 | 服务器 `/api/predict` 正常 | curl 测试 | ✅ |
| 3 | `/filter` 页面点击 Run Prediction 不再 404 | 浏览器点击 + Network 面板 | ✅ |
| 4 | `/demo` 页面点击 Run Prediction 不再 404 | 浏览器点击 + Network 面板 | ✅ |
| 5 | `/api/v1/stamp/demo-one` 仍正常 | curl 测试 | ✅ |
| 6 | 页面有 Demo Mode / 示例数据说明 | 浏览器截图 + snapshot | ✅ |
| 7 | 无伪造 Real BepiPred3 / ESM / 实验指标 | 代码审查 + 响应体审查 | ✅ |
| 8 | 生成封存报告 | 本文档 | ✅ |

---

## 8. GO / NO-GO

| 检查项 | 状态 |
|--------|------|
| 服务器 curl 验证全部通过 | ✅ |
| 浏览器验收全部通过 | ✅ |
| 代码审查通过（无伪造数据） | ✅ |
| Demo Mode 标注完整 | ✅ |
| STAMP 核心端点未受影响 | ✅ |
| 封存报告生成 | ✅ |

**最终判定**: **GO** ✅

v0.6d-P1c Demo-compatible `/api/predict` 修补已完成封存，所有 8 项验收标准通过。

---

*封存完成。*
