/**
 * STAMP Assembly API Client — v0.7-P1c
 *
 * Calls POST /stamp/assemble-v0.7 on the backend.
 */

import type {
  StampAssembleRequest,
  StampAssembleResponse,
} from "@/types/stampAssembly";
import { ASSEMBLED_STAMP_LS_KEY } from "@/types/stampAssembly";
import { API_BASE_URL } from "./api/client";

const BASE_URL = API_BASE_URL;

const BACKEND_UNAVAILABLE_MSG =
  "STAMP backend is not available. Please start the backend service.";

export async function assembleStamp(
  payload: StampAssembleRequest,
): Promise<{ data: StampAssembleResponse | null; error?: string }> {
  try {
    const response = await fetch(`${BASE_URL}/stamp/assemble-v0.7`, {
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

    const body = (await response.json()) as StampAssembleResponse;
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

// ── Assembled STAMP localStorage ──

export function storeAssembledStamp(data: StampAssembleResponse): void {
  localStorage.setItem(ASSEMBLED_STAMP_LS_KEY, JSON.stringify(data));
}

export function getAssembledStamp(): StampAssembleResponse | null {
  try {
    const raw = localStorage.getItem(ASSEMBLED_STAMP_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as StampAssembleResponse;
  } catch {
    return null;
  }
}

export function clearAssembledStamp(): void {
  localStorage.removeItem(ASSEMBLED_STAMP_LS_KEY);
}

// ── Export helpers ──

export function exportStampAsJson(data: StampAssembleResponse): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `stamp_candidate_${data.candidate_id}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function exportStampAsCsv(candidates: StampAssembleResponse[]): void {
  const headers = [
    "Candidate ID",
    "Targeting Peptide",
    "Linker",
    "AMP",
    "Full Sequence",
    "Length",
    "Net Charge",
    "pI",
    "GRAVY",
    "Cys Count",
    "Mode",
    "Validation Status",
    "Created At",
  ];
  const rows = candidates.map((c) => [
    c.candidate_id,
    c.targeting_domain.sequence,
    c.linker.sequence,
    c.amp.sequence,
    c.display_full_sequence,
    c.length,
    c.net_charge,
    c.pI,
    c.GRAVY,
    c.cys_count,
    c.mode,
    c.validation_status,
    c.created_at || "",
  ]);
  const csv = [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "stamp_candidates.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
