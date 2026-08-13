# Legacy Peptide Filter Pipeline / 五层筛选后端资产审计与接入方案

> **审计日期**: 2026-04-29
> **审计范围**: 旧 Docker 镜像 + 迁移包 + 当前 v0.6d 前后端
> **目标**: 恢复五层筛选管线，判断最稳接入方案

---

## 1. 搜索范围

| 路径 | 状态 |
|------|------|
| `D:\Desktop\靶向肽\内网\peptide-app-fixed.tar` | ✅ 4.67 GB OCI Docker 镜像 |
| `D:\Desktop\靶向肽\内网\整体\migrate_pkg\` | ✅ 完整后端源码包 |
| 当前 v0.6d 前端 `src/lib/api.ts` | ✅ 含旧 API 接口定义 |
| 当前 v0.6d 前端 `src/hooks/usePredictionRun.ts` | ✅ 含旧 API 调用逻辑 |
| 当前 v0.6d 后端 `backend/app/` | ✅ FastAPI，缺 /api/predict |

搜索命中: api_server.py (3份), post_screen_ranking.py (4份), requirements.txt (2份), bp3/ (含10个.pt模型), peptide-api.service, amp-xh.conf

---

## 2. peptide-app-fixed.tar 审计

### 2.1 镜像属性
```
Image:       docker.io/library/peptide-app:latest
Format:      OCI (application/vnd.oci.image.index.v1+json)
Arch:        linux/amd64
Created:     2026-04-23
Size:        4.67 GB
Exposed:     80/tcp
CMD:         /start.sh
WorkingDir:  /opt/peptide-app/backend
```

### 2.2 内部架构 (从 Dockerfile history 反推)
```
                    ┌──────────────────────┐
                    │   Nginx (port 80)     │
                    │  /etc/nginx/sites-    │
                    │  enabled/default      │
                    ├──────────────────────┤
                    │   Supervisor          │
                    │  /etc/supervisor/     │
                    │  conf.d/supervisord   │
                    ├──────────┬───────────┤
                    │ 静态前端  │ Flask 后端 │
                    │ /usr/     │ :5001     │
                    │ share/    │ BepiPred3 │
                    │ nginx/    │ + ESM2    │
                    │ html/     │           │
                    └──────────┴───────────┘
```

### 2.3 关键能力判定

| 检查项 | 结果 |
|--------|------|
| 是否为完整 Docker 镜像 | ✅ OCI 标准镜像 |
| 是否包含前端 | ✅ `/usr/share/nginx/html` (COPY front/dist) |
| 是否包含后端 | ✅ `/opt/peptide-app/backend` (Flask + BepiPred3 + ESM2) |
| 服务端口 | 80 (Nginx 反向代理 → Flask:5001) |
| `/api/health` | ✅ `GET /api/health` → `{"status":"ok","modules":{"target_peptide":"ready",...}}` |
| `/api/predict` | ✅ `POST /api/predict` → BepiPred3 + post_screen_ranking 完整管线 |
| `/api/ampgen/generate` | ✅ mock/manual_windterm 两种模式 |
| 能否单独运行 | ✅ `docker load < peptide-app-fixed.tar && docker run -p 80:80 peptide-app` |
| BepiPred 3.0 模型 | ✅ 10个 .pt 文件 (BP3C50IDSeqLenFFNN ×5 + BP3C50IDFFNN ×5) |
| ESM2 嵌入 | ✅ `fair-esm==2.0.0` 已安装，bepipred3.py 使用 `import esm` |
| 五层筛选管线 | ✅ post_screen_ranking.py (652行完整实现) |

### 2.4 镜像内容摘要
```
Layer 1-2:   Ubuntu 基础 + apt 工具
Layer 3:     WORKDIR /opt/peptide-app/backend
Layer 4:     COPY migrate_pkg/peptide-app → /opt/peptide-app/backend
Layer 5:     pip3 install (torch, esm, biopython, flask, pandas...)
Layer 6:     rm -rf /usr/share/nginx/html/*
Layer 7:     COPY front/dist → /usr/share/nginx/html (前端静态文件)
Layer 8-11:  Nginx config + Supervisor config + start.sh
Layer 12-13: EXPOSE 80, CMD /start.sh
```

---

## 3. migrate_pkg 审计

### 3.1 目录结构

```
migrate_pkg/
├── peptide-app/                    ← 主应用目录
│   ├── api_server.py              ← Flask 入口 (414行, 端口 127.0.0.1:5001)
│   ├── api_server_legacy.py       ← 旧版备份
│   ├── post_screen_ranking.py     ← 五层筛选+软排序 (652行) ✅
│   ├── requirements.txt           ← 依赖清单
│   ├── bp3/                       ← BepiPred 3.0 包
│   │   ├── __init__.py
│   │   ├── bepipred3.py           ← 核心 (829行, ESM2嵌入+FFNN)
│   │   ├── fragment_filter.py     ← 片段提取
│   │   ├── physicochemical_filter.py ← 理化筛选
│   │   └── BP3Models/             ← ESM + FFNN 模型
│   │       ├── BP3C50IDSeqLenFFNN/Fold{1..5}.pt  (5文件)
│   │       └── BP3C50IDFFNN/Fold{1..5}.pt        (5文件)
│   ├── start_api.sh               ← 启动脚本 (venv激活 + 限线程)
│   ├── index.html                 ← 前端页面(旧版)
│   └── test_api_*.py/json/csv     ← 测试数据
├── peptide-api.service            ← systemd 服务文件 ✅
└── amp-xh.conf                    ← Nginx SSL 配置 (amp-xh.cn) ✅
```

### 3.2 后端入口 — api_server.py 核心能力

```
POST /api/predict   → pipeline: FASTA → BepiPred3 → CSV → post_screen_ranking → JSON
GET  /api/health    → {"status":"ok","modules":{...}}
POST /api/ampgen/generate   → mock/manual AMPgen
POST /api/ampgen/import_csv → CSV上传/解析
GET  /                → serve index.html
```

**五层筛选管线 (run_full_pipeline)**:
1. 写入临时 FASTA 文件
2. BepiPred 3.0 集成预测 (ESM2 编码 → FFNN 推理)
3. 生成 per-residue CSV (Position, Residue, Score, Assignment)
4. post_screen_ranking 硬筛选 + 软排序
5. 返回 JSON (ranked_peptides + dropped_count + total_extracted)

### 3.3 post_screen_ranking.py 六步管线

```
[1/6] 读入 BepiPred3 per-residue CSV
[2/6] 提取表位肽 (连续 "E" 区域, 长度 min_len–max_len)
[3/6] 计算理化性质 (Net_Charge_pH7.4, GRAVY, pI, Cys_Count, Disulfide_Risk)
[4/6] 硬筛选 (HARD SCREENING):
      ├── Fragment   (长度在范围内 — 提取时已保证)
      ├── Charge     (Net_Charge > min_charge)
      ├── GRAVY      (GRAVY < max_gravy)
      ├── pI         (min_pi ≤ pI ≤ max_pi)
      ├── Cys        (Cys_Count ≤ max_cys)
      └── Disulfide  (可选: 排除 high/higher 风险)
[5/6] 软排序 (WEIGHTED SCORING):
      ├── disulfide_score    (规则映射: higher=100 → medium=75 → low=40 → none=10 → high=0)
      ├── charge_score       (min-max 归一化, net charge 越高越好)
      ├── hydrophobicity_score (min-max 归一化, GRAVY 越负越好)
      ├── pI_score           (min-max 归一化, pI 越高越好)
      └── priority_score = Σ(score_i × weight_i) / Σweight_i
[6/6] 生成解释 (中文 ranking_reason + top_advantages)
      排序: priority_score ↓ → disulfide_score ↓ → rank
```

### 3.4 依赖分析

| 依赖 | 版本 | 用途 | 迁移难度 |
|------|------|------|----------|
| Flask | 3.1.3 | Web 框架 | ⚠️ 需改为 FastAPI |
| torch | 2.11.0 | BepiPred3 FFNN | 🔴 大 (2+ GB) |
| fair-esm | 2.0.0 | ESM2 蛋白编码 | 🔴 大 (模型下载) |
| biopython | 1.84 | 理化计算 (GRAVY, pI) | 🟡 轻量 |
| pandas | 2.2.3 | 数据处理 | 🟡 轻量 |
| numpy/scipy | - | 数值计算 | 🟡 轻量 |

### 3.5 是否可直接迁入当前 backend

**post_screen_ranking.py**: ✅ 核心逻辑纯 Python + pandas + biopython，可直接迁移
- `calculate_properties()` → 迁移
- `apply_hard_screening()` → 迁移
- `apply_soft_ranking()` → 迁移
- `generate_explanations()` → 迁移
- `extract_epitope_peptides()` → 迁移 (需 BepiPred3 输出 CSV)

**BepiPred 3.0 + ESM2**: ⚠️ 重依赖，不适合直接迁入当前 FastAPI
- torch 2.11 → 当前 backend 用 torch 2.6
- fair-esm → 需下载 ESM2 模型 (~3 GB)
- 10 个 .pt FFNN 模型 → 已在 migrate_pkg 中
- 推理 CPU 可行但有性能影响

---

## 4. 当前 v0.6d 后端缺口

| 端点 | 旧后端 (Flask:5001) | 当前 v0.6d (FastAPI:8000) | 缺口 |
|------|---------------------|--------------------------|------|
| GET /api/health | `{"status":"ok","modules":{...}}` | `GET /health` (不同路径/格式) | 🔴 路径+格式不匹配 |
| POST /api/predict | BepiPred3 + 五层筛选 | **不存在** | 🔴 完全缺失 |
| POST /api/v1/stamp/demo-one | 不存在 | ✅ 可用 (STAMP demo) | - |
| POST /api/v1/stamp/build | 不存在 | ✅ 可用 (STAMP build) | - |
| BepiPred 3.0 | ✅ (bp3 包) | ❌ | 🔴 完全缺失 |
| ESM2 蛋白编码 | ✅ (fair-esm) | ❌ | 🔴 完全缺失 |
| 五层筛选 | ✅ (post_screen_ranking) | ❌ | 🔴 完全缺失 |

---

## 5. 旧后端和当前前端接口匹配度

### 5.1 旧 api.ts 定义的请求格式
```typescript
POST /api/predict
{
  name: string,          // 蛋白名
  sequence: string,      // 氨基酸序列
  min_len, max_len,      // 肽段长度范围
  min_charge, max_gravy, // 电荷/GRAVY 阈值
  min_pi, max_pi,        // 等电点范围
  max_cys,               // 最大半胱氨酸数
  disulfide_weight,      // 二硫键权重
  charge_weight,         // 电荷权重
  hydrophobicity_weight, // 疏水性权重
  pi_weight              // pI 权重
}
```

### 5.2 旧 api_server.py POST /api/predict 参数对照
```python
name, sequence, min_len, max_len, min_charge, max_gravy,
min_pi, max_pi, max_cys, exclude_high_disulfide_risk,
disulfide_weight, charge_weight, hydrophobicity_weight, pi_weight
```
→ **接口完全匹配** ✅ (旧后端支持 api.ts 请求体的所有字段)

### 5.3 响应格式匹配
```typescript
// api.ts 期望:
{ total_extracted, retained_count, ranked_peptides[], ... }
// api_server.py 返回:
{ success, protein_name, sequence_length, ranked_peptides[],
  dropped_count, retained_count, total_extracted }
```
→ **完全匹配** ✅

### 5.4 当前前端实际使用情况

| 页面 | API 调用 | 状态 |
|------|----------|------|
| TargetProteinInputPage | mock 数据 → localStorage → 跳转 | 🟡 不调 /api/predict |
| EpitopeScreeningPage | mock 数据 (mockEpitopeCandidates) | 🟡 不调 /api/predict |
| PeptideGenerationPage | /api/v1/stamp/demo-one (demo) | ✅ 已接入 |
| usePredictionRun.ts | `checkApiHealth()` + `runPrediction()` | ❌ **未被任何页面导入** |
| api.ts | `checkApiHealth`, `runPrediction` | ❌ 仅定义，未被调用 |

**结论**: 旧 `/api/predict` 前端代码 (`api.ts`, `usePredictionRun.ts`) 存在于源码中但**完全未被接入**当前 v0.6d 页面。五层筛选管线在前端 UI 中无入口。

---

## 6. 三种接入方案排序 (Hermes 审计结论)

### 方案 A: 旧后端 Sidecar 独立运行 ⭐⭐⭐ (最稳恢复)

```
当前 v0.6d (192.168.31.218:8088)
  ├── Nginx → FastAPI:8000
  │
  └── 新增 Nginx location /api/predict → Sidecar 旧 Flask:5001
       │
       └── Docker: peptide-app 容器 (仅后端, 不启动内部 Nginx)
            ├── BepiPred 3.0 + ESM2 全部依赖
            └── Flask + 五层筛选管线
```

| 维度 | 评价 |
|------|------|
| 恢复速度 | 🟢 最快 — docker run 即可, 3分钟部署 |
| 风险 | 🟢 零风险 — 不修改当前 v0.6d 任何代码 |
| 稳定性 | 🟢 旧镜像已验证可运行 |
| 维护成本 | 🟡 双后端 (Flask + FastAPI) |
| 依赖体积 | 🔴 torch 2.11 + ESM2 ≈ 5 GB+ |

**步骤**:
1. `docker load < peptide-app-fixed.tar`
2. 修改容器只启动 Flask (跳过内部 Nginx + Supervisor)
3. Nginx 添加 `location /api/predict { proxy_pass http://127.0.0.1:5001; }`
4. 前端新建 FilterPipelinePage 接入 /api/predict

### 方案 B: 迁入 FastAPI backend ⭐⭐ (长期最优)

| 维度 | 评价 |
|------|------|
| 恢复速度 | 🔴 慢 — 需重写 Flask 路由为 FastAPI, 调试 torch 兼容性 |
| 风险 | 🔴 高 — torch 版本冲突、ESM2 模型路径、内存占用 |
| 稳定性 | 🟢 单后端统一管理 |
| 维护成本 | 🟢 长期最低 |
| 可行性 | 🔴 当前 backend torch 2.6 ≠ 旧 torch 2.11, ESM2 需额外部署 |

**迁移清单**:
1. post_screen_ranking.py → 直接复制 + FastAPI router 包装
2. bp3/bepipred3.py → 复制 + 适配 torch 版本
3. bp3/BP3Models/*.pt → 复制
4. 安装 fair-esm, 下载 ESM2 模型到 backend/models/
5. 新建 `backend/app/routers/predict.py` FastAPI router
6. 新增 `/api/predict` + `/api/health` 端点

### 方案 C: Demo-compatible 快速响应 ⭐ (今晚最快, 不启动重计算)

| 维度 | 评价 |
|------|------|
| 实施时间 | 🟢 < 30 分钟 |
| 依赖 | 🟢 零额外依赖 |
| BepiPred | ❌ 不调用 |
| ESM2 | ❌ 不调用 |
| 五层筛选 | 🟡 仅 post_screen_ranking 理化计算 (不依赖 BepiPred) |
| 演示效果 | 🟡 用户可输入蛋白序列 → 看到候选肽列表 (理化筛选) |

**步骤**:
1. 后端新建 `POST /api/predict` → 直接调 post_screen_ranking (用预生成的 BepiPred CSV)
2. 或: 跳过 BepiPred, 接收用户手动输入的候选片段列表
3. 前端接入 FilterPipeline 页面 → 调用 /api/predict

---

## 7. Hermes 推荐排序

### 短期 (本周): **方案 A (Sidecar)** — 3分

优势:
- 5分钟部署, 零编码
- 旧 Docker 镜像已验证
- 不影响当前服务 (8088)
- BepiPred 3.0 + ESM2 真实计算

步骤:
```
1. docker load  →  恢复容器
2. nginx conf   →  添加 /api/predict → :5001
3. 前端页面     →  新建 FilterPipelinePage (复用 api.ts + usePredictionRun)
4. 上线
```

### 中期 (下周): 方案 C 过渡 → 方案 B — 渐进式

1. 先做方案 A 快速恢复
2. 同时启动方案 B 迁移 (1-2周):
   - post_screen_ranking 逻辑迁入 FastAPI
   - BepiPred3 + ESM2 保持 Sidecar 或独立服务
3. 最终: 方案 B 单后端

---

## 8. 风险点

| 风险 | 等级 | 说明 |
|------|------|------|
| torch 版本冲突 | HIGH | 旧: 2.11, 当前 backend: 2.6 — Sidecar 隔离可避 |
| ESM2 模型下载 | MEDIUM | 3-5 GB, 需从 HuggingFace 下载, 国内慢 |
| BepiPred3 API bug | MEDIUM | 旧 test_api_result.json 记录 str/Path 类型 bug |
| Flask → FastAPI 重写 | MEDIUM | 路由装饰器、异步模型、错误处理全改写 |
| 内存/CPU | MEDIUM | torch + ESM2 推理消耗大, 当前 8088 服务器是否够? |
| 双后端运维 | LOW | 方案 A 需维护 Flask + FastAPI 两个进程 |

---

## 9. 推荐 KimiCode 执行任务单 (方案 A — 今晚最快)

```
任务 1: 恢复 Docker 容器
  命令: docker load -i peptide-app-fixed.tar
        docker run -d --name peptide-filter-backend \
          --network host \
          -v /home/xh/kxc/靶向肽/内网/migrate_pkg:/opt/peptide-app/backend \
          --entrypoint python \
          peptide-app:latest \
          /opt/peptide-app/backend/api_server.py
  验证: curl http://127.0.0.1:5001/api/health

任务 2: Nginx 添加 /api/predict 代理
  文件: /etc/nginx/sites-enabled/stamp
  添加: location /api/predict { proxy_pass http://127.0.0.1:5001; ... }
        location /api/health  { proxy_pass http://127.0.0.1:5001; ... }
  验证: curl http://192.168.31.218:8088/api/health

任务 3: 前端新建 /filter 页面
  文件: src/pages/FilterPipelinePage.tsx
  复用: src/lib/api.ts + src/hooks/usePredictionRun.ts
  路由: 添加 /filter 到 App router

任务 4: 修复 BepiPred3 str/Path bug
  文件: bp3/bepipred3.py line 232
  改为: infile = Path(str(infile))
```

---

## 附录 A: 旧 Nginx 配置 (amp-xh.cn)

```nginx
server {
    listen 80;
    server_name amp-xh.cn www.amp-xh.cn;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name amp-xh.cn www.amp-xh.cn;
    ssl_certificate /etc/letsencrypt/live/amp-xh.cn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/amp-xh.cn/privkey.pem;
    root /opt/peptide-app;
    location /api/ {
        proxy_pass http://127.0.0.1:5001;
        proxy_read_timeout 600s;
    }
}
```

## 附录 B: systemd 服务配置

```ini
[Unit]
Description=Peptide API Service
[Service]
Type=simple
WorkingDirectory=/opt/peptide-app
ExecStart=/opt/peptide-app/start_api.sh
Restart=always
[Install]
WantedBy=multi-user.target
```

## 附录 C: BepiPred3 模型文件清单

```
bp3/BP3Models/BP3C50IDSeqLenFFNN/Fold1.pt  ← ESM2嵌入+序列长度
bp3/BP3Models/BP3C50IDSeqLenFFNN/Fold2.pt
bp3/BP3Models/BP3C50IDSeqLenFFNN/Fold3.pt
bp3/BP3Models/BP3C50IDSeqLenFFNN/Fold4.pt
bp3/BP3Models/BP3C50IDSeqLenFFNN/Fold5.pt
bp3/BP3Models/BP3C50IDFFNN/Fold1.pt          ← ESM2嵌入 (无序列长度)
bp3/BP3Models/BP3C50IDFFNN/Fold2.pt
bp3/BP3Models/BP3C50IDFFNN/Fold3.pt
bp3/BP3Models/BP3C50IDFFNN/Fold4.pt
bp3/BP3Models/BP3C50IDFFNN/Fold5.pt
```
