/**
 * STAMP Backend API Response Types — v0.6d
 *
 * NOTE: This file contains historical mock/placeholder fields that are
 * NOT returned by the P5-lite backend. Fields marked
 * MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND are kept for backward
 * compatibility with legacy UI demos but must NOT be treated as real
 * backend schema fields.
 */

export interface StampBackendDomain {
  name: string;
  sequence: string;
  length: number;
  net_charge: number | null;
  gravy: number | null;
}

export interface StampBackendLinker {
  name: string;
  sequence: string;
  length: number;
  type: string;
}

export interface StampBackendBiophysical {
  length: number;
  net_charge: number | null;
  pI: number | null;
  GRAVY: number | null;
  hydrophobicity_fraction: number | null;
}

/** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND — experimental assay placeholders. */
export interface StampBackendExperimental {
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  MIC_ug_ml: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  MBC_ug_ml: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  hemolysis_percent: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  LPS_binding_Kd_nM: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  pLDDT: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  ipTM: number | null;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  pDockQ: number | null;
  note: string | null;
}

export interface StampBackendStructureStatus {
  monomer_predicted: boolean;
  complex_predicted: boolean;
  experimental_structure: boolean;
}

export interface StampBackendCandidate {
  candidate_id: string;
  target_molecule: string;
  targeting_domain: StampBackendDomain;
  linker: StampBackendLinker;
  killing_domain: StampBackendDomain;
  orientation: string;
  terminal_modification: string;
  raw_full_sequence: string;
  display_full_sequence: string;
  is_complete: boolean;
  biophysical: StampBackendBiophysical;
  cys_count?: number;
  mock_scores: null;
  experimental: StampBackendExperimental;
  structure_status: StampBackendStructureStatus;
  validation_status: string;
}

export interface StampBackendResponse<T> {
  code: number;
  message: string;
  data: T;
}
