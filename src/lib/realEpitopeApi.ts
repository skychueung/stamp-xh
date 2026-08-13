/**
 * Real Epitope Scan API Client — v0.7-P1a
 *
 * Calls POST /epitope/scan on the backend and stores the result
 * in localStorage under stamp.realEpitopeScan.v0.7.
 * Also provides selected epitope persistence and CSV export.
 */

import type { EpitopeScanRequest, EpitopeScanResponse } from "@/types/realEpitope";
import {
  EPITOPE_SCAN_LS_KEY,
  SELECTED_EPITOPE_LS_KEY,
  type SelectedEpitope,
  type EpitopeCandidate,
} from "@/types/realEpitope";
import { API_BASE_URL } from "./api/client";

const BASE_URL = API_BASE_URL;

const BACKEND_UNAVAILABLE_MSG =
  "STAMP backend is not available. Please start the backend service.";

export async function runEpitopeScan(
  payload: EpitopeScanRequest,
): Promise<{ data: EpitopeScanResponse | null; error?: string }> {
  try {
    const response = await fetch(`${BASE_URL}/epitope/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
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

    const body = (await response.json()) as EpitopeScanResponse;
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

// ── Epitope scan localStorage ──

export function getStoredEpitopeScan(): EpitopeScanResponse | null {
  try {
    const raw = localStorage.getItem(EPITOPE_SCAN_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as EpitopeScanResponse;
  } catch {
    return null;
  }
}

export function storeEpitopeScan(data: EpitopeScanResponse): void {
  localStorage.setItem(EPITOPE_SCAN_LS_KEY, JSON.stringify(data));
}

export function clearEpitopeScan(): void {
  localStorage.removeItem(EPITOPE_SCAN_LS_KEY);
}

// ── Selected epitope localStorage (for flow to /peptide-generation) ──

export function storeSelectedEpitope(data: SelectedEpitope): void {
  localStorage.setItem(SELECTED_EPITOPE_LS_KEY, JSON.stringify(data));
}

export function getSelectedEpitope(): SelectedEpitope | null {
  try {
    const raw = localStorage.getItem(SELECTED_EPITOPE_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as SelectedEpitope;
  } catch {
    return null;
  }
}

export function clearSelectedEpitope(): void {
  localStorage.removeItem(SELECTED_EPITOPE_LS_KEY);
}

// ── CSV export ──

/**
 * Generate a CSV string from epitope candidates and trigger browser download.
 */
export function exportCandidatesCSV(
  candidates: EpitopeCandidate[],
  inputSummary: { target_name: string; sequence_length: number; window_size: number; total_windows: number },
  mode: string,
  validationStatus: string,
): void {
  const headers = [
    "Rank", "Candidate ID", "Start", "End", "Sequence", "Length",
    "Net Charge", "pI", "GRAVY", "Cys Count", "Disulfide Risk",
    "Hydrophobicity Class", "Filter Status", "Ranking Score",
    "Risk Notes", "Recommendation Reason",
  ];

  const rows = candidates.map((c, i) => [
    i + 1,
    c.candidate_id,
    c.start,
    c.end,
    c.sequence,
    c.length,
    c.net_charge,
    c.pI,
    c.GRAVY,
    c.cys_count,
    c.disulfide_risk,
    c.hydrophobicity_class,
    c.filter_status,
    c.ranking_score,
    c.risk_notes ?? "",
    c.recommendation_reason ?? "",
  ]);

  const metaRows = [
    ["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["# Scan Metadata", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Mode", mode, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Validation Status", validationStatus, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Target", inputSummary.target_name, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Sequence Length", inputSummary.sequence_length, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Window Size", inputSummary.window_size, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
    ["Total Windows", inputSummary.total_windows, "", "", "", "", "", "", "", "", "", "", "", "", "", ""],
  ];

  const escapeCsv = (v: unknown): string => {
    const s = String(v ?? "");
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };

  const csvContent = [
    headers.join(","),
    ...rows.map((r) => r.map(escapeCsv).join(",")),
    ...metaRows.map((r) => r.map(escapeCsv).join(",")),
  ].join("\n");

  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `epitope_scan_${inputSummary.target_name.replace(/\s+/g, "_")}_${Date.now()}.csv`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
