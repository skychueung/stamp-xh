# STAMP P33M — DiffPepBuilder Failed, Four-Model Continuation Stopped

## Final Gate

`P33M_DIFFPEPBUILDER_FAILED_STOPPED_NO_RETRY`

## Scope

User instructed execution of the four remaining models. P33M isolated this continuation from P33L and fixed the order as DiffPepBuilder → PepFlow → PepHAR → PPFlow, one attempt each, failure-stop, no retry.

Frozen execution manifest SHA256:

`82e8d3cc7301e6ea0d30a7872fadca6c6ddc5021849361f7c7ccf522912088a6`

## Results

| Order | Model | Result | Detail |
|---:|---|---|---|
| 1 | DiffPepBuilder | FAILED | Official receptor preprocessor could not find the project `.git` root indicator |
| 2 | PepFlow | SKIPPED_DUE_TO_PRIOR_FAILURE | Not started |
| 3 | PepHAR | SKIPPED_DUE_TO_PRIOR_FAILURE | Not started |
| 4 | PPFlow | SKIPPED_DUE_TO_PRIOR_FAILURE | Not started |

DiffPepBuilder job:

`p33m_diffpepbuilder_226b1a8fc8e043e0`

Exact error:

```text
FileNotFoundError: Project root directory not found. Indicators: ['.git']
```

The error occurred in the official `experiments/process_receptor.py` through `pyrootutils.setup_root` before inference/checkpoint loading. The extracted source directory does not provide the `.git` indicator expected by that script.

## Evidence SHA256

- P33M run manifest: `761c07d296510ba6867f10eaf9a530e53f35bf34a475a00c376b908e8599904f`
- Artifact SHA manifest: `9706044e3ec8b460b60d641dde1c2f0428bfe348f0f79049d4ffe234a3c46da0`
- DiffPepBuilder runner manifest: `78a9ed7564deae7a6a8cf1d7fda4758d456df9d2335ed4543f4ad2a06109be2f`
- Failure log: `a430561e57231911340dc950004ca3abe33cdfe7d2937f7e6a3809ce037d4b79`
- P33M state: `f8f7a85a15d9cc6714b97e93c5309b9605bb773b2efa357df6a2f6d949f032d3`
- Driver: `523349094542142dd865f6cc527e53b3b85b50e4c23ca1e9d94ea9aefa7d0ae6`

## Safety state

- P33M JSON gate is closed.
- GPU lock is absent.
- No P33M/model process remains.
- Ports 12823/12824/8001/8080 return HTTP 200.
- No existing GPU workload was terminated or preempted.
- All evidence remains `NOT_EXPERIMENTALLY_VALIDATED`.

## Boundary

No retry was attempted. PepFlow, PepHAR and PPFlow were not started. Fixing the source-root assumption and retrying requires a new task and new authorization.

