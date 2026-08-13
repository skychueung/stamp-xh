export type ModelProductGroup =
  | 'available_five'
  | 'blocked'
  | 'backlog'
  | 'unknown';

export type ModelUiExecutionState =
  | 'closed_available'
  | 'license_blocked'
  | 'backlog'
  | 'unknown';

export interface ModelRegistryEntry {
  model_id: string;
  display_name: string;
  category: string;
  status:
    | 'available'
    | 'installed'
    | 'not_connected'
    | 'planned'
    | 'disabled'
    | 'probed'
    | 'parked'
    | 'pending_probe'
    | 'pending_registry'
    | 'controlled_smoke_verified'
    | 'smoke_rerun_verified'
    | 'closed'
    | 'blocked_license'
    | 'backlog';
  status_reason?: string | null;
  description: string;
  supports_probe: boolean;
  supports_dry_run: boolean;
  supports_real_run: boolean;
  supports_structure_output: boolean;
  supports_sequence_output: boolean;
  supports_ranking: boolean;
  output_artifact_types: string[];
  adapter_id: string;
  safety_note: string;
  validation_policy: string;
  real_run_enabled: boolean;
  stage: string;
  notes?: string | null;
  // P32A display-only readiness fields (do not overwrite canonical stage)
  readiness_gate?: string | null;
  readiness_level?: string | null;
  execution_locked: boolean;
  blocker_code?: string | null;
  next_authorization?: string | null;
  last_verified_at?: string | null;
  evidence_ref?: string | null;
  // P33K product-group UI governance fields
  product_group: ModelProductGroup;
  ui_selectable: boolean;
  ui_execution_state: ModelUiExecutionState;
  activation_requirements: string;
  delivery_status: string;
  /** P33P: structured PPFlow evidence metadata (ppflow only). */
  evidence?: P33PFlowEvidence | null;
}

export interface P33PFlowEvidenceSha256 {
  success_report: string;
  execution_manifest: string;
  result_manifest: string;
  status: string;
}

/**
 * P33P: the only evidence identifiers the UI is allowed to render or download.
 * Unknown ids returned by the API MUST be filtered out before rendering.
 */
export type P33PFlowEvidenceId = 'success_report' | 'execution_manifest' | 'result_manifest' | 'status';

export interface P33PFlowEvidence {
  success_report: string;
  execution_manifest: string;
  result_manifest: string;
  status: string;
  artifact_dir: string;
  sha256: P33PFlowEvidenceSha256;
  exit_code: number;
  elapsed_seconds: number;
  sample_dirs: number;
  file_count: number;
  artifact_bytes: number;
  validation_status: string;
}

export interface P33PFlowEvidenceResponse {
  model_id: string;
  stage: string;
  execution_locked: boolean;
  real_run_enabled: boolean;
  validation_status: string;
  evidence: P33PFlowEvidence;
  downloadable_ids: P33PFlowEvidenceId[];
}

/**
 * P33Q: unified six-model evidence contract. Every registered model returns
 * this shape from GET /models/{id}/evidence. Unknown evidence ids MUST be
 * filtered against KnownEvidenceId before rendering or downloading.
 */
export type KnownEvidenceId =
  | 'success_report'
  | 'execution_manifest'
  | 'result_manifest'
  | 'status'
  | 'reasonix_review'
  | 'artifacts_index'
  | 'delivery_manifest'
  | 'p3b_report'
  | 'p3c_report';

export type ModelEvidenceAvailability = 'available' | 'partial' | 'unavailable' | 'pending';

export interface ModelEvidenceArtifact {
  id: string;
  filename: string;
  media_type: string;
  sha256: string;
  bytes: number | null;
}

/** Flexible numeric stats; keys vary per model (only truthfully-known fields). */
export type ModelEvidenceStats = Record<string, number>;

export interface ModelEvidenceResponse {
  model_id: string;
  stage: string;
  validation_status: string;
  execution_locked: boolean;
  real_run_enabled: boolean;
  supports_real_run: boolean;
  evidence_ref: string;
  availability: ModelEvidenceAvailability;
  stats: ModelEvidenceStats | null;
  downloadable_ids: string[];
  artifacts: ModelEvidenceArtifact[];
}

export interface ModelSafetyFlags {
  executed_model: boolean;
  generated_candidates: boolean;
  generated_structure: boolean;
  generated_msa: boolean;
  is_scientific_result: boolean;
  computational_prediction_only: boolean;
  validation_status: string;
}

export interface ModelsListResponse {
  models: ModelRegistryEntry[];
  scientific_boundary: string;
  available_models: number;
  blocked_models: number;
  backlog_models: number;
  available_model_ids: string[];
  blocked_model_ids: string[];
  backlog_model_ids: string[];
}

export interface ModelRegistryStatusEntry {
  model_id: string;
  display_name: string;
  status: string;
  status_reason?: string | null;
  stage: string;
  supports_probe: boolean;
  supports_dry_run: boolean;
  supports_real_run: boolean;
  notes?: string | null;
  // P33K product-group UI governance fields
  product_group: ModelProductGroup;
  ui_selectable: boolean;
  ui_execution_state: ModelUiExecutionState;
  activation_requirements: string;
  delivery_status: string;
}

export interface ModelRegistryStatusResponse {
  models: ModelRegistryStatusEntry[];
  parked_models: string[];
  pending_probe_models: string[];
  pending_registry_models: string[];
  scientific_boundary: string;
  count_total: number;
  count_parked: number;
  count_pending_probe: number;
  count_pending_registry: number;
}

export interface ModelDetailResponse {
  model: ModelRegistryEntry;
  safety_flags: ModelSafetyFlags;
  scientific_boundary: string;
}

export interface ModelProbeResult {
  model_id: string;
  display_name: string;
  status: string;
  message: string;
  probe_time: string;
  adapter_id: string;
  safety_flags: ModelSafetyFlags;
  detail: Record<string, unknown>;
  scientific_boundary: string;
}

export interface ModelDryRunPayload {
  target_sequence: string;
  peptide_length: number;
  model_name: string;
  max_recycles: number;
  num_iterations: number;
  dry_run: boolean;
  // PepMLM / PepPrCLIP / PepGLAD specific optional fields
  num_candidates?: number;
  max_length?: number;
  top_k?: number;
  device?: 'auto' | 'cpu' | 'cuda';
  seed?: number | null;
  candidate_peptides?: string | string[] | null;
  // PepGLAD structure-conditioned inputs
  target_pdb_path?: string | null;
  pocket_residues?: string[] | null;
}

export interface ModelDryRunResult {
  model_id: string;
  display_name: string;
  status: string;
  message: string;
  run_id?: string | null;
  artifacts: Record<string, string | null>;
  expected_artifacts?: Record<string, string | null>;
  command_preview?: string[] | null;
  env_preview: Record<string, string>;
  environment_summary?: Record<string, unknown>;
  blocked_reasons?: string[];
  safety_flags: ModelSafetyFlags;
  validation_status: string;
  scientific_boundary: string;
}

export interface ModelArtifactItem {
  name: string;
  path: string;
  artifact_type: string;
  exists: boolean;
  size_bytes: number;
  download_url?: string | null;
}

export interface ModelArtifactsResponse {
  model_id: string;
  job_id: string;
  status: string;
  validation_status: string;
  safety_note: string;
  artifacts: ModelArtifactItem[];
}

export interface ModelJobStatus {
  job_id: string;
  model_id: string;
  status: string;
  progress?: number | null;
  message?: string | null;
  error_message?: string | null;
  error_json?: Record<string, unknown> | null;
  output_json?: Record<string, unknown> | null;
  started_at?: string | null;
  finished_at?: string | null;
  validation_status: string;
}

export interface PepmlmCandidate {
  candidate_id: string;
  sequence: string;
  length?: number | string | null;
  peptide_length?: number | string | null;
  source_model?: string | null;
  job_id?: string | null;
  validation_status?: string | null;
  safety_note?: string | null;
  pseudo_perplexity?: number | null;
  [key: string]: unknown;
}

export interface ModelSubmitResponse {
  job_id: string;
  status: string;
  message?: string | null;
  run_id?: string | null;
  artifacts?: ModelArtifactItem[];
  validation_status?: string;
  safety_flags?: ModelSafetyFlags;
}


export interface TargetDesignWorkflowPayload {
  target_sequence: string;
  generator_model: string;
  ranker_model: string;
  structure_model: string;
  num_candidates: number;
  peptide_length: number;
  top_k: number;
  dry_run: boolean;
}

export interface WorkflowStep {
  step_id: string;
  name: string;
  model_id: string;
  status: string;
  message: string;
  blocked_reason?: string | null;
  command_preview?: string[] | null;
  env_preview: Record<string, string>;
  artifacts: Record<string, string | null>;
  expected_artifacts: Record<string, string | null>;
}

export interface WorkflowArtifactReference {
  label: string;
  model_id: string;
  job_id?: string | null;
  artifact_name: string;
  artifact_path?: string | null;
  status: 'Exists' | 'Expected' | 'Blocked' | string;
  reason?: string | null;
  validation_status: string;
  download_url?: string | null;
}

export interface TargetDesignWorkflowResult {
  workflow_id: string;
  workflow_type: string;
  status: string;
  message: string;
  steps: WorkflowStep[];
  expected_artifacts: Record<string, string | null>;
  safety_flags: ModelSafetyFlags;
  validation_status: string;
  scientific_boundary: string;
  blocked_reasons: string[];
  prior_artifacts_referenced: Record<string, string | null>;
  artifact_references: WorkflowArtifactReference[];
}
