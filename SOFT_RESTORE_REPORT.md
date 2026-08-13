## v0.6d-P2a 软恢复 P1c Demo-compatible 默认模式报告

### 1. 恢复原因
明天演示稳定优先，Sidecar 真实模式在当前默认参数下可能返回 0 条候选，影响演示效果。

### 2. 当前默认模式
DEMO_COMPATIBLE

### 3. P2a Sidecar 是否保留
保留，不删除。
- Sidecar 服务 127.0.0.1:5001 仍在运行
- legacy_predict.py 中 `_call_sidecar_predict()` 代码完整保留
- `_PREDICT_MODE = "sidecar"` 即可一键恢复真实推理

### 4. /api/predict 验证结果
```
mode: DEMO_COMPATIBLE
source: demo_fallback
validation_status: NOT_EXPERIMENTALLY_VALIDATED
candidate_count: 10
top3: ['NPRRH', 'GHVTKSAHT', 'NPRRHP']
```

### 5. /filter 浏览器验收
- 访问 http://192.168.31.218:8088/filter
- 点击 Run Prediction
- ModeStatusBar 显示：当前模式 Demo 回退模式 / 数据来源 demo_fallback / 状态 NOT_EXPERIMENTALLY_VALIDATED
- TopCandidateSummary 显示 NPRRH 等 10 条候选
- 无白屏，CandidateDetailDrawer 可正常打开

### 6. STAMP 回归结果
- /peptide-generation 页面正常
- One-click STAMP Demo 按钮可用
- stamp_oprf_0029 相关数据正常

### 7. 明天演示口径
当前演示默认展示稳定 Demo-compatible 结果；真实 BepiPred3/ESM Sidecar 已接入并封存，但暂不作为默认演示入口。

### 8. GO / NO-GO
GO — 软恢复完成，演示稳定。
