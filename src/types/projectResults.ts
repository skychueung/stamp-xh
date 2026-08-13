/**
 * STAMP Platform P5-lite — Project Results Types
 * Strictly aligned with backend/app/schemas/project_results.py
 * DO NOT add fields not present in the Pydantic schema.
 */

// ---------------------------------------------------------------------------
// Reusable lightweight schemas (mirroring Python *Lite classes)
// ---------------------------------------------------------------------------

export interface TargetProteinLite {
  id: string;
  name: string;
  sequence: string;
  length: number;
  organism: string | null;
  source_type: string;
  created_at: string;
}

export interface EpitopeScanLite {
  id: string;
  target_protein_id: string;
  algorithm: string;
  algorithm_version: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface EpitopeCandidateLite {
  id: string;
  scan_id: string;
  start: number;
  end: number;
  sequence: string;
  net_charge: number | null;
  hydrophobicity: number | null;
  pi: number | null;
  cys_count: number | null;
  surface_exposure_score: number | null;
  ranking_score: number | null;
  filter_status: string;
  created_at: string;
}

export interface GenerationRunLite {
  id: string;
  project_id: string;
  epitope_id: string | null;
  generator_name: string;
  generator_version: string | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
  parameters: Record<string, unknown> | null;
  created_at: string;
}

export interface ForbiddenMetrics {
  pDockQ?: null;
  delta_G?: null;
  docking_score?: null;
}

export interface StructurePredictionMetrics {
  mode?: string;
  model_source?: string;
  validation_status?: string;
  prediction_status?: string;
  metrics_are_real?: boolean;
  mean_plddt?: number | null;
  ptm?: number | null;
  iptm?: number | null;
  structure_file?: string | null;
  pae_file?: string | null;
  raw_score_json?: string | null;
  source_job_id?: string | null;
  source_result_dir?: string | null;
  forbidden_metrics?: ForbiddenMetrics;
}

// ---------------------------------------------------------------------------
// Future data contract — Interface Quality (v0.10-P6f design document)
// NOT activated. Do not write or display until real interface-quality tools
// (pDockQ, FoldX, etc.) are integrated.
// ---------------------------------------------------------------------------

export interface InterfaceQualityProvenance {
  input_complex_structure_file?: string | null;
  interface_parser_commit?: string | null;
  calculator_formula?: string | null;
  parameters?: Record<string, number> | null;
}

export interface InterfaceQualityInputFeatures {
  interface_contact_count?: number | null;
  interface_residue_plddt_mean?: number | null;
  x_value?: number | null;
  distance_cutoff_angstrom?: number | null;
}

export interface InterfaceQualityForbiddenMetrics {
  delta_G?: null;
  docking_score?: null;
}

export interface InterfaceQualityMetrics {
  /** pDockQ score from Bryant et al. 2022 sigmoid formula. */
  pdockq?: number | null;
  interface_contact_count?: number | null;
  interface_residue_count_A?: number | null;
  interface_residue_count_B?: number | null;
  pae_interface_mean?: number | null;
  validation_status?: string;
  prediction_status?: string;
  metrics_are_real?: boolean;
  algorithm?: string;
  algorithm_version?: string;
  source?: string;
  chain_mapping?: Record<string, string>;
  input_features?: InterfaceQualityInputFeatures;
  provenance?: InterfaceQualityProvenance;
  forbidden_metrics?: InterfaceQualityForbiddenMetrics;
}

// ---------------------------------------------------------------------------
// Energy Quality (v0.10-P6m) — FoldX AnalyseComplex interaction energy
// ---------------------------------------------------------------------------

export interface EnergyQualityForbiddenMetrics {
  docking_score?: null;
  mmgbsa_delta_G?: null;
  experimental_delta_G?: null;
}

export interface EnergyQualityTerms {
  backbone_hbond?: number | null;
  sidechain_hbond?: number | null;
  van_der_waals?: number | null;
  electrostatics?: number | null;
  solvation_polar?: number | null;
  solvation_hydrophobic?: number | null;
  vdw_clashes?: number | null;
  entropy_sidechain?: number | null;
  entropy_mainchain?: number | null;
  entropy_complex?: number | null;
}

export interface EnergyQualityFlags {
  unfavorable_interaction_energy?: boolean;
  favorable_interaction_energy?: boolean;
  high_vdw_clashes?: boolean;
  interpretation?: string;
}

export interface EnergyQualityMetrics {
  source?: string;
  algorithm?: string;
  algorithm_version?: string;
  validation_status?: string;
  prediction_status?: string;
  metrics_are_real?: boolean;
  chain_mapping?: Record<string, string>;
  interaction_energy_kcal_mol?: number | null;
  energy_terms?: EnergyQualityTerms;
  quality_flags?: EnergyQualityFlags;
  forbidden_metrics?: EnergyQualityForbiddenMetrics;
}

export interface StampCandidateDetail {
  id: string;
  project_id: string;
  epitope_id: string | null;
  generation_run_id: string | null;
  targeting_peptide_seq: string;
  linker_seq: string;
  full_sequence: string;
  composite_score: number | null;
  validation_status: string;
  metrics: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Project summary
// ---------------------------------------------------------------------------

export interface ProjectSummaryResponse {
  project_id: string;
  project_name: string;
  target_protein_count: number;
  epitope_scan_count: number;
  epitope_candidate_count: number;
  generation_run_count: number;
  stamp_candidate_count: number;
  assembled_candidate_count: number;
  ranked_candidate_count: number;
  latest_updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Pipeline results
// ---------------------------------------------------------------------------

export interface ProjectPipelineResultsResponse {
  project_id: string;
  project_name: string;
  target_proteins: TargetProteinLite[];
  epitope_scans: EpitopeScanLite[];
  epitope_candidates: EpitopeCandidateLite[];
  generation_runs: GenerationRunLite[];
  stamp_candidates: StampCandidateDetail[];
}

// ---------------------------------------------------------------------------
// STAMP results
// ---------------------------------------------------------------------------

export interface ProjectStampResultsResponse {
  project_id: string;
  project_name: string;
  total_count: number;
  returned_count: number;
  candidates: StampCandidateDetail[];
}

// ---------------------------------------------------------------------------
// Generation runs list
// ---------------------------------------------------------------------------

export interface GenerationRunListResponse {
  project_id: string;
  project_name: string;
  total_count: number;
  generation_runs: GenerationRunLite[];
}

// ---------------------------------------------------------------------------
// Single stamp candidate detail (via /stamp-candidates/{id})
// Backend returns ApiResponse[StampCandidateDetail]; fetchClient unwraps .data
// ---------------------------------------------------------------------------

export type StampCandidateDetailResponse = StampCandidateDetail;
