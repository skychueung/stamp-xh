/**
 * STAMP v1.2 — Production MD Types
 * Mirrors backend/app/routers/production_md.py schemas
 */

export type ProductionMDStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "BLOCKED"
  | "CANCELLED";

export interface ProductionMDJob {
  job_id: string;
  status: ProductionMDStatus;
  duration_ns: number;
  candidate_id: string;
  project_id: string;
  created_at: string;
}

export interface ProductionMDCreatePayload {
  project_id: string;
  candidate_id: string;
  duration_ns: number;
  topology_path: string;
  coordinates_path: string;
  previous_md_job_id?: string | null;
  server_host?: string | null;
  priority?: number;
}

export interface ProductionMDSubmitResponse {
  status: string;
  detail: string;
  job_id: string;
}

export interface ProductionMDDurationInfo {
  duration_ns: number;
  nsteps: number;
  timestep_ps: number;
}

export interface ProductionMDDurationListResponse {
  durations_ns: number[];
  details: ProductionMDDurationInfo[];
}

export interface MdPilotProbeResponse {
  status: string;
  stamp_md_env_available: boolean;
  gromacs_available: boolean;
  gromacs_version: string | null;
  gpu_available: boolean;
  gpu_info: Array<{ name: string; driver_version: string; memory: string }> | null;
  mdanalysis_available: boolean;
  openmm_available: boolean;
  parmed_available: boolean;
  amber_available: boolean;
  mmgbsa_available: boolean;
  mmgbsa_version: string | null;
  platform_version: string;
  input_pdb_valid: boolean;
  input_pdb_path: string | null;
  blocking_reasons: string[];
  next_actions: string[];
}
