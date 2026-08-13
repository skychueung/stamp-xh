# Peptide Frontend — 运维手册

> 常用命令速查。WSL / Windows 终端通用。

## STAMPUP 开发副本入口

当前 STAMPUP 开发副本的推荐入口如下：

```bash
cd /home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev
bash scripts/ops/stampup_start_backend.sh
bash scripts/ops/stampup_start_frontend.sh
bash scripts/ops/stampup_status.sh
bash scripts/ops/stampup_healthcheck.sh
bash scripts/ops/stampup_restart.sh
bash scripts/ops/stampup_stop.sh
```

约束：

- 只操作开发端口 `12823 / 12824`
- 日志只写入 `logs_dev`
- 报告只写入 `reports`
- 数据库 / artifacts / uploads / jobs 只写入 `data_dev`

历史说明：

- 旧的 `start_backend` / `start_frontend` / `healthcheck` / `demo` / `deploy` 入口保留为历史记录
- 不建议把它们当作 STAMPUP 开发副本默认入口

---

## 进入项目目录

```bash
cd "/mnt/d/Desktop/靶向肽/github/前端"
```

Windows CMD / PowerShell 等价命令：

```cmd
cd "D:\Desktop\靶向肽\github\前端"
```

---

## 安装依赖

```bash
npm install
```

---

## 开发服务器

```bash
npm run dev
```

默认启动在 `http://localhost:5173/`

---

## 生产构建

```bash
npm run build
```

构建产物输出到 `dist/` 目录。

**注意**：构建必须零报错、零警告。详见 `DEV_RULES.md`。

---

## 预览生产构建

```bash
npm run preview
```

---

## 代码检查

```bash
npm run lint
```

---

## 快速检查清单

| 场景 | 命令 |
|------|------|
| 首次克隆后 | `npm install` |
| 日常开发 | `npm run dev` |
| 提交前验证 | `npm run build` |
| 检查代码规范 | `npm run lint` |
| 预览生产包 | `npm run preview` |

---

## CASS 本地会话搜索

> CASS (Context-Aware Session Search) 用于检索 Kimi Code / Codex 历史会话。
> 安装路径：`D:\ai\product\cass`
> 数据目录：`D:\ai\product\cass\data`

### PowerShell 环境变量

```powershell
$env:CASS_DATA_DIR="D:\ai\product\cass\data"
```

### 常用搜索命令

```powershell
# 搜索关键词（robot 模式，限制 10 条）
cass search "Hermes" --robot --limit 10
cass search "Kimi Code" --robot --limit 10
cass search "AIAgent" --robot --limit 10

# 增量索引（新增会话后执行）
cass index

# 全量重建索引
cass index --full

# 诊断并修复索引问题
cass doctor --fix
```

### 会话来源

| 工具 | 真实路径 |
|------|----------|
| Kimi Code | `C:\Users\33319\.kimi\sessions` |
| Codex | `C:\Users\33319\.codex\sessions` |

当前索引：30 conversations / 2,042 messages（Kimi Code: 24 / Codex: 6）

---

*最后更新：2026-04-27*
