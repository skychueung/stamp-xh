# STAMPUP P3：模型状态探针与 PepMLM 环境可用性检查报告

## 1. 对账结果
- 宿主机：`xh-System-Product-Name`
- 当前用户：`xh`
- 工作目录：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- 正式软链接：`/home/xh/stamp -> /home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`，未变更
- 开发前端：`http://192.168.31.218:12823`，健康
- 开发后端：`http://192.168.31.218:12824/api/health`，健康
- 正式前端：`http://192.168.31.218:8080`，健康
- 正式后端：`http://192.168.31.218:8001/api/health`，健康
- 开发运行时端口：`12823/12824` 已重新启动并稳定监听
- 运行时代码中未再出现默认 `8000` 直连残留

## 2. 修改文件清单
- `backend/app/core/config.py`
- `backend/.env`
- `backend/app/schemas/target_peptide_design.py`
- `backend/app/schemas/__init__.py`
- `backend/app/routers/target_peptide_design.py`
- `backend/app/services/target_peptide_model_probe.py`
- `backend/tests/test_target_peptide_model_probe.py`
- `src/lib/targetPeptideDesignApi.ts`
- `src/pages/TargetedPeptideDesignPage.tsx`

## 3. 新增 probe API 清单
- `GET /api/v1/target-peptide-design/models/probe`
- `GET /api/v1/target-peptide-design/models/PepMLM/probe`

## 4. PepMLM 探针字段说明
- `probe_time`
- `model_id`
- `display_name`
- `status`
- `message`
- `dependency_status`
- `cuda_status`
- `path_status`
- `config_status`
- `scientific_boundary`
- `next_action`

### 4.1 状态判定
- `DEPENDENCY_MISSING`：后端环境里 `torch` / `transformers` / `huggingface_hub` 缺失
- `CONFIG_REQUIRED`：PepMLM 模型路径或 HuggingFace 模型 ID 未配置
- `OFFLINE_ONLY`：离线模式下无本地模型工件，不允许下载
- `GPU_NOT_AVAILABLE`：本地工件可用，但 CUDA 不可用
- `AVAILABLE`：环境探针通过，但本阶段仍不执行真实推理
- `MODEL_NOT_AVAILABLE`：模型工件不可用或路径不可写

## 5. 实际 Python / torch / transformers / CUDA 检查结果
- Python：`/usr/bin/python3`
- Python 版本：`3.12.3`
- pip：`/usr/bin/pip3`
- pip 版本：`24.0`
- `torch`：未安装，`ModuleNotFoundError: No module named 'torch'`
- `transformers`：未安装，`ModuleNotFoundError: No module named 'transformers'`
- `huggingface_hub`：未安装，`ModuleNotFoundError: No module named 'huggingface_hub'`
- CUDA：不可用，因为 `torch` 不存在，未进行真实推理
- `nvidia-smi`：检测到 2 张 `NVIDIA GeForce RTX 4090`，每张 24564 MiB，驱动 `580.126.09`

## 6. models_dev 可写性
- `TARGET_PEPTIDE_MODELS_DIR=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev`
- `models_dev` 可写：`true`
- `data_dev/target_peptide_design` 可写：`true`
- `data_dev/target_peptide_design/probes` 可写：`true`
- probe 结果文件已落盘：
  - `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/target_peptide_design/probes/models_probe_20260602_123851.json`
  - `/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/data_dev/target_peptide_design/probes/pepmlm_probe_20260602_123851.json`

## 7. 数据与配置状态
- `PEPMLM_MODEL_PATH`：未配置
- `PEPMLM_HF_MODEL_ID`：未配置
- `PEPMLM_DEVICE=auto`
- `PEPMLM_ALLOW_DOWNLOAD=false`
- `PEPMLM_OFFLINE_ONLY=true`
- `TARGET_PEPTIDE_MODELS_DIR` 已预留到 stampup `models_dev`
- 本次没有下载任何模型，也没有调用 GPU 推理

## 8. 当前 PepMLM 综合状态
- `/api/v1/target-peptide-design/models/probe` 返回的 PepMLM 汇总状态：`DEPENDENCY_MISSING`
- `/api/v1/target-peptide-design/models/PepMLM/probe` 返回的 PepMLM 详细状态：`DEPENDENCY_MISSING`
- `next_action`：安装缺失的 Python 依赖后再重新探针

## 9. 前端页面新增展示说明
- 页面：`/targeted-peptide-design`
- 新增了模型探针刷新按钮
- 新增了 PepMLM 环境状态卡片
- 展示了 torch / transformers / CUDA / 路径 / 配置 / next action
- 展示了模型探针概览表和科学边界提示
- 页面明确提示：当前仅执行环境探针，未下载模型、未运行 PepMLM、未生成候选肽

## 10. 后端测试结果
- `pytest backend/tests/test_target_peptide_design.py backend/tests/test_target_peptide_model_probe.py -q`
- 结果：`12 passed`
- `pytest -q`
- 结果：仍被既有 collection import error 阻断
- 阻断文件：`backend/tests/test_flexpepdock_batch.py`
- 错误：`ImportError: cannot import name 'compute_batch_status_from_items' from 'app.services.batch_compute_runner'`
- 该错误不是本次 P3 引入

## 11. 前端 `npm run build` 结果
- `npm run build` 通过
- `tsc -b && vite build` 成功
- Vite 提示当前 Node 版本为 `18.19.1`，低于其建议版本范围，但这次构建仍成功

## 12. 8000 残留检查结果
- `src/`、`vite.config.ts`、`.env*` 中未发现默认 `8000` 直连残留
- 运行时代码未再出现 `localhost:8000` / `127.0.0.1:8000` / `192.168.31.218:8000` / `:8000` 的默认 client
- `ss -lntp` 看到的 `8000` 端口属于其他系统服务 `labelu`，不是 STAMP 开发副本

## 13. 开发 12823 验证结果
- `curl -I http://192.168.31.218:12823`：`200 OK`
- `bash scripts/ops/stampup_status.sh`：PASS
- `bash scripts/ops/stampup_healthcheck.sh`：PASS

## 14. 开发 12824 验证结果
- `curl http://192.168.31.218:12824/api/health`：健康
- `curl http://192.168.31.218:12824/api/v1/target-peptide-design/models/probe`：返回 10 个模型探针与汇总
- `curl http://192.168.31.218:12824/api/v1/target-peptide-design/models/PepMLM/probe`：返回 PepMLM 详细探针，状态 `DEPENDENCY_MISSING`

## 15. 正式 8080 验证结果
- `curl -I http://192.168.31.218:8080`：`200 OK`
- 正式环境未改动

## 16. 正式 8001 验证结果
- `curl http://192.168.31.218:8001/api/health`：健康
- 正式后端未改动

## 17. `/home/xh/stamp` 验证结果
- `readlink -f /home/xh/stamp`
- 结果：`/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`
- 软链接未变

## 18. 是否真实运行 PepMLM：否
## 19. 是否下载模型：否
## 20. 是否生成候选肽：否
## 21. 是否伪造科学结果：否

## 22. 结果摘要
- 本次只完成环境探针、状态展示、probe 持久化与相关 UI/API 收口
- 未接入任何新模型
- 未对正式环境做写入、停止或重启
- 未改动 `/home/xh/stamp`

## 23. 下一步建议
1. 如果要继续进入 P4，先补齐后端 Python 依赖管理策略，并明确 PepMLM 是否走离线本地工件或受控下载。
2. 再为 `TARGET_PEPTIDE_MODELS_DIR`、`HF_HOME`、`TRANSFORMERS_CACHE` 设计统一的 stampup 隔离策略。
3. 在真正接入 PepMLM 之前，先把可用性探针做成可重复运行的运维入口。
