# STAMPUP P5：上传 PepMLM 离线模型工件到服务器 models_dev 并做 SHA256 校验报告

## 1. 对账结果
- 服务器连接：`ssh stamp218` 可用
- 服务器主机：`xh-System-Product-Name`
- 服务器用户：`xh`
- 开发环境：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev`
- 开发前端：`http://192.168.31.218:12823` 正常
- 开发后端：`http://192.168.31.218:12824/api/health` 正常
- 正式前端：`http://192.168.31.218:8080` 正常
- 正式后端：`http://192.168.31.218:8001/api/health` 正常
- `/home/xh/stamp` 软链接未变更，仍指向正式项目
- `stampup_status.sh` 与 `stampup_healthcheck.sh` 在项目目录下运行均 PASS
- 服务器磁盘空间：约 `82G` 可用，足够容纳本次 2.61GB 模型工件

## 2. 本地源目录
- PepMLM 本地根目录：`D:i\models\pepmlm`
- 模型权重目录：`D:i\models\pepmlm\models\ChatterjeeLab_PepMLM-650M`
- 源码目录：`D:i\models\pepmlm\source\pepmlm`
- manifest 目录：`D:i\models\pepmlm\manifests`

## 3. 服务器目标目录
- 模型权重目标目录：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M`
- 源码目标目录：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm`
- manifest 目标目录：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/manifests`
- checks 目标目录：`/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/checks`

## 4. 上传方式
- 模型权重：`scp -r`
- 源码目录：`scp -r`
- manifest 文件：`scp`
- 未压缩上传，未删除已上传内容

## 5. 上传文件数量
- 服务器模型文件数：`18`
- 服务器源码树文件数：`39`
- manifest 文件数：`4`
- 模型工件总大小：`2,609,662,634 bytes`

## 6. 必需文件检查结果
- `pytorch_model.bin`：OK
- `config.json`：OK
- `tokenizer_config.json`：OK
- `special_tokens_map.json`：OK
- `vocab.txt`：OK
- `README.md`：OK

## 7. pytorch_model.bin SHA256 本地值
- `8A3225BCA1F9ACD9F701CA2E46597C12BAB92320E32B68F380DDF3B6D3B20770`

## 8. pytorch_model.bin SHA256 服务器值
- `8a3225bca1f9acd9f701ca2e46597c12bab92320e32b68f380ddf3b6d3b20770`

## 9. SHA256 是否一致
- 一致

## 10. 源码本地 commit
- `3169c4920f8c383948e0a5d3a7c8f87e5e7d2436`

## 11. 源码服务器 commit
- `3169c4920f8c383948e0a5d3a7c8f87e5e7d2436`

## 12. commit 是否一致
- 一致

## 13. 服务器端 manifest 路径
- `models_dev/pepmlm/checks/server_model_files_manifest.tsv`
- `models_dev/pepmlm/checks/server_model_sha256.tsv`
- `models_dev/pepmlm/checks/server_source_files_manifest.tsv`
- `models_dev/pepmlm/checks/pytorch_model_bin.sha256.txt`
- `models_dev/pepmlm/checks/source_git_log.txt`

## 14. 是否更新 .env 或配置文件
- 已更新 `backend/.env`
- 新增或覆盖：
  - `PEPMLM_MODEL_PATH=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M`
  - `PEPMLM_SOURCE_PATH=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/pepmlm/source/pepmlm`
  - `TARGET_PEPTIDE_MODELS_DIR=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev`
  - `HF_HOME=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/hf_home`
  - `TRANSFORMERS_CACHE=/home/xh/kxc/stampup/stamp-targeted-peptide-platform-target-design-dev/models_dev/transformers_cache`
  - `PEPMLM_DEVICE=cuda`
  - `PEPMLM_ALLOW_DOWNLOAD=false`
  - `PEPMLM_OFFLINE_ONLY=true`
- 未设置 `PEPMLM_HF_MODEL_ID`，保持未配置状态

## 15. 重新 probe 结果
- `GET /api/v1/target-peptide-design/models/PepMLM/probe`
  - `pepmlm_model_path_configured: true`
  - `pepmlm_model_path_exists: true`
  - `pepmlm_model_path_is_dir: true`
  - `pepmlm_model_path_empty: false`
  - `status: DEPENDENCY_MISSING`
- `GET /api/v1/target-peptide-design/models/probe`
  - 汇总状态仍为 `DEPENDENCY_MISSING`
  - 说明：路径已识别，但服务器环境仍缺少 `torch` / `transformers` / `huggingface_hub`

## 16. 当前 PepMLM 综合状态
- `DEPENDENCY_MISSING`
- 原因：服务器 backend 环境中未安装 `torch`、`transformers`、`huggingface_hub`
- 这是正常状态，不影响本次离线工件上传与路径识别

## 17. 正式 8080 验证结果
- `curl -I http://192.168.31.218:8080`：`200 OK`
- 正式环境未改动

## 18. 正式 8001 验证结果
- `curl http://192.168.31.218:8001/api/health`：健康
- 正式环境未改动

## 19. 开发 12823 验证结果
- `curl -I http://192.168.31.218:12823`：`200 OK`
- `stampup_status.sh`：PASS
- `stampup_healthcheck.sh`：PASS

## 20. 开发 12824 验证结果
- `curl http://192.168.31.218:12824/api/health`：健康
- `curl http://192.168.31.218:12824/api/v1/target-peptide-design/models/PepMLM/probe`：可用，路径已识别，状态 `DEPENDENCY_MISSING`
- `curl http://192.168.31.218:12824/api/v1/target-peptide-design/models/probe`：可用，汇总状态 `DEPENDENCY_MISSING`

## 21. `/home/xh/stamp` 验证结果
- `readlink -f /home/xh/stamp`
- 结果：`/home/xh/kxc/靶向肽/stamp-targeted-peptide-platform`
- 软链接未变

## 22. 是否安装依赖：否
- 未安装 `torch`
- 未安装 `transformers`
- 未安装 `huggingface_hub`

## 23. 是否运行 PepMLM：否
## 24. 是否生成候选肽：否
## 25. 是否伪造科学结果：否

## 26. 额外说明
- `models_dev/hf_home` 和 `models_dev/transformers_cache` 已创建，用于后续隔离缓存
- 本次上传和校验都限定在 `stampup` 开发副本目录下，没有触碰正式环境
- 上传后本地校验与服务器校验一致，模型文件数、总大小、SHA256、源码 commit 均对齐

## 27. 下一步建议
1. 如果后续要真正接入 PepMLM，需要先补齐 backend Python 依赖，再决定是离线推理还是受控下载。
2. 建议下一步把 `PEPMLM_HF_MODEL_ID` 作为可选配置补上，再让 probe 区分“本地工件优先”与“HF 只读元数据”两种模式。
3. 在真正运行模型之前，不要把 `torch` / `transformers` 安装流程混入正式环境。
