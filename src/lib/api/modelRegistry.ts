import { API_BASE_URL, ApiError, fetchClient } from './client';
import type {
  ModelArtifactsResponse,
  ModelDetailResponse,
  ModelDryRunPayload,
  ModelDryRunResult,
  ModelJobStatus,
  ModelProbeResult,
  ModelsListResponse,
  ModelRegistryStatusResponse,
  ModelSubmitResponse,
  ModelEvidenceResponse,
  TargetDesignWorkflowPayload,
  TargetDesignWorkflowResult,
} from '@/types/modelRegistry';

export const modelRegistryApi = {
  getModels: () => fetchClient<ModelsListResponse>('/models'),

  getModelRegistry: () => fetchClient<ModelsListResponse>('/model-registry'),

  getModelRegistryStatus: () =>
    fetchClient<ModelRegistryStatusResponse>('/model-registry/status'),

  getModel: (modelId: string) =>
    fetchClient<ModelDetailResponse>(`/models/${encodeURIComponent(modelId)}`),

  getModelEvidence: (modelId: string) =>
    fetchClient<ModelEvidenceResponse>(
      `/models/${encodeURIComponent(modelId)}/evidence`
    ),

  downloadEvidenceBlob: async (modelId: string, evidenceId: string): Promise<Blob> => {
    const response = await fetch(
      `${API_BASE_URL}/models/${encodeURIComponent(modelId)}/evidence/${encodeURIComponent(evidenceId)}/download`,
      { method: 'GET' }
    );
    if (!response.ok) {
      let detail = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        if (body?.detail) detail = body.detail;
        else if (body?.message) detail = body.message;
      } catch {
        /* non-JSON error body; keep status-only detail */
      }
      throw new ApiError(response.status, detail);
    }
    return response.blob();
  },

  probeModel: (modelId: string) =>
    fetchClient<ModelProbeResult>(`/models/${encodeURIComponent(modelId)}/probe`),

  dryRunModel: (modelId: string, payload: ModelDryRunPayload) =>
    fetchClient<ModelDryRunResult>(`/models/${encodeURIComponent(modelId)}/dry-run`, {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  submitRealRun: (modelId: string, payload: ModelDryRunPayload, sync = true) =>
    fetchClient<ModelSubmitResponse>(
      `/models/${encodeURIComponent(modelId)}/submit?sync=${String(sync)}`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      }
    ),

  getModelJobStatus: (modelId: string, jobId: string) =>
    fetchClient<ModelJobStatus>(
      `/models/${encodeURIComponent(modelId)}/jobs/${encodeURIComponent(jobId)}`
    ),

  getModelArtifacts: (modelId: string, jobId: string) =>
    fetchClient<ModelArtifactsResponse>(
      `/models/${encodeURIComponent(modelId)}/jobs/${encodeURIComponent(jobId)}/artifacts`
    ),

  workflowDryRun: (payload: TargetDesignWorkflowPayload) =>
    fetchClient<TargetDesignWorkflowResult>('/workflows/target-design/dry-run', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  exportWorkflowReportJson: (workflowId: string) =>
    fetch(`/api/v1/workflows/target-design/reports/${encodeURIComponent(workflowId)}.json`, {
      method: 'GET',
    }),

  exportWorkflowReportMarkdown: (workflowId: string) =>
    fetch(`/api/v1/workflows/target-design/reports/${encodeURIComponent(workflowId)}.md`, {
      method: 'GET',
    }),

  downloadWorkflowArtifact: (artifactRef: string) =>
    fetch(`/api/v1/workflows/target-design/artifacts/${encodeURIComponent(artifactRef)}/download`, {
      method: 'GET',
    }),
};
