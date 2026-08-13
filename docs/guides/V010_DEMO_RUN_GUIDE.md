# STAMP v0.10 一键演示操作手册

**版本**: v0.10  
**日期**: 2026-05-09  
**适用场景**: 课题组演示、老师汇报、本地开发验证

---

## 1. 环境准备

### 1.1 目录结构

| 组件 | 路径 |
|------|------|
| BepiPred3 Sidecar | `D:\ai\tool\skill\bepipred3-api` |
| PepMLM Sidecar | `D:\ai\tool\skill\pepmlm-api` |
| STAMP Backend | `D:\Desktop\靶向肽\github\前端\backend` |
| STAMP Frontend | `D:\Desktop\靶向肽\github\前端` |

### 1.2 前置依赖

- Python 3.11+
- Node.js 20+
- PowerShell 7+ (Windows)
- BepiPred3 模型权重已下载
- PepMLM-650M 模型权重已下载

---

## 2. 启动 BepiPred3 Sidecar

打开 **第一个 PowerShell** 窗口：

```powershell
cd D:\ai\tool\skill\bepipred3-api
.\start-bepipred3-sidecar.ps1 -Warmup
```

验证状态：

```powershell
.\check-bepipred3-sidecar.ps1
```

预期输出：
```
Sidecar health: OK
Model info: { model_loaded: true, device: cpu, ... }
```

> **注意**：当前为 CPU 模式，首次预热可能需要 30–60 秒。

---

## 3. 启动 PepMLM Sidecar (REAL_MODEL)

打开 **第二个 PowerShell** 窗口：

```powershell
cd D:\ai\tool\skill\pepmlm-api
.\start-pepmlm-sidecar.ps1 -Warmup
```

验证状态：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:5011/health"
```

预期输出包含 `model_loaded: true` 和 `real_model: true`。

> **注意**：PepMLM-650M REAL_MODEL 在 CPU 上加载可能需要 1–3 分钟。

---

## 4. 启动 STAMP Backend

打开 **第三个 PowerShell** 窗口：

```powershell
cd D:\Desktop\靶向肽\github\前端\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证状态：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health"
```

预期返回 `{"status":"ok"}`。

---

## 5. 启动前端

打开 **第四个 PowerShell** 窗口：

```powershell
cd D:\Desktop\靶向肽\github\前端
npm run dev
```

前端默认运行在 `http://127.0.0.1:3000`。

---

## 6. 执行一体化 Workflow 脚本

打开 **第五个 PowerShell** 窗口：

```powershell
cd D:\Desktop\靶向肽\github\前端\backend\scripts
python run_bepipred3_to_pepmlm_workflow.py
```

脚本将自动执行：
1. 创建 Project
2. 创建 TargetProtein（默认 BSA N-terminal fragment，~200 aa）
3. 创建并运行 BepiPred3 scan job
4. Persist BepiPred3 结果 → `epitope_scans` + `epitope_candidates`
5. 选择 top-1 表位
6. 创建并运行 PepMLM generation job
7. Persist PepMLM 结果 → `stamp_generation_runs` + `stamp_candidates`
8. 输出报告到 `D:\ai\product\kimi\agent-bridge\reports\V010_P4_INTEGRATED_WORKFLOW_RUN_REPORT.md`

预期输出示例：
```
=== P4 WORKFLOW COMPLETE ===
Project ID: <uuid>
Epitope Scan ID: <uuid>
Selected Epitope: <uuid>
Generation Run ID: <uuid>
Stamp Candidates: 5
  #1: TAKASLALALAAAIG | PPL=10.73 | source=pepmlm_650m_real
  ...
```

> 如果 BepiPred3 返回零候选，workflow 会**诚实终止**，不伪造数据。这是完全正常的科学结果。

---

## 7. 打开结果页

### 7.1 前端查看

1. 打开浏览器访问 `http://127.0.0.1:3000`
2. 进入项目列表，找到刚创建的项目
3. 点击 **Epitope Screening** 查看表位候选
4. 点击 **Project Results** 查看生成的靶向肽
5. 点击 **Final Ranking** 查看排序后的最终候选

### 7.2 直接通过 URL 访问

```
http://127.0.0.1:3000/epitope-screening?scan_id=<scan_id>
http://127.0.0.1:3000/projects/<project_id>/results
http://127.0.0.1:3000/final-ranking?projectId=<project_id>
```

---

## 8. 常见错误与解决

### 8.1 端口 5001 未启动（BepiPred3 sidecar）

**现象**：
- BepiPred3 job 创建后迅速 `failed`
- 错误信息包含 `[SIDECAR_UNAVAILABLE]`

**解决**：
```powershell
cd D:\ai\tool\skill\bepipred3-api
.\start-bepipred3-sidecar.ps1 -Warmup
```

---

### 8.2 端口 5011 未启动（PepMLM sidecar）

**现象**：
- PepMLM job 创建后迅速 `failed`
- 错误信息包含 `[SIDECAR_UNAVAILABLE]` 或连接超时

**解决**：
```powershell
cd D:\ai\tool\skill\pepmlm-api
.\start-pepmlm-sidecar.ps1 -Warmup
```

---

### 8.3 端口 8000 未启动（STAMP backend）

**现象**：
- 前端页面显示 "无法连接到后端"
- API 请求返回 `ERR_CONNECTION_REFUSED`

**解决**：
```powershell
cd D:\Desktop\靶向肽\github\前端\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---

### 8.4 KimiCode session expired

**现象**：
- Kimi Code Web UI 报错：`Authentication failed. Your login session may have expired. Please run "/login" to sign in again.`

**解决**：
1. 在 Kimi Code Web UI 输入 `/login`
2. 按提示重新扫码登录
3. 登录后检查当前任务状态（git status、pytest、npm build）
4. 确认无未提交修改后再继续新功能

---

### 8.5 GitHub push failed

**现象**：
- `git push` 报错：`fatal: unable to access 'https://github.com/...': Failed to connect to github.com port 443 after ...`

**解决**：
- 当前 HTTPS 网络不稳定，**不阻塞本地开发**
- 继续本地 commit，待网络恢复后再 push
- 或者配置 SSH key + VPN 后再试

---

### 8.6 BepiPred3 CPU 推理超时

**现象**：
- Job 长时间 `running` 后 `failed`
- 错误：`[SIDECAR_TIMEOUT]`

**解决**：
- 缩短输入序列长度（推荐 ≤200 aa 用于演示）
- 等待后端自动重试（如已配置）
- 手动点击 **Retry Job**

动态超时策略：
- ≤100 aa = 60s
- 101–500 aa = 180s
- >500 aa = 300s

---

### 8.7 PepMLM REAL_MODEL 加载慢

**现象**：
- PepMLM job `running` 状态持续 1–3 分钟

**解决**：
- 这是正常的 CPU 加载时间，请耐心等待
- 如需加速，后续版本将评估 GPU 支持

---

## 9. 快速验证清单

演示前请确认：

- [ ] BepiPred3 sidecar 运行在 `http://127.0.0.1:5001`
- [ ] PepMLM sidecar 运行在 `http://127.0.0.1:5011`
- [ ] STAMP backend 运行在 `http://127.0.0.1:8000`
- [ ] 前端 dev server 运行在 `http://127.0.0.1:3000`
- [ ] `backend/scripts/run_bepipred3_to_pepmlm_workflow.py` 可正常执行
- [ ] pytest 314 passed（可选，用于展示代码质量）

---

## 10. 科研真实性提示

演示时请明确告知观众：

> "当前展示的是**计算预测与模型生成**结果，所有候选均标注为 **NOT_EXPERIMENTALLY_VALIDATED**。我们尚未进行结构预测、分子对接或湿实验验证，因此不能得出‘该肽具有抗菌活性’或‘该肽无毒’等结论。"

---

*手册生成时间*: 2026-05-09  
*生成人*: KimiCode
