/**
 * PepMLM data source types — strict, zero any
 */

export type PepmlmDataSourceLevel =
  | 'OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING'
  | 'EXPERIMENTAL_SIMPLIFIED_PARTIAL_MASK'
  | 'UNKNOWN';

export type PepmlmFilterStatus = 'Pass' | 'Warning' | 'Fail';

export interface PepmlmCandidate {
  candidate_id: string;
  target_name: string;
  target_sequence_length: number;
  peptide_length: number;
  generated_peptide: string;
  decoding_strategy: string;
  top_k: number;
  seed: number;
  iterations: number;
  ppl_score: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  hydrophobicity?: number;
  aromatic_ratio?: number;
  cysteine_count: number;
  max_repeat: number;
  repeat_details?: string;
  sequence_warning?: string;
  filter_status: PepmlmFilterStatus;
  recommendation_reason?: string;
  validation_warning?: string;
  rank?: number;
  ppl_rank_percentile?: number;
  physicochemical_score?: number;
  developability_score?: number;
  diversity_score?: number | null;
  ranking_score?: number;
}

export interface PepmlmFilteringSummary {
  total: number;
  passed: number;
  warning: number;
  failed: number;
  pass_rate: number;
  failure_reasons: Record<string, number>;
}

export interface PepmlmMetadata {
  model_name: string;
  model_version: string;
  model_architecture: string;
  generator_script: string;
  target_name: string;
  target_species: string;
  target_sequence_length: number;
  target_type: string;
  generation_date: string;
  peptide_lengths: number[];
  num_candidates_requested: number;
  num_candidates_generated: number;
  top_k: number;
  generation_mode: string;
  validation_status: string;
  validation_warning: string;
}

export interface PepmlmJsonStructure {
  $schema?: string;
  metadata: PepmlmMetadata;
  candidates: PepmlmCandidate[];
  top10?: PepmlmCandidate[];
  filtering_summary: PepmlmFilteringSummary;
}

export function isOfficialStyle(level: string): boolean {
  return level === 'OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING';
}

export function isExperimental(level: string): boolean {
  return level === 'EXPERIMENTAL_SIMPLIFIED_PARTIAL_MASK';
}
