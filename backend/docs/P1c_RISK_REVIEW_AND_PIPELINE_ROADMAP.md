# v0.6d-P1c Demo-compatible 风险复核与真实 Pipeline 接入路线报告

> **复核日期**: 2026-04-29
> **复核人**: Hermes Agent
> **版本**: v0.6d-P1c Demo-compatible 方案风险复核

---

## 1. KimiCode C 方案科学边界复核

### 1.1 实施范围确认

| 实施项 | 状态 | 说明 |
|--------|------|------|
| `/filter` 前端页面 | ✅ 已完成 | PeptideFilterPage + 全部子组件 |
| `/demo` 前端页面 | ✅ 已完成 | 同 PeptideFilterPage |
| peptideFilterStore (Zustand) | ✅ 已完成 | 参数管理 + 状态机 + 结果存储 |
| `api.ts` (API 接口层) | ✅ 已完成 | checkApiHealth + runPrediction |
| `usePredictionRun.ts` (Hook) | ✅ 已完成 | API 调用编排 + 错误处理 |
| HeroSection 标题 | ✅ 含 "(Demo)" | "Peptide Filter Pipeline (Demo)" |
| HeroSection 描述 | ✅ 含免责声明 | "当前为预计算示例数据演示模式" |
| ApiWarmupBanner | ✅ 含双语免责 | "预计算示例数据" + "真实 BepiPred 3.0 / ESM 推理将在后续版本接入" |
| MOCK_CANDIDATES | ✅ 示例数据 | BSA 来源序列，带完整评分字段 |
| STEP_DEFINITIONS | ✅ 无 BepiPred3 提及 | 仅描述五层筛选步骤 |
| 后端 `/api/predict` | 🔴 **缺失** | 无任何 predict 路由文件 |
| 后端 `/health` 路径 | 🔴 **不匹配** | 后端 `/health` ≠ 前端 `/api/health` |
| STAMP demo-one | ✅ **完好** | stamp.py 路由器未改动 |

### 1.2 关键判据：KimiCode C 方案边界

**C 方案承诺**: "/filter 和 /demo 页面不再 404，并能用 OprF 示例数据展示五层筛选流程"

| 判据 | 结论 |
|------|------|
| `/filter` 是否存在路由 | ✅ App.tsx 有 `<Route path="/filter" element={<PeptideFilterPage />} />` |
| `/demo` 是否存在路由 | ✅ App.tsx 有 `<Route path="/demo" element={<PeptideFilterPage />} />` |
| `usePredictionRun` 是否被页面使用 | ✅ HeroSection + RunActions 均调用 |
| API 接口层是否有 runPrediction | ✅ `api.ts` → `/api/predict` POST |
| 后端是否响应 `/api/predict` | 🔴 **404 — 端点不存在** |
| 后端是否响应 `/api/health` | 🔴 **404 — 后端为 `/health` 非 `/api/health`** |
| MOCK_CANDIDATES 是否可用于兜底 | ⚠️ 仅在 constants.ts 定义，**未被任何组件 fallback 使用** |

**边界结论**: 前端页面 "不再 404" 成立；但后端 `POST /api/predict` 300ms 内必然 404，前端无 catch 降级到 MOCK_CANDIDATES 的逻辑。

---

## 2. Demo Mode 标注是否充分

### 2.1 要求的标注 vs 实际标注

| 要求标注 | 是否存在 | 位置 |
|----------|----------|------|
| `DEMO_COMPATIBLE` | ❌ | 无 |
| `NOT_EXPERIMENTALLY_VALIDATED` | ❌ | 无 |
| `demo_precomputed` | ❌ | 无 |
| `not_real_bepipred_output` | ❌ | 无 |
| "(Demo)" | ✅ | HeroSection h1 行 27 |
| "预计算示例数据演示模式" | ✅ | HeroSection p 行 31 |
| "真实 BepiPred 3.0 / ESM 推理将在后续版本接入" | ✅ | ApiWarmupBanner 行 15 |

### 2.2 缺失标注评估

| 风险项 | 等级 | 说明 |
|--------|------|------|
| 主管可能误认为真实预测 | 🟡 **中等** | "(Demo)" 很小（text-xl），中文字号更小（text-lg），可能被忽略 |
| 缺少 DEMO_COMPATIBLE 标记 | 🟡 **中等** | 无标准化的风险标签 |
| ApiWarmupBanner 仅 warming 态显示 | 🟡 **中等** | 成功/错误态不可见，跑完即消失 |
| MOCK_CANDIDATES 无来源声明 | 🟢 低 | 序列来自 BSA 信号肽，非 OprF |

**判定**: KimiCode 标注**不够充分**。缺少 ALL_CAPS 标准化标记，且 ApiWarmupBanner 在成功态消失。

---

## 3. 是否存在伪造真实预测风险

### 3.1 禁止用语检查 (全项目扫描)

| 禁止用语 | 出现次数 | 文件 |
|----------|----------|------|
| "Real BepiPred3 prediction" | 0 | — |
| "ESM inference completed" | 0 | — |
| "experimentally validated" | 0 | — |
| "validated binder" | 0 | — |
| "real MIC" | 0 | — |
| "real pDockQ" | 0 | — |
| "real ipTM" | 0 | — |
| "real ΔG" | 0 | — |
| "BepiPred3 completed" | 0 | — |
| "表位预测完成" | 0 | — |

### 3.2 可能误导的表达

| 表达 | 文件 | 风险 |
|------|------|------|
| "Run Prediction" 按钮 | HeroSection + RunActions | 🟡 低 — "Run Prediction" 暗示真实预测，但有 "(Demo)" 平衡 |
| "Running Demo Filter" | ApiWarmupBanner | 🟢 安全 — 明确说 "Demo" |
| "从蛋白序列中发现更优候选肽段" | HeroSection | 🟡 中 — 前半句像真实功能，后半句才说明是演示 |
| "Filtering Pipeline — 5-step filtering process" | PipelineSection | 🟢 安全 — 仅描述流程结构 |

**判定**: **无伪造真实预测**。所有 MOCK_CANDIDATES 数据来自硬编码 BSA 序列片段，无任何基于 BepiPred3 / ESM 的真实计算。但 "Run Prediction" 按钮名称在无后端实际响应时容易误导。

---

## 4. 是否影响 STAMP demo-one

### 4.1 后端路由器检查

```
当前注册的路由器 (main.py 行 99-102):
  app.include_router(health.router)    → /health ✅
  app.include_router(pepmlm.router)    → /api/v1/pepmlm/* ✅
  app.include_router(amp.router)       → /api/v1/amp/* ✅
  app.include_router(stamp.router)     → /api/v1/stamp/* ✅

新增 (KimiCode 未修改):
  无新增路由器 — main.py 未改动 ✅
```

### 4.2 现有端点完整性

| 端点 | 修改前 | 修改后 | 状态 |
|------|--------|--------|------|
| `GET /health` | ✅ | ✅ | 不变 |
| `GET /api/v1/stamp/demo-one` | ✅ | ✅ | 不变 |
| `POST /api/v1/stamp/build` | ✅ | ✅ | 不变 |
| `GET /api/v1/pepmlm/candidates` | ✅ | ✅ | 不变 |
| `GET /api/v1/amp/candidates` | ✅ | ✅ | 不变 |

**判定**: ✅ STAMP demo-one **未受影响**。KimiCode 未修改任何后端路由器。

---

## 5. /filter 和 /demo 可演示性判断

### 5.1 当前实际可运行性

```
用户访问 /filter 或 /demo:
  1. PeptideFilterPage 渲染 ✅
  2. InputConsolePanel 显示输入参数 ✅
  3. 用户点击 "Run Prediction"
  4. usePredictionRun 调用 checkApiHealth()
  5. fetch("/api/health") → 后端 /health ✅ 或 404 ❌
     └─ 路径不匹配: 前端 /api/health ≠ 后端 /health → 404
  6. → 抛出错误: "API health check failed: /api/health is not reachable"
  7. ErrorBanner 显示错误 ⚠️
  8. MOCK_CANDIDATES 不会被加载 (无 fallback 逻辑) ⚠️
```

### 5.2 阻断点修复清单

| 阻断 | 修复 | 耗时 |
|------|------|------|
| 前端 `/api/health` → 后端 `/health` 路径不匹配 | 前端改为 `/health` 或后端添加 `/api/health` 别名 | 5 分钟 |
| 后端无 `/api/predict` 端点 | **必须添加 demo 适配器** | 30 分钟 |
| MOCK_CANDIDATES 无 fallback | add catch → load MOCK_CANDIDATES | 10 分钟 |

### 5.3 当前状态判定

**可演示性**: ⚠️ **当前不可演示** — 前后端路径不匹配 + 后端缺少 /api/predict 端点。

---

## 6. 当前版本给主管展示的推荐口径

### 6.1 推荐说辞

> **v0.6d-P1c Demo-compatible 肽段筛选管线**
>
> 本版本目的是**恢复旧版五层筛选管线的 UI 交互流程**，用于向团队演示从蛋白序列输入到候选肽段排序的完整过滤逻辑。
>
> **明确边界**:
> - "Run Prediction" 按钮触发的是 **预计算示例数据**（BSA 蛋白源），不调用真实 BepiPred 3.0 / ESM 推理
> - 候选肽的理化参数（电荷、GRAVY、pI、Cys）来自预计算，非实时推导
> - 本版本不产生任何可发表的生物学结论
> - 真实 BepiPred 3.0 + ESM2 五层筛选管线将在下一阶段接入（方案 A 或 B）
>
> **可演示内容**:
> - 五层筛选流程 UI（片段提取 → 电荷 → GRAVY → 等电点 → 半胱氨酸）
> - 候选肽排序与评分子系统
> - Top-3 卡片 / 数据表 / 候选详情抽屉 / 比较抽屉
> - 权重调节交互 (charge / hydrophobicity / pI / disulfide 四维权重)

### 6.2 应避免的说法

| 避免 | 原因 |
|------|------|
| "我们已经恢复了旧版预测功能" | 未恢复 — 只恢复了 UI 流程 |
| "BepiPred 3.0 表位预测已集成" | 未集成 — demo 数据不含表位预测 |
| "五层筛选是真实计算结果" | 不是 — MOCK_CANDIDATES 是硬编码 |
| "可以输入任意蛋白序列得到结果" | 不能 — 仅 BSA 示例数据 |

---

## 7. 下一阶段真实 BepiPred3/ESM 接入方案比较

### 7.1 方案矩阵

| 维度 | A: Sidecar Flask:5001 | B: 迁入 FastAPI | D: 旧 Docker 整体运行 |
|------|----------------------|-----------------|----------------------|
| **核心思路** | 旧 Flask 后端独立运行，FastAPI Nginx 代理 `/api/predict` | post_screen_ranking.py + bp3/ 直接迁入 FastAPI | 旧 Docker 镜像完整启动 |
| **最快恢复** | 🟢 即时 (docker run) | 🔴 1-2 周 (重写 FastAPI + torch 适配) | 🟡 数小时 (镜像 4.67 GB) |
| **稳定性** | 🟢 旧后端已验证，进程隔离 | 🟡 torch 2.11 vs 2.6 冲突风险 | 🟢 旧镜像已验证 |
| **维护成本** | 🟡 双后端 (Flask + FastAPI) | 🟢 单后端统一管理 | 🔴 旧 Docker 体系与当前服务平行 |
| **风险** | 🟢 零 (不修改 v0.6d) | 🔴 torch 版本冲突，ESM2 模型下载 (3-5 GB) | 🟡 端口冲突，资源占用 (5+ GB) |
| **扩展性** | 🟡 Flask 旧架构 | 🟢 FastAPI 原生 | 🔴 旧镜像不可迭代 |
| **BepiPred3** | ✅ 原生支持 | ⚠️ 需适配 torch 版本 | ✅ 原生支持 |
| **ESM2** | ✅ 已安装 | ⚠️ 需下载模型 | ✅ 已安装 |
| **五层筛选** | ✅ 完整 652 行 | ✅ 可迁入 (无外部依赖) | ✅ 完整 |
| **长期最优** | 🟡 过渡方案 | 🟢 是 | 🔴 否 |
| **回滚难度** | 🟢 移除 Nginx 规则即可 | 🔴 需 git revert | 🟡 docker stop |

### 7.2 方案 B 风险深度分析

```
┌─ torch 版本冲突 ──────────────────────────┐
│ 当前 backend: torch 2.6                    │
│ 旧 bp3:       torch 2.11                   │
│ 影响: FFNN 模型 forward() 可能不兼容       │
│ 解决: 独立 venv 或 conda env 隔离          │
└───────────────────────────────────────────┘

┌─ ESM2 模型下载 ───────────────────────────┐
│ 模型: esm2_t33_650M_UR50D (≈ 2.5 GB)     │
│ 下载: HuggingFace → 国内慢 / 可能失败     │
│ 解决: 从旧 Docker 镜像提取缓存模型        │
└───────────────────────────────────────────┘

┌─ BepiPred3 str/Path bug ──────────────────┐
│ 旧 test_api_result.json 记录:             │
│ "local variable 'device' referenced       │
│  before assignment"                       │
│ 需修复 bp3/bepipred3.py 第 232 行        │
└───────────────────────────────────────────┘

┌─ 资源占用 ────────────────────────────────┐
│ torch + ESM2 + 10 FFNN .pt ≈ 4-5 GB RAM  │
│ 服务器: 125 GB RAM 总量, 116 GB 可用 ✅   │
│ GPU: 未检测到 (free -h 无 GPU 显示)       │
│ 推理模式: CPU only (BepiPred3 慢)         │
└───────────────────────────────────────────┘
```

### 7.3 方案排序

#### 短期 — 最稳妥: 方案 A (Sidecar)
- 原因: 零风险，不修改 v0.6d 任何代码
- 耗时: **30 分钟** (docker load + Nginx 规则)
- 效果: 立即恢复真实 BepiPred3/ESM / 五层筛选
- 风险: 仅增加 1 个后台进程

#### 中期 — 最长期: 方案 A → 方案 B 渐进迁移
- 阶段 1: 方案 A Sidecar (本周)
- 阶段 2: post_screen_ranking.py 迁入 FastAPI (下周)
- 阶段 3: BepiPred3 + ESM2 独立微服务化 (下下周)
- 阶段 4: 退役 Sidecar Flask (第 4 周)

#### 长期 — 最优: 方案 B (全迁入)
- 前端已适配 FastAPI `/api/predict` 接口格式
- api.ts 的 `runPrediction()` 无需修改
- post_screen_ranking.py 纯 Python，可直接复制
- BepiPred3 需要 torch 版本适配 + ESM2 模型部署

---

## 8. 推荐方案

### 8.1 立即执行: 方案 A (Sidecar) — 最快恢复真实预测

```
服务器: 192.168.31.218

步骤 1: 加载旧 Docker 镜像
  cd /home/xh/kxc/靶向肽/内网/
  docker load -i peptide-app-fixed.tar

步骤 2: 启动 Flask 后端 (仅 API，不启动内部 Nginx)
  docker run -d --name peptide-filter-backend \
    --network host \
    -v /home/xh/kxc/靶向肽/内网/migrate_pkg/peptide-app:/opt/peptide-app/backend \
    --entrypoint python3 \
    peptide-app:latest \
    /opt/peptide-app/backend/api_server.py

步骤 3: Nginx 添加代理规则
  文件: /home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a/nginx/conf.d/stamp.conf
  新增:
    location /api/predict {
        proxy_pass http://127.0.0.1:5001;
        proxy_read_timeout 600s;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    location /api/health {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
    }
  nginx -s reload

步骤 4: 验证
  curl http://127.0.0.1:5001/api/health
  curl -X POST http://192.168.31.218:8088/api/predict \
    -H "Content-Type: application/json" \
    -d '{"name":"test","sequence":"MGILPSPG...","min_len":8,"max_len":25,...}'

步骤 5: 修复 BepiPred3 str/Path bug
  文件: /home/xh/kxc/靶向肽/内网/migrate_pkg/peptide-app/bp3/bepipred3.py
  行 232: infile = Path(str(infile))  # 原为 infile = Path(infile)
```

### 8.2 预计耗时

| 步骤 | 耗时 |
|------|------|
| docker load | 2-3 分钟 |
| docker run + 配置 | 5 分钟 |
| Nginx 规则 | 2 分钟 |
| 验证 | 3 分钟 |
| BepiPred3 bugfix | 5 分钟 |
| **合计** | **15-20 分钟** |

### 8.3 回滚方案

```bash
# 移除 Nginx 规则 → 删除新增 location 块 → nginx -s reload
docker stop peptide-filter-backend
docker rm peptide-filter-backend
# (不删除镜像和挂载的数据)
```

### 8.4 方案 B 迁移路径 (下一步)

```
第 1 周: post_screen_ranking.py → FastAPI router
  - backend/app/routers/predict.py (新建)
  - 复制 5 个计算函数 → FastAPI 端点
  - 保留 POST /api/predict 接口格式不变

第 2 周: BepiPred3 + ESM2 → 独立微服务
  - 保留 Sidecar Flask 或创建独立 docker 服务
  - FastAPI /api/predict 先调 Sidecar 获取 BepiPred3 输出 CSV
  - FastAPI 本地执行 post_screen_ranking

第 3-4 周: 退役 Sidecar
  - 迁移 BepiPred3 推理为 FastAPI 内部调用
  - 统一 torch 版本 + ESM2 路径
  - docker stop peptide-filter-backend
```

---

## 9. KimiCode 下一阶段任务单草案

### 9.1 紧急修复 (P0 — 让 /filter 可演示)

```
任务 1: 修复前端 health check 路径
  文件: src/lib/api.ts 行 11
  改: fetch("/api/health") → fetch("/health")
  验证: curl http://192.168.31.218:8088/health

任务 2: 前端添加 MOCK_CANDIDATES fallback
  文件: src/hooks/usePredictionRun.ts
  当 /api/predict 404 时，catch 中 load MOCK_CANDIDATES
  或: 当 API 不可用时，直接使用 MOCK_CANDIDATES

任务 3: 补充 DEMO_COMPATIBLE 标记
  文件: src/pages/PeptideFilterPage.tsx (顶部注释)
  添加: // DEMO_COMPATIBLE — 预计算示例数据，非真实 BepiPred3 推理
```

### 9.2 方案 A 部署 (P1 — 恢复真实预测)

```
任务 4: docker load 旧镜像
  命令: ssh 192.168.31.218 "docker load -i /home/xh/kxc/靶向肽/内网/peptide-app-fixed.tar"

任务 5: 启动 Flask Sidecar
  命令: ssh 192.168.31.218 "docker run -d --name peptide-filter-backend ..."

任务 6: 配置 Nginx 代理
  文件: /home/xh/kxc/靶向肽/releases/stamp-platform-v0.6d-P1a/nginx/conf.d/stamp.conf

任务 7: 修复 BepiPred3 bug
  文件: /home/xh/kxc/靶向肽/内网/migrate_pkg/peptide-app/bp3/bepipred3.py

任务 8: 端到端真实预测验证
  输入: OprF 序列 (或 BSA)
  验证: BepiPred3 输出 CSV → 五层筛选 → JSON 候选列表
```

---

## 10. GO / NO-GO

### 10.1 当前 v0.6d-P1c Demo-compatible 方案

| 判据 | 结论 |
|------|------|
| `/filter` 和 `/demo` 不再 404 | ⚠️ 条件成立 (路由存在) |
| 页面展示五层筛选流程 | ⚠️ 条件成立 (STEP_DEFINITIONS 完整) |
| 页面可实际运行演示 | 🔴 不成立 — 后端 /api/predict 不存在 + health 路径不匹配 |
| Demo 标注充分 | 🟡 部分 — 缺 ALL_CAPS 标准标记 |
| 无伪造真实预测 | ✅ 成立 — 0 处违规用语 |
| STAMP demo-one 完好 | ✅ 成立 — 未修改后端路由器 |

**判定: ⚠️ CONDITIONAL NO-GO — 需完成 P0 修复后再演示**

### 10.2 P0 修复后 GO 条件

1. ✅ 修复 `fetch("/api/health")` 路径
2. ✅ 添加 MOCK_CANDIDATES 404 fallback
3. ✅ 补充 `DEMO_COMPATIBLE` / `NOT_EXPERIMENTALLY_VALIDATED` 标记
4. 修复后: ✅ GO

### 10.3 方案 A Sidecar GO 条件

- docker 可用 (当前: `docker ps` 报 permission denied — 需 sudo 或加入 docker 组)
- 旧镜像文件存在: `/home/xh/kxc/靶向肽/内网/peptide-app-fixed.tar`
- 端口 5001 未被占用
- Nginx 可用 (当前: 127 not found — 需确认 Nginx 安装路径)

**风险**:
- docker 权限问题: 需要 sudo 或 docker 组配置
- Nginx 路径问题: 服务器 Nginx 不在 PATH，需找到实际安装路径

---

## 附录 A: 服务器当前状态快照

```
主机: xh-System-Product-Name (192.168.31.218)
内存: 125 GB 总量, 116 GB 可用
磁盘: 未检查
Docker: 29.2.1 (但 docker ps 无权限)
Nginx: 不在 PATH (which nginx → 127 not found)
KimiCode 工作目录: /home/xh/
当前服务: 8088 端口正常 (curl https://amp-xh.cn 可达)
```

## 附录 B: 关键文件路径索引

```
旧 Docker 镜像:  /mnt/d/Desktop/靶向肽/内网/peptide-app-fixed.tar
                → 服务器: /home/xh/kxc/靶向肽/内网/peptide-app-fixed.tar

旧迁移包:      /mnt/d/Desktop/靶向肽/内网/整体/migrate_pkg/peptide-app/
                → 服务器: /home/xh/kxc/靶向肽/内网/migrate_pkg/

旧 BepiPred3:  /mnt/d/Desktop/靶向肽/内网/整体/migrate_pkg/peptide-app/bp3/bepipred3.py
Bug 位置:      第 232 行 (infile = Path(infile) → infile = Path(str(infile)))

旧五层筛选:    /mnt/d/Desktop/靶向肽/内网/整体/migrate_pkg/peptide-app/post_screen_ranking.py

当前后端:      /mnt/d/Desktop/靶向肽/github/前端/backend/app/main.py
当前前端:      /mnt/d/Desktop/靶向肽/github/前端/src/

前端 /filter:  src/pages/PeptideFilterPage.tsx (+ 路由 App.tsx:43)
前端 API:      src/lib/api.ts (checkApiHealth + runPrediction)
前端 Store:    src/store/peptideFilterStore.ts
MOCK_DATA:     src/lib/constants.ts (MOCK_CANDIDATES)

审计报告:      backend/docs/LEGACY_PIPELINE_AUDIT.md
本复核报告:    backend/docs/P1c_RISK_REVIEW_AND_PIPELINE_ROADMAP.md
```
