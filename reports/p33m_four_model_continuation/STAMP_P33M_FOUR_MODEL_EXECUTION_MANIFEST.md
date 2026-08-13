# STAMP P33M — Four-Model Continuation Execution Manifest

## Authorization and scope

User instruction: `运行4个模型`.

This is a new isolated continuation after P33L stopped on EvoBind2. It does not alter, retry or reclassify PepMLM/EvoBind2 evidence.

- Fixed order: DiffPepBuilder → PepFlow → PepHAR → PPFlow
- One attempt per model
- Any failure stops the sequence
- No automatic or manual retry
- No model source, checkpoint, input or scientific-parameter modification
- Existing non-P33M GPU processes must not be terminated or preempted
- All outputs: `NOT_EXPERIMENTALLY_VALIDATED`

## Isolation

- Driver: `/home/xh/kxc/stampup/scripts/p33m_four_model_driver.py`
- Driver SHA256: `523349094542142dd865f6cc527e53b3b85b50e4c23ca1e9d94ea9aefa7d0ae6`
- Artifact root: `/mnt/sdb/kxc/stamp_models/artifacts/p33m/`
- Gate/state root: `/home/xh/kxc/stampup/run_gates/p33m/`
- P33L evidence remains read-only.

The driver uses a JSON authorization gate and, only where required by legacy runners, a separate `legacy_gate.flag`; it never overwrites the JSON gate.

## Frozen model inputs

### 1. DiffPepBuilder

- Source: `/mnt/sdb/kxc/stamp_models/source/diffpepbuilder/extracted_p24_install_probe/DiffPepBuilder-main/experiments/run_inference.py`
- Source SHA256: `872868f48e3cf66f0ce159ada589ca2126a3b2ba98470ab3bbcb9ffc4481f7c6`
- Runner: `/mnt/sdb/kxc/stamp_models/scripts/stamp_diffpepbuilder_p33l_real_runner.py`
- Runner SHA256: `09ed88320f9eef8dd5e8bb40814620e3a8c117d7c21a1e131a8fa9f2ec039d29`
- Checkpoint SHA256: `dbc4283257d27e38a1ce90c9344063b046ab7161745ebed1fd98a4b0439b992a`
- Fixture SHA256: `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc`
- Timeout: 3600 seconds

### 2. PepFlow

- Source: `/mnt/sdb/kxc/stamp_models/source/pepflow/extracted_p25_install_probe/PepFlowww-main/models_con/inference.py`
- Source SHA256: `c59b5096da6582adecca967d0506efbd69ece188ef9d0903c927a67490125605`
- Checkpoint SHA256: `ee3f0458cc47b63f2c5c8bc27f0e9897fab395592a2beb5e627a42f74754fb0a`
- Fixture SHA256: `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc`
- Timeout: 3600 seconds

### 3. PepHAR

- Source: `/mnt/sdb/kxc/stamp_models/source/pephar/extracted_p25_install_probe/PepHAR-main/evaluate/sample.py`
- Source SHA256: `f84f6a20f95dd644fd8d5952c7a7c61e58612310d80fd2756a2e4e24f2991a85`
- Runner: `/mnt/sdb/kxc/stamp_models/scripts/stamp_pephar_p33l_real_runner.py`
- Runner SHA256: `7b979aa2b1cd146e82523c5ea3356268aeb073a022c3dcbaa9ffebdd65d3265f`
- Prediction checkpoint SHA256: `94eb9933312a4c851e3a6dae44f2435dcfc417648d271ca75e8c22bebc1523f6`
- Density checkpoint SHA256: `06b9a2701a9594158de2650d10da756c51dda3cc410ea98c47cf9fd1dbc32d15`
- Fixture SHA256: `db60daf68e547f6f3727cdb7bccda77ae22520e586aa566c1e5f543dc6fc09dc`
- Timeout: 3600 seconds

### 4. PPFlow

- Source: `/mnt/sdb/kxc/stamp_models/source/ppflow/extracted_p25_install_probe/ppflow-main/codesign_ppf.py`
- Source SHA256: `1bf50964b4f4e34b594b894a274d6c119361e1eba00f2c58e70c41200fc92d08`
- Checkpoint SHA256: `be1b53ae09dee78c45faa84c4c90f6c65c285c64e70d3b6e8c931b93abaa6d5d`
- Fixture SHA256: `1091c39a332ff29e917f8124afc472b2d717b9a73ff2e40088fc408a264b999b`
- Timeout: 3600 seconds

## Final policy

The driver records one final state per model. A non-zero exit, timeout, quota violation, missing runtime dependency or other failure terminates P33M immediately, leaving subsequent models unstarted.
