import { useCallback, useEffect, useRef, useState } from "react";
import {
  cancelP33LJob,
  checkP33LAuthorized,
  fetchP33LJob,
  fetchP33LStatus,
  p33lDownloadUrl,
  startP33LRealRun,
  type P33LJobResponse,
  type P33LStatusResponse,
} from "@/lib/api/p33l";

const POLL_INTERVAL_MS = 2000;

export interface P33LRunState {
  authorized: boolean | null;
  manifestSha: string | null;
  status: P33LStatusResponse | null;
  currentJob: P33LJobResponse | null;
  loading: boolean;
  running: boolean;
  error: string | null;
}

const MODEL_ORDER = ["pepmlm", "evobind2", "diffpepbuilder", "pepflow", "pephar", "ppflow"];

export function useP33L() {
  const [state, setState] = useState<P33LRunState>({
    authorized: null,
    manifestSha: null,
    status: null,
    currentJob: null,
    loading: true,
    running: false,
    error: null,
  });
  const pollRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const refreshStatus = useCallback(async () => {
    if (!state.manifestSha) return;
    try {
      const status = await fetchP33LStatus(state.manifestSha);
      setState((prev) => ({ ...prev, status, error: null }));
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to refresh P33L status";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [state.manifestSha]);

  const refreshJob = useCallback(async (jobId: string) => {
    if (!state.manifestSha) return;
    try {
      const job = await fetchP33LJob(jobId, state.manifestSha);
      setState((prev) => ({ ...prev, currentJob: job }));
      if (["succeeded", "failed", "timeout", "cancelled", "blocked"].includes(job.status)) {
        setState((prev) => ({ ...prev, running: false }));
        stopPolling();
      }
      await refreshStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to refresh job";
      setState((prev) => ({ ...prev, error: msg, running: false }));
      stopPolling();
    }
  }, [state.manifestSha, refreshStatus, stopPolling]);

  const startPolling = useCallback((jobId: string) => {
    stopPolling();
    pollRef.current = window.setInterval(() => {
      void refreshJob(jobId);
    }, POLL_INTERVAL_MS);
  }, [refreshJob, stopPolling]);

  useEffect(() => {
    let mounted = true;
    void (async () => {
      try {
        const auth = await checkP33LAuthorized();
        if (!mounted) return;
        setState((prev) => ({
          ...prev,
          authorized: auth.authorized,
          manifestSha: auth.manifest_sha,
          loading: false,
        }));
        if (auth.authorized && auth.manifest_sha) {
          const status = await fetchP33LStatus(auth.manifest_sha);
          if (!mounted) return;
          setState((prev) => ({ ...prev, status }));
        }
      } catch (err) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : "Failed to check P33L authorization";
        setState((prev) => ({ ...prev, loading: false, error: msg }));
      }
    })();
    return () => {
      mounted = false;
      stopPolling();
    };
  }, [stopPolling]);

  const runNextModel = useCallback(async (modelId: string, input: Record<string, unknown>) => {
    setState((prev) => ({ ...prev, running: true, error: null }));
    try {
      if (!state.manifestSha) {
        throw new Error("P33L manifest SHA not available");
      }
      const resp = await startP33LRealRun(modelId, input, state.manifestSha);
      const job = resp.data;
      setState((prev) => ({ ...prev, currentJob: job }));
      if (["running", "queued"].includes(job.status)) {
        startPolling(job.job_id);
      } else {
        setState((prev) => ({ ...prev, running: false }));
        await refreshStatus();
      }
      return job;
    } catch (err) {
      const msg = err instanceof Error ? err.message : "P33L run failed";
      setState((prev) => ({ ...prev, running: false, error: msg }));
      throw err;
    }
  }, [state.manifestSha, startPolling, refreshStatus]);

  const cancelCurrent = useCallback(async () => {
    if (!state.currentJob || !state.manifestSha) return;
    try {
      const job = await cancelP33LJob(state.currentJob.job_id, state.manifestSha);
      setState((prev) => ({ ...prev, currentJob: job, running: false }));
      stopPolling();
      await refreshStatus();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Cancel failed";
      setState((prev) => ({ ...prev, error: msg }));
    }
  }, [state.currentJob, state.manifestSha, refreshStatus, stopPolling]);

  const downloadUrl = useCallback((filePath: string) => {
    if (!state.currentJob || !state.manifestSha) return "#";
    return p33lDownloadUrl(state.currentJob.job_id, filePath, state.manifestSha);
  }, [state.currentJob, state.manifestSha]);

  const nextModelId = state.status?.next_model ?? MODEL_ORDER[0];

  return {
    ...state,
    nextModelId,
    refreshStatus,
    runNextModel,
    cancelCurrent,
    downloadUrl,
  };
}
