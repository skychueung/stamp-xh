import { fetchClient } from './client';
import type { Project, ProjectCreate } from '@/types/project';

export const projectsApi = {
  list: () => fetchClient<Project[]>('/projects'),
  getById: (id: string) => fetchClient<Project>(`/projects/${id}`),
  create: (data: ProjectCreate) => fetchClient<Project>('/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};
