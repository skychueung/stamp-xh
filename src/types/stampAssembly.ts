/**
 * STAMP Assembly Types — v0.7-P1c
 * TypeScript interfaces matching POST /api/v1/stamp/assemble-v0.7 response.
 */

export interface StampAssembleRequest {
  targeting_peptide: {
    candidate_id: string;
    sequence: string;
  };
  linker?: string;
  amp_name?: string;
  amp_sequence?: string;
  terminal_modification?: string;
}

export interface TargetingDomainComponent {
  name: string;
  sequence: string;
  length: number;
}

export interface LinkerComponent {
  sequence: string;
  length: number;
}

export interface AmpComponent {
  name: string;
  sequence: string;
  length: number;
}

export interface StampAssembleResponse {
  code: number;
  message: string;
  mode: string;
  validation_status: string;
  candidate_id: string;
  targeting_domain: TargetingDomainComponent;
  linker: LinkerComponent;
  amp: AmpComponent;
  raw_full_sequence: string;
  display_full_sequence: string;
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  cys_count: number;
  created_at: string;
}

/** localStorage stamp key for the assembled STAMP candidate. */
export const ASSEMBLED_STAMP_LS_KEY = "stamp.assembledCandidate.v0.7";
