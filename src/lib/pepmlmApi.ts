import type { PepmlmJsonStructure, PepmlmDataSourceLevel } from '@/types/pepmlm';

const DEFAULT_EMPTY: PepmlmJsonStructure = {
  metadata: {
    model_name: '',
    model_version: '',
    model_architecture: '',
    generator_script: '',
    target_name: '',
    target_species: '',
    target_sequence_length: 0,
    target_type: '',
    generation_date: '',
    peptide_lengths: [],
    num_candidates_requested: 0,
    num_candidates_generated: 0,
    top_k: 0,
    generation_mode: 'unknown',
    validation_status: 'unknown',
    validation_warning: 'Data source unknown or missing',
  },
  candidates: [],
  filtering_summary: { total: 0, passed: 0, warning: 0, failed: 0, pass_rate: 0, failure_reasons: {} },
};

function extractLevel(data: PepmlmJsonStructure): PepmlmDataSourceLevel {
  const raw = data.metadata?.generation_mode ?? '';
  if (raw.includes('official') || raw.includes('target_conditioned')) {
    return 'OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING';
  }
  if (raw.includes('experimental') || raw.includes('simplified')) {
    return 'EXPERIMENTAL_SIMPLIFIED_PARTIAL_MASK';
  }
  return 'UNKNOWN';
}

export async function loadPepmlmData(): Promise<{
  data: PepmlmJsonStructure;
  level: PepmlmDataSourceLevel;
  official: boolean;
  error?: string;
}> {
  try {
    const response = await fetch('/data/pepmlm_generated_targeting_peptides.json');
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const raw = (await response.json()) as PepmlmJsonStructure;
    const level = extractLevel(raw);
    return {
      data: raw,
      level,
      official: level === 'OFFICIAL_STYLE_TARGET_CONDITIONED_MASK_INFILLING',
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : 'Unknown error';
    return { data: DEFAULT_EMPTY, level: 'UNKNOWN', official: false, error: msg };
  }
}
