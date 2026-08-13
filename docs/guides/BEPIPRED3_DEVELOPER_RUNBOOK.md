# BepiPred3 开发者运行手册

> **适用范围**：STAMP 平台 BepiPred3 模块的开发、调试与运维  
> **版本**：v0.10-P2e  
> **最后更新**：2026-05-09

---

## 1. 架构概览

### 1.1 数据流

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BepiPred3 工作流架构                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐     HTTP POST      ┌────────────────────────────────┐│
│   │ BepiPred3       │ ──────────────────>│ STAMP Backend                  ││
│   │ Sidecar         │    /api/predict    │ (FastAPI + BackgroundTasks)    ││
│   │ (CPU mode)      │<────────────────── │                                ││
│   │ localhost:8010  │     JSON result    │  ┌─────────┐   ┌────────────┐  ││
│   └─────────────────┘                    │  │ Job     │──>│ job.output │  ││
│          ▲                               │  │ System  │   │ _json      │  ││
│          │                               │  └─────────┘   └────────────┘  ││
│          │ warmup                        │       │                          ││
│   ┌──────┴──────┐                       │       ▼                          ││
│   │ /api/warmup │                       │  POST /persist-bepipred3-results ││
│   └─────────────┘                       │       │                          ││
│                                         │       ▼                          ││
│                                         │  ┌──────────┐  ┌────────────────┐││
│                                         │  │ epitope  │  │ epitope        │││
│                                         │  │ _scans   │  │ _candidates    │││
│                                         │  └──────────┘  └────────────────┘││
│                                         │       │                          ││
│                                         └───────┼──────────────────────────┘│
│                                                 │                           │
│                                                 ▼ HTTP GET                  │
│                                         ┌──────────────┐                   │
│                                         │ Epitope      │                   │
│                                         │ Screening    │                   │
│                                         │ Page         │                   │
│                                         │ (React/Vite) │                   │
│                                         └──────────────┘                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 组件说明

| 组件 | 技术栈 | 地址 | 职责 |
|------|--------|------|------|
| BepiPred3 Sidecar | Python, PyTorch, ESM | `127.0.0.1:8010` | 模型推理 |
| STAMP Backend | FastAPI, SQLAlchemy, SQLite | `127.0.0.1:8000` | API 与业务逻辑 |
| STAMP Frontend | React, Vite, Tailwind | `127.0.0.1:3000` | 用户界面 |

---

## 2. 关键 API 参考

### 2.1 Job 管理

#### 创建 Job
```http
POST /api/v1/jobs
Content-Type: application/json

{
  "project_id": "<uuid>",
  "job_type": "bepipred3_scan",
  "input_json": {
    "sequence": "MKWVT...",
    "min_length": 8,
    "max_length": 25
  }
}
```

#### 异步启动
```http
POST /api/v1/jobs/{job_id}/start
```
响应：
```json
{
  "job_id": "<uuid>",
  "status": "running",
  "progress": 0,
  "message": "Job started in background"
}
```

#### 查询状态
```http
GET /api/v1/jobs/{job_id}
```

#### 取消 Job
```http
POST /api/v1/jobs/{job_id}/cancel
```
仅 `pending` 或 `running` 状态可取消。

#### 重试 Job
```http
POST /api/v1/jobs/{job_id}/retry
```
仅 `failed` 或 `cancelled` 状态可重试。创建新 Job，旧 Job 保留。

#### 同步执行（不推荐生产环境）
```http
POST /api/v1/jobs/{job_id}/run
```

### 2.2 结果持久化

```http
POST /api/v1/jobs/{job_id}/persist-bepipred3-results
```
将 `job.output_json` 写入 `epitope_scans` + `epitope_candidates` 表。

### 2.3 候选查询

```http
GET /api/v1/epitope-scans/{scan_id}/candidates
```

### 2.4 Sidecar 接口

```http
GET  /api/health        # 健康检查
GET  /api/model-info    # 模型加载状态
POST /api/warmup        # 模型预热
POST /api/predict       # 执行预测
```

---

## 3. Job 状态机

```
                    ┌─────────────┐
                    │   pending   │
                    └──────┬──────┘
                           │ POST /start
                           ▼
                    ┌─────────────┐
         ┌─────────│   running   │─────────┐
         │         └──────┬──────┘         │
         │                │                │
    POST │           success          POST │
   /cancel│                │           /cancel
         ▼                ▼                ▼
   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
   │  cancelled  │  │  succeeded  │  │    failed   │
   └─────────────┘  └──────┬──────┘  └──────┬──────┘
                           │                │
                           │ POST /persist  │ POST /retry
                           ▼                ▼
                    ┌─────────────┐  ┌─────────────┐
                    │  persisted  │  │   pending   │ (new job)
                    └─────────────┘  └─────────────┘
```

**状态说明**：

| 状态 | 含义 | 可执行操作 |
|------|------|------------|
| `pending` | 已创建，等待启动 | `/start`, `/cancel` |
| `running` | 后台执行中 | `/cancel` |
| `succeeded` | 执行成功 | `/persist-bepipred3-results` |
| `failed` | 执行失败 | `/retry` |
| `cancelled` | 已取消 | `/retry` |

---

## 4. 错误码说明

后端 `job.error_message` 使用结构化前缀：

| 前缀 | 触发条件 | 建议处理 |
|------|----------|----------|
| `[USER_CANCELLED]` | 用户点击 Cancel | 无需处理，可 Retry |
| `[SIDECAR_TIMEOUT]` | Sidecar 推理超时 | 缩短序列或重试 |
| `[SIDECAR_UNAVAILABLE]` | Sidecar 未启动或网络不通 | 启动 sidecar |
| `[SIDECAR_HTTP_ERROR]` | Sidecar 返回 HTTP 错误 | 检查 sidecar 日志 |
| `[INVALID_INPUT]` | 输入序列格式错误 | 检查输入参数 |
| `[UNSUPPORTED_JOB_TYPE]` | Job type 不被支持 | 使用 `bepipred3_scan` |
| `[INTERNAL_ERROR]` | 后端内部异常 | 联系开发者 |

---

## 5. 测试命令

### 5.1 后端测试

```powershell
# 全量测试
cd D:\Desktop\靶向肽\github\前端\backend
python -m pytest tests/ -q

# 关键模块单独测试
python -m pytest tests\test_job_cancel_retry.py -q
python -m pytest tests\test_job_async.py -q
python -m pytest tests\test_bepipred3_job.py -q
python -m pytest tests\test_bepipred3_persistence.py -q
python -m pytest tests\test_bepipred3_timeout.py -q
```

### 5.2 前端构建

```powershell
cd D:\Desktop\靶向肽\github\前端
npm run build
```

### 5.3 Agent Bridge All-Review

```powershell
cd D:\ai\product\kimi\agent-bridge
.\run-agent-bridge.ps1 all-review -TaskContent "cd backend && pytest -x"
```

---

## 6. 已知风险与限制

| 风险 | 影响 | 缓解措施 | 后续计划 |
|------|------|----------|----------|
| CPU 推理慢 | 长序列（>500 aa）可能超时 | 动态超时策略（60s/180s/300s） | 评估 GPU 加速 |
| 无 Celery/Redis | 后台任务不可持久化 | FastAPI BackgroundTasks + 轮询 | 后续按需引入 |
| Sidecar 单点故障 | sidecar 崩溃导致所有预测失败 | 健康检查 + 自动重启脚本 | 评估 sidecar 集群化 |
| 候选为空 | 过滤条件下无候选通过 | 明确提示空结果合法 | 优化默认过滤参数 |
| 无实验验证 | 候选未经湿实验确认 | 界面标注 NOT_EXPERIMENTALLY_VALIDATED | 对接实验数据模块（未来） |

---

## 7. 目录速查

| 路径 | 内容 |
|------|------|
| `D:\ai\tool\skill\bepipred3-api` | Sidecar 源码、启动脚本 |
| `D:\Desktop\靶向肽\github\前端\backend` | STAMP 后端 |
| `D:\Desktop\靶向肽\github\前端\src` | STAMP 前端源码 |
| `D:\Desktop\靶向肽\github\前端\scripts\demo` | 一键演示脚本 |
| `D:\Desktop\靶向肽\github\前端\docs\guides` | 用户/开发者文档 |
| `D:\ai\product\kimi\agent-bridge` | Agent Bridge、自动化验收 |
| `D:\ai\product\kimi\agent-bridge\reports` | 验收报告 |

---

## 8. 快速启动清单

```powershell
# Terminal 1: Sidecar
cd D:\ai\tool\skill\bepipred3-api
.\start-bepipred3-sidecar.ps1 -Warmup

# Terminal 2: Backend
cd D:\Desktop\靶向肽\github\前端\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 3: Frontend
cd D:\Desktop\靶向肽\github\前端
npm run dev

# Terminal 4: Demo (optional)
cd D:\Desktop\靶向肽\github\前端\scripts\demo
.\run-bepipred3-demo.ps1
```

---

## 9. 相关文档

- [BepiPred3 用户工作流指南](./BEPIPRED3_WORKFLOW_USER_GUIDE.md)
- STAMP 平台 README
- Agent Bridge 报告目录：`D:\ai\product\kimi\agent-bridge\reports\`
