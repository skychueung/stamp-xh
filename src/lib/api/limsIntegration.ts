import { fetchClient } from './client';
import type {
  IntegrationConfig,
  IntegrationConfigCreatePayload,
  IntegrationConfigUpdatePayload,
  IntegrationConfigListResponse,
} from '@/types/limsIntegration';

export const limsIntegrationApi = {
  list: (params?: { integration_type?: string; enabled?: boolean; limit?: number; offset?: number }) => {
    const search = new URLSearchParams();
    if (params?.integration_type) search.append('integration_type', params.integration_type);
    if (params?.enabled !== undefined) search.append('enabled', String(params.enabled));
    if (params?.limit !== undefined) search.append('limit', String(params.limit));
    if (params?.offset !== undefined) search.append('offset', String(params.offset));
    const query = search.toString();
    return fetchClient<IntegrationConfigListResponse>(`/integrations${query ? `?${query}` : ''}`);
  },

  getById: (id: string) => fetchClient<IntegrationConfig>(`/integrations/${id}`),

  create: (data: IntegrationConfigCreatePayload) =>
    fetchClient<IntegrationConfig>('/integrations', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  update: (id: string, data: IntegrationConfigUpdatePayload) =>
    fetchClient<IntegrationConfig>(`/integrations/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  delete: (id: string) =>
    fetchClient<void>(`/integrations/${id}`, {
      method: 'DELETE',
    }),

  testSync: (id: string) =>
    fetchClient<IntegrationConfig>(`/integrations/${id}/test-sync`, {
      method: 'POST',
    }),

  setStatus: (id: string, status: string) =>
    fetchClient<IntegrationConfig>(`/integrations/${id}/set-status?status=${encodeURIComponent(status)}`, {
      method: 'POST',
    }),
};
