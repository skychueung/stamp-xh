import { fetchClient } from './client';
import type { EpitopeScan, EpitopeScanCreate } from '@/types/epitope';

export const epitopeScansApi = {
  create: (data: EpitopeScanCreate) =>
    fetchClient<EpitopeScan>('/epitope-scans', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  getById: (scanId: string) =>
    fetchClient<EpitopeScan>(`/epitope-scans/${scanId}`),
  // 预留获取扫描候选结果的接口
  getCandidates: (scanId: string) =>
    fetchClient<any[]>(`/epitope-scans/${scanId}/candidates`),
};
