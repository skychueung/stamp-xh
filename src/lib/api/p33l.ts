// P33L one-click six-model real-run API helpers.
// These are appended to src/lib/api.ts in the final patch.

export interface P33LAuthorizedResponse {
  authorized: boolean;
  manifest_sha: string | null;
}

export interface P33LStatusResponse {
  authorized: boolean;
  completed_models: string[];
  failed_model: string | null;
  next_model: string | null;
  total_jobs: number;
}

export interface P33LJobResponse {
  job_id: string;
  model_id: string;
  status: string;
  run_dir: string;
  pid: number | null;
  result: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
}

export interface P33LRealRunResponse {
  code: number;
  data: P33LJobResponse;
}

export async function checkP33LAuthorized(): Promise<P33LAuthorizedResponse> {
  const res = await fetch("/api/v1/p33l/authorized", { cache: "no-store" });
  if (!res.ok) {
    return { authorized: false, manifest_sha: null };
  }
  const json = await res.json();
  return json.data ?? { authorized: false, manifest_sha: null };
}

export async function fetchP33LStatus(manifestSha: string): Promise<P33LStatusResponse> {
  const res = await fetch("/api/v1/p33l/status", {
    headers: { "P33L-Authorized-Manifest-SHA": manifestSha },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`P33L status failed: HTTP ${res.status}`);
  }
  const json = await res.json();
  return json.data;
}

export async function startP33LRealRun(
  modelId: string,
  input: Record<string, unknown>,
  manifestSha: string
): Promise<P33LRealRunResponse> {
  const res = await fetch("/api/v1/p33l/real-run", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "P33L-Authorized-Manifest-SHA": manifestSha,
    },
    body: JSON.stringify({ model_id: modelId, input }),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "P33L real-run failed");
    throw new Error(text);
  }
  return res.json();
}

export async function fetchP33LJob(
  jobId: string,
  manifestSha: string
): Promise<P33LJobResponse> {
  const res = await fetch(`/api/v1/p33l/jobs/${jobId}`, {
    headers: { "P33L-Authorized-Manifest-SHA": manifestSha },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`P33L job fetch failed: HTTP ${res.status}`);
  }
  const json = await res.json();
  return json.data;
}

export async function cancelP33LJob(
  jobId: string,
  manifestSha: string
): Promise<P33LJobResponse> {
  const res = await fetch(`/api/v1/p33l/jobs/${jobId}/cancel`, {
    method: "POST",
    headers: { "P33L-Authorized-Manifest-SHA": manifestSha },
  });
  if (!res.ok) {
    throw new Error(`P33L cancel failed: HTTP ${res.status}`);
  }
  const json = await res.json();
  return json.data;
}

export function p33lDownloadUrl(jobId: string, filePath: string, manifestSha: string): string {
  const encodedPath = encodeURIComponent(filePath);
  return `/api/v1/p33l/jobs/${jobId}/download/${encodedPath}?manifest_sha=${encodeURIComponent(manifestSha)}`;
}
