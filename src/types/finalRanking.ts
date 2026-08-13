/**
 * Final Ranking Types — v0.7-P1e
 *
 * TypeScript interfaces for the heuristic final-ranking page.
 * Only uses sequence-derived biophysical properties.
 */

import type { StructurePredictionMetrics, InterfaceQualityMetrics, EnergyQualityMetrics } from './structureValidation';

export interface FinalRankingCandidateInput {
  candidate_id: string;
  full_sequence: string;
  targeting_peptide: string;
  linker: string;
  amp: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  mode?: string;
  created_at?: string | null;
}

export interface FinalRankingCandidateOutput {
  candidate_id: string;
  full_sequence: string;
  targeting_peptide: string;
  linker: string;
  amp: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  composite_score: number;
  mode: string;
  validation_status: string;
  created_at: string | null;
  // PepMLM-specific optional fields
  ppl?: number;
  source?: string;
  real_model_loaded?: boolean;
  generation_status?: string;
  warnings?: string;
  // Structure prediction metrics (v0.10-P6e)
  structure_prediction?: StructurePredictionMetrics;
  // Interface quality metrics (v0.10-P6k)
  interface_quality?: InterfaceQualityMetrics;
  // Energy quality metrics (v0.10-P6m)
  energy_quality?: EnergyQualityMetrics;
}

export interface FinalRankingMethodology {
  description: string;
  weights: Record<string, number>;
  ideal_values: Record<string, number>;
  scoring_method: string;
  experimental_validation: string;
  excluded_metrics: string[];
}

export interface FinalRankingComputeResponse {
  code: number;
  message: string;
  mode: string;
  validation_status: string;
  total_candidates: number;
  ranked_candidates: FinalRankingCandidateOutput[];
  ranking_methodology: FinalRankingMethodology;
}

/** localStorage key for the STAMP candidate history (array). */
export const STAMP_HISTORY_LS_KEY = "stamp.stampHistory.v0.7";

/** localStorage key for the candidate selected for structure validation. */
export const SELECTED_FOR_VALIDATION_LS_KEY = "stamp.selectedStampForValidation.v0.7";
