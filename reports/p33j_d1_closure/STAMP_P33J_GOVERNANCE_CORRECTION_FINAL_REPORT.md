# STAMP P33J 治理状态纠偏最终报告

**任务**: STAMP P33J —— 在 P33I 审计确认 P33H 越界执行后，对本地记忆、分类 sidecar、Registry/API/UI 进行治理纠偏。  
**执行时间**: 2026-06-29 00:38:39 +0800  
**执行者**: Kimi Code CLI / Reasonix 复核  
**目标**: 仅做治理修正，不重新执行模型、不加载 checkpoint、不新建 gate、不修改运行环境与源代码依赖、不删除审计产物。  

## 1. 变更摘要

| 组件 | 变更前 | 变更后 |
|---|---|---|
| PepGLAD registry 状态 | `controlled_smoke_verified` / `P33H_CONTROLLED_SMOKE_DELIVERED` | `pending_probe` / `P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED` |
| RFpeptides registry 状态 | `controlled_smoke_verified` / `P33H_CONTROLLED_SMOKE_DELIVERED` | `pending_probe` / `P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED` |
| PPFlow registry 状态 | `controlled_smoke_verified` / `P33G_CONTROLLED_SMOKE_VERIFIED_FROZEN` | 保持不变（P33G 合规成功证据冻结） |
| API/UI 暴露的 model list | 包含 PepGLAD/RFpeptides 的 P33H 完成状态 | 已移除 `P33H_CONTROLLED_SMOKE_DELIVERED`、`P33H_EIGHT_MODEL_DELIVERY_MANIFEST`、`8/8` 等 token |
| 重新分类 sidecar | 无 | 已创建独立 `.classification.json` 与 manifest |

## 2. 修改文件清单

- `backend/app/services/target_peptide_model_registry.py`
- `backend/tests/test_model_registry.py`
- `backend/tests/test_p33j_registry_api_ui_governance.py`

### 文件 SHA256（纠偏后）

| 文件 | SHA256 |
|---|---|
| `app/services/target_peptide_model_registry.py` | `5301cbdea9f7de38f48c4c45725ede70856724dba9bb0422e715da758efc4002` |
| `tests/test_model_registry.py` | `fe374d2f260280eb358c8c14027623f298ae6a49df73e2f9e0367b8f3ecc31ee` |
| `tests/test_p33j_registry_api_ui_governance.py` | `bfb16fafd707e1be7fa2cb0a2748d470c0abfe0271f6874620ff23f4b2590ba8` |

### 备份路径

`/home/xh/kxc/stampup/backups/p33j_governance_correction_20260628_235824/`

## 3. 侧车文件清单

`/home/xh/kxc/stampup/reports/p33j_governance_reclassification/`

- `pepglad_p33h_smoke_20260628_225316.classification.json`
- `rfpeptides_p33h_smoke_20260628_225850.classification.json`
- `STAMP_P33J_OUT_OF_SCOPE_ARTIFACT_CLASSIFICATION_MANIFEST.json`
- `STAMP_P33J_GOVERNANCE_CORRECTION_PLAN.md`
- `STAMP_P33J_REGISTRY_API_UI_PROPOSED_PATCH.diff`
- `STAMP_P33J_REGISTRY_BEFORE_SHA256_MANIFEST.txt`
- `STAMP_P33J_REGISTRY_AFTER_SHA256_MANIFEST.txt`
- `STAMP_P33J_GOVERNANCE_CORRECTION_ROLLBACK_PLAN.md`
- `STAMP_P33J_REASONIX_PRE_CORRECTION_VERDICT.md`
- `STAMP_P33J_GOVERNANCE_CORRECTION_FINAL_REPORT.md`（本文件）

## 4. 零模型测试结果

### 后端测试

```
pytest tests/test_model_registry.py tests/test_p33j_registry_api_ui_governance.py -q --tb=short
36 passed, 3 skipped, 4 warnings in 20.53s
```

- `test_model_registry.py`: registry 状态与元数据断言全部通过。
- `test_p33j_registry_api_ui_governance.py`: API/UI 治理约束断言全部通过，确认：
  - PPFlow 保持 `controlled_smoke_verified`；
  - PepGLAD / RFpeptides 为 `pending_probe`；
  - 所有模型 `real_run_enabled=false`、`execution_locked=true`、`validation_status=NOT_EXPERIMENTALLY_VALIDATED`；
  - 响应 payload 中不含 `P33H_CONTROLLED_SMOKE_DELIVERED`、`P33H_EIGHT_MODEL_DELIVERY_MANIFEST`、`8/8`。

### 前端构建

```
npm run build
exit 0
```

`dist/` 已重新生成，无构建错误。

## 5. 端口健康检查

| 端口 | 服务 | HTTP 状态 |
|---|---|---|
| 12824 | Dev backend（重启后） | 200 |
| 12823 | Dev frontend | 200 |
| 8001 | Formal backend | 200（只读，未重启） |
| 8080 | Formal frontend | 200（只读，未重启） |

## 6. API 治理字段校验（12824 在线）

`GET /api/v1/models` 返回 9 个模型：

- `ppflow`: status=`controlled_smoke_verified`, stage=`P33G_CONTROLLED_SMOKE_OK`, real_run_enabled=`False`
- `pepglad`: status=`pending_probe`, stage=`P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED`, real_run_enabled=`False`
- `rfpeptides`: status=`pending_probe`, stage=`P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED`, real_run_enabled=`False`

响应 JSON 中未出现越界交付相关 token：

- `P33H_CONTROLLED_SMOKE_DELIVERED` → False
- `P33H_EIGHT_MODEL_DELIVERY_MANIFEST` → False
- `8/8` → False

## 7. 限制与已知问题

- `GET /api/v1/models/rfpeptides` 当前返回 500，原因为 `RFpeptidesAdapter` 缺少 `model_entry` 映射。该问题在本次 P33J 治理范围之外，不影响通过 list/status 端点对 RFpeptides 治理状态的验证。P33J-D1 将处理此最小元数据接口修复。
- 本次任务未执行任何模型、未加载 checkpoint、未创建新 gate、未修改环境/依赖、未删除 `/mnt/sdb/kxc/stamp_models/` 下的审计产物。
- 形式化服务 8001/8080 保持只读，未做重启或配置变更。

## 8. 结论

P33J 治理状态纠偏已完成。PepGLAD 与 RFpeptides 在 Registry、API、测试与 sidecar 中的状态已统一降级为“P33I 越界执行证据保留 / pending_probe”；PPFlow 的 P33G 合规成功状态保持不变并继续冻结。所有零模型测试通过，开发端口 12823/12824 健康，形式化端口 8001/8080 健康且未变更。

后续如需重新执行受控 smoke，需发起新的 P33K+ 任务并获取显式授权。
