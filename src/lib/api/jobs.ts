import { fetchClient } from './client';

export interface JobResponse {
  id: string;
  project_id: string;
  job_type: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  progress: number | null;
  message: string | null;
  error_message: string | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
}

export interface JobListResponse {
  project_id: string;
  total_count: number;
  jobs: JobResponse[];
}

export interface JobFailureDiagnosis {
  job_id: string;
  job_type: string;
  status: string;
  error_category: string;
  cause: string;
  suggestions: string[];
  related_logs: string[];
  related_artifacts: { type?: string; path: string }[];
  raw_error_message: string | null;
  raw_error_json: Record<string, unknown> | null;
}

export const jobsApi = {
  createJob: (payload: { project_id: string; job_type: string; input_json?: Record<string, unknown> }) =>
    fetchClient<JobResponse>('/jobs', { method: 'POST', body: JSON.stringify(payload) }),

  getJob: (jobId: string) =>
    fetchClient<JobResponse>(`/jobs/${jobId}`),

  listJobsByProject: (projectId: string, options?: { status?: string; job_type?: string; limit?: number; offset?: number }) => {
    const params = new URLSearchParams();
    if (options?.status) params.append('status', options.status);
    if (options?.job_type) params.append('job_type', options.job_type);
    if (options?.limit !== undefined) params.append('limit', options.limit.toString());
    if (options?.offset !== undefined) params.append('offset', options.offset.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    return fetchClient<JobListResponse>(`/jobs/by-project/${projectId}${query}`);
  },

  runMock: (jobId: string, options?: { sleep_seconds?: number; should_fail?: boolean; fail_message?: string }) =>
    fetchClient<{ job_id: string; status: string; message: string; validation_status: string }>(
      `/jobs/${jobId}/run-mock`,
      { method: 'POST', body: JSON.stringify(options || {}) }
    ),

  runReal: (jobId: string) =>
    fetchClient<JobResponse>(`/jobs/${jobId}/run`, { method: 'POST' }),

  startJob: (jobId: string) =>
    fetchClient<{ job_id: string; status: string; progress: number; message: string }>(
      `/jobs/${jobId}/start`,
      { method: 'POST' }
    ),

  persistBepiPred3Results: (jobId: string) =>
    fetchClient<{
      job_id: string;
      scan_id: string;
      candidate_count: number;
      created_candidate_ids: string[];
      status: string;
      validation_status: string;
      prediction_status: string;
      skipped_count: number;
    }>(`/jobs/${jobId}/persist-bepipred3-results`, { method: 'POST' }),

  persistPepMLMResults: (jobId: string) =>
    fetchClient<{
      job_id: string;
      generation_run_id: string;
      candidate_count: number;
      created_candidate_ids: string[];
      status: string;
      validation_status: string;
      generation_status: string;
      real_model_loaded: boolean;
    }>(`/jobs/${jobId}/persist-pepmlm-results`, { method: 'POST' }),

  cancelJob: (jobId: string) =>
    fetchClient<{ job_id: string; previous_status: string; status: string; message: string }>(
      `/jobs/${jobId}/cancel`,
      { method: 'POST' }
    ),

  retryJob: (jobId: string) =>
    fetchClient<{ original_job_id: string; new_job_id: string; status: string; message: string }>(
      `/jobs/${jobId}/retry`,
      { method: 'POST' }
    ),

  getDiagnosis: (jobId: string) =>
    fetchClient<{ data: JobFailureDiagnosis }>(`/jobs/${jobId}/diagnosis`),
};
