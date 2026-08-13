/**
 * STAMP v1.5 — Batch Computation Types
 * Mirrors backend/app/routers/batch_computations.py schemas
 */

export type BatchJobType = "COLABFOLD" | "FOLDX" | "MMGBSA" | "MIXED" | "FLEXPEPDOCK";

export type BatchComputationStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "BLOCKED"
  | "CANCELLED";

export interface BatchComputation {
  id: string;
  project_id: string;
  name: string;
  job_type: BatchJobType;
  status: BatchComputationStatus;
  artifact_dir: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BatchComputationCreatePayload {
  project_id: string;
  name: string;
  job_type: BatchJobType;
  candidate_ids: string[];
  input_json?: Record<string, unknown>;
  created_by?: string | null;
}

export interface BatchComputationListResponse {
  items: BatchComputation[];
  total: number;
  limit: number;
  offset: number;
}

export interface BatchItem {
  id: string;
  batch_id: string;
  candidate_id: string | null;
  job_type: string;
  status: BatchComputationStatus;
  error_message: string | null;
  artifact_dir: string | null;
  output_json: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface ArtifactFile {
  name: string;
  path: string;
  size: number;
  is_dir: boolean;
  modified_at: string | null;
}

export interface LogContent {
  stdout: string;
  stderr: string;
  exists: boolean;
}

export interface BatchReport {
  batch_id: string;
  job_type: string;
  status: string;
  total_items: number;
  succeeded_items: number;
  failed_items: number;
  blocked_items: number;
  pending_items: number;
  md_results: MdResultItem[];
  flexpepdock_results: FlexPepDockResultItem[];
  mmgbsa_results: MmGbsaResultItem[];
}

export interface MdResultItem {
  item_id: string;
  candidate_id: string | null;
  status: string;
  rmsd_file_exists: boolean;
  rmsd_file_path: string | null;
  rmsf_file_exists: boolean;
  rmsf_file_path: string | null;
  rg_file_exists: boolean;
  rg_file_path: string | null;
  output_json: Record<string, unknown>;
}

export interface FlexPepDockResultItem {
  item_id: string;
  candidate_id: string | null;
  status: string;
  score_sc_exists: boolean;
  score_sc_path: string | null;
  output_json: Record<string, unknown>;
}

export interface MmGbsaResultItem {
  item_id: string;
  candidate_id: string | null;
  status: string;
  dg_file_exists: boolean;
  dg_file_path: string | null;
  output_json: Record<string, unknown>;
}

export interface MmgbsaResultResponse {
  status: string;
  source_file: string | null;
  run_type: string | null;
  convergence_status: string | null;
  frames_used: number | null;
  delta_g_total: number | null;
  components: {
    vdW?: number | null;
    electrostatic?: number | null;
    polar_solvation?: number | null;
    nonpolar_solvation?: number | null;
  };
  official_mm_gbsa_delta_g: number | null;
  warnings: string[];
  decomposition_available: boolean;
  message: string | null;
}

export interface RunnerLogResponse {
  batch_id: string;
  item_id: string;
  job_type: string;
  exists: boolean;
  command: string | null;
  returncode: string | null;
  started_at: string | null;
  finished_at: string | null;
  stdout_exists: boolean;
  stderr_exists: boolean;
  stdout_size: number;
  stderr_size: number;
  stdout: string;
  stderr: string;
  is_tail: boolean;
}
