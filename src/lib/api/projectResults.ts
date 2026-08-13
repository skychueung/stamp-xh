import { fetchClient, API_BASE_URL } from './client';
import type { 
  ProjectSummaryResponse, 
  ProjectPipelineResultsResponse, 
  ProjectStampResultsResponse, 
  GenerationRunListResponse, 
  StampCandidateDetailResponse 
} from '@/types/projectResults';

export const projectResultsApi = {
  getProjectSummary: (projectId: string) => 
    fetchClient<ProjectSummaryResponse>(`/projects/${projectId}/summary`),
    
  getProjectPipelineResults: (projectId: string) => 
    fetchClient<ProjectPipelineResultsResponse>(`/projects/${projectId}/pipeline-results`),
    
  getProjectStampResults: (projectId: string, options?: { top_k?: number; include_metrics?: boolean }) => {
    const params = new URLSearchParams();
    if (options?.top_k !== undefined) params.append('top_k', options.top_k.toString());
    if (options?.include_metrics !== undefined) params.append('include_metrics', options.include_metrics.toString());
    const query = params.toString() ? `?${params.toString()}` : '';
    return fetchClient<ProjectStampResultsResponse>(`/projects/${projectId}/stamp-results${query}`);
  },
    
  getProjectGenerationRuns: (projectId: string) => 
    fetchClient<GenerationRunListResponse>(`/projects/${projectId}/generation-runs`),
    
  getStampCandidate: (candidateId: string) => 
    fetchClient<StampCandidateDetailResponse>(`/stamp-candidates/${candidateId}`),

  exportCandidateReport: async (projectId: string, format: 'json' | 'markdown' | 'csv', top_k: number = 10) => {
    const url = `${API_BASE_URL}/projects/${projectId}/candidate-report?format=${format}&top_k=${top_k}`;
    const response = await fetch(url, { headers: { 'Accept': format === 'json' ? 'application/json' : 'text/plain' } });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(errorData.message || 'Report export failed');
    }
    const content = await response.text();
    return { content, format };
  }
};
