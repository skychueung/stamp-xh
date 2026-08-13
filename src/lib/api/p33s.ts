// P33S real-model GPU inference + scientific scoring pipeline API helpers.
// All responses are tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.

export interface P33SScorerAvailability {
  scorers: Record<
    string,
    {
      backend: string;
      status: string;
      label?: string;
      bin_present?: boolean;
      env_present?: boolean;
      weights_present?: boolean;
      gpu_inference?: string;
      real_cpu_test?: string;
      requires_env?: string;
      reason?: string;
    }
  >;
  models: Record<
    string,
    { order: number; unavailable: boolean; unavailable_reason: string }
  >;
  validation_status: string;
  prediction_tag: string;
}

export interface P33SPipelineRequest {
  target_sequence: string;
  peptide_length: number;
  seed: number;
  gpu_device: string | null;
  max_wall_seconds: number;
  output_quota_bytes: number;
}

export interface P33SPipelineSummary {
  model_id: string;
  job_id: string;
  mode: string;
  validation_status: string;
  prediction_tag: string;
  stages?: Array<{
    stage: string;
    status: string;
    manifest_path?: string;
    detail?: Record<string, unknown>;
  }>;
  manifest_path?: string;
  plan?: Record<string, unknown>;
  manifest_dir?: string;
  status?: string;
  reason?: string;
  message?: string;
}

export interface P33SCancelResult {
  model_id: string;
  job_id: string;
  gate_state: Record<string, unknown> | null;
  validation_status: string;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
  const json = await res.json().catch(() => ({ code: res.status, data: {} }));
  return (json.data ?? json) as T;
}

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  return (json.data ?? json) as T;
}

export async function fetchScorerAvailability(): Promise<P33SScorerAvailability> {
  return getJson<P33SScorerAvailability>("/api/v1/p33s/scorer-availability");
}

export async function p33sProbe(modelId: string): Promise<P33SPipelineSummary> {
  return postJson<P33SPipelineSummary>(`/api/v1/p33s/${modelId}/probe`, {});
}

export async function p33sDryRun(
  modelId: string,
  req: P33SPipelineRequest
): Promise<P33SPipelineSummary> {
  return postJson<P33SPipelineSummary>(`/api/v1/p33s/${modelId}/dry-run`, req);
}

export async function p33sRealRun(
  modelId: string,
  req: P33SPipelineRequest
): Promise<P33SPipelineSummary> {
  // Returns 403/BLOCKED when real_run_enabled=false or execution_locked=true.
  return postJson<P33SPipelineSummary>(`/api/v1/p33s/${modelId}/real-run`, req);
}

export async function p33sJobStatus(
  modelId: string,
  jobId: string
): Promise<P33SPipelineSummary> {
  return getJson<P33SPipelineSummary>(
    `/api/v1/p33s/${modelId}/jobs/${jobId}/status`
  );
}

export async function p33sCancel(
  modelId: string,
  jobId: string
): Promise<P33SCancelResult> {
  const res = await fetch(`/api/v1/p33s/${modelId}/jobs/${jobId}/cancel`, {
    method: "POST",
    cache: "no-store",
  });
  const json = await res.json();
  return (json.data ?? json) as P33SCancelResult;
}

export async function p33sManifest(
  modelId: string,
  jobId: string
): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(
    `/api/v1/p33s/${modelId}/jobs/${jobId}/manifest`
  );
}
