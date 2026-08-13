import { useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { jobsApi, type JobResponse, type JobFailureDiagnosis } from '@/lib/api/jobs';
import { useAuth } from '@/contexts/AuthContext';
import {
  Briefcase,
  Loader2,
  AlertTriangle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  Activity,
  Ban,
  Play,
  RotateCcw,
  Search,
  ChevronDown,
  ChevronUp,
  FileText,
  Package,
  Wrench,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  pending: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
  running: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Activity className="w-3 h-3" />, label: 'Running' },
  succeeded: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Succeeded' },
  failed: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
  cancelled: { bg: 'bg-slate-50', text: 'text-slate-600', icon: <Ban className="w-3 h-3" />, label: 'Cancelled' },
};

const CATEGORY_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  tool_missing: { bg: 'bg-orange-50', text: 'text-orange-700', label: 'Tool Missing' },
  input_missing: { bg: 'bg-amber-50', text: 'text-amber-700', label: 'Input Missing' },
  invalid_parameter: { bg: 'bg-yellow-50', text: 'text-yellow-700', label: 'Invalid Parameter' },
  command_failed: { bg: 'bg-red-50', text: 'text-red-700', label: 'Command Failed' },
  artifact_missing: { bg: 'bg-rose-50', text: 'text-rose-700', label: 'Artifact Missing' },
  permission_denied: { bg: 'bg-purple-50', text: 'text-purple-700', label: 'Permission Denied' },
  storage_unwritable: { bg: 'bg-pink-50', text: 'text-pink-700', label: 'Storage Unwritable' },
  gpu_locked: { bg: 'bg-indigo-50', text: 'text-indigo-700', label: 'GPU Locked' },
  external_api_failed: { bg: 'bg-cyan-50', text: 'text-cyan-700', label: 'External API Failed' },
  unknown: { bg: 'bg-gray-50', text: 'text-gray-700', label: 'Unknown' },
};

export default function JobCenterPage() {
  const { canSubmit, canManage } = useAuth();
  const [projectId, setProjectId] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [jobs, setJobs] = useState<JobResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [actionId, setActionId] = useState<string | null>(null);
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [diagnoses, setDiagnoses] = useState<Record<string, JobFailureDiagnosis>>({});
  const [diagnosisLoading, setDiagnosisLoading] = useState<Record<string, boolean>>({});

  const handleSearch = async () => {
    if (!projectId.trim()) {
      setError('Please enter a Project ID');
      return;
    }
    try {
      setIsLoading(true);
      setError(null);
      const resp = await jobsApi.listJobsByProject(projectId, {
        status: statusFilter || undefined,
        limit: 100,
      });
      setJobs(resp.jobs);
    } catch (err: any) {
      setError(err?.message || 'Failed to load jobs');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = async (jobId: string) => {
    if (!confirm('Cancel this job?')) return;
    try {
      setActionId(jobId);
      await jobsApi.cancelJob(jobId);
      await handleSearch();
    } catch (err: any) {
      setError(err?.message || 'Cancel failed');
    } finally {
      setActionId(null);
    }
  };

  const handleRetry = async (jobId: string) => {
    if (!confirm('Retry this job?')) return;
    try {
      setActionId(jobId);
      await jobsApi.retryJob(jobId);
      await handleSearch();
    } catch (err: any) {
      setError(err?.message || 'Retry failed');
    } finally {
      setActionId(null);
    }
  };

  const toggleDiagnosis = async (jobId: string) => {
    if (expandedJobId === jobId) {
      setExpandedJobId(null);
      return;
    }
    setExpandedJobId(jobId);

    if (!diagnoses[jobId]) {
      try {
        setDiagnosisLoading((prev) => ({ ...prev, [jobId]: true }));
        const resp = await jobsApi.getDiagnosis(jobId);
        setDiagnoses((prev) => ({ ...prev, [jobId]: resp.data }));
      } catch (err: any) {
        setDiagnoses((prev) => ({
          ...prev,
          [jobId]: {
            job_id: jobId,
            job_type: '',
            status: '',
            error_category: 'unknown',
            cause: err?.message || 'Failed to load diagnosis',
            suggestions: ['Try refreshing the page or contact the platform admin.'],
            related_logs: [],
            related_artifacts: [],
            raw_error_message: null,
            raw_error_json: null,
          },
        }));
      } finally {
        setDiagnosisLoading((prev) => ({ ...prev, [jobId]: false }));
      }
    }
  };

  const showDiagnosisButton = (status: string) => {
    return status === 'failed' || status === 'cancelled' || status === 'blocked';
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Briefcase className="w-6 h-6 text-xh-primary" />
            Job Center
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            View and manage background jobs by project. Admin can cancel or retry failed jobs.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 mb-6">
          <div className="flex flex-wrap items-end gap-3">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs font-medium text-slate-700 mb-1">Project ID</label>
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  value={projectId}
                  onChange={(e) => setProjectId(e.target.value)}
                  placeholder="e.g., proj-001"
                  className="w-full text-sm pl-9 pr-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                />
              </div>
            </div>
            <div className="w-40">
              <label className="block text-xs font-medium text-slate-700 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
              >
                <option value="">All</option>
                <option value="pending">Pending</option>
                <option value="running">Running</option>
                <option value="succeeded">Succeeded</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <button
              onClick={handleSearch}
              disabled={isLoading}
              className="flex items-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
            >
              {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Load Jobs
            </button>
          </div>
        </div>

        {jobs.length === 0 && !isLoading && (
          <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
            <Briefcase className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <p className="text-sm text-slate-500">Enter a Project ID to load jobs.</p>
          </div>
        )}

        <div className="space-y-3">
          {jobs.map((job) => {
            const style = STATUS_STYLES[job.status] || STATUS_STYLES.pending;
            const isExpanded = expandedJobId === job.id;
            const diagnosis = diagnoses[job.id];
            const loadingDiagnosis = diagnosisLoading[job.id];
            const categoryStyle = diagnosis ? CATEGORY_STYLES[diagnosis.error_category] || CATEGORY_STYLES.unknown : null;

            return (
              <div
                key={job.id}
                className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <h3 className="text-sm font-bold text-slate-900 font-mono">{job.id.slice(0, 12)}...</h3>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                        {job.job_type}
                      </span>
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                        {style.icon}
                        {style.label}
                      </span>
                      {categoryStyle && (
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${categoryStyle.bg} ${categoryStyle.text}`}>
                          {categoryStyle.label}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Project: {job.project_id} · Progress: {job.progress ?? 0}%
                    </p>
                    {job.message && (
                      <p className="text-xs text-slate-600 mt-1">{job.message}</p>
                    )}
                    {job.error_message && (
                      <p className="text-xs text-red-600 mt-1">{job.error_message}</p>
                    )}
                    <p className="text-[10px] text-slate-400 mt-2">
                      Created: {new Date(job.created_at).toLocaleString()}
                      {job.finished_at && ` · Finished: ${new Date(job.finished_at).toLocaleString()}`}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 ml-3 shrink-0">
                    {showDiagnosisButton(job.status) && (
                      <button
                        onClick={() => toggleDiagnosis(job.id)}
                        disabled={loadingDiagnosis}
                        className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                        title="Show failure diagnosis"
                      >
                        {loadingDiagnosis ? <Loader2 className="w-3 h-3 animate-spin" /> : <Wrench className="w-3 h-3" />}
                        {isExpanded ? 'Hide' : 'Diagnose'}
                        {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                      </button>
                    )}
                    {(job.status === 'pending' || job.status === 'running') && canManage && (
                      <button
                        onClick={() => handleCancel(job.id)}
                        disabled={actionId === job.id}
                        className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
                      >
                        {actionId === job.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
                        Cancel
                      </button>
                    )}
                    {(job.status === 'failed' || job.status === 'cancelled') && canSubmit && (
                      <button
                        onClick={() => handleRetry(job.id)}
                        disabled={actionId === job.id}
                        className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50 disabled:opacity-50"
                      >
                        {actionId === job.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                        Retry
                      </button>
                    )}
                    {job.status === 'pending' && canSubmit && (
                      <button
                        onClick={() => { /* start job */ }}
                        disabled={actionId === job.id}
                        className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-emerald-200 text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                        title="Start job"
                      >
                        <Play className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Diagnosis Panel */}
                {isExpanded && diagnosis && (
                  <div className="mt-4 border-t border-slate-100 pt-4">
                    <div className="space-y-4">
                      {/* Cause */}
                      <div className="bg-slate-50 rounded-lg p-3">
                        <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-1.5 mb-1">
                          <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
                          Root Cause
                        </h4>
                        <p className="text-xs text-slate-600 leading-relaxed">{diagnosis.cause}</p>
                      </div>

                      {/* Suggestions */}
                      {diagnosis.suggestions.length > 0 && (
                        <div className="bg-emerald-50 rounded-lg p-3">
                          <h4 className="text-xs font-semibold text-emerald-800 flex items-center gap-1.5 mb-2">
                            <Wrench className="w-3.5 h-3.5" />
                            Suggested Fixes
                          </h4>
                          <ul className="space-y-1.5">
                            {diagnosis.suggestions.map((s, i) => (
                              <li key={i} className="text-xs text-emerald-700 flex items-start gap-1.5">
                                <span className="mt-0.5 w-1 h-1 rounded-full bg-emerald-400 shrink-0" />
                                {s}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Related Logs */}
                      {diagnosis.related_logs.length > 0 && (
                        <div className="bg-blue-50 rounded-lg p-3">
                          <h4 className="text-xs font-semibold text-blue-800 flex items-center gap-1.5 mb-2">
                            <FileText className="w-3.5 h-3.5" />
                            Related Logs
                          </h4>
                          <ul className="space-y-1">
                            {diagnosis.related_logs.map((log, i) => (
                              <li key={i} className="text-[11px] text-blue-700 font-mono break-all">{log}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Related Artifacts */}
                      {diagnosis.related_artifacts.length > 0 && (
                        <div className="bg-purple-50 rounded-lg p-3">
                          <h4 className="text-xs font-semibold text-purple-800 flex items-center gap-1.5 mb-2">
                            <Package className="w-3.5 h-3.5" />
                            Related Artifacts
                          </h4>
                          <ul className="space-y-1">
                            {diagnosis.related_artifacts.map((art, i) => (
                              <li key={i} className="text-[11px] text-purple-700 font-mono break-all">
                                {art.type ? `[${art.type}] ` : ''}{art.path}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Raw Error */}
                      {diagnosis.raw_error_message && (
                        <div className="bg-red-50 rounded-lg p-3">
                          <h4 className="text-xs font-semibold text-red-800 mb-1">Raw Error Message</h4>
                          <p className="text-[11px] text-red-700 font-mono break-all">{diagnosis.raw_error_message}</p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </PlatformLayout>
  );
}
