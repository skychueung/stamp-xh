import { API_BASE_URL } from './client';
import type {
  BatchComputation,
  BatchComputationCreatePayload,
  BatchComputationListResponse,
  BatchItem,
  ArtifactFile,
  LogContent,
  BatchReport,
  MmgbsaResultResponse,
  RunnerLogResponse,
} from '@/types/batchComputation';

export const batchComputationApi = {
  list: (params?: { project_id?: string; status?: string; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    if (params?.project_id) search.append('project_id', params.project_id);
    if (params?.status) search.append('status', params.status);
    if (params?.limit !== undefined) search.append('limit', String(params.limit));
    if (params?.offset !== undefined) search.append('offset', String(params.offset));
    const query = search.toString();
    return fetchClient<BatchComputationListResponse>(`/batch-computations${query ? `?${query}` : ''}`);
  },

  getById: (id: string) => fetchClient<BatchComputation>(`/batch-computations/${id}`),

  getItems: (id: string) => fetchClient<BatchItem[]>(`/batch-computations/${id}/items`),

  getReport: (id: string) => fetchClient<BatchReport>(`/batch-computations/${id}/report`),

  getItemArtifacts: (batchId: string, itemId: string) =>
    fetchClient<ArtifactFile[]>(`/batch-computations/${batchId}/items/${itemId}/artifacts`),

  getItemLogs: (batchId: string, itemId: string) =>
    fetchClient<LogContent>(`/batch-computations/${batchId}/items/${itemId}/logs`),

  create: (data: BatchComputationCreatePayload) =>
    fetchClient<BatchComputation>('/batch-computations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  retryFailed: (id: string) =>
    fetchClient<{ batch_id: string; retried_count: number }>(`/batch-computations/${id}/retry-failed`, {
      method: 'POST',
    }),

  cancel: (id: string) =>
    fetchClient<BatchComputation>(`/batch-computations/${id}/cancel`, {
      method: 'POST',
    }),

  dispatch: (id: string) =>
    fetchClient<{ batch_id: string; total_pending: number; dispatched: number; blocked: number; failed: number }>(
      `/batch-computations/${id}/dispatch`,
      { method: 'POST' }
    ),

  download: (id: string, format: 'zip' | 'json' | 'csv' | 'md' = 'zip') =>
    fetch(`${API_BASE_URL}/batch-computations/${id}/download?format=${format}`),

  downloadComputationReport: (id: string, format: 'json' | 'markdown' | 'md' | 'pdf' = 'json') =>
    fetch(`${API_BASE_URL}/batch-computations/${id}/computation-report?format=${format}`),

  getMmgbsaResults: (batchId: string, itemId: string) =>
    fetchClient<MmgbsaResultResponse>(`/batch-computations/${batchId}/items/${itemId}/mmgbsa-results`),

  getRunnerLogs: (batchId: string, itemId: string, full?: boolean) =>
    fetchClient<RunnerLogResponse>(
      `/runner-logs/${batchId}/${itemId}${full ? '?full=true' : ''}`
    ),

  downloadRunnerLogs: (batchId: string, itemId: string) =>
    fetch(`${API_BASE_URL}/runner-logs/${batchId}/${itemId}/download`),
};

async function fetchClient<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${url}`, {
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    ...init,
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ message: response.statusText }));
    throw new Error(errorData.message || `HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
