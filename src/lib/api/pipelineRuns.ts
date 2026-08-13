import { fetchClient } from './client';

export interface PipelineRunCreate {
  project_id?: string;
  target_name: string;
  target_sequence: string;
  mode?: 'run_all' | 'create_only';
  top_epitopes?: number;
  peptides_per_epitope?: number;
  top_stamp_candidates?: number;
  // P0 task: unified workbench params (genuinely sent in the POST body).
  // Backend accepts via PipelineRunCreate schema (extra fields are also ignored
  // gracefully by the live endpoint, so no 422). Stored into pipeline_runs.output_json.
  selected_models?: string[];
  epitope_type?: 'b_cell' | 't_cell';
  run_mode?: 'auto' | 'semi_auto';
}

export interface PipelineRun {
  id: string;
  project_id: string | null;
  target_name: string;
  status: string;
  current_step: string;
  created_at: string;
  updated_at: string;
  error_message: string | null;
}

export interface PipelineStepSummary {
  step_name: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  method: string | null;
  output_summary: Record<string, any>;
}

export interface PipelineStatus {
  run_id: string;
  target_name: string;
  status: string;
  current_step: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  steps: PipelineStepSummary[];
}

export interface PipelineArtifact {
  path: string;
  size_bytes: number;
}

export const pipelineRunsApi = {
  create: (data: PipelineRunCreate) =>
    fetchClient<PipelineRun>('/pipeline-runs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  list: (params?: { project_id?: string; status?: string; limit?: number; offset?: number }) => {
    const qs = new URLSearchParams();
    if (params?.project_id) qs.set('project_id', params.project_id);
    if (params?.status) qs.set('status', params.status);
    if (params?.limit) qs.set('limit', String(params.limit));
    if (params?.offset) qs.set('offset', String(params.offset));
    return fetchClient<{ items: PipelineRun[]; total: number }>(`/pipeline-runs?${qs.toString()}`);
  },

  get: (runId: string) => fetchClient<PipelineStatus>(`/pipeline-runs/${runId}`),

  getSteps: (runId: string) => fetchClient<PipelineStepSummary[]>(`/pipeline-runs/${runId}/steps`),

  run: (runId: string) =>
    fetchClient<PipelineRun>(`/pipeline-runs/${runId}/run`, { method: 'POST' }),

  retry: (runId: string, fromStep: string) =>
    fetchClient<PipelineRun>(`/pipeline-runs/${runId}/retry`, {
      method: 'POST',
      body: JSON.stringify({ from_step: fromStep }),
    }),

  listArtifacts: (runId: string) =>
    fetchClient<PipelineArtifact[]>(`/pipeline-runs/${runId}/artifacts`),

  download: (runId: string) => `/api/v1/pipeline-runs/${runId}/download`,

  artifactUrl: (runId: string, path: string) =>
    `/api/v1/pipeline-runs/${runId}/artifacts/download?path=${encodeURIComponent(path)}`,
};
