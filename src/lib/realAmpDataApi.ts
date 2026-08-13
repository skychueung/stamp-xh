/**
 * STAMP v0.6b — Real AMP Data API
 * Type-safe JSON fetch wrappers with fallback defaults.
 * Zero `any` usage.
 */

import type {
  AmpStructureManifest,
  StampCandidatesResponse,
  AmpStructureRecord,
  StampHybridCandidate,
} from '@/types/stamp';

const API_BASE = '/data';

async function fetchJson<T>(path: string, defaultValue: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`);
    if (!response.ok) {
      console.warn(`[realAmpDataApi] Failed to fetch ${path}: ${response.status}`);
      return defaultValue;
    }
    const data: unknown = await response.json();
    return data as T;
  } catch (error) {
    console.error(`[realAmpDataApi] Error fetching ${path}:`, error);
    return defaultValue;
  }
}

// ───────────────────────────────────────────────
// Raw API fetches
// ───────────────────────────────────────────────

export const fetchAmpStructureManifest = (): Promise<AmpStructureManifest> =>
  fetchJson<AmpStructureManifest>('/amp_structure_manifest.json', {
    generatedAt: '',
    version: '',
    note: '',
    source: { zipFile: '', unzippedDir: '' },
    counts: { expected: 0, observed: 0, status: 'empty', cifTotal: 0, bestModelsCopied: 0, plddtExtracted: 0 },
    qualityDistribution: {},
    plddtRange: { min: 0, max: 0, mean: 0 },
    structures: [],
  });

export const fetchStampHybridCandidates = (): Promise<StampCandidatesResponse> =>
  fetchJson<StampCandidatesResponse>('/stamp_hybrid_candidates.json', {
    generatedAt: '',
    version: '',
    note: '',
    total_candidates: 0,
    candidates: [],
  });

export const fetchRealAmpStructures = (): Promise<Record<string, unknown>> =>
  fetchJson<Record<string, unknown>>('/real_amp_structures.json', {});

export const fetchPriorityAmpLibrary = (): Promise<Record<string, unknown>> =>
  fetchJson<Record<string, unknown>>('/priority_amp_library.json', {});

// ───────────────────────────────────────────────
// Convenience extractors
// ───────────────────────────────────────────────

export async function getAmpStructureRecords(): Promise<AmpStructureRecord[]> {
  const manifest = await fetchAmpStructureManifest();
  return manifest.structures ?? [];
}

export async function getStampCandidates(): Promise<StampHybridCandidate[]> {
  const response = await fetchStampHybridCandidates();
  return response.candidates ?? [];
}

export function computeMeanPlddt(records: AmpStructureRecord[]): number {
  if (records.length === 0) return 0;
  const sum = records.reduce((acc, r) => acc + r.confidence.meanPlddt, 0);
  return sum / records.length;
}

export function countVeryHighConfidence(records: AmpStructureRecord[]): number {
  return records.filter((r) => r.confidence.meanPlddt >= 90).length;
}
