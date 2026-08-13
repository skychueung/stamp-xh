import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { jobsApi, type JobResponse } from '@/lib/api/jobs';
import { Loader2, CheckCircle, XCircle, AlertTriangle, Clock, Database, Play, Ban, RotateCcw } from 'lucide-react';

interface JobStatusPanelProps {
  jobId: string;
  refreshInterval?: number;
}

const statusConfig: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  pending: { label: 'Pending', color: 'text-slate-500 bg-slate-50 border-slate-200', icon: <Clock className="w-4 h-4" /> },
  running: { label: 'Running', color: 'text-blue-600 bg-blue-50 border-blue-200', icon: <Loader2 className="w-4 h-4 animate-spin" /> },
  succeeded: { label: 'Succeeded', color: 'text-green-600 bg-green-50 border-green-200', icon: <CheckCircle className="w-4 h-4" /> },
  failed: { label: 'Failed', color: 'text-red-600 bg-red-50 border-red-200', icon: <XCircle className="w-4 h-4" /> },
  cancelled: { label: 'Cancelled', color: 'text-amber-600 bg-amber-50 border-amber-200', icon: <AlertTriangle className="w-4 h-4" /> },
};

export default function JobStatusPanel({ jobId, refreshInterval = 3000 }: JobStatusPanelProps) {
  const navigate = useNavigate();
  const [job, setJob] = useState<JobResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);
  const [persisting, setPersisting] = useState(false);
  const [persistError, setPersistError] = useState<string | null>(null);
  const [persistResult, setPersistResult] = useState<{
    generation_run_id: string;
    candidate_count: number;
    real_model_loaded: boolean;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await jobsApi.getJob(jobId);
        if (!cancelled) {
          setJob(data);
          setError(null);
        }
      } catch (err: any) {
        if (!cancelled) setError(err.message || 'Failed to fetch job');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();

    const interval = setInterval(() => {
      if (job?.status === 'running' || job?.status === 'pending') {
        load();
      }
    }, refreshInterval);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId, refreshInterval, job?.status]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Loader2 className="w-4 h-4 animate-spin" />
        Loading job status...
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
        {error || 'Job not found'}
      </div>
    );
  }

  const config = statusConfig[job.status] || statusConfig.pending;
  const progress = job.progress ?? 0;

  return (
    <div className="space-y-3">
      <div className={`flex items-center gap-2 px-3 py-2 rounded-md border text-sm font-medium ${config.color}`}>
        {config.icon}
        <span className="uppercase tracking-wider">{config.label}</span>
        <span className="ml-auto font-mono text-xs">{job.job_type}</span>
      </div>

      {(job.status === 'running' || job.status === 'pending') && (
        <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
          <div
            className="bg-blue-500 h-full rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}

      {job.message && (
        <p className="text-xs text-slate-600">{job.message}</p>
      )}

      {job.error_message && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-1.5">
          <strong>Error:</strong> {job.error_message}
        </div>
      )}

      {job.status === 'pending' && (
        <button
          onClick={async () => {
            setStarting(true);
            setStartError(null);
            try {
              await jobsApi.startJob(job.id);
              // Trigger an immediate refresh so the panel switches to running
              const refreshed = await jobsApi.getJob(job.id);
              setJob(refreshed);
            } catch (err: any) {
              setStartError(err.message || 'Failed to start job');
            } finally {
              setStarting(false);
            }
          }}
          disabled={starting}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-md text-xs font-bold uppercase tracking-wider bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {starting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          {starting ? 'Starting...' : 'Start Async Job'}
        </button>
      )}

      {startError && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-1.5">
          <strong>Start Error:</strong> {startError}
        </div>
      )}

      {(job.status === 'running' || job.status === 'pending') && (
        <button
          onClick={async () => {
            setCancelling(true);
            setCancelError(null);
            try {
              await jobsApi.cancelJob(job.id);
              const refreshed = await jobsApi.getJob(job.id);
              setJob(refreshed);
            } catch (err: any) {
              setCancelError(err.message || 'Failed to cancel job');
            } finally {
              setCancelling(false);
            }
          }}
          disabled={cancelling}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-md text-xs font-bold uppercase tracking-wider bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {cancelling ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Ban className="w-3.5 h-3.5" />}
          {cancelling ? 'Cancelling...' : 'Cancel Job'}
        </button>
      )}

      {cancelError && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-1.5">
          <strong>Cancel Error:</strong> {cancelError}
        </div>
      )}

      {(job.status === 'failed' || job.status === 'cancelled') && (
        <button
          onClick={async () => {
            setRetrying(true);
            setRetryError(null);
            try {
              const result = await jobsApi.retryJob(job.id);
              // Switch to new job
              const refreshed = await jobsApi.getJob(result.new_job_id);
              setJob(refreshed);
            } catch (err: any) {
              setRetryError(err.message || 'Failed to retry job');
            } finally {
              setRetrying(false);
            }
          }}
          disabled={retrying}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-md text-xs font-bold uppercase tracking-wider bg-slate-700 text-white hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {retrying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RotateCcw className="w-3.5 h-3.5" />}
          {retrying ? 'Retrying...' : 'Retry Job'}
        </button>
      )}

      {retryError && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-1.5">
          <strong>Retry Error:</strong> {retryError}
        </div>
      )}

      {job.status === 'succeeded' && job.job_type === 'bepipred3_scan' && (
        <button
          onClick={async () => {
            setPersisting(true);
            setPersistError(null);
            try {
              const result = await jobsApi.persistBepiPred3Results(job.id);
              if (result.scan_id) {
                navigate(`/epitope-screening?scan_id=${result.scan_id}`);
              } else {
                setPersistError('Persist succeeded but no scan_id returned');
              }
            } catch (err: any) {
              setPersistError(err.message || 'Failed to persist BepiPred3 results');
            } finally {
              setPersisting(false);
            }
          }}
          disabled={persisting}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-md text-xs font-bold uppercase tracking-wider bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {persisting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Database className="w-3.5 h-3.5" />}
          {persisting ? 'Persisting...' : 'Persist BepiPred3 Results'}
        </button>
      )}

      {job.status === 'succeeded' && job.job_type === 'pepmlm_generation' && (
        <button
          onClick={async () => {
            setPersisting(true);
            setPersistError(null);
            setPersistResult(null);
            try {
              const result = await jobsApi.persistPepMLMResults(job.id);
              if (result.generation_run_id) {
                setPersistResult({
                  generation_run_id: result.generation_run_id,
                  candidate_count: result.candidate_count,
                  real_model_loaded: result.real_model_loaded ?? false,
                });
              } else {
                setPersistError('Persist succeeded but no generation_run_id returned');
              }
            } catch (err: any) {
              setPersistError(err.message || 'Failed to persist PepMLM results');
            } finally {
              setPersisting(false);
            }
          }}
          disabled={persisting}
          className="flex items-center justify-center gap-2 w-full px-3 py-2 rounded-md text-xs font-bold uppercase tracking-wider bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {persisting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Database className="w-3.5 h-3.5" />}
          {persisting ? 'Persisting...' : 'Persist PepMLM Results'}
        </button>
      )}

      {persistError && (
        <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded-md px-2 py-1.5">
          <strong>Persist Error:</strong> {persistError}
        </div>
      )}

      {persistResult && (
        <div className="text-xs bg-emerald-50 border border-emerald-200 rounded-md px-2 py-1.5 space-y-1">
          <div className="flex items-center gap-1 text-emerald-700 font-semibold">
            <CheckCircle className="w-3 h-3" />
            Persist Succeeded
          </div>
          <div className="text-emerald-600 font-mono">
            Run: {persistResult.generation_run_id.slice(0, 12)}... | Candidates: {persistResult.candidate_count}
          </div>
          <button
            onClick={() => navigate(`/projects/${job.project_id}/results`)}
            className="text-[10px] text-emerald-700 underline hover:text-emerald-900"
          >
            View in Project Results →
          </button>
        </div>
      )}

      {/* PepMLM mode indicator */}
      {job.job_type === 'pepmlm_generation' && (
        <div className="space-y-1">
          {job.output_json?.mode === 'PEPMLM_HTTP_SIDECAR_REAL' || job.output_json?.real_model_loaded ? (
            <div className="flex items-center gap-1 text-[10px] text-blue-600 font-mono uppercase tracking-tight">
              <AlertTriangle className="w-3 h-3" />
              PepMLM REAL_MODEL — computational generation
            </div>
          ) : (
            <div className="flex items-center gap-1 text-[10px] text-amber-500 font-mono uppercase tracking-tight">
              <AlertTriangle className="w-3 h-3" />
              PepMLM STUB_ONLY — NOT_REAL_MODEL
            </div>
          )}
          {/* Preview candidate count if available */}
          {typeof job.output_json?.candidate_count === 'number' && (
            <div className="text-[10px] text-slate-500 font-mono">
              Generated: {job.output_json.candidate_count} candidates
            </div>
          )}
        </div>
      )}

      <div className="flex items-center gap-1 text-[10px] text-slate-400 font-mono uppercase tracking-tight">
        <AlertTriangle className="w-3 h-3" />
        NOT_EXPERIMENTALLY_VALIDATED
      </div>
    </div>
  );
}
