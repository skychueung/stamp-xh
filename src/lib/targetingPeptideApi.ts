/**
 * Targeting Peptide Generation API Client — v0.7-P1b
 *
 * Calls POST /targeting-peptide/generate on the backend.
 */

import type {
  TargetingPeptideGenerateRequest,
  TargetingPeptideGenerateResponse,
  TargetingPeptideCandidate,
} from "@/types/targetingPeptide";
import { SELECTED_TARGETING_PEPTIDE_LS_KEY } from "@/types/targetingPeptide";
import { API_BASE_URL } from "./api/client";

const BASE_URL = API_BASE_URL;

const BACKEND_UNAVAILABLE_MSG =
  "STAMP backend is not available. Please start the backend service.";

export async function generateTargetingPeptides(
  payload: TargetingPeptideGenerateRequest,
): Promise<{ data: TargetingPeptideGenerateResponse | null; error?: string }> {
  try {
    const response = await fetch(`${BASE_URL}/targeting-peptide/generate`, {
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

    const body = (await response.json()) as TargetingPeptideGenerateResponse;
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

// ── Selected targeting peptide localStorage ──

export function storeSelectedTargetingPeptide(data: TargetingPeptideCandidate): void {
  localStorage.setItem(SELECTED_TARGETING_PEPTIDE_LS_KEY, JSON.stringify(data));
}

export function getSelectedTargetingPeptide(): TargetingPeptideCandidate | null {
  try {
    const raw = localStorage.getItem(SELECTED_TARGETING_PEPTIDE_LS_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as TargetingPeptideCandidate;
  } catch {
    return null;
  }
}

export function clearSelectedTargetingPeptide(): void {
  localStorage.removeItem(SELECTED_TARGETING_PEPTIDE_LS_KEY);
}
