# BepiPred3 用户工作流指南

> **适用范围**：BepiPred3 计算表位预测工作流  
> **版本**：v0.10-P2e  
> **最后更新**：2026-05-09

---

## 1. 适用范围与边界

本文档指导用户通过 STAMP 平台使用 **BepiPred3** 进行计算表位预测。

**本工作流提供的是**：
- 基于 BepiPred3 模型的计算预测结果
- 候选表位的排序与展示
- 非实验性验证的初步筛选

**本工作流不提供的是**：
- 实验验证数据（MIC、MBC、溶血性、毒性等）
- 结构预测（AlphaFold/FoldX 对接评分、ipTM、pDockQ、ΔG）
- 湿实验（wet-lab）确认结果

所有候选表位的状态为：
- `validation_status`: `NOT_EXPERIMENTALLY_VALIDATED`
- `prediction_status`: `COMPUTATIONAL_PREDICTION_ONLY`

---

## 2. 环境准备

### 2.1 目录结构

| 组件 | 路径 |
|------|------|
| BepiPred3 Sidecar | `D:\ai\tool\skill\bepipred3-api` |
| STAMP Backend | `D:\Desktop\靶向肽\github\前端\backend` |
| STAMP Frontend | `D:\Desktop\靶向肽\github\前端` |

### 2.2 前置依赖

- Python 3.11+
- Node.js 20+ (前端开发)
- PowerShell 7+ (Windows)
- BepiPred3 模型权重已下载

---

## 3. 启动 BepiPred3 Sidecar

打开 PowerShell，执行：

```powershell
cd D:\ai\tool\skill\bepipred3-api
.\setup-bepipred3-sidecar.ps1      # 首次运行：安装依赖
.\start-bepipred3-sidecar.ps1 -Warmup  # 启动并预热模型
```

验证 sidecar 运行状态：

```powershell
.\check-bepipred3-sidecar.ps1
```

预期输出：
```
Sidecar health: OK
Model info: { model_loaded: true, device: cpu, ... }
```

> **注意**：当前 sidecar 运行在 **CPU 模式**。长序列（>500 氨基酸）推理可能需要数分钟。GPU 支持将在后续版本中评估。

---

## 4. 启动 STAMP Backend

在另一个 PowerShell 窗口中执行：

```powershell
cd D:\Desktop\靶向肽\github\前端\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

验证 backend 运行状态：

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/health"
```

---

## 5. 启动前端（开发模式）

在第三个 PowerShell 窗口中执行：

```powershell
cd D:\Desktop\靶向肽\github\前端
npm run dev
```

前端默认运行在 `http://127.0.0.1:3000`。

---

## 6. 用户工作流步骤

### 步骤 1：创建 Project

在浏览器中打开 `http://127.0.0.1:3000`，点击 **New Project**，填写：
- **Name**: 例如 "BSA Epitope Screening"
- **Species**: 例如 "Bovine"
- **Project Type**: "epitope_screening"

### 步骤 2：创建 Target Protein（可选）

在 Project 页面中，可以创建 Target Protein 并输入氨基酸序列。

### 步骤 3：创建 BepiPred3 Job

在 Project 的 Jobs 标签页中：
1. 点击 **Create Job**
2. 选择 **Job Type**: `bepipred3_scan`
3. 输入氨基酸序列（或通过 Target Protein 引用）
4. 点击 **Create**

Job 创建后状态为 `pending`。

### 步骤 4：启动异步 Job

在 Job 详情页面中：
1. 点击 **Start Async Job**（蓝色按钮）
2. Job 状态变为 `running`
3. 页面自动轮询，显示进度条

> **同步执行**：也可以点击 **Run Sync** 进行同步执行，但会阻塞页面，不推荐用于长序列。

### 步骤 5：查看 Job Status

Job 执行期间：
- `pending`：等待启动
- `running`：BepiPred3 推理中（CPU 模式可能较慢）
- `succeeded`：推理完成
- `failed`：推理失败（见第 9 节错误处理）
- `cancelled`：用户取消

**取消 Job**：在 `running` 或 `pending` 状态下，点击 **Cancel Job** 按钮。

### 步骤 6：Persist Results

Job 状态变为 `succeeded` 后：
1. 点击 **Persist BepiPred3 Results**
2. 系统将结果写入 `epitope_scans` 和 `epitope_candidates` 表
3. 生成 `scan_id`

### 步骤 7：打开 Epitope Screening Page

Persist 成功后，可以：
- 点击页面中的链接直接跳转到 **Epitope Screening Page**
- 或在浏览器中访问：`http://127.0.0.1:3000/epitope-screening?scan_id=<scan_id>`

### 步骤 8：查看候选表位

Epitope Screening Page 展示：
- 候选表位序列
- Ranking Score（BepiPred3 预测得分）
- Source（`bepipred3`）
- 半胱氨酸标记（Cys）
- 过滤与排序选项

---

## 7. 页面字段解释

| 字段 | 含义 |
|------|------|
| **NOT_EXPERIMENTALLY_VALIDATED** | 该候选未经过实验验证，仅基于计算预测 |
| **COMPUTATIONAL_PREDICTION_ONLY** | 预测结果仅来自算法模型，非实验数据 |
| **BepiPred3 HTTP Sidecar** | 后端通过 HTTP 调用本地 BepiPred3 sidecar 进行推理 |
| **Cys** | 半胱氨酸标记，指示序列中是否包含 Cys 残基（影响后续二硫键设计） |
| **Source** | 候选来源，此处固定为 `bepipred3` |
| **Ranking Score** | BepiPred3 模型的预测得分，用于候选排序 |

---

## 8. 空结果解释

**candidate_count = 0 不代表系统失败。**

空结果是一个完全有效的科学结果，意味着：
- BepiPred3 sidecar 正常运行并完成推理
- 但当前过滤条件（最小/最大长度、得分阈值等）下没有候选通过筛选

**系统不会伪造候选。** 如果 BepiPred3 返回空结果，页面上不会显示任何虚假数据。

**建议**：
- 检查输入序列长度（过短可能导致无候选）
- 调整过滤参数（如放宽长度范围）
- 确认输入序列是有效的氨基酸序列

---

## 9. 错误处理

### 9.1 Sidecar 未启动

**现象**：Job 创建成功但启动后迅速 `failed`，错误信息包含 `[SIDECAR_UNAVAILABLE]`。

**解决**：
```powershell
cd D:\ai\tool\skill\bepipred3-api
.\start-bepipred3-sidecar.ps1 -Warmup
```

### 9.2 CPU 推理超时

**现象**：Job 长时间 `running` 后 `failed`，错误信息包含 `[SIDECAR_TIMEOUT]`。

**原因**：当前为 CPU 模式，长序列推理耗时较长。

**解决**：
- 缩短输入序列长度
- 等待后端自动重试（如已配置）
- 手动点击 **Retry Job** 按钮重试

> 动态超时策略：≤100 aa = 60s，101–500 aa = 180s，>500 aa = 300s。

### 9.3 Job Failed

**现象**：Job 状态变为 `failed`。

**解决**：
1. 查看 Job 详情中的 `error_message`
2. 根据错误前缀判断原因：
   - `[SIDECAR_TIMEOUT]` → 超时，重试或缩短序列
   - `[SIDECAR_UNAVAILABLE]` → sidecar 未运行，启动 sidecar
   - `[INVALID_INPUT]` → 检查输入序列格式
   - `[INTERNAL_ERROR]` → 后端内部错误，联系开发者

### 9.4 Job Cancelled

**现象**：Job 状态变为 `cancelled`。

**原因**：用户点击了 Cancel 按钮，或系统资源不足时自动取消。

**解决**：点击 **Retry Job** 按钮重新创建并执行 Job。

### 9.5 Retry Failed Job

在 `failed` 或 `cancelled` 状态下：
1. 点击 **Retry Job**（琥珀色按钮）
2. 系统创建一个新的 `pending` Job，复制原 Job 的输入参数
3. 旧 Job 保留用于审计
4. 新 Job 可再次 **Start Async Job**

---

## 10. 一键演示脚本

用户也可以直接使用一键演示脚本，无需手动操作前端：

```powershell
cd D:\Desktop\靶向肽\github\前端\scripts\demo
.\run-bepipred3-demo.ps1
```

脚本将自动完成：创建 project → 创建 job → 启动 → 轮询 → persist → 查询 candidates → 输出报告。

---

## 11. 科研真实性边界

本工作流严格遵守以下边界：

| 指标 | 是否包含 | 说明 |
|------|----------|------|
| MIC（最低抑菌浓度） | ❌ 否 | 未经过实验测定 |
| MBC（最低杀菌浓度） | ❌ 否 | 未经过实验测定 |
| Hemolysis（溶血性） | ❌ 否 | 未经过实验测定 |
| Toxicity（毒性） | ❌ 否 | 未经过实验测定 |
| ipTM（界面预测 TM-score） | ❌ 否 | 未进行结构预测 |
| pDockQ（对接质量评分） | ❌ 否 | 未进行分子对接 |
| ΔG（结合自由能） | ❌ 否 | 未进行热力学计算 |
| Docking Score | ❌ 否 | 未进行分子对接 |
| Wet-lab Validation | ❌ 否 | 仅计算预测 |

所有候选表位的元数据：
- `validation_status` = `NOT_EXPERIMENTALLY_VALIDATED`
- `prediction_status` = `COMPUTATIONAL_PREDICTION_ONLY`

---

## 12. 相关文档

- [BepiPred3 开发者运行手册](./BEPIPRED3_DEVELOPER_RUNBOOK.md)
- STAMP 平台 README
- Agent Bridge 报告目录：`D:\ai\product\kimi\agent-bridge\reports\`
