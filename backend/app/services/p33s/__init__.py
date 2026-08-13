"""P33S — Real-model GPU inference & scientific scoring pipeline (Phase 3).

Unified architecture: generation -> structure -> affinity/MIC -> MM-GBSA -> delivery.

Design constraints (per P33S goal):
- Every job emits a provenance manifest: manifest SHA, input SHA, weight SHA,
  code SHA, env, seed, GPU, start/end time, exit code.
- Idempotent, timeout, disk-quota, precise PID cleanup, GPU lock, cancel,
  failure-state persistence.
- No pkill / no rm -rf globs / no cross-task gate sharing.
- API distinguishes probe / dry-run / real-run.
- Scorers are independent post-processing modules; never fabricate values.
  not_applicable / failed_with_evidence / unavailable_with_reason are first-class.
- All outputs tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL PREDICTION ONLY.

This package is additive; it does not modify existing P33Q/P33R adapters or
the production registry. It reuses gpu_lock_service for GPU arbitration.
"""

from app.services.p33s.provenance import (  # noqa: F401
    ProvenanceManifest,
    code_sha_of_files,
    sha256_bytes,
    sha256_file,
    write_manifest,
)
from app.services.p33s.gate import (  # noqa: F401
    GateState,
    cancel_gate,
    close_gate,
    list_open_gates,
    mark_stale,
    open_gate,
)
