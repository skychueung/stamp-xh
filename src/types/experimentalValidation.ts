/**
 * STAMP Platform v0.11-P2 — Experimental Validation Types
 * Mirrors backend/app/schemas/experimental_validation.py
 */

export type ExperimentType =
  | "MIC"
  | "MBC"
  | "HEMOLYSIS"
  | "CYTOTOXICITY"
  | "SERUM_STABILITY"
  | "PROTEASE_STABILITY"
  | "SALT_STABILITY"
  | "BIOFILM"
  | "RESISTANCE_INDUCTION"
  | "OTHER";

export type RunStatus = "PLANNED" | "RUNNING" | "COMPLETED" | "FAILED" | "INVALIDATED";

export type ValidationStatus =
  | "NOT_EXPERIMENTALLY_VALIDATED"
  | "EXPERIMENT_PLANNED"
  | "PARTIALLY_VALIDATED"
  | "EXPERIMENTALLY_VALIDATED"
  | "VALIDATION_FAILED";

export type MetricName =
  | "MIC_ug_ml"
  | "MBC_ug_ml"
  | "hemolysis_percent"
  | "HC50_ug_ml"
  | "IC50_ug_ml"
  | "cell_viability_percent"
  | "serum_half_life_min"
  | "protease_remaining_percent"
  | "biofilm_inhibition_percent";

export type QualityFlag = "PASS" | "WARNING" | "FAILED" | "NEEDS_REVIEW";

export interface ExperimentalValidationRun {
  id: string;
  project_id: string;
  candidate_id: string;
  experiment_type: ExperimentType;
  organism: string | null;
  strain: string | null;
  protocol_name: string | null;
  protocol_version: string | null;
  operator: string | null;
  experiment_date: string | null;
  status: RunStatus;
  validation_status: ValidationStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ExperimentalMeasurement {
  id: string;
  validation_run_id: string;
  candidate_id: string;
  metric_name: MetricName;
  value: number | null;
  unit: string | null;
  condition_json: Record<string, unknown>;
  replicate_id: string | null;
  raw_data_path: string | null;
  quality_flag: QualityFlag;
  created_at: string;
  updated_at: string;
}

export interface ExperimentalValidationSummary {
  candidate_id: string;
  overall_validation_status: ValidationStatus;
  run_count: number;
  completed_run_count: number;
  measurements: ExperimentalMeasurement[];
}

export interface CandidateExperimentalPriority {
  candidate_id: string;
  composite_score: number | null;
  experimental_priority_score: number | null;
  priority_status: string;
  computational_score_contribution: number | null;
  structure_support_contribution: number | null;
  experimental_activity_contribution: number | null;
  safety_contribution: number | null;
  validation_status: ValidationStatus;
  has_experimental_data: boolean;
}

export interface ValidationRunCreatePayload {
  project_id: string;
  candidate_id: string;
  experiment_type: ExperimentType;
  organism?: string;
  strain?: string;
  protocol_name?: string;
  protocol_version?: string;
  operator?: string;
  experiment_date?: string;
  notes?: string;
}

export interface MeasurementCreatePayload {
  validation_run_id: string;
  candidate_id: string;
  metric_name: MetricName;
  value?: number;
  unit?: string;
  condition_json?: Record<string, unknown>;
  replicate_id?: string;
  quality_flag?: QualityFlag;
}

export interface ProjectExperimentalValidationSummary {
  project_id: string;
  total_candidates: number;
  candidates_with_experimental_data: number;
  candidates_fully_validated: number;
  candidates_failed_validation: number;
  candidates_pending: number;
  experiment_type_counts: Record<string, number>;
  validation_status_counts: Record<string, number>;
  measurement_counts: Record<string, number>;
  coverage: {
    candidates_with_any_measurement: number;
    candidates_with_mic: number;
    candidates_with_safety: number;
    experimental_coverage_percent: number;
  };
  top_priority_candidates: Array<{
    candidate_id: string;
    sequence: string;
    experimental_priority_score: number | null;
    priority_status: string;
    validation_status: ValidationStatus;
  }>;
}

export interface CsvImportError {
  row: number;
  candidate_id: string;
  reason: string;
}

export interface CsvImportResult {
  project_id: string;
  total_rows: number;
  success_count: number;
  failed_count: number;
  created_run_count: number;
  created_measurement_count: number;
  errors: CsvImportError[];
}

export interface PriorityDecision {
  decision: 'SHORTLIST' | 'HOLD' | 'REJECT' | 'NEEDS_REPEAT_EXPERIMENT';
  decision_reason: string;
  reviewer: string;
  reviewed_at: string;
  manual_override: boolean;
  notes: string | null;
}

export interface CandidatePrioritizationItem {
  candidate_id: string;
  sequence: string;
  composite_score: number | null;
  experimental_priority_score: number | null;
  priority_status: string;
  validation_status: ValidationStatus;
  computational_summary: {
    pepmlm_source: string | null;
    mean_plddt: number | null;
    pdockq: number | null;
    interaction_energy_kcal_mol: number | null;
  };
  experimental_summary: Record<string, unknown>;
  run_count: number;
  measurement_count: number;
  decision: PriorityDecision | null;
}

export interface ProjectCandidatePrioritization {
  project_id: string;
  summary: {
    candidate_count: number;
    ready_for_review: number;
    needs_more_data: number;
    safety_concern: number;
    validation_failed: number;
    shortlisted: number;
    rejected: number;
  };
  candidates: CandidatePrioritizationItem[];
}

export interface PriorityDecisionPayload {
  decision: 'SHORTLIST' | 'HOLD' | 'REJECT' | 'NEEDS_REPEAT_EXPERIMENT';
  decision_reason: string;
  reviewer?: string;
  notes?: string;
}

// v0.11-P5: Wet-lab validation report export
export interface WetlabValidationReport {
  project_id: string;
  report_type: string;
  generated_at: string;
  scientific_boundary: Record<string, boolean>;
  summary: {
    candidate_count: number;
    candidates_with_measurements: number;
    experimental_coverage_percent: number;
    shortlisted: number;
    rejected: number;
    needs_more_data: number;
    safety_concern: number;
    ready_for_review: number;
    validation_failed: number;
  };
  candidates: Array<{
    candidate_id: string;
    sequence: string;
    validation_status: ValidationStatus;
    experimental_priority_score: number | null;
    priority_status: string;
    manual_decision: {
      decision: string;
      decision_reason: string;
      reviewer: string;
      reviewed_at: string;
    } | null;
    experimental_measurements: Array<{
      experiment_type: string;
      metric_name: string;
      value: number;
      unit: string;
      quality_flag: string;
      replicate_id: string | null;
    }>;
    computational_reference: {
      composite_score: number | null;
      mean_plddt: number | null;
      pdockq: number | null;
      interaction_energy_kcal_mol: number | null;
    };
    run_count: number;
    measurement_count: number;
  }>;
}
