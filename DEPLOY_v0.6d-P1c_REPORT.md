# v0.6d-P1c Demo-compatible `/api/predict` 修补报告

**日期**: 2026-04-28  
**方案**: C（Demo-compatible 兼容层）  
**风险等级**: 最低  
**目标**: 恢复 `/filter` 和 `/demo` 页面可演示能力，不接入真实 BepiPred3/ESM

---

## 1. 修改文件清单

### 后端（2 个文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/app/routers/legacy_predict.py` | **新增** | Demo-compatible `/api/health` + `/api/predict` |
| `backend/app/main.py` | **修改** | 注册 `legacy_predict` router |

### 前端（3 个文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `src/pages/PeptideFilterPage.tsx` | **修改** | 顶部添加 Demo Mode banner（琥珀色） |
| `src/components/hero/HeroSection.tsx` | **修改** | 标题加 (Demo) 标注，描述加说明 |
| `src/components/status/ApiWarmupBanner.tsx` | **修改** | warming 状态文案改为 Demo 相关 |

---

## 2. 后端接口契约

### GET `/api/health`

```json
{
  "status": "ok",
  "service": "legacy-peptide-filter-demo",
  "mode": "demo-compatible"
}
```

✅ 前端 `checkApiHealth()` 的 `res.ok` 检查通过。

### POST `/api/predict`

**请求体**（兼容旧 Flask 后端）：
```json
{
  "name": "protein_id",
  "sequence": "ACDEFG...",
  "min_len": 5,
  "max_len": 15,
  ...
}
```

**响应体**（旧 Flask 格式，非 `ApiResponse` 包装）：
```json
{
  "success": true,
  "protein_name": "OprF_Demo",
  "sequence_length": 61,
  "ranked_peptides": [ /* 10 条真实历史数据 */ ],
  "dropped_count": 45,
  "retained_count": 10,
  "total_extracted": 55,
  "mode": "DEMO_COMPATIBLE",
  "validation_status": "NOT_EXPERIMENTALLY_VALIDATED",
  "note": "This endpoint returns precomputed demo data..."
}
```

✅ 字段完全兼容 `src/lib/api.ts` 的 `PredictResponse` 映射。

---

## 3. 本地测试结果

| 测试项 | 结果 |
|--------|------|
| 后端语法验证 | ✅ App 创建成功，路由注册正确 |
| GET /api/health | ✅ HTTP 200 |
| POST /api/predict | ✅ HTTP 200，`success=true`，10 条 ranked peptides |
| npm run build | ✅ TypeScript 编译通过，22.42s |

---

## 4. 服务器部署与验证

**部署方式**: SSH (kimi_bridge_ed25519 key) + SCP 直接传输

**操作记录**:
1. 上传 `legacy_predict.py` → `/home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a/backend/app/routers/`
2. 上传 `main.py` → `/home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a/backend/app/`
3. 上传前端 `dist/*` → `/home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a/dist/`
4. 重启后端（`uvicorn app.main:app --host 0.0.0.0 --port 8088`）
5. 新 PID: **3693700**

### 服务器端回归测试

| 测试项 | 命令 | 结果 |
|--------|------|------|
| GET /api/health | `curl http://127.0.0.1:8088/api/health` | ✅ 200 |
| POST /api/predict | `curl -X POST http://127.0.0.1:8088/api/predict -d '{"sequence":"..."}'` | ✅ 200, retained=10, dropped=45 |
| GET /api/v1/stamp/demo-one | `curl http://127.0.0.1:8088/api/v1/stamp/demo-one` | ✅ 200, stamp_oprf_0029 |
| POST /api/v1/stamp/build | `curl -X POST .../build -d '{"candidate_id":"OPRF_0029"}'` | ✅ 200, stamp_oprf_0029 |

---

## 5. 浏览器端验证

### `/filter` 页面

- Demo Mode banner 显示正常（琥珀色顶部条）
- 点击 **Run Prediction** → API 预热中提示 → 结果面板展示 10 条候选肽段
- 无控制台错误
- Network: `GET /api/health [200]`, `POST /api/predict [200]`

### `/demo` 页面

- 同上，Run Prediction 正常工作
- 无控制台错误

### `/peptide-generation` 页面

- 一键 STAMP 示例按钮正常
- Network: `GET /api/v1/stamp/demo-one [200]`
- 无控制台错误

---

## 6. 前端 Demo Mode 标注位置

| 位置 | 内容 |
|------|------|
| `/filter` & `/demo` 页面顶部 | 🟡 **Demo Mode** — 当前展示为预计算示例数据，用于演示五层筛选流程。真实 BepiPred 3.0 / ESM 实时推理将在后续版本接入。 |
| `HeroSection` 标题 | Peptide Filter Pipeline **(Demo)** |
| `HeroSection` 描述 | "当前为预计算示例数据演示模式。" |
| `ApiWarmupBanner` | "运行示例表位筛选流程 / Running Demo Filter — 正在返回预计算示例数据..." |

---

## 7. 已知问题与修复记录

| 问题 | 原因 | 修复 |
|------|------|------|
| `topAdvantages.slice(...).map is not a function` | 后端返回 `top_advantages` 为分号分隔字符串，前端期望数组 | 修改 `legacy_predict.py`，`top_advantages` 统一返回数组格式 `["hydrophobicity", "pI"]` |

---

## 8. 限制与后续工作

| 限制 | 说明 | 后续方案 |
|------|------|---------|
| `/api/predict` 返回固定数据 | 不基于输入序列实时计算 | 方案 A（Sidecar）或方案 B（迁入 FastAPI）接入真实 BepiPred3+ESM |
| `EpitopeScreeningPage` 仍为纯前端 | "运行五层表位筛选" 按钮未调用 API | 如需，可接入 `/api/predict` 或后续独立 endpoint |
| 无 GPU 加速 | 演示数据不涉及计算 | 后续接入时确认服务器 GPU/CUDA |

---

## 9. 验收标准检查

| # | 标准 | 状态 |
|---|------|------|
| 1 | GET /api/health 返回 200 | ✅ |
| 2 | POST /api/predict 返回 200 | ✅ |
| 3 | /filter 页面点击 Run Prediction 不再 404 | ✅ |
| 4 | /demo 页面点击 Run Prediction 不再 404 | ✅ |
| 5 | 页面显示 Demo Mode / 示例数据说明 | ✅ |
| 6 | /peptide-generation 的 One-click STAMP 仍正常 | ✅ |
| 7 | /api/v1/stamp/demo-one 仍正常 | ✅ |
| 8 | npm run build 通过 | ✅ |
| 9 | 未接入 BepiPred3/ESM 时，不得写成 real-time prediction | ✅ |
| 10 | 不显示任何伪造结构/实验指标 | ✅ |

---

## 10. GO / NO-GO

| 检查项 | 状态 |
|--------|------|
| 代码本地验证 | ✅ GO |
| 构建通过 | ✅ GO |
| 接口格式兼容前端 | ✅ GO |
| Demo Mode 标注完整 | ✅ GO |
| 服务器部署完成 | ✅ GO |
| 服务器端回归测试 | ✅ GO |
| 浏览器端验证 | ✅ GO |

**结论**: **GO** — v0.6d-P1c Demo-compatible `/api/predict` 修补已完成，所有验收标准通过。`/filter` 和 `/demo` 页面不再 404，可正常展示预计算示例数据。

---

*报告结束。*
