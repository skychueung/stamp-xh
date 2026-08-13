import { fetchClient } from './client';
import type { FileAsset } from '@/types/fileAsset';

export const fileAssetsApi = {
  listByJob: (jobId: string) =>
    fetchClient<FileAsset[]>(`/assets?job_id=${encodeURIComponent(jobId)}`),

  listByBatch: (batchId: string) =>
    fetchClient<FileAsset[]>(`/assets?batch_id=${encodeURIComponent(batchId)}`),

  getById: (assetId: string) =>
    fetchClient<FileAsset>(`/assets/${assetId}`),

  downloadBundle: (batchId: string): Promise<Blob> => {
    const url = `/assets/bundles/${batchId}`;
    return fetch(`${import.meta.env.VITE_API_BASE_URL || '/api/v1'}${url}`, {
      method: 'GET',
      headers: {},
    }).then((res) => {
      if (!res.ok) throw new Error(`Download failed: ${res.statusText}`);
      return res.blob();
    });
  },
};
