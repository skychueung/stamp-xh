/**
 * STAMP v0.6b — Strict TypeScript interfaces for AMP / STAMP hybrid data
 * Zero `any` usage. All fields explicitly typed.
 */

// ───────────────────────────────────────────────
// Domain-level types
// ───────────────────────────────────────────────

export interface DomainValidation {
  isValid: boolean;
  illegalChar: string | null;
  illegalPosition: number | null;
  length: number;
  warning: string | null;
}

export interface TargetingDomain {
  name: string;
  sequence: string;
  length: number;
  net_charge: number;
  gravy: number;
  validation: DomainValidation;
}

export interface Linker {
  name: string;
  sequence: string;
  length: number;
  type: 'cleavable' | 'rigid' | 'flexible' | string;
}

export interface KillingDomain {
  name: string;
  sequence: string;
  length: number;
  net_charge: number;
  gravy: number;
  validation: DomainValidation;
}

// ───────────────────────────────────────────────
// Biophysical & scores
// ───────────────────────────────────────────────

export interface BiophysicalParams {
  length: number;
  net_charge: number;
  pI: number;
  GRAVY: number;
  hydrophobicity_fraction: number;
}

/** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND — placeholder scores for UI demo. */
export interface MockScores {
  AMP_score: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  toxicity_score: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  hemolysis_score: number;
  LPS_binding_score: number;
  final_score: number;
  note: string;
}

/** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND — experimental assay placeholders. */
export interface ExperimentalData {
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
  note: string;
}

export interface StructureStatus {
  monomer_predicted: boolean;
  complex_predicted: boolean;
  experimental_structure: boolean;
  note: string;
}

// ───────────────────────────────────────────────
// STAMP Hybrid Candidate
// ───────────────────────────────────────────────

export interface StampHybridCandidate {
  candidate_id: string;
  target_molecule: string;
  targeting_domain: TargetingDomain;
  linker: Linker;
  killing_domain: KillingDomain;
  orientation: string;
  terminal_modification: string;
  reference: string;
  raw_full_sequence: string;
  display_full_sequence: string;
  is_complete: boolean;
  biophysical: BiophysicalParams;
  mock_scores: MockScores;
  experimental: ExperimentalData;
  structure_status: StructureStatus;
}

// ───────────────────────────────────────────────
// AMP Structure Record (from manifest)
// ───────────────────────────────────────────────

export interface AmpConfidence {
  meanPlddt: number;
  ptm: number;
  iptm: number | null;
  fractionDisordered: number;
  hasClash: number;
  numRecycles: number;
  rankingScore: number;
  sourceFile: string;
  note: string;
}

export interface AmpStructureRecord {
  id: string;
  originalDir: string;
  originalFullPath: string;
  publicPath: string;
  format: string;
  modelsAvailable: number;
  isPriorityCandidate: boolean;
  priorityName: string | null;
  confidence: AmpConfidence;
  quality: 'very_high' | 'high' | 'low' | 'very_low' | 'unknown';
}

// ───────────────────────────────────────────────
// API Response wrappers
// ───────────────────────────────────────────────

export interface StampCandidatesResponse {
  generatedAt: string;
  version: string;
  note: string;
  total_candidates: number;
  candidates: StampHybridCandidate[];
}

export interface AmpStructureManifest {
  generatedAt: string;
  version: string;
  note: string;
  source: {
    zipFile: string;
    unzippedDir: string;
  };
  counts: {
    expected: number;
    observed: number;
    status: string;
    cifTotal: number;
    bestModelsCopied: number;
    plddtExtracted: number;
  };
  qualityDistribution: Record<string, number>;
  plddtRange: {
    min: number;
    max: number;
    mean: number;
  };
  structures: AmpStructureRecord[];
}

// ───────────────────────────────────────────────
// UI-specific derived types
// ───────────────────────────────────────────────

export interface CandidateBadgeInfo {
  text: string;
  variant: 'default' | 'secondary' | 'destructive' | 'warning' | 'outline';
}

export interface StatCardData {
  labelKey: string;
  value: string | number;
  source: string;
}
