"""P33U — Lane D-min engineering + executable runner package (additive, independent).

Independent namespace for the Lane D minimal real-run scope:
    PepMLM, DiffPepBuilder, PepFlow, PepHAR

Boundaries (per P33U-C2 / P33U-D0):
- Does NOT inherit P33L attempt counts / gate state / failure history.
  P33L history (`run_gates/p33l/`) stays read-only and frozen.
- Does NOT modify p33l, p33s, model_adapters, or production (8001/8080) code.
- RunnerContract.execute() is a REAL implementation that delegates to
  runner.execute_run(). It refuses on manifest-SHA mismatch, retry (retry_count=0),
  or P33U_BLOCK_ALL_EXECUTION on the real subprocess path. Tests inject
  MockProcessRunner — no real process, no GPU, no 8189, no checkpoint load.
- Commands are list[str]; never shell=True; never string-concatenated.
- Output parsers reject empty output (never mark empty as success).
- Scorer interfaces are mock-only by default; real HTTP/PRODIGY/MM-GBSA
  execution is deferred to Lane D and requires explicit authorization.
- MIC and ipTM stay blocked. No fabricated values, ever.
- Every artifact / result tagged NOT_EXPERIMENTALLY_VALIDATED /
  COMPUTATIONAL_PREDICTION_ONLY.

Excluded from Lane D-min (require separate authorization):
    EvoBind2 (CC BY-NC 4.0), PPFlow (no LICENSE + PyRosetta + FoldX),
    MIC (no validated model), ipTM (AF2 params + GPU).
"""

from app.services.p33u.config import (  # noqa: F401
    ARTIFACT_ROOT,
    EXCLUDED_MODELS,
    GATE_ROOT,
    GPU_LOCK_PATH,
    LANE_D_MIN_MODELS,
    LINEAGE,
    MANIFEST_PATH,
    MANIFEST_SHA_PATH,
    MODEL_BY_ID,
    STATE_PATH,
    VALIDATION_STATUS,
    lane_d_min_model_ids,
)
from app.services.p33u.paths import (  # noqa: F401
    artifact_dir,
    contract_summary,
    gate_path,
    new_run_id,
    run_input_dir,
    run_output_dir,
)
from app.services.p33u.state import P33UState  # noqa: F401
from app.services.p33u import gate  # noqa: F401
from app.services.p33u.gate import (  # noqa: F401
    P33UGate,
    cancel_gate,
    close_gate,
    list_open_gates,
    mark_stale,
    open_gate,
    read_gate,
    update_pid,
)
from app.services.p33u.runner import (  # noqa: F401
    ExecutionBlocked,
    ExecutionOutcome,
    ExecutionRefused,
    MockProcessRunner,
    ProcessTransport,
    RealSubprocessTransport,
    execute_run,
)
from app.services.p33u.output_parsers import (  # noqa: F401
    ParsedOutput,
    parse_diffpepbuilder,
    parse_output,
    parse_pephar,
    parse_pepflow,
    parse_pepmlm,
)
from app.services.p33u.runner_contracts import (  # noqa: F401
    DiffPepBuilderContract,
    PepFlowContract,
    PepHARContract,
    PepMLMContract,
    RunnerContract,
    all_contracts,
    get_contract,
)
from app.services.p33u.scorer_contracts import (  # noqa: F401
    DEFAULT_ESMFOLD_ENDPOINT,
    ESMFoldHTTPScorer,
    MockTransport,
    score_iptm,
    score_kd_prodigy,
    score_mic,
    score_mmgbsa,
    validate_mmgbsa_topology_trajectory,
    validate_prodigy_complex_pdb,
)
