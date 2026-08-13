---
name: STAMP v1.4 - 服务器恢复后部署与 smoke 验收
about: 服务器 192.168.31.218 恢复后的部署与验收流程
title: "STAMP v1.4 - 服务器恢复后部署与 smoke 验收"
labels: ["deployment", "v1.4", "server"]
assignees: []
---

## 目标

服务器 `192.168.31.218` 恢复后，将 `v1.4-batch-computation` 部署到内网环境，并完成健康检查、前端访问、Batch Computation 页面访问、批量任务 smoke 和科学边界验证。

## 当前状态

- `v1.4-batch-computation` 分支已推送 GitHub ✅
- `v1.4.0-batch-computation` tag 已推送 GitHub ✅
- 后端测试 **813 passed, 0 failed** ✅
- `DEPLOY_v1.4.sh` 已准备 ✅
- 服务器当前 SSH timeout，等待恢复 ⏳

## 前置检查（干净环境）

如果服务器是重新格式化后的干净环境，先执行：

```bash
python3 --version   # >= 3.10
node -v             # >= 18
npm -v              # >= 9
git --version       # >= 2.30
nginx -v            # 或确认 Docker 可用
which uvicorn       # 或通过 pip 安装
which sqlite3       # 通常自带
```

缺失依赖的安装参考：

```bash
# Ubuntu 24.04
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nodejs npm git docker.io nginx

# uvicorn (在 venv 中安装)
pip install uvicorn[standard]
```

## 部署步骤

```bash
# 1. 进入项目目录
cd ~/stamp-targeted-peptide-platform || {
    git clone https://github.com/skychueung/stamp-targeted-peptide-platform.git ~/stamp-targeted-peptide-platform
    cd ~/stamp-targeted-peptide-platform
}

# 2. 拉取 v1.4
git fetch --all --tags
git checkout v1.4-batch-computation
git pull origin v1.4-batch-computation

# 3. 执行部署脚本
bash DEPLOY_v1.4.sh
```

## 验收标准

### 基础连通性
- [ ] 能 SSH 登录 `192.168.31.218`
- [ ] 能拉取 `v1.4-batch-computation` 分支
- [ ] `DEPLOY_v1.4.sh` 执行成功（无报错退出）

### 服务可用性
- [ ] Frontend 可访问：`http://192.168.31.218:8080`
- [ ] Backend API 可访问：`http://192.168.31.218:8001/api`
- [ ] `GET /api/health` → `{"status":"ok"}`
- [ ] `GET /api/health/db` → SQLite 连接正常
- [ ] `GET /api/health/storage` → 目录可写
- [ ] `GET /api/health/queue` → 队列状态正常

### 功能验收
- [ ] Batch Computation 页面可访问（Sidebar → Layers 图标）
- [ ] 创建 batch 任务成功：`POST /api/v1/batch-computations`
- [ ] 缺失命令返回 `BLOCKED`（如 `colabbatch` 未安装）
- [ ] 输入非法返回 `FAILED` 或 `422`（如序列过短、非法 job_type）
- [ ] 无真实 artifact 不进入 `SUCCEEDED`（空输出目录 → `FAILED`）
- [ ] Retry-failed 功能正常：FAILED/BLOCKED → PENDING
- [ ] Cancel 功能正常：RUNNING/PENDING → CANCELLED

### 科学边界验证
- [ ] 创建 batch 后 artifact 目录已按标准结构生成
- [ ] 不伪造 pLDDT / ipTM / RMSD / RMSF / ΔG / MM-GBSA 值
- [ ] 只有通过真实计算并验证输出文件后，item 才进入 `SUCCEEDED`

## 部署报告模板

验收完成后，在 `reports/` 目录生成：

```markdown
# STAMP v1.4 部署验收报告

**Date:** YYYY-MM-DD HH:MM  
**Server:** 192.168.31.218  
**Branch:** v1.4-batch-computation  
**Commit:** <hash>  
**Tag:** v1.4.0-batch-computation

## 环境检查

| 工具 | 版本 | 状态 |
|------|------|------|
| python3 | x.x.x | ✅ |
| node | x.x.x | ✅ |
| npm | x.x.x | ✅ |
| git | x.x.x | ✅ |
| nginx/docker | x.x.x | ✅ |

## 服务状态

| 端点 | 状态 | 响应 |
|------|------|------|
| /api/health | ✅ | ... |
| /api/health/db | ✅ | ... |
| /api/health/storage | ✅ | ... |
| /api/health/queue | ✅ | ... |

## 功能验收

| 测试项 | 状态 | 备注 |
|--------|------|------|
| 创建 batch | ✅ | ... |
| BLOCKED (命令缺失) | ✅ | ... |
| FAILED/422 (非法输入) | ✅ | ... |
| 无 artifact 不进 SUCCEEDED | ✅ | ... |

## 结论

[通过 / 不通过]
```

## 风险与回滚

| 风险 | 缓解措施 |
|------|---------|
| Docker Hub 仍被代理阻断 | 使用 native Python + nginx，不依赖 Docker build |
| DB  schema 不兼容 | 重新初始化 SQLite（`Base.metadata.create_all`）|
| 依赖包安装失败 | 使用 `--index-url` 切换到国内 PyPI 镜像 |

回滚命令：

```bash
# 回滚到 v1.3
git checkout v1.3.0-server-real-run
cd backend && pip install -r requirements.txt
pkill -f uvicorn; nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 &
```
