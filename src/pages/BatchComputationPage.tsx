import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { batchComputationApi } from '@/lib/api/batchComputation';
import type { BatchComputation, BatchComputationCreatePayload } from '@/types/batchComputation';
import {
  Boxes,
  Plus,
  Loader2,
  AlertTriangle,
  RefreshCw,
  XCircle,
  Play,
  Clock,
  CheckCircle2,
  ShieldAlert,
  Info,
  FolderOpen,
  Eye,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  PENDING: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
  RUNNING: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Loader2 className="w-3 h-3 animate-spin" />, label: 'Running' },
  SUCCEEDED: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Succeeded' },
  FAILED: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
  BLOCKED: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <ShieldAlert className="w-3 h-3" />, label: 'Blocked' },
  CANCELLED: { bg: 'bg-slate-50', text: 'text-slate-600', icon: <XCircle className="w-3 h-3" />, label: 'Cancelled' },
};

export default function BatchComputationPage() {
  const navigate = useNavigate();
  const [batches, setBatches] = useState<BatchComputation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [form, setForm] = useState<BatchComputationCreatePayload>({
    project_id: '',
    name: '',
    job_type: 'COLABFOLD',
    candidate_ids: [],
    input_json: {},
  });

  useEffect(() => {
    loadBatches();
  }, []);

  const loadBatches = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const resp = await batchComputationApi.list();
      setBatches(resp.items);
    } catch (err: any) {
      setError(err?.message || 'Failed to load batches');
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.project_id.trim() || !form.name.trim()) return;
    try {
      setIsCreating(true);
      setError(null);
      setSuccess(null);
      await batchComputationApi.create(form);
      setForm({ project_id: '', name: '', job_type: 'COLABFOLD', candidate_ids: [], input_json: {} });
      await loadBatches();
      setSuccess('Batch computation created successfully.');
    } catch (err: any) {
      setError(err?.message || 'Failed to create batch');
    } finally {
      setIsCreating(false);
    }
  };

  const handleRetry = async (id: string) => {
    try {
      setError(null);
      await batchComputationApi.retryFailed(id);
      await loadBatches();
      setSuccess('Retry initiated for failed items.');
    } catch (err: any) {
      setError(err?.message || 'Retry failed');
    }
  };

  const handleCancel = async (id: string) => {
    if (!confirm('Cancel this batch computation?')) return;
    try {
      setError(null);
      await batchComputationApi.cancel(id);
      await loadBatches();
      setSuccess('Batch cancelled.');
    } catch (err: any) {
      setError(err?.message || 'Cancel failed');
    }
  };

  const handleDispatch = async (id: string) => {
    try {
      setError(null);
      const resp = await batchComputationApi.dispatch(id);
      await loadBatches();
      setSuccess(`Dispatched: ${resp.dispatched} running, ${resp.blocked} blocked, ${resp.failed} failed`);
    } catch (err: any) {
      setError(err?.message || 'Dispatch failed');
    }
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Boxes className="w-6 h-6 text-xh-primary" />
            Batch Computation
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Run ColabFold, FoldX, or MM-GBSA on multiple candidates. No fabricated metrics.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Scientific boundary notice */}
        <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700 flex items-start gap-2">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Scientific Boundary</p>
            <p className="text-xs mt-0.5 opacity-90">
              pLDDT, ipTM, RMSD, RMSF, ΔG, and MM-GBSA values are only shown after real command execution and file verification.
              No synthetic metrics will be displayed.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Create form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <Plus className="w-4 h-4" /> New Batch
              </h2>
              <form onSubmit={handleCreate} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Project ID *</label>
                  <input
                    type="text"
                    value={form.project_id}
                    onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                    placeholder="e.g., proj-001"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Batch Name *</label>
                  <input
                    type="text"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    placeholder="e.g., OprF ColabFold Batch"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Job Type *</label>
                  <select
                    value={form.job_type}
                    onChange={(e) => setForm({ ...form, job_type: e.target.value as any })}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  >
                    <option value="COLABFOLD">ColabFold</option>
                    <option value="FOLDX">FoldX</option>
                    <option value="MMGBSA">MM-GBSA</option>
                    <option value="FLEXPEPDOCK">FlexPepDock</option>
                    <option value="MIXED">Mixed</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Candidate IDs (comma separated)</label>
                  <input
                    type="text"
                    value={form.candidate_ids.join(', ')}
                    onChange={(e) => setForm({ ...form, candidate_ids: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })}
                    placeholder="cand-1, cand-2, cand-3"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="w-full flex items-center justify-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isCreating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  Create Batch
                </button>
              </form>
            </div>
          </div>

          {/* Batch list */}
          <div className="lg:col-span-2">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                <Boxes className="w-4 h-4" /> Batch Jobs
              </h2>
              <button
                onClick={loadBatches}
                disabled={isLoading}
                className="text-xs flex items-center gap-1 text-xh-primary hover:underline disabled:opacity-50"
              >
                <RefreshCw className={`w-3 h-3 ${isLoading ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>

            {isLoading ? (
              <div className="flex items-center justify-center py-12 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin" />
              </div>
            ) : batches.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
                <Boxes className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No batch computations yet. Create one to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {batches.map((batch) => {
                  const style = STATUS_STYLES[batch.status] || STATUS_STYLES.PENDING;
                  return (
                    <div
                      key={batch.id}
                      className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900">{batch.name}</h3>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              {batch.job_type}
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-1">
                            Project: {batch.project_id} · ID: {batch.id.slice(0, 8)}...
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                              {style.icon}
                              {style.label}
                            </span>
                            {batch.artifact_dir && (
                              <span className="text-[10px] text-slate-400 flex items-center gap-1">
                                <FolderOpen className="w-3 h-3" />
                                {batch.artifact_dir.split('/').slice(-2).join('/')}
                              </span>
                            )}
                          </div>
                        </div>
                        <div className="flex items-center gap-1 ml-3">
                          <button
                            onClick={() => navigate(`/batch-computation/${batch.id}`)}
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50"
                            title="View details"
                          >
                            <Eye className="w-3 h-3" />
                            View
                          </button>
                          <button
                            onClick={() => handleDispatch(batch.id)}
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50"
                            title="Dispatch pending items"
                          >
                            <Play className="w-3 h-3" />
                            Run
                          </button>
                          <button
                            onClick={() => handleRetry(batch.id)}
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:bg-slate-50"
                            title="Retry failed items"
                          >
                            <RefreshCw className="w-3 h-3" />
                            Retry
                          </button>
                          <button
                            onClick={() => handleCancel(batch.id)}
                            className="text-xs flex items-center gap-1 px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50"
                            title="Cancel batch"
                          >
                            <XCircle className="w-3 h-3" />
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
