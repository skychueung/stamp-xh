/**
 * Final Ranking API Client — v0.10-P5-lite
 *
 * Priority data sources:
 *   1. Backend GET /api/v1/projects/{project_id}/stamp-results (P5-lite P5)
 *   2. localStorage assembled STAMP candidates (legacy v0.7)
 *   3. Mock fallback (explicitly labeled)
 *
 * All real data is marked NOT_EXPERIMENTALLY_VALIDATED.
 */

import type {
  FinalRankingCandidateInput,
  FinalRankingCandidateOutput,
  FinalRankingComputeResponse,
} from "@/types/finalRanking";
import {
  STAMP_HISTORY_LS_KEY,
  SELECTED_FOR_VALIDATION_LS_KEY,
} from "@/types/finalRanking";
import { ASSEMBLED_STAMP_LS_KEY } from "@/types/stampAssembly";
import type { StampAssembleResponse } from "@/types/stampAssembly";
import { SELECTED_TARGETING_PEPTIDE_LS_KEY } from "@/types/targetingPeptide";
import type { TargetingPeptideCandidate } from "@/types/targetingPeptide";
import { SELECTED_EPITOPE_LS_KEY } from "@/types/realEpitope";
import type { SelectedEpitope } from "@/types/realEpitope";
import { projectResultsApi } from "@/lib/api/projectResults";
import type { StampCandidateDetail } from "@/types/projectResults";
import { API_BASE_URL } from "./api/client";

const BASE_URL = API_BASE_URL;

const BACKEND_UNAVAILABLE_MSG =
  "STAMP backend is not available. Please start the backend service.";

// ── localStorage aggregators ──

function getStampHistory(): StampAssembleResponse[] {
  try {
    const raw = localStorage.getItem(STAMP_HISTORY_LS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (Array.isArray(parsed)) return parsed as StampAssembleResponse[];
    return [];
  } catch {
    return [];
  }
}

function getAssembledStamp(): StampAssembleResponse | null {
  try {
    const raw = localStorage.getItem(ASSEMBLED_STAMP_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StampAssembleResponse;
  } catch {
    return null;
  }
}

function getSelectedTargetingPeptide(): TargetingPeptideCandidate | null {
  try {
    const raw = localStorage.getItem(SELECTED_TARGETING_PEPTIDE_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as TargetingPeptideCandidate;
  } catch {
    return null;
  }
}

function getSelectedEpitope(): SelectedEpitope | null {
  try {
    const raw = localStorage.getItem(SELECTED_EPITOPE_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SelectedEpitope;
  } catch {
    return null;
  }
}

// ── Data provenance helpers ──

export type DataProvenance =
  | "stamp_history"
  | "assembled_candidate"
  | "targeting_peptide_plus_epitope"
  | "mock";

export interface EnrichedCandidate extends FinalRankingCandidateOutput {
  provenance: DataProvenance;
}

function stampResponseToInput(
  r: StampAssembleResponse,
  _provenance: DataProvenance,
): FinalRankingCandidateInput {
  return {
    candidate_id: r.candidate_id,
    full_sequence: r.display_full_sequence,
    targeting_peptide: r.targeting_domain.sequence,
    linker: r.linker.sequence,
    amp: r.amp.sequence,
    length: r.length,
    net_charge: r.net_charge,
    pI: r.pI,
    GRAVY: r.GRAVY,
    cys_count: r.cys_count,
    mode: r.mode,
    created_at: r.created_at,
  };
}

function buildFromTargetingPeptideAndEpitope(
  tp: TargetingPeptideCandidate,
  _epitope: SelectedEpitope,
): FinalRankingCandidateInput {
  const linker = "EAAAK";
  const amp = "FSRFLRRVRRYRPKISFNLEPFFKF";
  const fullSeq = tp.sequence + linker + amp;
  // We don't have biophysical for the full sequence here; approximate with TP values
  return {
    candidate_id: tp.candidate_id,
    full_sequence: fullSeq,
    targeting_peptide: tp.sequence,
    linker,
    amp,
    length: tp.length + linker.length + amp.length,
    net_charge: tp.net_charge,
    pI: tp.pI,
    GRAVY: tp.GRAVY,
    cys_count: tp.cys_count,
    mode: "FALLBACK_TP_EPI_TOPE_V0_7",
    created_at: undefined,
  };
}

/**
 * Convert backend StampCandidateDetail to FinalRankingCandidateInput.
 */
function stampDetailToInput(d: StampCandidateDetail): FinalRankingCandidateInput {
  return {
    candidate_id: d.id,
    full_sequence: d.full_sequence,
    targeting_peptide: d.targeting_peptide_seq,
    linker: d.linker_seq,
    amp: "-", // AMP not stored in stamp_candidates table; mark as unavailable
    length: d.full_sequence.length,
    net_charge: 0, // Not available in StampCandidateDetail; will be computed
    pI: 0,
    GRAVY: 0,
    cys_count: 0,
    mode: "BACKEND_STAMP_CANDIDATE",
    created_at: d.created_at,
  };
}

/**
 * Gather real candidates according to priority:
 *  1. Backend GET /api/v1/projects/{project_id}/stamp-results (P5-lite)
 *  2. localStorage stamp.stampHistory.v0.7
 *  3. localStorage stamp.assembledCandidate.v0.7
 *  4. localStorage targeting peptide + epitope
 */
export async function gatherRealCandidates(projectId?: string): Promise<{
  inputs: FinalRankingCandidateInput[];
  provenance: DataProvenance;
}> {
  // Priority 1: Backend project stamp results
  if (projectId) {
    try {
      const response = await projectResultsApi.getProjectStampResults(projectId, {
        top_k: 50,
        include_metrics: true,
      });
      if (response.candidates && response.candidates.length > 0) {
        return {
          inputs: response.candidates.map(stampDetailToInput),
          provenance: "stamp_history", // Reuse provenance type for tracking
        };
      }
    } catch (err) {
      console.warn("Backend stamp-results unavailable, falling back to localStorage:", err);
    }
  }

  // Priority 2: localStorage history
  const history = getStampHistory();
  if (history.length > 0) {
    return {
      inputs: history.map((h) => stampResponseToInput(h, "stamp_history")),
      provenance: "stamp_history",
    };
  }

  // Priority 3: single assembled candidate
  const assembled = getAssembledStamp();
  if (assembled) {
    return {
      inputs: [stampResponseToInput(assembled, "assembled_candidate")],
      provenance: "assembled_candidate",
    };
  }

  // Priority 4: targeting peptide + epitope
  const tp = getSelectedTargetingPeptide();
  const epitope = getSelectedEpitope();
  if (tp && epitope) {
    return {
      inputs: [buildFromTargetingPeptideAndEpitope(tp, epitope)],
      provenance: "targeting_peptide_plus_epitope",
    };
  }

  return { inputs: [], provenance: "mock" };
}

// ── Backend compute ──

export async function computeFinalRanking(
  candidates: FinalRankingCandidateInput[],
): Promise<{ data: FinalRankingComputeResponse | null; error?: string }> {
  try {
    const response = await fetch(`${BASE_URL}/final-ranking/compute`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidates }),
    });

    if (!response.ok) {
      let msg = `HTTP ${response.status}`;
      try {
        const body = (await response.json()) as { message?: string; detail?: string };
        if (body.detail) {
          msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        } else if (body.message) {
          msg = body.message;
        }
      } catch {
        /* ignore parse error */
      }
      return { data: null, error: msg };
    }

    const body = (await response.json()) as FinalRankingComputeResponse;
    if (body.code !== 200) {
      return { data: null, error: body.message || `API error code ${body.code}` };
    }
    return { data: body };
  } catch (err) {
    const isNetwork =
      err instanceof TypeError &&
      (err.message.includes("fetch") ||
        err.message.includes("Failed to fetch") ||
        err.message.includes("NetworkError"));
    return {
      data: null,
      error: isNetwork ? BACKEND_UNAVAILABLE_MSG : err instanceof Error ? err.message : "Unknown error",
    };
  }
}

// ── Validation localStorage ──

export function storeSelectedForValidation(candidate: FinalRankingCandidateOutput): void {
  localStorage.setItem(SELECTED_FOR_VALIDATION_LS_KEY, JSON.stringify(candidate));
}

export function getSelectedForValidation(): FinalRankingCandidateOutput | null {
  try {
    const raw = localStorage.getItem(SELECTED_FOR_VALIDATION_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as FinalRankingCandidateOutput;
  } catch {
    return null;
  }
}

// ── Export helpers ──

export function exportFinalRankingAsCsv(candidates: EnrichedCandidate[]): void {
  const headers = [
    "Rank",
    "Candidate ID",
    "Full Sequence",
    "Targeting Peptide",
    "Linker",
    "AMP",
    "Length",
    "Net Charge",
    "pI",
    "GRAVY",
    "Cys Count",
    "Composite Score",
    "Mode",
    "Validation Status",
    "Data Provenance",
  ];
  const rows = candidates.map((c, i) => [
    i + 1,
    c.candidate_id,
    c.full_sequence,
    c.targeting_peptide,
    c.linker,
    c.amp,
    c.length,
    c.net_charge,
    c.pI,
    c.GRAVY,
    c.cys_count,
    c.composite_score,
    c.mode,
    c.validation_status,
    c.provenance,
  ]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `final_ranking_v0.7_${Date.now()}.csv`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportFinalRankingAsJson(candidates: EnrichedCandidate[]): void {
  const blob = new Blob([JSON.stringify(candidates, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `final_ranking_v0.7_${Date.now()}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
