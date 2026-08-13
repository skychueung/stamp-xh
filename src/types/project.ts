export interface Project {
  id: string;
  name: string;
  description?: string;
  species?: string;
  project_type?: string;
  created_at: string;
  updated_at: string;
}

export type ProjectCreate = Omit<Project, 'id' | 'created_at' | 'updated_at'>;
