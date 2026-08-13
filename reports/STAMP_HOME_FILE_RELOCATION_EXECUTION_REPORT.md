# STAMP /home/xh 文件迁移执行报告

> 执行时间：2026-06-02 15:13 CST  
> 服务器：stamp218  
> 操作人：自动化迁移脚本  
> 原则：**只迁移 A 类，不删除 B 类，不破坏服务**

---

## 一、迁移前服务状态

| 检查项 | 状态 |
|---|---|
| 前端 `8080/pipeline` | **200 OK** |
| 后端 `8001/api/health` | **healthy** |
| `/home/xh/stamp` 软链接 | **正常**，指向 `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform` |
| watchdog cron | **正常**，每 3 分钟执行 |
| docker 容器 | **全部运行中** |

---

## 二、迁移执行概况

| 项目 | 数值 |
|---|---|
| 执行脚本路径 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/scripts/ops/relocate_stamp_home_files_execute.sh` |
| 迁移清单 manifest 路径 | `/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/manifest/relocation_manifest.tsv` |
| 归档根目录 | `/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/` |
| **A 类迁移文件/目录总数** | **34 项** |
| 迁移成功 | 34 项 |
| 跳过/未找到 | 0 项 |
| 错误 | 0 项 |

---

## 三、A 类迁移明细

### 目录迁移（9 项）

| 序号 | 源路径 | 目标路径 | 大小 |
|---:|---|---:|---|
| 1 | `/home/xh/stamp_check_logs/` | `logs/stamp_check_logs/` | 7.3K |
| 2 | `/home/xh/stamp_backup_20260512_181319/` | `old_project_copies/stamp_backup_20260512_181319/` | 525.9M |
| 3 | `/home/xh/stamp_real/` | `old_project_copies/stamp_real/` | 548.2M |
| 4 | `/home/xh/backend/` | `old_project_copies/backend/` | 5.9M |
| 5 | `/home/xh/docs/` | `old_project_copies/docs/` | 2.3M |
| 6 | `/home/xh/scripts/` | `old_project_copies/scripts/` | 89K |
| 7 | `/home/xh/src/` | `old_project_copies/src/` | 973K |
| 8 | `/home/xh/data/` | `old_project_copies/data/` | 2.3K |
| 9 | `/home/xh/public/` | `old_project_copies/public/` | 2.9M |

### 文件迁移（25 项）

| 序号 | 源路径 | 目标路径 | 大小 |
|---:|---|---:|---|
| 10 | `stamp-v1.4-deploy.tar.gz` | `old_project_copies/stamp-v1.4-deploy.tar.gz` | 7.6M |
| 11 | `STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md` | `reports/STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md` | 17K |
| 12 | `stamp_demo_one.json` | `json/stamp_demo_one.json` | 1.5K |
| 13 | `vite-dev-server.log` | `logs/vite-dev-server.log` | 2.4K |
| 14 | `vite-dev-server2.log` | `logs/vite-dev-server2.log` | 900B |
| 15 | `uvicorn.pid` | `logs/uvicorn.pid` | 3B |
| 16 | `DEPLOY_v1.4.sh` | `scripts/DEPLOY_v1.4.sh` | 1.7K |
| 17 | `DEPLOY_v0.6d-P1c_REPORT.md` | `reports/DEPLOY_v0.6d-P1c_REPORT.md` | 6.4K |
| 18 | `CHANGELOG.md` | `reports/CHANGELOG.md` | 5.9K |
| 19 | `SEAL_v0.6d-P1c_FINAL.md` | `reports/SEAL_v0.6d-P1c_FINAL.md` | 6.5K |
| 20 | `SEAL_v0.6d-P1c_REPORT.md` | `reports/SEAL_v0.6d-P1c_REPORT.md` | 7.4K |
| 21 | `SOFT_RESTORE_REPORT.md` | `reports/SOFT_RESTORE_REPORT.md` | 1.4K |
| 22 | `SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md` | `reports/SOFT_RESTORE_v0.6d-P2a_DEMO_DEFAULT.md` | 1.4K |
| 23 | `STRUCTURE_PIPELINE.md` | `reports/STRUCTURE_PIPELINE.md` | 3.2K |
| 24 | `TODO.md` | `reports/TODO.md` | 7.3K |
| 25 | `v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md` | `reports/v0.7-P1a_EPITOPE_PARAMETER_AND_FLOW_REPORT.md` | 4.6K |
| 26 | `v0.7-real-backend-integration_REPORT.md` | `reports/v0.7-real-backend-integration_REPORT.md` | 7.0K |
| 27 | `PROJECT_CONTEXT.md` | `reports/PROJECT_CONTEXT.md` | 4.0K |
| 28 | `README.md` | `reports/README_HOME.md` | 2.6K |
| 29 | `RUNBOOK.md` | `reports/RUNBOOK_HOME.md` | 2.0K |
| 30 | `info.md` | `reports/info_HOME.md` | 1.4K |
| 31 | `FINAL_REPORT_v1.4.md` | `reports/FINAL_REPORT_v1.4.md` | 6.4K |
| 32 | `DEV_RULES.md` | `reports/DEV_RULES.md` | 3.5K |
| 33 | `DISPLAYABLE_SEQUENCES_v0.6d-P1c.md` | `reports/DISPLAYABLE_SEQUENCES_v0.6d-P1c.md` | 4.1K |
| 34 | `PEPMLM_GPU_GENERATION_REPORT.md` | `reports/PEPMLM_GPU_GENERATION_REPORT.md` | 9.3K |

---

## 四、B 类未迁移清单（需人工确认）

以下 7 项文件**未迁移**，仍保留在 `/home/xh` 根目录，等待后续人工确认：

| 路径 | 大小 | 备注 |
|---|---|---|
| `/home/xh/gen_gpu0.log` | 124B | 疑似 STAMP GPU 生成日志 |
| `/home/xh/gen_gpu1.log` | 124B | 疑似 STAMP GPU 生成日志 |
| `/home/xh/gmx_MMPBSA.log` | 691B | 疑似分子动力学日志 |
| `/home/xh/gpu_smoke_condarun.log` | 27K | 疑似 GPU 冒烟测试日志 |
| `/home/xh/P6B_PARSE_OUTPUT_RUN_2.log` | 0B | 空文件，P6B 相关 |
| `/home/xh/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | 0B | 空文件，P6B 相关 |
| `/home/xh/ROSETTA_CRASH.log` | 11K | 疑似 ROSETTA 崩溃日志 |

---

## 五、D 类保护清单（未移动）

以下系统/环境文件在扫描阶段即被明确保护，**未做任何操作**：

- `/home/xh/.ssh`
- `/home/xh/.bashrc` / `.profile` / `.bash_logout`
- `/home/xh/.conda` / `.mamba` / `miniconda3` / `micromamba`
- `/home/xh/.cache` / `.config` / `.local`
- `/home/xh/.vscode-server`
- `/home/xh/.npm` / `.npm-global`
- `/home/xh/.docker`
- `/home/xh/cuda-repo-*.deb`

---

## 六、`/home/xh/stamp` 软链接保护结果

| 检查项 | 结果 |
|---|---|
| 软链接是否被移动 | **否** ✅ |
| 软链接指向是否正确 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform` ✅ |
| docker 挂载是否正常 | `/home/xh/stamp/dist` → `/usr/share/nginx/html` ✅ |
| watchdog 日志路径是否正常 | `/home/xh/stamp/logs/stamp_watchdog.log` ✅ |
| 后端日志路径是否正常 | `/home/xh/stamp/logs/backend.log` ✅ |

---

## 七、迁移后服务状态

| 检查项 | 状态 |
|---|---|
| 前端 `8080/pipeline` | **200 OK** ✅ |
| 后端 `8001/api/health` | **healthy** ✅ |
| watchdog 日志最后记录 | `backend=healthy action=none \| frontend=healthy action=none` ✅ |
| cron 任务 | **正常存在** ✅ |
| `/home/xh/stamp` 软链接 | **完好** ✅ |

**服务未受任何影响。**

---

## 八、/home/xh 根目录残留扫描结果

迁移后重新扫描 `/home/xh` 根目录：

- **STAMP 相关 `.md` / `.sh` / `.json` 散落文件**：已清零 ✅
- **STAMP 相关目录**（`backend` `docs` `scripts` `src` `data` `public`）：已清零 ✅
- 残留的 B 类文件：7 项（见第四节）
- 残留的系统/项目配置文件（如 `package.json` `tsconfig.json` 等）：属于正常项目配置，不在本次迁移范围内

---

## 九、操作声明

| 项目 | 结果 |
|---|---|
| 本次是否删除任何文件 | **否** |
| 本次是否清理磁盘空间 | **否，仅规范目录结构** |
| 本次是否重启服务 | **否** |
| 本次是否修改代码 | **否** |
| 本次是否破坏软链接 | **否** |

---

## 十、后续建议

1. **B 类文件处理**：建议人工确认 `/home/xh/gen_gpu0.log` 等 7 项日志是否属于 STAMP，确认后可用 dry-run 脚本中的注释段执行迁移。
2. **重复文件清理**：`/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/` 中已存在与本次迁移部分文件内容相同的文档（如 `STAMP_WORKFLOW_AUDIT_v0.6d-P1c.md`），未来可考虑清理归档目录与正式项目目录之间的重复。
3. **归档目录备份**：`stamp_related_20260602/` 总大小约 **1.1GB**，如需进一步释放 `/home/xh` 空间，可将旧备份（`stamp_backup_20260512_181319/`、`stamp_real/`）压缩后转存至冷存储。
4. **目录规范**：后续 STAMP 运行日志、报告、脚本应直接生成在 `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/` 的对应子目录下，避免再次散落在 `/home/xh` 根目录。

---

*报告生成时间：2026-06-02 15:15*  
*迁移脚本：`relocate_stamp_home_files_execute.sh`*  
*迁移清单：`relocation_manifest.tsv`*
