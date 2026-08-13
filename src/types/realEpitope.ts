/**
 * Real Epitope Scan Types — v0.7
 * TypeScript interfaces matching the POST /api/v1/epitope/scan response.
 */

export interface EpitopeScanFilters {
  min_charge?: number;
  max_charge?: number;
  min_pI?: number;
  max_pI?: number;
  max_gravy?: number;
  max_cys?: number;
}

export interface EpitopeScanRequest {
  target_name: string;
  species: string;
  sequence: string;
  window_size?: number;
  top_k?: number;
  filters?: EpitopeScanFilters;
}

export interface EpitopeCandidate {
  candidate_id: string;
  start: number;
  end: number;
  sequence: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  disulfide_risk: string;
  hydrophobicity_class: string;
  filter_status: "Pass" | "Warning" | "Fail";
  ranking_score: number;
  risk_notes: string | null;
  recommendation_reason: string | null;
  /** Source of the candidate prediction (e.g. bepipred3_sidecar). */
  source?: string;
}

export interface InputSummary {
  target_name: string;
  species: string;
  sequence_length: number;
  window_size: number;
  total_windows: number;
}

export interface FilteringSummary {
  total_windows: number;
  passed: number;
  warning: number;
  failed: number;
  returned: number;
}

export interface EpitopeScanResponse {
  code: number;
  message: string;
  mode: string;
  validation_status: string;
  input_summary: InputSummary;
  filtering_summary: FilteringSummary;
  candidates: EpitopeCandidate[];
}

/** localStorage stamp key for the real epitope scan result. */
export const EPITOPE_SCAN_LS_KEY = "stamp.realEpitopeScan.v0.7";

/** Selected epitope candidate sent from EpitopeScreeningPage to PeptideGenerationPage. */
export interface SelectedEpitope {
  candidate_id: string;
  start: number;
  end: number;
  sequence: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  disulfide_risk: string;
  hydrophobicity_class: string;
  filter_status: string;
  ranking_score: number;
  target_name: string;
  species: string;
  /** The scan parameters used when this epitope was generated. */
  scan_params?: ScanParams;
}

/** Scan parameters snapshot stored alongside the selected epitope. */
export interface ScanParams {
  window_size: number;
  top_k: number;
  min_charge: number;
  max_charge: number;
  max_gravy: number;
  max_cys: number;
  target_name: string;
  species: string;
  sequence_length: number;
  total_windows: number;
}

/** localStorage key for the selected epitope candidate. */
export const SELECTED_EPITOPE_LS_KEY = "stamp.selectedEpitope.v0.7";

/** localStorage key for scan parameters snapshot. */
export const EPITOPE_SCAN_PARAMS_LS_KEY = "stamp.scanParams.v0.7";
