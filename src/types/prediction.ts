export type PredictionSummary = {
  totalExtracted: number;
  finalRetained: number;
  dropRate: number;
  top1Sequence: string | null;
  top1Score: number | null;
  averageTop3Score?: number | null;
  averageTop10Score?: number | null;
  proteinName?: string | null;
  sequenceLength?: number | null;
  /** Sidecar proxy mode: REAL_BEPIPRED3_ESM_SIDECAR | DEMO_COMPATIBLE */
  mode?: string | null;
  /** Data source: legacy_bepipred3_sidecar | demo_fallback */
  source?: string | null;
  /** validation_status: NOT_EXPERIMENTALLY_VALIDATED */
  validationStatus?: string | null;
  /** Human-readable note from backend */
  note?: string | null;
};
