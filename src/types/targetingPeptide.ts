/**
 * Targeting Peptide Generation Types — v0.7-P1b
 * TypeScript interfaces matching POST /api/v1/targeting-peptide/generate response.
 */

export interface TargetingPeptideGenerateRequest {
  source_epitope: {
    candidate_id: string;
    sequence: string;
    start: number;
    end: number;
    target_name: string;
    species: string;
  };
}

export interface TargetingPeptideCandidate {
  candidate_id: string;
  source_epitope_id: string;
  sequence: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  complementarity_note: string;
  filter_status: "Pass" | "Warning" | "Fail";
  ranking_score: number;
  validation_status: string;
  mode: string;
}

export interface TargetingPeptideInputSummary {
  source_epitope_id: string;
  source_sequence: string;
  source_length: number;
  source_net_charge: number;
  source_target_name: string;
  source_species: string;
  requested_count: number;
}

export interface TargetingPeptideGenerateResponse {
  code: number;
  message: string;
  mode: string;
  validation_status: string;
  input_summary: TargetingPeptideInputSummary;
  candidates: TargetingPeptideCandidate[];
}

/** localStorage stamp key for the selected targeting peptide candidate. */
export const SELECTED_TARGETING_PEPTIDE_LS_KEY = "stamp.selectedTargetingPeptide.v0.7";
