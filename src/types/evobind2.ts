/**
 * STAMP v1.2 — EvoBind2 Types (P3C artifact hardening)
 * Mirrors backend/app/schemas/evobind2.py
 *
 * NOTE: This is a dry-run / job-queue skeleton. No real model execution,
 * no candidate peptide generation, and no experimental validation results.
 */

export type EvoBind2ValidationStatus = "NOT_EXPERIMENTALLY_VALIDATED";

export type EvoBind2JobState =
  | "pending"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "blocked"
  | "ready_for_dry_run";

export interface EvoBind2SafetyFlags {
  is_candidate_generation: boolean;
  is_scientific_result: boolean;
  uses_uniref30: boolean;
  requires_manual_review?: boolean;
  requires_real_validation?: boolean;
}

export interface EvoBind2DryRunRequest {
  run_id: string;
  receptor_fasta: string;
  peptide_length: number;
  mode?: string;
  peptide_sequence?: string | null;
  model_name?: string;
  max_recycles?: number;
  num_iterations?: number;
  use_gpu?: boolean;
  selected_gpu?: string | number;
  msa_mode?: string;
  receptor_msa_a3m?: string | null;
}

export interface EvoBind2DryRunResponse {
  run_id: string;
  status: "READY" | "BLOCKED";
  mode: string;
  model_name: string;
  used_gpu: boolean;
  selected_gpu: number | null;
  runtime_seconds: number | null;
  artifacts: Record<string, string | null>;
  safety_flags: EvoBind2SafetyFlags;
  command_preview: string[] | null;
  env_preview: Record<string, string>;
  error_message: string | null;
}

export interface EvoBind2JobSubmitRequest {
  project_id: string;
  target_sequence: string;
  peptide_sequence?: string | null;
  mode?: string;
  model_name?: string;
  msa_mode?: string;
  dry_run?: boolean;
  max_recycles?: number;
  num_iterations?: number;
  use_gpu?: boolean;
  selected_gpu?: string | number;
  receptor_msa_a3m?: string | null;
}

export interface EvoBind2JobResponse {
  job_id: string;
  project_id: string;
  status: EvoBind2JobState;
  job_type: string;
  model_name: string;
  mode: string;
  safety_flags: EvoBind2SafetyFlags;
  message: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface EvoBind2ArtifactItem {
  name: string;
  /** Internal relative path under the EvoBind2 artifact root; never an absolute server path. */
  path: string;
  artifact_type: "metrics" | "pdb" | "log" | "manifest" | "input" | "other";
  exists: boolean;
  size_bytes: number;
  download_url?: string | null;
}

export interface EvoBind2ArtifactResponse {
  job_id: string;
  status: EvoBind2JobState;
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED';
  safety_note: string;
  artifacts: EvoBind2ArtifactItem[];
}

export interface EvoBind2JobCancelResponse {
  job_id: string;
  previous_status: string;
  status: string;
  message: string;
}

export interface EvoBind2ProbeCheck {
  name: string;
  status: 'PASS' | 'FAIL' | 'DEGRADED';
  message: string;
  detail?: string | null;
  severity: 'INFO' | 'WARNING' | 'ERROR';
}

export interface EvoBind2ProbeResponse {
  status: 'AVAILABLE' | 'DEGRADED' | 'UNAVAILABLE';
  dry_run_status: 'READY_FOR_DRY_RUN' | 'BLOCKED';
  real_run_status: 'BLOCKED';
  install_status: 'INSTALL_COMPLETE' | 'INSTALL_INCOMPLETE';
  checks: EvoBind2ProbeCheck[];
  warnings: string[];
  errors: string[];
  resolved_paths: Record<string, string | null>;
  gpu_devices: Array<{ id: number; name: string }>;
  safety_flags: Record<string, boolean>;
  real_run_enabled: boolean;
  executed_model: boolean;
  executed_hhblits_search: boolean;
  generated_msa: boolean;
  generated_candidates: boolean;
  generated_pdb: boolean;
  is_candidate_generation: boolean;
  is_scientific_result: boolean;
  validation_status: 'NOT_EXPERIMENTALLY_VALIDATED';
}
