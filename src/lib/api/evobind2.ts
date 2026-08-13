import { fetchClient } from './client';
import type {
  EvoBind2DryRunRequest,
  EvoBind2DryRunResponse,
  EvoBind2JobSubmitRequest,
  EvoBind2JobResponse,
  EvoBind2ArtifactResponse,
  EvoBind2JobCancelResponse,
  EvoBind2ProbeResponse,
} from '@/types/evobind2';

const API_BASE = '/evobind2';

/**
 * EvoBind2 API client.
 *
 * - /evobind2/probe is always available and performs no real execution.
 * - /evobind2/dry-run is always available (safe planning, no execution).
 * - /evobind2/jobs and related endpoints are gated by compute_endpoints_enabled()
 *   and will return 403 in public-demo mode.
 */
export const evobind2Api = {
  getProbe: () => fetchClient<EvoBind2ProbeResponse>(`${API_BASE}/probe`),

  createDryRun: (data: EvoBind2DryRunRequest) =>
    fetchClient<EvoBind2DryRunResponse>(`${API_BASE}/dry-run`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  submitJob: (data: EvoBind2JobSubmitRequest) =>
    fetchClient<EvoBind2JobResponse>(`${API_BASE}/jobs`, {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  getJob: (jobId: string) => fetchClient<EvoBind2JobResponse>(`${API_BASE}/jobs/${jobId}`),

  getArtifacts: (jobId: string) =>
    fetchClient<EvoBind2ArtifactResponse>(`${API_BASE}/jobs/${jobId}/artifacts`),

  downloadArtifact: (jobId: string, artifactName: string) =>
    `${API_BASE}/jobs/${jobId}/artifacts/${artifactName}/download`,

  cancelJob: (jobId: string) =>
    fetchClient<EvoBind2JobCancelResponse>(`${API_BASE}/jobs/${jobId}/cancel`, {
      method: 'POST',
    }),
};
