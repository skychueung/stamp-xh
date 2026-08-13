# STAMP P33J 零模型测试摘要

**时间**: 2026-06-29 00:38:39 +0800  
**命令**: `pytest tests/test_model_registry.py tests/test_p33j_registry_api_ui_governance.py -q --tb=short`  
**结果**: 36 passed, 3 skipped, 4 warnings  
**前端构建**: `npm run build` exit 0  
**端口**: 12823/12824/8001/8080 均 200  

## 关键断言

- PPFlow 保持 `controlled_smoke_verified` / `P33G_CONTROLLED_SMOKE_OK` / `real_run_enabled=false`。
- PepGLAD / RFpeptides 降级为 `pending_probe` / `P33I_OUT_OF_SCOPE_EXECUTION_EVIDENCE_PRESERVED` / `real_run_enabled=false`。
- API 响应不含 `P33H_CONTROLLED_SMOKE_DELIVERED`、`P33H_EIGHT_MODEL_DELIVERY_MANIFEST`、`8/8`。
- 所有模型 `execution_locked=true`、`validation_status=NOT_EXPERIMENTALLY_VALIDATED`。
