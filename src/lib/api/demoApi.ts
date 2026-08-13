// Demo overview API client (止血 demo mainline).
// Reads REAL golden-run pipeline data from the read-only backend endpoint
// /api/v1/demo/overview. All data is NOT_EXPERIMENTALLY_VALIDATED /
// COMPUTATIONAL_PREDICTION_ONLY. Mock must never silently substitute for this.

import { fetchClient } from './client';

export interface DemoEpitopeCandidate {
  id: string;
  start: number | null;
  end: number | null;
  sequence: string | null;
  net_charge: number | null;
  hydrophobicity: number | null;
  pi: number | null;
  cys_count: number | null;
  surface_exposure_score: number | null;
  ranking_score: number | null;
  accessibility_score: number | null;
}

export interface DemoSourceModel {
  name: string;
  version: string | null;
  count: number;
}

export interface DemoStampCandidate {
  id: string;
  full_sequence: string | null;
  targeting_peptide_seq: string | null;
  linker_seq: string | null;
  composite_score: number | null;
  length: number | null;
  net_charge: number | null;
  hydrophobicity: number | null;
  source_model: string | null;
  functional_peptide_source: string | null;
  functional_peptide_name: string | null;
  linker_type: string | null;
  validation_status: string;
  created_at: string | null;
}

export interface DemoOverview {
  data_source: 'real_db' | 'empty';
  run_id?: string;
  project_id?: string | null;
  target_name?: string;
  target_sequence?: string;
  target_sequence_length?: number;
  status?: string;
  current_step?: string;
  created_at?: string | null;
  epitope_candidate_count: number;
  epitope_candidates: DemoEpitopeCandidate[];
  stamp_candidate_count: number;
  stamp_candidate_total_for_run?: number;
  source_models: DemoSourceModel[];
  stamp_candidates: DemoStampCandidate[];
  selected_source_model: string;
  validation_status: string;
  prediction_tag: string;
  disclosure?: string;
  message?: string;
}

export const demoApi = {
  getOverview: (params?: { run_id?: string; source_model?: string }) => {
    const qs = new URLSearchParams();
    if (params?.run_id) qs.set('run_id', params.run_id);
    if (params?.source_model) qs.set('source_model', params.source_model);
    const query = qs.toString();
    return fetchClient<DemoOverview>(`/demo/overview${query ? `?${query}` : ''}`);
  },
};
