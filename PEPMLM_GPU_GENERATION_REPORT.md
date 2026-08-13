# PepMLM GPU 生成 OprF 靶向肽候选库报告

**版本**: v0.6d-P1c GPU Expansion
**生成日期**: 2026-04-29 23:45:08
**服务器**: 192.168.31.218
**GPU**: 2x NVIDIA GeForce RTX 4090 (24GB)

---

## 1. GPU 状态

- torch: 2.11.0+cu130
- CUDA Available: True
- CUDA Devices: 2
  - NVIDIA GeForce RTX 4090
  - NVIDIA GeForce RTX 4090

## 2. Python / Torch / CUDA 状态

- Python: 3.12.3
- torch: 2.11.0+cu130
- transformers: 5.7.0
- numpy: 1.26.4
- pandas: 3.0.2

## 3. PepMLM 模型是否可用

- 模型名称: TianlaiChen/PepMLM-650M
- 架构: EsmForMaskedLM
- 加载状态: ✅ 成功（本地缓存加载）

## 4. 是否使用 GPU

✅ **是**，使用 CUDA (RTX 4090)

## 5. 生成参数

- 目标蛋白: Pseudomonas_OprF (61 aa)
- 生成模式: OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING
- 解码策略: top_k_sampling_on_full_mask
- top_k: 3
- seeds: [42, 43, 44]
- peptide_lengths: [12, 15, 18]
- 请求数量: 1000

## 6. 总候选数

- 生成总数: 1000
- 去重后唯一: 999
- 生成耗时: 61.4 秒

## 7. Pass / Warning / Fail 数量

- Pass: 659
- Warning: 340
- Fail: 0

## 8. Top50 序列列表

| Rank | ID | 序列 | 长度 | PPL | 电荷 | GRAVY | pI | Cys | 状态 | 推荐理由 |
|---:|:---|:---|---:|---:|---:|---:|---:|---:|:---|:---|
| 1 | OPRF_0001 | `KKTAQAALAALS` | 12 | 5.5683 | 2.0 | 0.317 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 2 | OPRF_0002 | `KKTLQQALAAGG` | 12 | 5.845 | 2.0 | -0.275 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 3 | OPRF_0003 | `DKTAKAFLAALG` | 12 | 5.1895 | 1.0 | 0.433 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 4 | OPRF_0004 | `DKTAKAAAILGG` | 12 | 5.3241 | 1.0 | 0.225 | 7.4 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 5 | OPRF_0005 | `KKTAKQAIALLG` | 12 | 6.086 | 3.0 | 0.1 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 6 | OPRF_0006 | `KATAAQALALAS` | 12 | 5.2349 | 1.0 | 0.792 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 7 | OPRF_0007 | `DKSKQALAIALG` | 12 | 5.6339 | 1.0 | 0.125 | 7.4 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 8 | OPRF_0008 | `KAKAAQAAALLG` | 12 | 6.182 | 2.0 | 0.558 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 9 | OPRF_0009 | `KATLQQALAKAS` | 12 | 6.3805 | 2.0 | -0.125 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 10 | OPRF_0010 | `DATKKQALAAAG` | 12 | 5.7778 | 1.0 | -0.258 | 7.4 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 11 | OPRF_0011 | `SATLKQALALGG` | 12 | 5.5991 | 1.0 | 0.592 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 12 | OPRF_0012 | `SKTAQALALAAG` | 12 | 5.7475 | 1.0 | 0.608 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 13 | OPRF_0013 | `DATLAQALAAAG` | 12 | 4.3948 | -1.0 | 0.858 | 6.6 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 14 | OPRF_0014 | `KKDSAKALKLAAAIN` | 15 | 6.8096 | 3.0 | -0.153 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 15 | OPRF_0015 | `DAAKAAASAKKAGAAAKG` | 18 | 6.8199 | 3.0 | -0.15 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 16 | OPRF_0016 | `KKTAAAFLAALG` | 12 | 6.4689 | 2.0 | 0.875 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 17 | OPRF_0017 | `DKDSAKKIAKLLAAG` | 15 | 6.9296 | 2.0 | -0.3 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 18 | OPRF_0018 | `DKTAKLLAIAGS` | 12 | 6.2636 | 1.0 | 0.358 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 19 | OPRF_0019 | `KKTAKAAAAALT` | 12 | 7.0235 | 3.0 | 0.125 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 20 | OPRF_0020 | `KKSLKALIAAGG` | 12 | 7.0739 | 3.0 | 0.35 | 8.2 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 21 | OPRF_0021 | `TKTAASAAILAAGAALAK` | 18 | 6.684 | 2.0 | 0.994 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 22 | OPRF_0022 | `KATAKAFIAALS` | 12 | 6.7614 | 2.0 | 0.9 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 23 | OPRF_0023 | `KKTAKQLAILLG` | 12 | 7.1993 | 3.0 | 0.267 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 24 | OPRF_0024 | `DKTLQAALALGG` | 12 | 5.8543 | 0.0 | 0.367 | 7.0 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 25 | OPRF_0025 | `KKKAQALAAKAG` | 12 | 7.2559 | 4.0 | -0.558 | 8.6 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 26 | OPRF_0026 | `DKKAKLAAALAG` | 12 | 7.2945 | 2.0 | 0.083 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 27 | OPRF_0027 | `DATLKQALIAGG` | 12 | 5.9351 | 0.0 | 0.425 | 7.0 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 28 | OPRF_0028 | `KKTAQQAIAKLT` | 12 | 7.3525 | 3.0 | -0.533 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 29 | OPRF_0029 | `KTTLKQAAILAG` | 12 | 7.4004 | 2.0 | 0.367 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 30 | OPRF_0030 | `DKTAKAALIALG` | 12 | 6.5981 | 1.0 | 0.575 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 31 | OPRF_0031 | `DKTAQQALAALG` | 12 | 6.1512 | 0.0 | -0.058 | 7.0 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 32 | OPRF_0032 | `DKTAKAAAIKLS` | 12 | 7.4896 | 2.0 | -0.1 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 33 | OPRF_0033 | `DKTVKKALKLAGAAG` | 15 | 7.4916 | 3.0 | -0.107 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 34 | OPRF_0034 | `TADSALKAAKAAALK` | 15 | 7.5161 | 2.0 | 0.233 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 35 | OPRF_0035 | `DATAKAALIAAG` | 12 | 5.7973 | 0.0 | 0.883 | 7.0 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 36 | OPRF_0036 | `SAKAAQLAALGG` | 12 | 6.6653 | 1.0 | 0.633 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 37 | OPRF_0037 | `DKTAQQALAALS` | 12 | 6.2285 | 0.0 | -0.092 | 7.0 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 38 | OPRF_0038 | `DKTAQQLAALLG` | 12 | 6.2298 | 0.0 | 0.108 | 7.0 | 0 | Pass | Low PPL; Good hydrophobicity; No Cys; Ideal length |
| 39 | OPRF_0039 | `KKTAAALAAAAAGLAAAG` | 18 | 7.1539 | 2.0 | 1.006 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 40 | OPRF_0040 | `TATASKSAILAGALAAAK` | 18 | 7.2775 | 2.0 | 0.85 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 41 | OPRF_0041 | `TATAAKALALAGGLAAKK` | 18 | 7.4458 | 3.0 | 0.661 | 8.2 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 42 | OPRF_0042 | `DKTAKAFLIALT` | 12 | 6.824 | 1.0 | 0.633 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 43 | OPRF_0043 | `TATAKKAAAKAAAIG` | 15 | 7.6958 | 3.0 | 0.36 | 8.2 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 44 | OPRF_0044 | `DATAKSSLAKAGALAAAG` | 18 | 7.0244 | 1.0 | 0.422 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 45 | OPRF_0045 | `DATKSALAKKAGAAAAAA` | 18 | 7.837 | 2.0 | 0.261 | 7.8 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |
| 46 | OPRF_0046 | `KADAKKLAAALALLG` | 15 | 7.5972 | 2.0 | 0.693 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 47 | OPRF_0047 | `TATKSAAAIKKLGAAIAG` | 18 | 7.6948 | 3.0 | 0.594 | 8.2 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 48 | OPRF_0048 | `KATAQALLALAG` | 12 | 6.7832 | 1.0 | 0.992 | 7.4 | 0 | Warning | Low PPL; No Cys; Ideal length |
| 49 | OPRF_0049 | `KTTAKQLAILLG` | 12 | 7.7573 | 2.0 | 0.533 | 7.8 | 0 | Pass | Low PPL; Good charge; No Cys; Ideal length |
| 50 | OPRF_0050 | `KKTLKQAALLGG` | 12 | 7.9155 | 3.0 | -0.142 | 8.2 | 0 | Pass | Low PPL; Good charge; Good hydrophobicity; No Cys; Ideal length |

## 9. Top100 文件路径

- JSON: `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top100_candidates.json`
- CSV: `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top100_candidates.csv`

## 10. 输出文件路径

服务器路径:
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_1000_candidates.json`
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_1000_candidates.csv`
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top50_candidates.json`
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top50_candidates.csv`
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top100_candidates.json`
- `/home/xh/kxc/靶向肽/pepmlm_gpu_generation/outputs/pepmlm_oprf_top100_candidates.csv`

## 11. 当前 8088 服务是否未受影响

✅ **未受影响**。STAMP 平台后端 (PID 3693700) 持续运行中。

## 12. GO / NO-GO

| 检查项 | 状态 |
|:---|:---|
| GPU 可用 | ✅ |
| 模型加载成功 | ✅ |
| 1000 条候选生成完成 | ✅ |
| 去重后 999 条唯一 | ✅ |
| Top50/Top100 输出完成 | ✅ |
| 8088 服务未受影响 | ✅ |
| 无伪造实验指标 | ✅ |

**最终判定**: **GO** ✅

---
*报告结束*