import type { StampBackendCandidate, StampBackendResponse } from '@/types/stampBackend';
import { API_BASE_URL } from './api/client';

const BASE_URL = API_BASE_URL;

const BACKEND_UNAVAILABLE_MSG =
  'STAMP backend is not available. Please start the backend service.';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<{ data: T | null; error?: string }> {
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });

    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      try {
        const body = (await response.json()) as StampBackendResponse<unknown>;
        if (body.message) msg = body.message;
      } catch {
        /* ignore parse error */
      }
      return { data: null, error: msg };
    }

    const body = (await response.json()) as StampBackendResponse<T>;
    if (body.code !== 200 && body.code !== 201) {
      return { data: null, error: body.message || `API error code ${body.code}` };
    }
    return { data: body.data };
  } catch (err) {
    const isNetwork =
      err instanceof TypeError &&
      (err.message.includes('fetch') ||
        err.message.includes('Failed to fetch') ||
        err.message.includes('NetworkError'));
    return {
      data: null,
      error: isNetwork ? BACKEND_UNAVAILABLE_MSG : err instanceof Error ? err.message : 'Unknown error',
    };
  }
}

export async function fetchStampDemoOne(): Promise<{
  candidate: StampBackendCandidate | null;
  error?: string;
}> {
  const { data, error } = await apiFetch<StampBackendCandidate>('/stamp/demo-one');
  return { candidate: data, error };
}

export async function buildStampCandidate(payload: {
  candidate_id: string;
  amp_name?: string | null;
}): Promise<{ candidate: StampBackendCandidate | null; error?: string }> {
  const body = JSON.stringify({
    candidate_id: payload.candidate_id,
    amp_name: payload.amp_name ?? null,
  });
  const { data, error } = await apiFetch<StampBackendCandidate>('/stamp/build', {
    method: 'POST',
    body,
  });
  return { candidate: data, error };
}
