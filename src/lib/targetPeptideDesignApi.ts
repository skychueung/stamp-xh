import { fetchClient } from './api/client';

export interface TargetPeptideDesignModelInfo {
  model_id: string;
  display_name: string;
  category: string;
  input_type: string;
  status: string;
  stage: string;
  description: string;
  requires_structure: boolean;
  requires_gpu: boolean;
  notes: string;
}

export interface TargetPeptideDesignModelsResponse {
  models: TargetPeptideDesignModelInfo[];
  scientific_boundary: string;
}

export interface TargetPeptideDesignModelProbeDependencyStatus {
  available: boolean;
  version?: string | null;
  error?: string | null;
}

export interface TargetPeptideDesignModelProbeCudaStatus {
  available: boolean;
  device_count: number;
  devices: Array<{ index: number; name: string }>;
  torch_cuda_version?: string | null;
  current_device?: number | null;
  error?: string | null;
}

export interface TargetPeptideDesignModelProbePathStatus {
  path: string;
  exists: boolean;
  is_dir: boolean;
  writable: boolean;
  error?: string | null;
}

export interface TargetPeptideDesignModelProbeConfigStatus {
  pepmlm_model_path_configured: boolean;
  pepmlm_model_path?: string | null;
  pepmlm_model_path_exists: boolean;
  pepmlm_model_path_is_dir: boolean;
  pepmlm_model_path_empty: boolean;
  pepmlm_hf_model_id_configured: boolean;
  pepmlm_hf_model_id?: string | null;
  pepmlm_device: string;
  pepmlm_allow_download: boolean;
  pepmlm_offline_only: boolean;
  target_peptide_models_dir: string;
}

export interface TargetPeptideDesignModelProbeResult {
  probe_time: string;
  model_id: string;
  display_name: string;
  status: string;
  message: string;
  backend_env_status: string;
  pepmlm_env_status: string;
  pepmlm_env_python?: string | null;
  pepmlm_env_check_script: string;
  recommended_runtime_env: string;
  dependency_status: {
    python_executable: string;
    python_version: string;
    pip_executable?: string | null;
    torch: TargetPeptideDesignModelProbeDependencyStatus;
    transformers: TargetPeptideDesignModelProbeDependencyStatus;
    huggingface_hub: TargetPeptideDesignModelProbeDependencyStatus;
  };
  cuda_status: TargetPeptideDesignModelProbeCudaStatus;
  path_status: {
    target_peptide_models_dir: TargetPeptideDesignModelProbePathStatus;
    target_peptide_design_root: TargetPeptideDesignModelProbePathStatus;
    probe_root: TargetPeptideDesignModelProbePathStatus;
  };
  config_status: TargetPeptideDesignModelProbeConfigStatus;
  scientific_boundary: string;
  next_action: string;
  pepmlm_env_status_detail?: Record<string, unknown> | null;
}

export interface TargetPeptideDesignModelProbeSummary {
  probe_time: string;
  total_models: number;
  available_models: number;
  config_required_models: number;
  dependency_missing_models: number;
  gpu_not_available_models: number;
  model_not_available_models: number;
  offline_only_models: number;
  planned_models: number;
  pepmlm_status: string;
  pepmlm_env_status?: string | null;
  pepmlm_next_action: string;
  pepmlm_env_python?: string | null;
  pepmlm_env_check_script: string;
  recommended_runtime_env: string;
  probe_dir: string;
  models_dir: string;
  models_dir_writable: boolean;
  data_dir_writable: boolean;
  probe_dir_writable: boolean;
  pepmlm_model_path_configured: boolean;
  pepmlm_hf_model_id_configured: boolean;
  pepmlm_allow_download: boolean;
  pepmlm_offline_only: boolean;
  backend_env_status?: string | null;
}

export interface TargetPeptideDesignModelProbesResponse {
  probe_time: string;
  probes: TargetPeptideDesignModelProbeResult[];
  scientific_boundary: string;
  summary: TargetPeptideDesignModelProbeSummary;
}

export interface TargetPeptideDesignJobCreatePayload {
  target_name: string;
  target_sequence: string;
  model_id: string;
  peptide_length: number;
  num_candidates: number;
  notes?: string | null;
}

export interface TargetPeptideDesignJob {
  job_id: string;
  target_name: string;
  target_sequence: string;
  model_id: string;
  peptide_length: number;
  num_candidates: number;
  status: string;
  message: string;
  artifact_dir: string;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  scientific_boundary: string;
}

export interface TargetPeptideDesignCandidate {
  sequence: string;
  length: number;
  source_model: string;
  status: string;
  notes?: string | null;
}

export interface TargetPeptideDesignCandidatesResponse {
  job_id: string;
  candidates: TargetPeptideDesignCandidate[];
  note: string;
  scientific_boundary: string;
}

export const targetPeptideDesignApi = {
  getModels: () => fetchClient<TargetPeptideDesignModelsResponse>('/target-peptide-design/models'),

  getModelProbes: () =>
    fetchClient<TargetPeptideDesignModelProbesResponse>('/target-peptide-design/models/probe'),

  getModelProbe: (modelId: string) =>
    fetchClient<TargetPeptideDesignModelProbeResult>(`/target-peptide-design/models/${encodeURIComponent(modelId)}/probe`),

  createJob: (payload: TargetPeptideDesignJobCreatePayload) =>
    fetchClient<TargetPeptideDesignJob>('/target-peptide-design/jobs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getJob: (jobId: string) =>
    fetchClient<TargetPeptideDesignJob>(`/target-peptide-design/jobs/${jobId}`),

  getCandidates: (jobId: string) =>
    fetchClient<TargetPeptideDesignCandidatesResponse>(`/target-peptide-design/jobs/${jobId}/candidates`),
};
