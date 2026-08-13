// P33U D20G Dev Run Console API client.
// All responses tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.
// PPFlow is never invoked. Dev-only.

export const P33U_API_BASE = '/api/v1/p33u';

export interface P33UConsoleMatrixModel {
  model_id: string;
  category: 'available' | 'blocked' | 'backlog';
  run_button: 'enabled' | 'disabled' | 'disabled_blocked_dependency';
  default?: boolean;
  real_run_maturity?: string;
  license_status?: string;
  dependency_status?: string;
  runtime_status?: string;
  console_status?: string;
  smoke_status?: string;
  real_run_enabled?: boolean;
  blocked_reason?: string;
  expected_artifact?: string;
  evidence_ref?: string;
  reason?: string;
  risk_hint?: string;
}

export interface P33UConsoleMatrixScorer {
  scorer_id: string;
  category: 'available' | 'blocked';
  run_button: 'enabled' | 'disabled' | 'disabled_blocked_dependency';
  reason?: string;
  risk_hint?: string;
  // D25: input readiness + smoke status
  input_ready?: boolean;
  missing_complex?: boolean;
  blocked_dependency?: string;
  smoke_passed?: boolean;
  requires?: string;
  d19_evidence_ref?: string;
  complex_source_label?: string;
}

export interface P33UConsoleMatrix {
  models: P33UConsoleMatrixModel[];
  scorers: P33UConsoleMatrixScorer[];
  candidates: string[];
  default_model: string;
  default_scorer: string;
  default_candidate: string;
  validation_status: string;
  prediction_tag: string;
  wetlab_validation_planned: boolean;
  ppflow_status: string;
  round: string;
}

export interface P33UConfirmFlags {
  dev_only_acknowledged: boolean;
  no_experimental_validation_acknowledged: boolean;
  do_not_run_ppflow_acknowledged: boolean;
  gpu_may_be_used_acknowledged: boolean;
}

export interface P33UGate {
  gate_id: string;
  job_id: string;
  kind: string;
  model_or_scorer: string;
  safety_confirmations: P33UConfirmFlags;
  ppflow_blocked: boolean;
  prod_untouched: boolean;
  validation_status: string;
  prediction_tag: string;
  wetlab_validation_planned: boolean;
  opened_at: string;
}

export interface P33UJob {
  job_id: string;
  run_id: string;
  kind: string;
  model_or_scorer: string;
  input_target: string;
  input_candidate: string;
  start_time: string;
  end_time: string;
  command: string[];
  env: Record<string, unknown>;
  gpu_used: string | null;
  checkpoint_loaded: string;
  exit_code: number | null;
  status: string;
  failure_reason: string;
  output_path: string;
  sha256: string;
  gate: P33UGate;
  validation_status: string;
  prediction_tag: string;
  wetlab_validation_planned: boolean;
  round: string;
  result_summary?: Record<string, unknown>;
  // P33U-D23: registry submit contract provenance + dispatch metadata.
  provenance?: {
    adapter_id?: string;
    adapter_formal_path?: boolean;
    smoke_type?: string;
    script_path?: string;
    script_sha256?: string;
    config_sha256?: string;
    checkpoint_sha256?: Record<string, string>;
    env_python?: string;
    env_python_exists?: boolean;
    seed?: number | null;
    seed_note?: string;
  };
  dispatch_contract?: string;
  dispatch_module?: string;
  dispatch_entrypoint?: string;
  adapter_registry_id?: string;
}

// P33U-D23A: classified API errors so the Run Console surfaces a specific
// failure reason (auth / CSRF / 404 / validation / blocked_license /
// blocked_dependency) instead of a generic "API request failed".
export type P33UApiErrorKind =
  | 'auth_failed'
  | 'csrf_failed'
  | 'endpoint_404'
  | 'validation_error'
  | 'blocked_license'
  | 'blocked_dependency'
  | 'http_error'
  | 'network_error';

export class P33UApiError extends Error {
  kind: P33UApiErrorKind;
  status: number;
  detail: string;
  constructor(kind: P33UApiErrorKind, status: number, detail: string) {
    super(`${kind} (${status}): ${detail}`);
    this.name = 'P33UApiError';
    this.kind = kind;
    this.status = status;
    this.detail = detail;
  }
}

function extractDetail(json: unknown, status: number): string {
  if (!json || typeof json !== 'object') return `HTTP ${status}`;
  const j = json as Record<string, unknown>;
  if (typeof j.detail === 'string') return j.detail;
  const data = j.data as Record<string, unknown> | undefined;
  if (data && typeof data.reason === 'string') return data.reason;
  if (typeof j.message === 'string') return j.message;
  if (typeof j.reason === 'string') return j.reason;
  try {
    return JSON.stringify(json).slice(0, 240);
  } catch {
    return `HTTP ${status}`;
  }
}

function classifyHttpError(res: Response, json: unknown): P33UApiError {
  const status = res.status;
  const detail = extractDetail(json, status);
  // Keyword-detect across all human-readable fields: `detail` may be a short
  // reason (e.g. "dev_only_acknowledged required") while the top-level
  // `message` carries the classifying keyword ("Safety confirmations ...").
  const j = json && typeof json === 'object' ? (json as Record<string, unknown>) : {};
  const data = j.data as Record<string, unknown> | undefined;
  const combined = [detail, j.message, data?.reason, data?.status]
    .filter((x): x is string => typeof x === 'string')
    .join(' ')
    .toLowerCase();
  if (status === 401) return new P33UApiError('auth_failed', status, detail);
  if (status === 403) {
    if (combined.includes('license')) return new P33UApiError('blocked_license', status, detail);
    if (combined.includes('csrf') || combined.includes('safety') || combined.includes('confirm')) {
      return new P33UApiError('csrf_failed', status, detail);
    }
    if (combined.includes('dependency')) return new P33UApiError('blocked_dependency', status, detail);
    return new P33UApiError('http_error', status, detail);
  }
  if (status === 404) return new P33UApiError('endpoint_404', status, detail);
  if (status === 422) return new P33UApiError('validation_error', status, detail);
  if (combined.includes('license')) return new P33UApiError('blocked_license', status, detail);
  if (combined.includes('dependency')) return new P33UApiError('blocked_dependency', status, detail);
  return new P33UApiError('http_error', status, detail);
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      cache: 'no-store',
    });
  } catch (e) {
    throw new P33UApiError('network_error', 0, e instanceof Error ? e.message : 'network fetch failed');
  }
  const json = await res.json().catch(() => ({ code: res.status, data: {} }));
  if (!res.ok) throw classifyHttpError(res, json);
  return (json.data ?? json) as T;
}

async function getJson<T>(url: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(url, { cache: 'no-store' });
  } catch (e) {
    throw new P33UApiError('network_error', 0, e instanceof Error ? e.message : 'network fetch failed');
  }
  const json = await res.json().catch(() => ({ code: res.status, data: {} }));
  if (!res.ok) throw classifyHttpError(res, json);
  return (json.data ?? json) as T;
}

// ---- D26 unified scoring matrix types ----
export interface P33UD26Score {
  delta_g_kcal_mol?: number | null;
  kd_molar?: number | null;
  pose_score_kcal_mol?: number | null;
  initial_energy_kj_mol?: number | null;
  final_energy_kj_mol?: number | null;
  minimize_steps?: number | null;
  missing_atoms?: number | null;
  plddt?: number | null;
  ptm?: number | null;
  iptm?: number | null;
  max_pae?: number | null;
  msa_mode?: string | null;
  status?: string;
  job_id?: string;
  label?: string;
}

export interface P33UD26Candidate {
  candidate_id: string;
  console_key: string;
  model: string;
  sequence: string;
  length: number;
  d15_d18_top4_rank: number | null;
  d26_proposal_rank: number;
  complex_source: "PLACEMENT_ARTIFACT" | "EXISTING_AF2_COMPLEX";
  complex_source_label: string;
  complex_pdb_sha256_16: string;
  scores: {
    prodigy: P33UD26Score;
    vina: P33UD26Score;
    openmm: P33UD26Score;
    mmgbsa: P33UD26Score;
    af2_multimer: P33UD26Score;
  };
  blocked_scorers: Record<string, string>;
}

export interface P33UD26RerankEntry {
  proposal_rank: number;
  candidate_id: string;
  d15_d18_rank: number | null;
  change: string;
}

export interface P33UD26ScoringMatrix {
  round: string;
  gate: string;
  scope: string;
  ranking_rule: string;
  honesty_disclaimer: string;
  frozen_top4_disclaimer: string;
  reranking_proposal: P33UD26RerankEntry[];
  candidates: P33UD26Candidate[];
}

export interface P33UD31SynthesisSpec {
  purity_hplc_min: string;
  amount_mg: number;
  salt_form: string;
  n_terminus: string;
  c_terminus: string;
  cyclization: string;
  label: string;
  storage: string;
  delivery_docs: string;
}

export interface P33UD31OrderDecision {
  d31_round: string;
  candidate_id: string;
  order_decision:
    | 'APPROVE_FOR_QUOTE'
    | 'HOLD_AS_REVIEWED_CHALLENGER'
    | 'HOLD_NOT_FIRST_ROUND'
    | 'NOT_FOR_FIRST_ROUND';
  order_status: 'not_ordered';
  experimental_validation: false;
  pending_order: boolean;
  reason: string;
  risk_flags: string;
  synthesis_spec: P33UD31SynthesisSpec | null;
  validation_plan: string | null;
  disclosure: string;
}

export interface P33UD31OrderDecisions {
  round: string;
  d31_round: string;
  gate: string;
  top4: P33UD31OrderDecision[];
  challenger: P33UD31OrderDecision;
  hold_not_first_round: P33UD31OrderDecision[];
  synthesis_spec_top4: P33UD31SynthesisSpec;
  validation_plan_top4: string;
  order_status_all: 'not_ordered';
  experimental_validation_all: false;
  pending_order_top4: true;
  ppflow_status: string;
  decision_counts: Record<string, number>;
  disclosure: string;
  warning: string;
}

export const p33uApi = {
  getConsoleMatrix: () => getJson<P33UConsoleMatrix>(`${P33U_API_BASE}/run/console-matrix`),

  runModel: (payload: {
    model_id: string;
    target_sequence: string;
    peptide_length?: number;
    num_candidates?: number;
    device?: string;
    gpu_device?: string | null;
    seed?: number | null;
    top_k?: number;
    confirm: P33UConfirmFlags;
  }) => postJson<P33UJob>(`${P33U_API_BASE}/run/model`, payload),

  runScorer: (payload: {
    scorer_id: string;
    candidate_id?: string;
    gpu_device?: string | null;
    confirm: P33UConfirmFlags;
  }) => postJson<P33UJob>(`${P33U_API_BASE}/run/scorer`, payload),

  getJob: (jobId: string) => getJson<P33UJob>(`${P33U_API_BASE}/jobs/${jobId}`),

  getJobLogs: (jobId: string) =>
    getJson<{ job_id: string; log: string; sha256?: string }>(`${P33U_API_BASE}/jobs/${jobId}/logs`),

  getJobArtifacts: (jobId: string) =>
    getJson<{
      job_id: string;
      artifacts: Array<{ name: string; path: string; sha256: string; size: number }>;
      count: number;
      gate_json_path?: string | null;
      provenance?: Record<string, unknown>;
      dispatch?: Record<string, unknown>;
      source_round?: string | null;
    }>(`${P33U_API_BASE}/jobs/${jobId}/artifacts`),

  listJobs: (limit = 20) =>
    getJson<{ jobs: P33UJob[]; count: number }>(`${P33U_API_BASE}/jobs?limit=${limit}`),

  getD26ScoringMatrix: () =>
    getJson<P33UD26ScoringMatrix>(`${P33U_API_BASE}/d26/scoring-matrix`),

  getD31OrderDecisions: () =>
    getJson<P33UD31OrderDecisions>(`${P33U_API_BASE}/d31/order-decisions`),
};
