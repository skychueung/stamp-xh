// P33T result delivery center types.
// All data originates from P33S-C real model runs and is tagged
// NOT_EXPERIMENTALLY_VALIDATED / computational_prediction_only.

export interface P33TBaseResponse<T> {
  code: number;
  data: T;
  validation_status: string;
  computational_prediction_only: boolean;
  experimental_validation: boolean;
}

export interface D16WetlabPlan {
  wetlab_planned_status: string;
  top4_wetlab_shortlist: boolean;
  tracking_status: string;
  order_status: string;
  sample_status: string;
  assay_status: {
    binding_assay_status: string;
    activity_assay_status: string;
    safety_assay_status: string;
    mechanism_assay_status: string;
  };
  experimental_validation: boolean;
  pending_experiment: boolean;
  planned_assays: string[];
}

export interface D19Scoring {
  round: string;
  scores: {
    prodigy_deltaG_kcal_mol?: number | null;
    vina_pose_score_kcal_mol?: number | null;
    openmm_final_energy_kj_mol?: number | null;
    mmgbsa_deltaG_kcal_mol?: number | null;
    af2_plddt?: number | null;
    af2_ptm?: number | null;
    af2_iptm?: number | null;
  };
  unavailable: {
    gnina?: string;
    pyrosetta?: string;
    haddock?: string;
    mic?: string;
  };
  provenance?: string;
  validation_status: string;
  prediction_tag: string;
}

export interface P33TCandidate {
  candidate_id: string;
  sequence: string;
  length: number;
  source_model_id: string;
  source_run_id: string;
  generation_rank: number | null;
  generation_score: number | null;
  input_target: string | null;
  created_at: string;
  validation_status: string;
  computational_prediction_only: boolean;
  experimental_validation: boolean;
  // P33U-D16: wet-lab plan display (optional; present for Top4).
  top4_wetlab_shortlist?: boolean;
  wetlab_planned_status?: string;
  order_status?: string;
  pending_experiment?: boolean;
  d16_wetlab_plan?: D16WetlabPlan;
  // P33U-D19: computational scoring (optional; present when D19 matrix loaded).
  d19_scoring?: D19Scoring;
}

export interface P33TCandidateMetric {
  metric_id: string;
  metric_name: string;
  metric_value: number | string | null;
  unit: string | null;
  scorer_name: string | null;
  scorer_version: string | null;
  scorer_license: string | null;
  metric_provenance: Record<string, unknown>;
  unavailable_with_reason: string | null;
  artifact_sha256: string | null;
}

export interface P33TCandidateMetricsResponse {
  candidate_id: string;
  metrics: P33TCandidateMetric[];
}

export interface P33TCandidateListResponse {
  items: P33TCandidate[];
  page: number;
  page_size: number;
  total: number;
}

export interface P33TFilterRequest {
  sequence_contains?: string;
  source_model_id?: string;
  min_length?: number;
  max_length?: number;
  // P33U-D12: scope disambiguates P33U vs legacy p33t_ P33S-C demo candidates.
  scope?: "all" | "P33U" | "legacy";
  length?: number;
  deviation?: boolean;
  top4?: boolean;
}

export interface P33TFilterResponse {
  items: P33TCandidate[];
  total: number;
}

export interface P33TDeliveryBundle {
  bundle_id: string;
  selected_candidate_ids: string[];
  ranking_policy: string;
  export_files: string[];
  sha256_manifest: string;
  created_at: string;
}

export type P33TMetricStatus =
  | { kind: 'available'; value: number | string; unit: string | null }
  | { kind: 'unavailable'; reason: string };
