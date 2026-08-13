# STAMP B 类日志内容覆盖事故复核报告

> 复核时间：2026-06-02  
> 服务器：stamp218  
> 复核原则：**只读检查，不修改、不删除、不恢复任何文件**

---

## 一、事故影响范围

| 项目 | 详情 |
|---|---|
| 受影响文件数 | **7 个** |
| 受影响目录 | `/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/needs_review_logs/` |
| 事故表现 | 文件内容被脚本输出覆盖，原始日志内容丢失 |
| 服务影响 | **无**（前端/后端/watchdog 均正常） |

---

## 二、7 个日志当前大小和内容状态

### 当前状态（已覆盖）

| 文件名 | 原始大小 | 原始修改时间 | 当前大小 | 当前内容 | 状态 |
|---|---:|---|---:|---|---|
| `gen_gpu0.log` | 124B | Mar 17 13:05 | **39B** | `[OK] Migrated: /home/xh/gen_gpu0.log -` | ❌ 已覆盖 |
| `gen_gpu1.log` | 124B | Mar 17 13:05 | **39B** | `[OK] Migrated: /home/xh/gen_gpu1.log -` | ❌ 已覆盖 |
| `gmx_MMPBSA.log` | 691B | May 13 13:01 | **41B** | `[OK] Migrated: /home/xh/gmx_MMPBSA.log -` | ❌ 已覆盖 |
| `gpu_smoke_condarun.log` | 27K | May 13 10:25 | **49B** | `[OK] Migrated: /home/xh/gpu_smoke_condarun.log -` | ❌ 已覆盖 |
| `P6B_PARSE_OUTPUT_RUN_2.log` | 0B | May 10 11:13 | **53B** | `[OK] Migrated: /home/xh/P6B_PARSE_OUTPUT_RUN_2.log -` | ❌ 已覆盖 |
| `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | 0B/3.1K | May 10 11:13 | **60B** | `[OK] Migrated: /home/xh/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log -` | ❌ 已覆盖 |
| `ROSETTA_CRASH.log` | 11K | May 13 01:26 | **44B** | `[OK] Migrated: /home/xh/ROSETTA_CRASH.log -` | ❌ 已覆盖 |

### 原始内容确认（来自迁移前快照）

- `gen_gpu0.log` / `gen_gpu1.log`：`nohup: ignoring input` + `conditional_generation_msa.py` 错误
- `gmx_MMPBSA.log`：`gmx_MMPBSA v1.5.0.3` 启动日志
- `gpu_smoke_condarun.log`：GROMACS `gmx mdrun` 运行日志
- `P6B_PARSE_OUTPUT_RUN_2.log`：空文件
- `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`：空文件（或 3.1K 内容）
- `ROSETTA_CRASH.log`：Rosetta 崩溃报告日志

---

## 三、同名备份搜索结果

### 全服务器 find 结果

```
10292784 2026-03-17 /home/xh/kxc/AMPGen/AMP_generator/gen_gpu0.log   ← AMPGen 项目，非 STAMP
10292784 2026-03-17 /home/xh/kxc/ampgenkxc/AMPGen/AMP_generator/gen_gpu0.log
10320022 2026-04-04 /home/xh/kxc/AMPGen/AMP_generator/gen_gpu1.log   ← AMPGen 项目，非 STAMP
10320022 2026-04-04 /home/xh/kxc/ampgenkxc/AMPGen/AMP_generator/gen_gpu1.log
24516    2026-05-13 /home/xh/kxc/stamp_md_pilot/xia41_1ns_md_20260513_095840/gmx_MMPBSA.log ← 不同实例
737      2026-05-13 /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend/gmx_MMPBSA.log ← 正式项目
3121     2026-05-10 /home/xh/kxc/p6b/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log                   ← 高度疑似同一实例
3121     2026-05-10 /home/xh/kxc/p6b/p6b_return_20260510_112017/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log ← 同上
3121     2026-05-10 /home/xh/kxc/p6b/p6b_return_20260510_112049/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log ← 同上
3121     2026-05-10 /home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/old_project_copies/stamp_backup_20260512_181319/.../P6B_RUN_COLABFOLD_SMOKE_RUN_2.log ← 同上
994      2026-05-11 /home/xh/kxc/v012_p2d_flexpepdock_pilot/ROSETTA_CRASH.log              ← 不同实例
```

### 关键发现

| 文件名 | 是否找到同名备份 | 备份位置 | 与原始一致性 | 可恢复性 |
|---|---|---|---|---|
| `gen_gpu0.log` | ❌ 无 STAMP 备份 | — | — | **不可恢复** |
| `gen_gpu1.log` | ❌ 无 STAMP 备份 | — | — | **不可恢复** |
| `gmx_MMPBSA.log` | ⚠️ 有相似日志 | `backend/gmx_MMPBSA.log` (737B) | 大小接近，时间不同，不同运行实例 | **不可完全恢复** |
| `gpu_smoke_condarun.log` | ❌ 无备份 | — | — | **不可恢复** |
| `P6B_PARSE_OUTPUT_RUN_2.log` | ❌ 无备份 | — | — | **不可恢复** |
| `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log` | ✅ 有备份 | `/home/xh/kxc/p6b/` 下 3 个副本 + `stamp_backup` 中 1 个 | 时间/大小高度一致，疑似同一运行实例 | **可恢复** |
| `ROSETTA_CRASH.log` | ⚠️ 有相似日志 | `/home/xh/kxc/v012_p2d_flexpepdock_pilot/ROSETTA_CRASH.log` (994B) | 时间更早（May 11 vs May 13），大小更小（994B vs 11K） | **不可完全恢复** |

---

## 四、按关键内容搜索备份结果

| 搜索关键词 | 是否找到相关备份 | 说明 |
|---|---|---|
| `nohup: ignoring input` | ❌ 否 | 仅在当前报告和 uvicorn/frontend 日志中命中 |
| `ROSETTA` | ⚠️ 有引用 | 大量报告和脚本提及，但无原始日志副本 |
| `gmx_MMPBSA` | ⚠️ 有引用 | 报告和脚本大量提及，另有 2 个不同实例的日志 |
| `P6B_RUN_COLABFOLD` | ✅ 是 | 在 `p6b/` 目录和 `stamp_backup` 中找到完整副本 |

---

## 五、恢复可行性结论

| 类别 | 数量 | 文件 |
|---|---|---|
| **可恢复** | **1 个** | `P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`（在 `/home/xh/kxc/p6b/` 和 `stamp_backup` 中均有 3.1K 完整副本） |
| **不可恢复** | **6 个** | `gen_gpu0.log`、`gen_gpu1.log`、`gmx_MMPBSA.log`、`gpu_smoke_condarun.log`、`P6B_PARSE_OUTPUT_RUN_2.log`、`ROSETTA_CRASH.log` |

### 备份详情

**P6B_RUN_COLABFOLD_SMOKE_RUN_2.log 可用备份：**
- `/home/xh/kxc/p6b/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`（3.1K，May 10 11:17）
- `/home/xh/kxc/p6b/p6b_return_20260510_112017/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`（3.1K，May 10 11:20）
- `/home/xh/kxc/p6b/p6b_return_20260510_112049/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`（3.1K，May 10 11:20）
- `/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/old_project_copies/stamp_backup_20260512_181319/backend/data/structure_predictions/localcolabfold_smoke_20260510_111732/P6B_RUN_COLABFOLD_SMOKE_RUN_2.log`（3.1K，May 10 11:20）

备份内容预览（前 5 行）：
```
========================================
P6B ColabFold Smoke Test
Timestamp: 20260510_111732
Sequence length: 39 aa
Output: /home/xh/kxc/tools/localcolabfold/runs/smoke_20260510_111732
========================================
```

---

## 六、服务是否受影响

| 检查项 | 状态 |
|---|---|
| 前端 `8080/pipeline` | **200 OK** ✅ |
| 后端 `8001/api/health` | **healthy** ✅ |
| `/home/xh/stamp` 软链接 | **完好** ✅ |
| watchdog 日志 | **正常写入** ✅ |
| docker 容器 | **全部运行中** ✅ |

**结论：服务完全未受影响。** 本次事故仅影响已归档的历史日志文件内容，不涉及运行中服务。

---

## 七、根因判断

### 直接原因

归档脚本通过 SSH 内联命令执行时，`echo` 的输出被错误地写入了目标日志文件，而非仅输出到 stdout。

### 深层原因

**PowerShell → OpenSSH → 远程 shell 的多层转义兼容性问题：**

1. 本地 PowerShell 解析 `ssh host 'command'` 时，单引号字符串中的 `$` 不会被扩展，但 `"` 和 `\` 的处理可能与 bash 不同
2. `ssh.exe` 在 Windows 上接收参数时，对引号和反斜杠的解析可能存在差异
3. 远程服务器上的 `/bin/sh`（dash）与 bash 对 `echo`、`-e`、`	`、`
` 的处理不同
4. 综合作用下，`echo` 的输出被重定向到了错误的目标文件

### 证据

- Manifest 文件中的 `	` 和 `
` 均未被正确解析（显示为字面 `t` 和 `n`）
- 7 个目标文件内容完全一致地变成了 `[OK] Migrated: ...` 格式
- 文件大小统一缩小到 39~60 字节（即 `echo` 输出字符串的长度）

---

## 八、后续防范规则

1. **禁用 SSH 内联命令执行文件操作**：所有涉及 `mv`/`cp`/`echo` 的文件操作，必须先上传 `.sh` 脚本到服务器，再本地执行
2. **脚本上传后本地执行**：使用 `scp script.sh host:/path/` + `ssh host 'bash /path/script.sh'` 的方式，避免多层转义
3. **归档前强制校验**：移动文件后，立即用 `md5sum` 或 `diff` 校验源和目标内容一致性
4. **使用 `rsync -av` 替代 `mv`**：`rsync` 支持校验和验证，且 `--remove-source-files` 可在验证后删除源文件
5. **保留源文件直到验证通过**：先复制到目标目录，验证无误后再删除源文件
6. **避免在归档脚本中使用 `echo` 输出状态信息**：使用 `logger` 或写入独立的 `.status` 文件，避免 stdout/stderr 污染目标文件

---

## 九、操作声明

| 项目 | 结果 |
|---|---|
| 本次是否删除文件 | **否** |
| 本次是否移动文件 | **否** |
| 本次是否覆盖文件 | **否** |
| 本次是否恢复文件 | **否** |
| 本次是否修改服务配置 | **否** |
| 本次是否重启服务 | **否** |

**本任务仅执行只读检查和报告生成，未对服务器做任何修改。**

---

*报告生成时间：2026-06-02*  
*复核目录：`/home/xh/kxc/靶向肽/archived-home-files/stamp_related_20260602/needs_review_logs/`*
