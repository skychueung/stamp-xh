# v0.6d-P1c 内网演示闭环版最终封口文档

**版本**: v0.6d-P1c  
**日期**: 2026-04-28  
**执行**: KimiCode  
**复核**: Hermes  
**状态**: GO  
**服务器**: 192.168.31.218:8088  

---

## 1. 封口声明

本文档为 v0.6d-P1c Demo-compatible `/api/predict` 的最终封口记录。  
所有验证项已逐项确认通过，代码不再变更，服务运行稳定。

---

## 2. 当前版本状态

| 属性 | 值 |
|------|-----|
| 版本号 | v0.6d-P1c |
| 部署路径 | `/home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a` |
| 后端进程 | uvicorn `app.main:app` @ `0.0.0.0:8088` |
| 前端 | SPA static files (`dist/`) |
| 方案 | C — Demo-compatible 兼容层（最低风险） |
| 真实 BepiPred3 / ESM | **未接入** |

---

## 3. 服务器端点验证

### 3.1 GET `/api/health`

```
$ curl -s http://127.0.0.1:8088/api/health
{"status":"ok","service":"legacy-peptide-filter-demo","mode":"demo-compatible"}
```

✅ HTTP 200

### 3.2 POST `/api/predict`

```
$ curl -s -X POST http://127.0.0.1:8088/api/predict \
  -H 'Content-Type: application/json' \
  -d '{"sequence":"MKKTAIAIAIVAAGVATVQAATAEQVNTLKGNVAAGAANLNETTSGVQNYTQFDFNLDKES"}'
```

关键返回字段：
- `success: true`
- `mode: DEMO_COMPATIBLE`
- `validation_status: NOT_EXPERIMENTALLY_VALIDATED`
- `retained_count: 10`
- `dropped_count: 45`
- 含 10 条预计算 ranked peptides（历史 post-screen-ranking 输出）

✅ HTTP 200

### 3.3 GET `/api/v1/stamp/demo-one`

```
$ curl -s http://127.0.0.1:8088/api/v1/stamp/demo-one
```

关键返回字段：
- `candidate_id: stamp_oprf_0029`
- `validation_status: NOT_EXPERIMENTALLY_VALIDATED`

✅ HTTP 200

---

## 4. 浏览器验收验证

| 页面 | 检查项 | 结果 |
|------|--------|------|
| `/` (首页) | 可访问 | ✅ |
| `/filter` | Demo Mode banner | ✅ 琥珀色顶部条 |
| `/filter` | 标题 "(Demo)" | ✅ |
| `/filter` | Run Prediction 按钮 | ✅ |
| `/filter` | 点击后 POST `/api/predict` 200 | ✅ |
| `/filter` | 结果面板展示候选肽段 | ✅ |
| `/filter` | 控制台无错误 | ✅ |
| `/demo` | Demo Mode banner | ✅ |
| `/demo` | Run Prediction 按钮 | ✅ |
| `/demo` | 点击后 POST `/api/predict` 200 | ✅ |
| `/demo` | 结果面板展示候选肽段 | ✅ |
| `/demo` | 控制台无错误 | ✅ |
| `/peptide-generation` | 一键 STAMP 示例按钮 | ✅ "运行单候选全流程" |
| `/peptide-generation` | 点击后 GET `/api/v1/stamp/demo-one` 200 | ✅ |
| `/peptide-generation` | 控制台无错误 | ✅ |

---

## 5. 可演示功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 首页浏览 | ✅ | STAMP 平台介绍、团队、概念图 |
| `/filter` 表位筛选演示 | ✅ | 输入序列 → Run Prediction → 五层筛选结果 |
| `/demo` 表位筛选演示 | ✅ | 同上 |
| 候选肽段排序与评分展示 | ✅ | priority_score, disulfide_score, charge_score 等 |
| 五层筛选指标展示 | ✅ | Length, Charge, Hydrophobicity, pI, Cysteine/Disulfide |
| `/peptide-generation` PepMLM 展示 | ✅ | 静态 JSON 候选列表 |
| `/peptide-generation` STAMP One-click Demo | ✅ | 组装 stamp_oprf_0029 |
| `/stamp-hybrid-design` STAMP Build | ✅ | 输入 candidate_id → 组装完整 STAMP |
| AMP 文库展示 | ✅ | 静态 JSON 数据 |

---

## 6. 暂不可宣称功能清单

| 功能 | 状态 | 说明 |
|------|------|------|
| 实时 BepiPred 3.0 表位预测 | ❌ 未接入 | `/api/predict` 返回预计算数据，非实时 ESM+FFNN 推理 |
| ESM-1b 蛋白质语言模型编码 | ❌ 未接入 | fair-esm 未安装 |
| BepiPred3 模型推理 | ❌ 未接入 | bp3/BP3Models/*.pt 未加载 |
| 实验验证数据 (MIC/MBC/溶血) | ❌ 无 | 所有 experimental 字段为 None |
| 结构预测 (pDockQ/ipTM/pLDDT) | ❌ 无 | 所有 structure 字段为 False/None |
| 分子对接评分 (ΔG) | ❌ 无 | mock_scores 全部为 None |
| GPU 加速推理 | ❌ 不适用 | 演示数据不涉及计算 |

---

## 7. 汇报口径（必须严格遵守）

### ✅ 可以说的

> "当前版本已接通演示兼容接口，可展示表位筛选与五层过滤流程；STAMP 嵌合肽组装功能已真实可用。"

### ❌ 不可以说的

> ~~"真实 BepiPred3 已集成"~~  
> ~~"ESM 实时推理已上线"~~  
> ~~"实验验证数据已产生"~~  
> ~~"分子对接评分已计算"~~  
> ~~"MIC/MBC 已测定"~~

### 推荐话术

> "当前为 v0.6d-P1c 演示兼容版本，前端可完整展示从目标蛋白输入 → 表位筛选 → 肽段生成 → STAMP 组装的全流程界面；后端 STAMP 组装为真实计算，表位筛选为预计算示例数据，用于流程演示。真实 BepiPred3 / ESM 后端资产已审计找回，将以 Sidecar 方式在后续版本接入。"

---

## 8. 下一阶段计划

| 阶段 | 目标 | 方案 |
|------|------|------|
| v0.6d-P1d | Sidecar 接入真实 BepiPred3 / ESM | 方案 A：旧 Flask 后端运行在 5001 端口，FastAPI 代理 `/api/predict` |
| v0.6d-P2 | 统一 FastAPI 架构 | 方案 B：将 BepiPred3 + post_screen_ranking 逻辑迁入当前 FastAPI |

---

## 9. 修改文件清单（最终封存版）

### 后端
- `backend/app/routers/legacy_predict.py`（新增）
- `backend/app/main.py`（修改：注册 legacy_predict router）

### 前端
- `src/pages/PeptideFilterPage.tsx`（修改：Demo Mode banner）
- `src/components/hero/HeroSection.tsx`（修改：标题 + 描述 Demo 标注）
- `src/components/status/ApiWarmupBanner.tsx`（修改：Demo 文案）

---

## 10. GO / NO-GO

| # | 验收项 | 验证方式 | 状态 |
|---|--------|---------|------|
| 1 | 服务器 `http://192.168.31.218:8088/` 可访问 | 浏览器导航 | ✅ |
| 2 | `/filter` Run Prediction 返回 200 | 浏览器点击 + Network | ✅ |
| 3 | `/demo` Run Prediction 返回 200 | 浏览器点击 + Network | ✅ |
| 4 | `/peptide-generation` One-click STAMP Demo 正常 | 浏览器点击 + Network | ✅ |
| 5 | `/api/v1/stamp/demo-one` 正常 | curl | ✅ |
| 6 | 页面有 Demo Mode / NOT_EXPERIMENTALLY_VALIDATED 标注 | 浏览器截图 + 代码审查 | ✅ |
| 7 | 无伪造 Real BepiPred3 / ESM / 实验指标 | 代码审查 + 响应体审查 | ✅ |

**最终判定**: **GO** ✅

---

*封口完成。代码冻结，不做 Sidecar，不重启服务。*
