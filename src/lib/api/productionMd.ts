import { fetchClient } from './client';
import type {
  ProductionMDJob,
  ProductionMDCreatePayload,
  ProductionMDSubmitResponse,
  ProductionMDDurationListResponse,
  MdPilotProbeResponse,
} from '@/types/productionMd';

export const productionMdApi = {
  listDurations: () =>
    fetchClient<ProductionMDDurationListResponse>('/production-md/durations'),

  createJob: (data: ProductionMDCreatePayload) =>
    fetchClient<ProductionMDJob>('/production-md/jobs', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  probeEnvironment: () =>
    fetchClient<MdPilotProbeResponse>('/md-pilot/probe'),

  submitJob: (jobId: string) =>
    fetchClient<ProductionMDSubmitResponse>(`/production-md/jobs/${jobId}/submit`, {
      method: 'POST',
    }),
};
