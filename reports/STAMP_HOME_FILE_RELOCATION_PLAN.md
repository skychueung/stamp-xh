# STAMP /home/xh 文件迁移计划

> 生成时间：2026-06-02  
> 服务器：stamp218  
> 原则：**只判断，不迁移，不删除**

---

## 一、现状对账结果

| 检查项 | 结果 |
|---|---|
| /home/xh/stamp 类型 | **软链接** |
| /home/xh/stamp 指向 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform` |
| 前端 8080/pipeline | **200 OK** |
| 后端 8001/api/health | **healthy** |
| watchdog cron | **存在**（每3分钟） |
| docker stamp-frontend | **运行中**，挂载 `/home/xh/stamp/dist` |
| 当前前端/后端依赖 | **依赖 `/home/xh/stamp` 软链接** |

**结论**：`/home/xh/stamp` 软链接是生产环境的关键兼容路径，**严禁移动或删除**。

---

## 二、扫描统计

| 类别 | 数量 |
|---|---|
| 疑似 STAMP 文件/目录总数 | **41 项** |
| A 类：明确可迁移 | **34 项** |
| B 类：需人工确认 | **7 项** |
| D 类：不能移动 | **15+ 项（系统/环境文件）** |
| 已在正确位置（C 类） | **正式项目目录全部符合** |

---

## 三、文件归属判定与迁移计划

### A 类：明确属于 STAMP，建议迁移

| 当前路径 | 文件大小 | 判定类别 | 判断依据 | 建议目标路径 | 是否建议迁移 | 风险 |
|---|---:|---|---|---|---|---|
| `/home/xh/stamp_check_logs/` | 12K | A | STAMP 服务器检查日志目录，含 `server_check_20260512_180940.log` | `logs/stamp_check_logs/` | 是 | 低：历史日志，无服务依赖 |
| `/home/xh/stamp_backup_20260512_181319/` | 639M | A | 明确命名的 STAMP 备份目录，含完整旧项目副本 | `backups/stamp_backup_20260512_181319/` | 是 | 低：旧备份，已确认有更新版本在运行 |
| `/home/xh/stamp_real/` | 654M | A | 疑似旧 STAMP 项目完整副本，含 `backend/` `docs/` `src/` 等 | `backups/stamp_real_20260512/` | 是 | 低：疑似旧副本，与正式项目内容不同 |
| `/home/xh/stamp-v1.4-deploy.tar.gz` | 7.6M | A | STAMP v1.4 部署包 | `backups/stamp-v1.4-deploy.tar.gz` | 是 | 低：历史部署包 |
| `/home/xh/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md` | 17K | A | STAMP 工作流审计文档；与正式项目文件**内容相同**（md5 一致） | `docs/operations/` | 是 | 低：可能产生重复文件，可覆盖或跳过 |
| `/home/xh/stamp_demo_one.json` | 1.6K | A | STAMP 演示数据；与正式项目文件**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/vite-dev-server.log` | 2.4K | A | STAMP 前端开发服务器日志 | `logs/` | 是 | 低：旧日志 |
| `/home/xh/vite-dev-server2.log` | 900B | A | STAMP 前端开发服务器日志2 | `logs/` | 是 | 低：旧日志 |
| `/home/xh/uvicorn.pid` | 3B | A | STAMP uvicorn PID 文件（旧） | `logs/` | 是 | 低：可能已失效 |
| `/home/xh/DEPLOY_v1.4.sh` | 1.7K | A | STAMP 部署脚本；与正式项目**内容相同** | `scripts/ops/` | 是 | 低：可能重复 |
| `/home/xh/DEPLOY_v0.6d-P1c_REPORT.md` | 6.3K | A | STAMP 部署报告 | `reports/` | 是 | 低：历史报告 |
| `/home/xh/CHANGELOG.md` | 5.9K | A | STAMP 变更日志；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/SEAL_v0.6d-P1c_FINAL.md` | 6.4K | A | STAMP 封印文档；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/SEAL_v0.6d-P1c_REPORT.md` | 7.2K | A | STAMP 封印报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/SOFT_RESTORE_REPORT.md` | 1.4K | A | STAMP 恢复报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md` | 1.4K | A | STAMP 恢复文档；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/STRUCTURE_PIPELINE.md` | 3.2K | A | STAMP 结构流程文档；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/TODO.md` | 7.2K | A | STAMP 待办事项；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md` | 4.5K | A | STAMP 报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/v0.7-real-backend-integration_REPORT.md` | 6.9K | A | STAMP 报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/PROJECT_CONTEXT.md` | 4.0K | A | STAMP 项目上下文；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/README.md` | 2.6K | A | STAMP 说明文档；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/RUNBOOK.md` | 2.0K | A | STAMP 运行手册；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/info.md` | 1.4K | A | STAMP 信息文档；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/FINAL_REPORT_v1.4.md` | 6.3K | A | STAMP 最终报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/DEV_RULES.md` | 3.5K | A | STAMP 开发规则；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md` | 4.0K | A | STAMP 序列文档；与正式项目**内容相同** | `docs/operations/` | 是 | 低：可能重复 |
| `/home/xh/PEPMLM_GPU_GENERATION_REPORT.md` | 9.1K | A | STAMP GPU 生成报告；与正式项目**内容相同** | `reports/` | 是 | 低：可能重复 |
| `/home/xh/backend/` | 6.8M | A | STAMP 后端代码旧副本；与正式项目 backend **源代码存在差异** | `archived-home-files/backend/` | 是 | 中：是旧代码副本，非当前运行版本 |
| `/home/xh/docs/` | 2.4M | A | STAMP 文档旧副本 | `archived-home-files/docs/` | 是 | 低：旧副本 |
| `/home/xh/scripts/` | 144K | A | STAMP 脚本旧副本（`deploy_server.sh` `healthcheck.sh` 等） | `archived-home-files/scripts/` | 是 | 低：旧副本 |
| `/home/xh/src/` | 1.6M | A | STAMP 前端源码旧副本 | `archived-home-files/src/` | 是 | 低：旧副本 |
| `/home/xh/data/` | 16K | A | STAMP 数据旧副本 | `archived-home-files/data/` | 是 | 低：旧副本 |
| `/home/xh/public/` | 3.1M | A | STAMP 公共资源旧副本 | `archived-home-files/public/` | 是 | 低：旧副本 |

### B 类：疑似属于 STAMP，需人工确认

| 当前路径 | 文件大小 | 判定类别 | 判断依据 | 建议目标路径 | 是否建议迁移 | 风险 |
|---|---:|---|---|---|---|---|
| `/home/xh/gen_gpu0.log` | 124B | B | 文件名 `gen_gpu` 疑似 STAMP GPU 肽生成日志，但无明确 stamp 标识 | `logs/` | **需确认** | 中：可能为其他项目日志 |
| `/home/xh/gen_gpu1.log` | 124B | B | 同上 | `logs/` | **需确认** | 中 |
| `/home/xh/gmx_MMPBSA.log` | 691B | B | GROMACS MMPBSA 日志，STAMP 包含分子动力学模块，但未明确标识 | `logs/` | **需确认** | 中 |
| `/home/xh/gpu_smoke_condarun.log` | 27K | B | GPU 冒烟测试日志，`condarun` 提示可能与 conda 环境测试相关 | `logs/` | **需确认** | 中 |
| `/home/xh/P6B_PARSE_OUTPUT_RUN_2.log` | 0B | B | P6B 标识与 stamp_real 中 `P6B_*` 脚本对应，但为空文件 | `logs/` | **需确认** | 低：空文件 |
| `/home/xh/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | 0B | B | 同上 | `logs/` | **需确认** | 低：空文件 |
| `/home/xh/ROSETTA_CRASH.log` | 11K | B | ROSETTA 崩溃日志，STAMP 包含 FlexPepDock 结构验证，可能相关 | `logs/` | **需确认** | 中 |

### C 类：已在正确位置，无需移动

- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/` 及其全部子目录
- `/home/xh/stamp` 软链接本身（生产关键兼容路径）
- `/home/xh/kxc/靶向肽/stamp-platform-v0.8-e2e/`
- `/home/xh/kxc/靶向肽/stamp-platform-v0.8-e2e-backup-20260508_1027/`

### D 类：不能移动

- `/home/xh/.ssh` — 系统密钥
- `/home/xh/.bashrc` / `.profile` / `.bash_logout` — Shell 配置
- `/home/xh/.conda` / `.mamba` / `miniconda3` / `micromamba` — Python 环境
- `/home/xh/.cache` / `.config` / `.local` — 用户配置缓存
- `/home/xh/.vscode-server` — VS Code Server
- `/home/xh/.npm` / `.npm-global` — Node 环境
- `/home/xh/.docker` — Docker 配置
- `/home/xh/cuda-repo-*.deb` — CUDA 安装包（非 STAMP）
- `/home/xh/backend/data` — 若存在运行中数据（当前未确认）

### E 类：非 STAMP 文件，不处理

- `/home/xh/webui.log` — 无明确 STAMP 关联
- `/home/xh/ww/` / `yjj/` / `zhr/` / `zy/` / `lkf/` — 其他用户/项目目录
- `/home/xh/molecules/` / `rag_storage/` — 其他项目
- `/home/xh/Desktop` / `Documents` / `Downloads` 等 — 系统目录

---

## 四、迁移路径规则

| 文件类型 | 目标根目录 |
|---|---|
| 日志类 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/logs/` |
| watchdog / ops 脚本 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/scripts/ops/` |
| 报告类 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/reports/` |
| 文档类 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/docs/operations/` |
| 旧备份类（完整项目备份） | `/home/xh/kxc/靶向肽/backups/` |
| 旧项目子目录副本 | `/home/xh/kxc/靶向肽/archived-home-files/` |

---

## 五、特别说明

### 5.1 关于 `/home/xh/stamp` 软链接

**严禁移动或删除**。当前生产环境配置：
- docker `stamp-frontend` 挂载：`/home/xh/stamp/dist` → `/usr/share/nginx/html`
- watchdog 写日志路径：`/home/xh/stamp/logs/stamp_watchdog.log`
- start_backend 写日志路径：`/home/xh/stamp/logs/backend.log`
- 用户习惯路径：`/home/xh/stamp` 是常用快捷方式

### 5.2 关于 `/home/xh/backend/` 等旧副本

经 `diff -r` 比对，`/home/xh/backend/` 与正式项目 `backend/` **源代码存在差异**（如缺少 `pipeline_runs` 路由）。说明 `/home/xh` 下的 `backend/` `docs/` `scripts/` `src/` `data/` `public/` 是**旧的项目副本**，并非当前运行版本。建议整体归档到 `archived-home-files/`。

### 5.3 关于重复文件

`/home/xh` 根目录下大量 `.md` `.sh` `.json` 文件与正式项目中同名文件 **md5 完全一致**。迁移后会在目标目录产生重复。建议：
- 若目标已存在且 md5 相同，可**跳过不迁移**
- 或迁移后统一清理重复项

---

## 六、用户确认后方可执行

**本次未执行任何迁移。**

如用户确认迁移，后续需要：
1. 生成正式迁移脚本（含备份清单）
2. 使用 `rsync -a --remove-source-files` 或 `mv` 前复制验证
3. 保留 `/home/xh/stamp` 软链接
4. 更新 watchdog / start_backend / status 脚本中的日志路径（如需要）
5. 迁移后验证：
   - `curl -I http://127.0.0.1:8080/pipeline` → 200
   - `curl -s http://127.0.0.1:8001/api/health` → healthy
   - watchdog cron 正常
   - 日志正常写入新目录

---

*报告由自动化扫描脚本生成，仅用于规划，未修改任何文件。*
