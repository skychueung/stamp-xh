import { fetchClient } from './client';
import type { TargetProtein, TargetProteinCreate } from '@/types/targetProtein';

export const targetProteinsApi = {
  create: (data: TargetProteinCreate) =>
    fetchClient<TargetProtein>('/target-proteins', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  listByProject: (projectId: string) =>
    fetchClient<TargetProtein[]>(`/projects/${projectId}/target-proteins`),
};
