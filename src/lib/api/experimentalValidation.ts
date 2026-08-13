import { fetchClient, API_BASE_URL } from './client';
import type {
  ExperimentalValidationRun,
  ExperimentalValidationSummary,
  CandidateExperimentalPriority,
  ValidationRunCreatePayload,
  MeasurementCreatePayload,
  ExperimentalMeasurement,
  ProjectExperimentalValidationSummary,
  CsvImportResult,
  ProjectCandidatePrioritization,
  PriorityDecisionPayload,
} from '@/types/experimentalValidation';

export const experimentalValidationApi = {
  /** POST /api/v1/experimental-validation/runs */
  createValidationRun: (payload: ValidationRunCreatePayload) =>
    fetchClient<ExperimentalValidationRun>('/experimental-validation/runs', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** GET /api/v1/experimental-validation/candidates/{candidate_id}/validation */
  getCandidateExperimentalValidation: (candidateId: string) =>
    fetchClient<ExperimentalValidationSummary>(`/experimental-validation/candidates/${candidateId}/validation`),

  /** POST /api/v1/experimental-validation/runs/{run_id}/measurements */
  addMeasurement: (runId: string, payload: MeasurementCreatePayload) =>
    fetchClient<ExperimentalMeasurement>(`/experimental-validation/runs/${runId}/measurements`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  /** GET /api/v1/experimental-validation/candidates/{candidate_id}/priority */
  getCandidateExperimentalPriority: (candidateId: string) =>
    fetchClient<CandidateExperimentalPriority>(`/experimental-validation/candidates/${candidateId}/priority`),

  /** GET /api/v1/experimental-validation/projects/{project_id}/summary */
  getProjectExperimentalValidationSummary: (projectId: string) =>
    fetchClient<ProjectExperimentalValidationSummary>(`/experimental-validation/projects/${projectId}/summary`),

  /** GET /api/v1/experimental-validation/projects/{project_id}/candidate-prioritization */
  getProjectCandidatePrioritization: (projectId: string) =>
    fetchClient<ProjectCandidatePrioritization>(`/experimental-validation/projects/${projectId}/candidate-prioritization`),

  /** POST /api/v1/experimental-validation/candidates/{candidate_id}/priority-decision */
  savePriorityDecision: (candidateId: string, payload: PriorityDecisionPayload) =>
    fetchClient<{ candidate_id: string; decision: Record<string, unknown>; composite_score: number | null; validation_status: string }>(
      `/experimental-validation/candidates/${candidateId}/priority-decision`,
      { method: 'POST', body: JSON.stringify(payload) },
    ),

  /** GET /api/v1/experimental-validation/projects/{project_id}/wetlab-validation-report */
  exportWetlabValidationReport: async (
    projectId: string,
    format: 'json' | 'markdown' | 'csv',
    topK: number = 50
  ): Promise<string | Record<string, unknown>> => {
    const url = `${API_BASE_URL}/experimental-validation/projects/${projectId}/wetlab-validation-report?format=${format}&top_k=${topK}`;
    const response = await fetch(url);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(errorData.message || 'Report export failed');
    }
    if (format === 'json') {
      const rawData = await response.json();
      return rawData.data !== undefined ? rawData.data : rawData;
    }
    return response.text();
  },

  /** POST /api/v1/experimental-validation/projects/{project_id}/import-measurements-csv */
  importMeasurementsCsv: async (projectId: string, file: File): Promise<CsvImportResult> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE_URL}/experimental-validation/projects/${projectId}/import-measurements-csv`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ message: response.statusText }));
      throw new Error(errorData.message || 'CSV import failed');
    }
    const rawData = await response.json();
    return rawData.data !== undefined ? rawData.data : rawData;
  },
};

// Re-export type for convenience
export type { ExperimentalMeasurement } from '@/types/experimentalValidation';
