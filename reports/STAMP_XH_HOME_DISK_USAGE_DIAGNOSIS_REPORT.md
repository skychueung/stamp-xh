# /home/xh 磁盘占用诊断报告

**时间**：2026-06-01 23:52
**服务器**：stamp218 (xh@192.168.31.218)
**本次未删除任何文件。**

---

## 一、基础磁盘状态

```
Filesystem      Size  Used Avail Use%  Mounted on
/dev/nvme0n1p2  1.8T  1.7T   87G  95% /          ← 危险
/dev/sda2        15T   12T  3.3T  78% /mnt/sda
/dev/sdb2        15T  6.4T  8.2T  44% /mnt/sdb
```

- **根分区 95% 满，剩余 87G，已进入危险状态**
- inode 使用率 4%，不是 inode 问题
- /mnt/sda 和 /mnt/sdb 有大量空闲空间，可用于迁移

---

## 二、/home/xh 一级目录大小（降序）

| 目录 | 大小 |
|------|------|
| /home/xh/zhr | **562G** |
| /home/xh/ww | **418G** |
| /home/xh/kxc | **189G** |
| /home/xh/miniconda3 | **166G** |
| /home/xh/.cache | **165G** |
| /home/xh/saves | 13G |
| /home/xh/micromamba | 9.6G |
| /home/xh/.local | 9.3G |
| /home/xh/.vscode-server | 3.5G |
| /home/xh/stamp_real | 654M |
| /home/xh/stamp_backup_20260512_181319 | 639M |
| /home/xh/.bun | 588M |
| /home/xh/backups | 475M |
| /home/xh/.npm-global | 368M |
| /home/xh/.npm | 326M |

**前 5 项合计约 1.5T，占 /home/xh 总量 1.6T 的 94%。**

---

## 三、/home/xh 二级目录 Top（降序）

| 目录 | 大小 | 说明 |
|------|------|------|
| /home/xh/zhr/MD | **529G** | MD 轨迹文件 |
| /home/xh/ww/hug5 | **170G** | 模型训练权重 |
| /home/xh/ww/af3 | **140G** | AlphaFold3 数据 |
| /home/xh/miniconda3/envs | **132G** | conda 环境（14个） |
| /home/xh/kxc/tools | **78G** | Rosetta 等工具 |
| /home/xh/ww/segment | **70G** | 分割模型 |
| /home/xh/.cache/modelscope | **54G** | ModelScope 模型缓存 |
| /home/xh/kxc/ampgenkxc | **46G** | AMPGen 副本 |
| /home/xh/.cache/pip | **46G** | pip 缓存 |
| /home/xh/kxc/AMPGen | **42G** | AMPGen 主目录 |
| /home/xh/zhr/AMPGen | **32G** | AMPGen 另一副本 |
| /home/xh/miniconda3/pkgs | **29G** | conda 包缓存 |
| /home/xh/.cache/uv | **26G** | uv 包缓存 |
| /home/xh/.cache/torch | **21G** | torch 模型缓存 |
| /home/xh/ww/af | **20G** | AlphaFold 数据 |
| /home/xh/.cache/huggingface | **16G** | HuggingFace 缓存 |
| /home/xh/saves | **13G** | Qwen2.5 微调权重 |
| /home/xh/kxc/靶向肽 | **11G** | STAMP 项目目录 |
| /home/xh/micromamba/envs | **8.5G** | micromamba 环境 |
| /home/xh/.local/share/labelu | **5.6G** | labelu 数据 |
| /home/xh/kxc/colabfold_params_downloads | **5.3G** | ColabFold 参数 |
| /home/xh/.cache/colabfold | **4.9G** | ColabFold 缓存 |
| /home/xh/kxc/靶向肽/pepmlm_gpu_generation | **4.7G** | PepMLM 生成结果 |
| /home/xh/.local/lib | **3.4G** | Python 本地库 |
| /home/xh/.vscode-server | **3.5G** | VSCode Server |

---

## 四、最大文件 Top（>500M）

| 大小 | 路径 | 类型 |
|------|------|------|
| **136G** | zhr/MD/32_PEDV-S/md_0_1.trr | MD 轨迹 |
| **136G** | zhr/MD/9_PEDV-S/md_0_1.trr | MD 轨迹 |
| **41G** | zhr/MD/32_PEDV-S/nvt.trr | MD 轨迹 |
| **41G** | zhr/MD/32_PEDV-S/npt.trr | MD 轨迹 |
| **41G** | zhr/MD/9_PEDV-S/nvt.trr | MD 轨迹 |
| **41G** | zhr/MD/9_PEDV-S/npt.trr | MD 轨迹 |
| **22G** | zhr/MD/32_PEDV-S/md_0_1.xtc | MD 轨迹 |
| **22G** | zhr/MD/9_PEDV-S/md_0_1.xtc | MD 轨迹 |
| **22G** | zhr/MD/32_PEDV-S/md_0_1_noPBC.xtc | MD 轨迹 |
| **22G** | zhr/MD/9_PEDV-S/md_0_1_noPBC.xtc | MD 轨迹 |
| **20G** | kxc/tools/rosetta/rosetta_binary_ubuntu_3.15_bundle.tar.bz2 | Rosetta 安装包 |
| **7.2G x3** | kxc/AMPGen/.../oaar-640M.tar (3份副本) | EvoDiff 模型 |
| **7.2G** | .cache/torch/hub/checkpoints/oaar-640M.tar | torch 缓存副本 |
| **5.3G x3** | kxc/AMPGen/.../esm2_t36_3B_UR50D.pt (3份副本) | ESM2 模型 |
| **5.3G** | .cache/torch/hub/checkpoints/esm2_t36_3B_UR50D.pt | torch 缓存副本 |
| **5.2G** | kxc/colabfold_params_downloads/alphafold_params_2022-12-06.tar | ColabFold 参数包 |
| **4.4G** | kxc/peptide-app-fixed.tar | 旧项目压缩包 |
| **4.3G x8+** | ww/hug5/models/mi-pig-1b-prod-seed17/model_weights_*.pth | 训练 checkpoint |

**严重重复**：oaar-640M.tar 存在 4 份（~29G），esm2_t36_3B_UR50D.pt 存在 4 份（~21G）。

---

## 五、STAMP 项目目录占用

```
1.7G  stamp-targeted-peptide-platform/
 442M   node_modules/        ← 可重建（npm install）
 425M   data/                ← 不能删
 385M   .git/                ← 不能删
 249M   backend/             ← 不能删
 124M   dist/                ← 不能删（当前服务用）
```

---

## 六、/home/xh/kxc/靶向肽 各项目占用

| 目录 | 大小 | 说明 |
|------|------|------|
| pepmlm_gpu_generation | 4.7G | GPU 生成结果 |
| stamp-targeted-peptide-platform | 1.7G | 正式项目 |
| stamp-platform-v0.8-e2e | 640M | 旧版本 |
| backups | 493M | 备份 |
| stamp-platform-v0.8-e2e-backup-20260508_1027 | 189M | 旧备份 |

---

## 七、Docker 占用

| 类型 | 总量 | 可回收 |
|------|------|--------|
| 镜像 | 43GB | **34GB (79%)** |
| 容器 | 647MB | 475KB |
| Build Cache | **7.1GB** | **7.1GB (100%)** |
| Volumes | 28MB | 47KB |

已停止容器（对应镜像可清理）：
- peptide-app (Exited 5周前) → 镜像 peptide-app:latest **13.2GB**
- rag-memgraph (Exited 4周前) → 镜像 memgraph/memgraph-mage:3.4 **4.6GB**
- light-rag-qdrant (Exited 4周前)
- lightrag-redis (Exited 4周前)
- gallant_wright (Exited 7天前)
- docker-init_permissions-1 (Exited 4周前)

Build Cache 7.1GB 全部可清理（`docker builder prune -f`）。

---

## 八、日志占用

| 路径 | 大小 |
|------|------|
| /var/log/journal | **4.0G** |
| /var/log/sysstat | 29M |
| /home/xh/stamp/logs | 28K（正常） |

journalctl 归档日志 3.9G，可用 `journalctl --vacuum-size=500M` 清理约 3.5G。

---

## 九、缓存占用

| 缓存 | 大小 | 可清理 |
|------|------|--------|
| .cache/modelscope | 54G | 需确认（Qwen3-VL-8B 模型） |
| .cache/pip | 46G | ✅ 可清理 |
| .cache/uv | 26G | ✅ 可清理 |
| .cache/torch | 21G | 含 oaar-640M.tar 副本，需确认 |
| .cache/huggingface | 16G | 需确认 |
| .cache/colabfold | 4.9G | 需确认 |
| miniconda3/pkgs | 29G | ✅ 可清理（conda clean -p） |
| miniconda3/envs | 132G | 需确认哪些 env 不再使用 |

---

## 十、A/B/C/D 四类清理判断

### A 类：绝对不能删除

- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/` — 正式项目
- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/data/` — 数据库
- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/backend/data/` — 后端数据
- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/dist/` — 当前前端
- `/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform/.git/` — Git 历史
- `/home/xh/kxc/tools/rosetta/` — Rosetta 工具（.tar.bz2 安装包需人工确认）
- `/home/xh/micromamba/envs/localcolabfold` — ColabFold 运行环境
- `/home/xh/micromamba/envs/mmgbsa` — MMGBSA 运行环境
- `/home/xh/miniconda3/envs/stamp-md` — STAMP MD 环境
- 所有正在运行的 Docker 容器及其数据卷

### B 类：需人工确认后才能处理

- `/home/xh/zhr/MD/` (529G) — MD 轨迹，需 zhr 确认是否已分析完毕
- `/home/xh/ww/hug5/models/mi-pig-1b-prod-seed17/` (119G) — 训练 checkpoint，需确认保留哪几个
- `/home/xh/ww/af3/` (140G) — AlphaFold3 数据，需确认
- `/home/xh/kxc/AMPGen/` vs `/home/xh/kxc/ampgenkxc/` — 两份副本，需确认哪份是主用
- `/home/xh/zhr/AMPGen/` (32G) — 第三份 AMPGen 副本
- `/home/xh/kxc/colabfold_params_downloads/alphafold_params_2022-12-06.tar` (5.2G) — 已解压则可删
- `/home/xh/kxc/peptide-app-fixed.tar` (4.4G) — 旧项目压缩包
- `/home/xh/stamp_real/` (654M) — 旧版本目录
- `/home/xh/stamp_backup_20260512_181319/` (639M) — 旧备份
- `/home/xh/backups/` (475M) — 旧备份
- `/home/xh/kxc/靶向肽/stamp-platform-v0.8-e2e/` (640M) — 旧版本
- `/home/xh/kxc/靶向肽/stamp-platform-v0.8-e2e-backup-20260508_1027/` (189M) — 旧备份
- `/home/xh/saves/` (13G) — Qwen2.5 微调权重，需确认是否还需要
- `/home/xh/miniconda3/envs/` 中不再使用的 env（evodiff/yolo1/segment/dasheng 等）
- Docker 已停止容器：peptide-app、rag-memgraph、light-rag-qdrant、lightrag-redis

### C 类：通常可清理，本次不执行

| 项目 | 估计大小 | 清理命令 |
|------|----------|----------|
| pip cache | 46G | `pip cache purge` |
| uv cache | 26G | `uv cache clean` |
| conda pkgs cache | 29G | `conda clean -p` |
| Docker build cache | 7.1G | `docker builder prune -f` |
| Docker stopped containers | ~1MB | `docker container prune -f` |
| journalctl 日志 | 4G | `journalctl --vacuum-size=500M` |
| .cache/torch 中的 .tar 副本 | ~7G | 手动删 oaar-640M.tar 多余副本 |
| npm cache | 326M | `npm cache clean --force` |

**C 类合计可释放约 119G+**

### D 类：建议迁移到 /mnt/sda 或 /mnt/sdb

| 项目 | 大小 | 目标 |
|------|------|------|
| /home/xh/zhr/MD/ | 529G | /mnt/sda（剩 3.3T） |
| /home/xh/ww/hug5/ | 170G | /mnt/sda |
| /home/xh/ww/af3/ | 140G | /mnt/sda |
| /home/xh/miniconda3/envs/ | 132G | /mnt/sda（部分） |
| /home/xh/.cache/modelscope | 54G | /mnt/sdb（剩 8.2T） |
| /home/xh/kxc/AMPGen 模型文件 | ~42G | /mnt/sda |

---

## 十一、推荐优先处理前 10 项

| 优先级 | 项目 | 估计可释放 | 风险 |
|--------|------|-----------|------|
| 1 | pip cache 清理 | **46G** | 零风险 |
| 2 | conda pkgs cache 清理 | **29G** | 零风险 |
| 3 | uv cache 清理 | **26G** | 零风险 |
| 4 | Docker build cache 清理 | **7G** | 零风险 |
| 5 | journalctl vacuum | **3.5G** | 零风险 |
| 6 | 删除 oaar-640M.tar 重复副本（保留1份） | **~22G** | 低风险，需确认 |
| 7 | 删除 esm2_t36_3B_UR50D.pt 重复副本（保留1份） | **~16G** | 低风险，需确认 |
| 8 | 停止容器镜像清理（peptide-app 13G + memgraph 4.6G） | **~18G** | 需确认不再使用 |
| 9 | stamp_real + stamp_backup 旧备份 | **1.3G** | 低风险，需确认 |
| 10 | zhr/MD 迁移到 /mnt/sda | **529G** | 需 zhr 确认 |

仅 C 类（零风险）可释放约 111G，足以将磁盘从 95% 降至约 89%。
若再处理重复模型文件，可额外释放约 38G，降至约 87%。
若迁移 zhr/MD，可释放 529G，降至约 65%。

---

## 十二、预计可释放空间估算

| 操作类型 | 估计释放 |
|----------|----------|
| C 类缓存清理（零风险） | ~119G |
| 重复模型文件（低风险） | ~38G |
| 旧备份/旧版本（需确认） | ~3G |
| 停止容器镜像（需确认） | ~18G |
| zhr/MD 迁移（需协调） | ~529G |
| **合计（全部）** | **~707G** |

---

## 声明

**本次未删除任何文件。**
**本次未移动任何文件。**
**本次未执行任何清理命令。**
**本次未重启任何服务。**
