"""P33U configuration constants and Lane D-min model registry.

P33U is an INDEPENDENT execution namespace for the Lane D minimal real-run
scope. It does NOT inherit P33L attempt counts, gate state, or failure
history. P33L history (`run_gates/p33l/`) stays read-only and frozen.

Lane D-min scope (this package):
    PepMLM, DiffPepBuilder, PepFlow, PepHAR

Explicitly EXCLUDED from P33U Lane D-min (require separate authorization):
    EvoBind2  : CC BY-NC 4.0 design-protocol license — awaits user decision
    PPFlow    : no upstream LICENSE + PyRosetta + FoldX registration required
    MIC       : no validated model — stays unavailable_with_reason
    ipTM      : AF2-Multimer params + GPU — stays blocked

All checkpoint / source SHAs below are verified read-only on stamp218-ts.
No checkpoint is loaded by this package; no model is executed.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Independent namespace roots (sibling of p33l/, NOT under p33l/)
# ---------------------------------------------------------------------------
GATE_ROOT = "/home/xh/kxc/stampup/run_gates/p33u_lane_d"
STATE_PATH = "/home/xh/kxc/stampup/run_gates/p33u_lane_d/state.json"
ARTIFACT_ROOT = "/mnt/sdb/kxc/stamp_models/artifacts/p33u_lane_d"

# P33U does NOT reuse the P33L GPU lock path. A P33U-tagged lock avoids
# cross-namespace contention with any future P33L activity.
GPU_LOCK_PATH = "/tmp/stamp_gpu_p33u.lock"

# Lineage marker written into state.json. Explicitly declares that P33U
# attempt counts start at zero and do NOT inherit P33L's frozen history
# (PepMLM succeeded / EvoBind2 failed under P33L).
LINEAGE = "P33U_LANE_D_INDEPENDENT_OF_P33L"

# Run-id prefix distinguishes P33U jobs from P33L jobs (p33l_<model>_<uuid>).
RUN_ID_PREFIX = "p33u"

# Manifest SHA source-of-truth. The dev backend must be restarted with
# P33U_AUTHORIZED_MANIFEST_SHA=<value from this file> before any Lane D run.
MANIFEST_PATH = "/home/xh/kxc/stampup/STAMP_P33U_LANE_D_PREEXECUTION_AUTHORIZATION_MANIFEST.md"
MANIFEST_SHA_PATH = "/home/xh/kxc/stampup/STAMP_P33U_LANE_D_PREEXEC_SHA256_MANIFEST.txt"

# Block flag. Zero-model validation sets this so any runner_contract that
# accidentally tries to execute returns BLOCKED instead of spawning a process.
BLOCK_ALL_EXECUTION_ENV = "P33U_BLOCK_ALL_EXECUTION"

# Validation tag stamped on every artifact / scorer result.
VALIDATION_STATUS = "NOT_EXPERIMENTALLY_VALIDATED"
PREDICTION_TAG = "COMPUTATIONAL_PREDICTION_ONLY"

# ---------------------------------------------------------------------------
# Lane D-min model registry
# ---------------------------------------------------------------------------
# Order is the suggested execution sequence. Each model runs at most once;
# failure stops the sequence immediately (no retry, manual or automatic).
#
# SHAs verified read-only on 2026-07-02 via sha256sum on stamp218-ts.
LANE_D_MIN_MODELS = [
    {
        "order": 1,
        "model_id": "pepmlm",
        "display_name": "PepMLM",
        "license": "MIT",
        "source": "/home/xh/kxc/stampup/models_dev/pepmlm/scripts/pepmlm_infer.py",
        "source_sha256": "3805fd68bbce940f6318ec460633157b73670195915a490b205ed8e8591d988b",
        "env_python": "/home/xh/kxc/stampup/tools/envs/pepmlm/bin/python",
        "checkpoint": "/home/xh/kxc/stampup/models_dev/pepmlm/ChatterjeeLab_PepMLM-650M/model.safetensors",
        "checkpoint_sha256": "e80587d2ac4a3fb84f2be2cd4f4d02d5f2127cafc75144108ba349d4796c3668",
        "device": "cpu_or_cuda",
        "timeout_seconds": 3600,
        "disk_quota_bytes": 10737418240,
    },
    {
        "order": 2,
        "model_id": "diffpepbuilder",
        "display_name": "DiffPepBuilder",
        "license": "MIT",
        "source": "/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main",
        "source_entry_sha256": "9e32347afb16f663fb9c363511c916407c63207a38531a984603d61d83c975b2",
        "source_entry_note": "SHA of experiments/process_receptor.py (official preprocess entry)",
        "env_python": "/mnt/sdb/kxc/stamp_models/envs/diffpepbuilder_py39/bin/python",
        "checkpoint": "/mnt/sdb/kxc/stamp_models/weights/diffpepbuilder/diffpepbuilder_v1.pth",
        "checkpoint_sha256": "dbc4283257d27e38a1ce90c9344063b046ab7161745ebed1fd98a4b0439b992a",
        "device": "cuda",
        "timeout_seconds": 3600,
        "disk_quota_bytes": 10737418240,
    },
    {
        "order": 3,
        "model_id": "pepflow",
        "display_name": "PepFlow",
        "license": "MIT",
        "source": "/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main/models_con/inference.py",
        "source_sha256": "c59b5096da6582adecca967d0506efbd69ece188ef9d0903c927a67490125605",
        "env_python": "/mnt/sdb/kxc/stamp_models/envs/pepflow_py310_pypi_candidate/bin/python",
        # model2.pt is the REAL-DESIGN checkpoint (README §57); model1.pt is
        # benchmark-only. P33L manifest used model1.pt — P33U corrects to model2.pt.
        "checkpoint": "/mnt/sdb/kxc/stamp_models/checkpoints/pepflow/p25_install_probe/PepFlow2024_share/model2.pt",
        "checkpoint_sha256": "80ef4d7a07eddd877067859b5df95c50833cb72c40ef10d6ff5aa1263f0dba21",
        "device": "cuda",
        "timeout_seconds": 3600,
        "disk_quota_bytes": 10737418240,
    },
    {
        "order": 4,
        "model_id": "pephar",
        "display_name": "PepHAR",
        "license": "MIT",
        "source": "/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main",
        "source_entry_sha256": "6122cefd954591ad25be4233fa3a3464874fecbb25a6bf125bd7180387677ab2",
        "source_entry_note": "SHA of sample.py (official entry)",
        "env_python": "/mnt/sdb/kxc/stamp_models/envs/pephar_py310/bin/python",
        # CORRECTED from P33L manifest. P33L pointed at <source>/logs/... which
        # does not exist. Real checkpoints live under checkpoints/pephar/...
        "density_checkpoint": "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/density_v4_x5o2_2024_09_08__11_25_36/checkpoints/1400.pt",
        "density_checkpoint_sha256": "06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15",
        "density_config": "/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main/configs/density_v4_x5o2.yml",
        "prediction_checkpoint": "/mnt/sdb/kxc/stamp_models/checkpoints/pephar/p25_install_probe/PepHAR_ICLR2025_SHARE/ckpts/prediction_d2_x2o1_2024_09_08__11_21_33/checkpoints/2400.pt",
        "prediction_checkpoint_sha256": "94eb9933312a4c851e3a6dae44f2435dcfc417648d271ca75e8c22bebc1523f6",
        "prediction_config": "/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main/configs/prediction_d2_x2o1.yml",
        "device": "cuda",
        "timeout_seconds": 3600,
        "disk_quota_bytes": 10737418240,
    },
]

# Explicitly excluded models with reasons (for manifest transparency).
EXCLUDED_MODELS = {
    "evobind2": "CC BY-NC 4.0 design-protocol license — awaits explicit user non-commercial-research authorization",
    "ppflow": "no upstream LICENSE file + PyRosetta registration + FoldX academic license all required",
    "mic": "no validated MIC model on disk — stays unavailable_with_reason",
    "iptm": "AF2-Multimer params repair + GPU window required — stays blocked",
}

MODEL_BY_ID = {m["model_id"]: m for m in LANE_D_MIN_MODELS}


def lane_d_min_model_ids() -> list[str]:
    return [m["model_id"] for m in LANE_D_MIN_MODELS]
