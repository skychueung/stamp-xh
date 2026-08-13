// P33T result delivery center API helpers.
// All responses are tagged NOT_EXPERIMENTALLY_VALIDATED / COMPUTATIONAL_PREDICTION_ONLY.

import type {
  P33TBaseResponse,
  P33TCandidate,
  P33TCandidateListResponse,
  P33TCandidateMetricsResponse,
  P33TDeliveryBundle,
  P33TFilterRequest,
  P33TFilterResponse,
} from '@/types/p33t';

const API_PREFIX = '/api/v1/target-design';

async function getJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  const json = (await res.json()) as P33TBaseResponse<T>;
  return (json.data ?? json) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    cache: 'no-store',
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  const json = (await res.json()) as P33TBaseResponse<T>;
  return (json.data ?? json) as T;
}

export async function fetchP33TCandidates(
  page = 1,
  pageSize = 20,
  sourceModelId?: string,
  scope: "all" | "P33U" | "legacy" = "P33U",
  top4?: boolean
): Promise<P33TCandidateListResponse> {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('page_size', String(pageSize));
  params.set('scope', scope);
  if (top4) params.set('top4', "true");
  if (sourceModelId) params.set('source_model_id', sourceModelId);
  return getJson<P33TCandidateListResponse>(`${API_PREFIX}/results?${params.toString()}`);
}

export async function fetchP33TCandidate(candidateId: string): Promise<P33TCandidate> {
  return getJson<P33TCandidate>(`${API_PREFIX}/results/${candidateId}`);
}

export async function fetchP33TCandidateMetrics(
  candidateId: string
): Promise<P33TCandidateMetricsResponse> {
  return getJson<P33TCandidateMetricsResponse>(`${API_PREFIX}/results/${candidateId}/metrics`);
}

export async function fetchP33TCandidateManifest(
  candidateId: string
): Promise<Record<string, unknown>> {
  return getJson<Record<string, unknown>>(`${API_PREFIX}/results/${candidateId}/manifest`);
}

export function buildP33TDownloadUrl(candidateId: string, artifactId: string): string {
  return `${API_PREFIX}/results/${encodeURIComponent(candidateId)}/downloads/${encodeURIComponent(
    artifactId
  )}`;
}

export async function downloadP33TArtifact(
  candidateId: string,
  artifactId: string
): Promise<Blob> {
  const url = buildP33TDownloadUrl(candidateId, artifactId);
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.blob();
}

export async function filterP33TCandidates(req: P33TFilterRequest): Promise<P33TFilterResponse> {
  return postJson<P33TFilterResponse>(`${API_PREFIX}/results/filter`, req);
}

export async function createP33TDeliveryBundle(): Promise<P33TDeliveryBundle> {
  return postJson<P33TDeliveryBundle>(`${API_PREFIX}/delivery-bundles`, {});
}

export async function fetchP33TDeliveryBundle(bundleId: string): Promise<P33TDeliveryBundle> {
  return getJson<P33TDeliveryBundle>(`${API_PREFIX}/delivery-bundles/${bundleId}`);
}

export function buildP33TBundleDownloadUrl(bundleId: string): string {
  return `${API_PREFIX}/delivery-bundles/${encodeURIComponent(bundleId)}/download`;
}

export async function downloadP33TBundle(bundleId: string): Promise<Blob> {
  const url = buildP33TBundleDownloadUrl(bundleId);
  const res = await fetch(url, { cache: 'no-store' });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.blob();
}
