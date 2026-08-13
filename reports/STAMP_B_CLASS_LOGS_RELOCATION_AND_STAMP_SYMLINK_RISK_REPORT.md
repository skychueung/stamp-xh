# STAMP B 类日志归档与 /home/xh/stamp 软链接风险报告

> 执行时间：2026-06-02 15:24 CST  
> 服务器：stamp218  
> 操作原则：**不删除文件，不移动软链接，不破坏服务**

---

## 一、迁移前服务状态

| 检查项 | 状态 |
|---|---|
| 主机名 | xh-System-Product-Name |
| 当前用户 | xh |
| 前端 `8080/pipeline` | **200 OK** |
| 后端 `8001/api/health` | **healthy** |
| `/home/xh/stamp` 类型 | **软链接** |
| `/home/xh/stamp` 指向 | `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform` |
| docker stamp-frontend | **运行中**（Up 15 hours） |
| watchdog cron | **正常**，每 3 分钟执行 |

---

## 二、`/home/xh/stamp` 软链接检查结果

### 当前状态

- **路径**：`/home/xh/stamp`
- **类型**：符号链接（symbolic link）
- **指向**：`/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`
- **权限**：`lrwxrwxrwx`

### 生产依赖

| 依赖方 | 依赖路径 | 说明 |
|---|---|---|
| docker `stamp-frontend` | `/home/xh/stamp/dist` | 挂载到容器内 `/usr/share/nginx/html` |
| watchdog 脚本 | `/home/xh/stamp/logs/stamp_watchdog.log` | 健康检查日志写入路径 |
| start_backend 脚本 | `/home/xh/stamp/logs/backend.log` | 后端启动日志写入路径 |
| 用户/开发习惯 | `/home/xh/stamp` | 常用快捷访问路径 |

### 风险判断：是否可以移动 `/home/xh/stamp`？

**结论：不建议移动。**

原因：
1. 它是软链接（不是真实散落目录），本身不占用空间
2. 它已经指向 `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`，即目标统一目录
3. 前端 Docker 当前挂载依赖 `/home/xh/stamp/dist`
4. watchdog 日志当前依赖 `/home/xh/stamp/logs`
5. 旧脚本可能硬编码了 `/home/xh/stamp` 路径
6. 移动它可能导致前端 404、日志写入失败、脚本异常

### 如果未来必须取消软链接

需按顺序执行：
1. 修改 Docker 挂载为正式路径 `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/dist`
2. 修改 watchdog 脚本中的日志路径
3. 修改 start_backend/status 脚本中的路径引用
4. 修改 cron 中引用路径
5. 全量验证 8080/8001/watchdog
6. 确认无依赖后，再删除或替换软链接

**本次不做。**

---

## 三、B 类 7 个日志文件归档情况

### 迁移前存在性与大小

| 路径 | 大小 | 修改时间 | 内容预览 |
|---|---|---|---|
| `/home/xh/gen_gpu0.log` | 124B | Mar 17 13:05 | `nohup: ignoring input` + `conditional_generation_msa.py` 错误 |
| `/home/xh/gen_gpu1.log` | 124B | Mar 17 13:05 | 同上 |
| `/home/xh/gmx_MMPBSA.log` | 691B | May 13 13:01 | `gmx_MMPBSA v1.5.0.3` 启动日志 |
| `/home/xh/gpu_smoke_condarun.log` | 27K | May 13 10:25 | GROMACS `gmx mdrun` 运行日志 |
| `/home/xh/P6B_PARSE_OUTPUT_RUN_2.log` | 0B | May 10 11:13 | 空文件 |
| `/home/xh/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | 0B | May 10 11:13 | 空文件 |
| `/home/xh/ROSETTA_CRASH.log` | 11K | May 13 01:26 | Rosetta 崩溃报告日志 |

**内容判断**：所有文件均与 STAMP 项目相关（肽生成、MMPBSA、GROMACS、ColabFold、Rosetta）。

### 归档操作

- **目标目录**：`/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/needs_review_logs/`
- **Manifest 路径**：`/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/manifest/b_class_logs_relocation_manifest.tsv`
- **操作方式**：`mv` 移动（非复制）

### 迁移结果

| 文件 | 状态 |
|---|---|
| `gen_gpu0.log` | **已归档** |
| `gen_gpu1.log` | **已归档** |
| `gmx_MMPBSA.log` | **已归档** |
| `gpu_smoke_condarun.log` | **已归档** |
| `P6B_PARSE_OUTPUT_RUN_2.log` | **已归档** |
| `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | **已归档** |
| `ROSETTA_CRASH.log` | **已归档** |

**归档数量：7/7（100%）**

---

## 四、迁移后 `/home/xh` 根目录残留情况

### 已清理的散落文件

以下 B 类日志文件已不再出现在 `/home/xh` 根目录：
- `gen_gpu0.log` ✅
- `gen_gpu1.log` ✅
- `gmx_MMPBSA.log` ✅
- `gpu_smoke_condarun.log` ✅
- `P6B_PARSE_OUTPUT_RUN_2.log` ✅
- `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` ✅
- `ROSETTA_CRASH.log` ✅

### 仍存在的非日志文件

以下文件与 B 类日志同名但非日志，仍保留在 `/home/xh` 根目录：
- `gpu_smoke_condarun.cpt`（651K，GROMACS 检查点文件）
- `gpu_smoke_condarun.edr`（1.7K，GROMACS 能量文件）
- `gpu_smoke_condarun.gro`（1.9M，GROMACS 结构文件）
- `gpu_smoke_condarun.trr`（975K，GROMACS 轨迹文件）

这些不属于日志，不在本次归档范围内。

---

## 五、迁移后服务状态

| 检查项 | 状态 |
|---|---|
| 前端 `8080/pipeline` | **200 OK** ✅ |
| 后端 `8001/api/health` | **healthy** ✅ |
| `/home/xh/stamp` 软链接 | **完好**，指向不变 ✅ |
| watchdog 日志最后记录 | `backend=healthy action=none \| frontend=healthy action=none` ✅ |
| cron 任务 | **正常存在** ✅ |
| docker 容器 | **全部运行中** ✅ |

**服务未受任何影响。**

---

## 六、操作声明

| 项目 | 结果 |
|---|---|
| 本次是否删除任何文件 | **否** |
| 本次是否移动 `/home/xh/stamp` | **否** |
| 本次是否修改服务配置 | **否** |
| 本次是否重启服务 | **否** |
| 本次是否清理磁盘空间 | **否，仅规范目录结构** |

---

## 七、后续建议

1. **`/home/xh/stamp` 软链接保留**：当前它是生产关键兼容路径，维持现状最安全。
2. **GROMACS 辅助文件**：`/home/xh/gpu_smoke_condarun.{cpt,edr,gro,trr}` 仍散落在根目录，如需归档可单独评估。
3. **日志规范**：后续 STAMP 运行日志应直接生成在 `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/logs/` 下，避免再次散落在 `/home/xh` 根目录。
4. **脚本执行方式优化**：本次通过 SSH 内联命令执行归档时，遇到 shell 转义兼容性问题（`\t` `\n` 未被正确解析）。建议后续复杂操作优先上传 `.sh` 脚本到服务器后执行，避免 PowerShell→SSH→远程 shell 的多层转义风险。

---

*报告生成时间：2026-06-02 15:35*  
*归档目录：`/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/needs_review_logs/`*
