import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { batchComputationApi } from '@/lib/api/batchComputation';
import type {
  BatchComputation,
  BatchItem,
  ArtifactFile,
  BatchReport,
  RunnerLogResponse,
} from '@/types/batchComputation';
import {
  Boxes,
  Loader2,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
  FolderOpen,
  FileText,
  Download,
  FileJson,
  FileSpreadsheet,
  FileCode,
  Archive,
  ChevronDown,
  ChevronRight,
  Activity,
  FlaskConical,
  Zap,
  Ban,
  FileBarChart,
  TerminalSquare,
  ScrollText,
  AlertCircle,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  PENDING: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
  RUNNING: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Loader2 className="w-3 h-3 animate-spin" />, label: 'Running' },
  SUCCEEDED: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Succeeded' },
  FAILED: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
  BLOCKED: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <ShieldAlert className="w-3 h-3" />, label: 'Blocked' },
  CANCELLED: { bg: 'bg-slate-50', text: 'text-slate-600', icon: <XCircle className="w-3 h-3" />, label: 'Cancelled' },
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || STATUS_STYLES.PENDING;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text}`}>
      {style.icon}
      {style.label}
    </span>
  );
}

function FileStatusRow({ label, exists, path }: { label: string; exists: boolean; path: string | null }) {
  return (
    <div className="flex items-center justify-between py-1.5 text-sm">
      <span className="text-slate-600">{label}</span>
      <div className="flex items-center gap-2">
        {path && <span className="text-xs text-slate-400 font-mono truncate max-w-[200px]">{path}</span>}
        {exists ? (
          <span className="inline-flex items-center gap-1 text-xs text-emerald-600 font-medium">
            <CheckCircle2 className="w-3.5 h-3.5" /> Found
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-xs text-slate-400">
            <Ban className="w-3.5 h-3.5" /> Missing
          </span>
        )}
      </div>
    </div>
  );
}

export default function BatchComputationDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [batch, setBatch] = useState<BatchComputation | null>(null);
  const [items, setItems] = useState<BatchItem[]>([]);
  const [report, setReport] = useState<BatchReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedItem, setExpandedItem] = useState<string | null>(null);
  const [artifactsMap, setArtifactsMap] = useState<Record<string, ArtifactFile[]>>({});
  const [logsMap, setLogsMap] = useState<Record<string, RunnerLogResponse>>({});
  const [fullLogItem, setFullLogItem] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    if (!id) return;
    try {
      setIsLoading(true);
      setError(null);
      const [batchRes, itemsRes, reportRes] = await Promise.all([
        batchComputationApi.getById(id),
        batchComputationApi.getItems(id),
        batchComputationApi.getReport(id).catch(() => null),
      ]);
      setBatch(batchRes);
      setItems(itemsRes);
      setReport(reportRes);
    } catch (err: any) {
      setError(err?.message || 'Failed to load batch details');
    } finally {
      setIsLoading(false);
    }
  }, [id]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const toggleItem = async (itemId: string) => {
    if (expandedItem === itemId) {
      setExpandedItem(null);
      return;
    }
    setExpandedItem(itemId);
    if (!id) return;
    if (!artifactsMap[itemId]) {
      try {
        const artifacts = await batchComputationApi.getItemArtifacts(id, itemId);
        setArtifactsMap(prev => ({ ...prev, [itemId]: artifacts }));
      } catch {
        setArtifactsMap(prev => ({ ...prev, [itemId]: [] }));
      }
    }
    if (!logsMap[itemId]) {
      try {
        const logs = await batchComputationApi.getRunnerLogs(id, itemId);
        setLogsMap(prev => ({ ...prev, [itemId]: logs }));
      } catch {
        setLogsMap(prev => ({ ...prev, [itemId]: {
          batch_id: id,
          item_id: itemId,
          job_type: '',
          exists: false,
          command: null,
          returncode: null,
          started_at: null,
          finished_at: null,
          stdout_exists: false,
          stderr_exists: false,
          stdout_size: 0,
          stderr_size: 0,
          stdout: '',
          stderr: '',
          is_tail: false,
        } }));
      }
    }
  };

  const handleDownload = async (format: 'zip' | 'json' | 'csv' | 'md') => {
    if (!id) return;
    try {
      setDownloading(format);
      const resp = await batchComputationApi.download(id, format);
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `batch_${id}.${format === 'md' ? 'md' : format}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Download failed');
    } finally {
      setDownloading(null);
    }
  };

  const handleReportDownload = async (format: 'json' | 'markdown' | 'pdf') => {
    if (!id) return;
    try {
      setDownloading(format);
      const resp = await batchComputationApi.downloadComputationReport(id, format);
      if (!resp.ok) throw new Error('Report download failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'markdown' ? 'md' : format;
      a.download = `batch_${id}_report.${ext}`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Report download failed');
    } finally {
      setDownloading(null);
    }
  };

  const failedItems = items.filter(i => i.status === 'FAILED' || i.status === 'BLOCKED');

  const handleDownloadLogs = async (batchId: string, itemId: string) => {
    try {
      const resp = await batchComputationApi.downloadRunnerLogs(batchId, itemId);
      if (!resp.ok) throw new Error('Download failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `runner_logs_${batchId}_${itemId}.zip`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err?.message || 'Log download failed');
    }
  };

  const handleToggleFullLog = async (itemId: string) => {
    if (!id) return;
    if (fullLogItem === itemId) {
      setFullLogItem(null);
      return;
    }
    setFullLogItem(itemId);
    try {
      const logs = await batchComputationApi.getRunnerLogs(id, itemId, true);
      setLogsMap(prev => ({ ...prev, [itemId]: logs }));
    } catch {
      /* keep existing */
    }
  };

  if (isLoading) {
    return (
      <PlatformLayout>
        <div className="flex items-center justify-center h-96 text-slate-400">
          <Loader2 className="w-8 h-8 animate-spin" />
        </div>
      </PlatformLayout>
    );
  }

  if (!batch) {
    return (
      <PlatformLayout>
        <div className="max-w-5xl mx-auto px-6 py-8">
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error || 'Batch not found'}</span>
          </div>
        </div>
      </PlatformLayout>
    );
  }

  return (
    <PlatformLayout>
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/batch-computation')}
            className="text-xs flex items-center gap-1 text-slate-500 hover:text-xh-primary mb-3"
          >
            <ArrowLeft className="w-3 h-3" />
            Back to Batches
          </button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
                <Boxes className="w-6 h-6 text-xh-primary" />
                {batch.name}
              </h1>
              <p className="text-sm text-slate-500 mt-1">
                Project: {batch.project_id} · ID: {batch.id}
              </p>
            </div>
            <StatusBadge status={batch.status} />
          </div>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Summary Cards */}
        {report && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {[
              { label: 'Total', value: report.total_items, icon: <Boxes className="w-4 h-4" />, color: 'text-slate-700' },
              { label: 'Succeeded', value: report.succeeded_items, icon: <CheckCircle2 className="w-4 h-4 text-emerald-600" />, color: 'text-emerald-700' },
              { label: 'Failed', value: report.failed_items, icon: <XCircle className="w-4 h-4 text-red-600" />, color: 'text-red-700' },
              { label: 'Blocked', value: report.blocked_items, icon: <ShieldAlert className="w-4 h-4 text-rose-600" />, color: 'text-rose-700' },
              { label: 'Pending', value: report.pending_items, icon: <Clock className="w-4 h-4 text-amber-600" />, color: 'text-amber-700' },
            ].map(card => (
              <div key={card.label} className="bg-white border border-slate-200 rounded-xl p-4">
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                  {card.icon}
                  {card.label}
                </div>
                <div className={`text-xl font-bold ${card.color}`}>{card.value}</div>
              </div>
            ))}
          </div>
        )}

        {/* Download Section */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
            <Download className="w-4 h-4" /> Export & Download
          </h2>
          <div className="flex flex-wrap gap-2 mb-4">
            {[
              { key: 'json' as const, label: 'JSON', icon: <FileJson className="w-4 h-4" /> },
              { key: 'csv' as const, label: 'CSV', icon: <FileSpreadsheet className="w-4 h-4" /> },
              { key: 'md' as const, label: 'Markdown', icon: <FileCode className="w-4 h-4" /> },
              { key: 'zip' as const, label: 'ZIP (Artifacts)', icon: <Archive className="w-4 h-4" /> },
            ].map(fmt => (
              <button
                key={fmt.key}
                onClick={() => handleDownload(fmt.key)}
                disabled={downloading === fmt.key}
                className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
              >
                {downloading === fmt.key ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : fmt.icon}
                {fmt.label}
              </button>
            ))}
          </div>
          <div className="border-t border-slate-100 pt-4">
            <h3 className="text-xs font-semibold text-slate-600 flex items-center gap-1.5 mb-2">
              <FileBarChart className="w-3.5 h-3.5" /> Computation Report
            </h3>
            <div className="flex flex-wrap gap-2">
              {[
                { key: 'json' as const, label: 'JSON Report', icon: <FileJson className="w-4 h-4" /> },
                { key: 'markdown' as const, label: 'Markdown Report', icon: <FileCode className="w-4 h-4" /> },
                { key: 'pdf' as const, label: 'PDF Report', icon: <FileText className="w-4 h-4" /> },
              ].map(fmt => (
                <button
                  key={fmt.key}
                  onClick={() => handleReportDownload(fmt.key)}
                  disabled={downloading === fmt.key}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-md border border-slate-200 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                >
                  {downloading === fmt.key ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : fmt.icon}
                  {fmt.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Failure Visualization */}
        {failedItems.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4 text-red-500" /> Failure Analysis
            </h2>
            <div className="space-y-2">
              {failedItems.map(item => {
                const isBlocked = item.status === 'BLOCKED';
                const is422 = item.error_message?.includes('422') || item.error_message?.includes('validation');
                const isConfig = item.error_message?.includes('CONFIG_REQUIRED') || item.error_message?.includes('required');
                return (
                  <div key={item.id} className={`rounded-lg border p-3 ${isBlocked ? 'bg-rose-50 border-rose-200' : 'bg-red-50 border-red-200'}`}>
                    <div className="flex items-center gap-2 mb-1">
                      <StatusBadge status={item.status} />
                      <span className="text-xs font-medium text-slate-700">{item.candidate_id || 'Unknown'}</span>
                      <span className="text-[10px] text-slate-400 font-mono">{item.id.slice(0, 8)}</span>
                    </div>
                    <div className="text-xs text-slate-600 font-mono bg-white/60 rounded px-2 py-1.5 mt-1">
                      {item.error_message || 'No error message'}
                    </div>
                    {isBlocked && (
                      <div className="mt-1.5 flex items-center gap-1 text-[10px] text-rose-600">
                        <ShieldAlert className="w-3 h-3" />
                        Environment or dependency missing. Check installation.
                      </div>
                    )}
                    {is422 && (
                      <div className="mt-1.5 flex items-center gap-1 text-[10px] text-amber-600">
                        <AlertTriangle className="w-3 h-3" />
                        Validation error. Check input parameters.
                      </div>
                    )}
                    {isConfig && (
                      <div className="mt-1.5 flex items-center gap-1 text-[10px] text-blue-600">
                        <Activity className="w-3 h-3" />
                        Configuration required. Review input JSON.
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Items List */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
          <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
            <Boxes className="w-4 h-4" /> Batch Items
          </h2>
          {items.length === 0 ? (
            <div className="text-center py-8 text-slate-400 text-sm">No items in this batch.</div>
          ) : (
            <div className="space-y-2">
              {items.map(item => {
                const isExpanded = expandedItem === item.id;
                const artifacts = artifactsMap[item.id] || [];
                const logs = logsMap[item.id];
                return (
                  <div key={item.id} className="border border-slate-200 rounded-lg overflow-hidden">
                    <button
                      onClick={() => toggleItem(item.id)}
                      className="w-full flex items-center justify-between p-3 hover:bg-slate-50 text-left"
                    >
                      <div className="flex items-center gap-3">
                        {isExpanded ? <ChevronDown className="w-4 h-4 text-slate-400" /> : <ChevronRight className="w-4 h-4 text-slate-400" />}
                        <StatusBadge status={item.status} />
                        <span className="text-sm font-medium text-slate-800">{item.candidate_id || '—'}</span>
                        <span className="text-xs text-slate-400 font-mono">{item.id.slice(0, 8)}</span>
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">{item.job_type}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {item.artifact_dir && (
                          <span className="text-[10px] text-slate-400 flex items-center gap-1">
                            <FolderOpen className="w-3 h-3" />
                            artifacts
                          </span>
                        )}
                      </div>
                    </button>
                    {isExpanded && (
                      <div className="border-t border-slate-200 p-3 bg-slate-50/50">
                        {/* Artifacts */}
                        <div className="mb-3">
                          <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-1 mb-2">
                            <FolderOpen className="w-3.5 h-3.5" /> Output Files
                          </h4>
                          {artifacts.length === 0 ? (
                            <p className="text-xs text-slate-400">No artifacts found.</p>
                          ) : (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-1 max-h-48 overflow-y-auto">
                              {artifacts.map(f => (
                                <div key={f.path} className="flex items-center gap-2 text-xs py-1 px-2 rounded hover:bg-white">
                                  {f.is_dir ? (
                                    <FolderOpen className="w-3 h-3 text-amber-500 shrink-0" />
                                  ) : (
                                    <FileText className="w-3 h-3 text-blue-500 shrink-0" />
                                  )}
                                  <span className="truncate text-slate-600" title={f.path}>{f.path}</span>
                                  {!f.is_dir && <span className="text-[10px] text-slate-400 shrink-0">{(f.size / 1024).toFixed(1)} KB</span>}
                                </div>
                              ))}
                            </div>
                          )}
                        </div>

                        {/* Runner Logs */}
                        <div className="mb-3">
                          <div className="flex items-center justify-between mb-2">
                            <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                              <TerminalSquare className="w-3.5 h-3.5" /> Runner Logs
                            </h4>
                            {logs?.exists && (
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => handleToggleFullLog(item.id)}
                                  className="text-[10px] flex items-center gap-1 px-2 py-0.5 rounded border border-slate-200 hover:bg-slate-100"
                                >
                                  <ScrollText className="w-3 h-3" />
                                  {fullLogItem === item.id ? 'Show Tail' : 'View Full'}
                                </button>
                                <button
                                  onClick={() => handleDownloadLogs(batch.id, item.id)}
                                  className="text-[10px] flex items-center gap-1 px-2 py-0.5 rounded border border-slate-200 hover:bg-slate-100"
                                >
                                  <Download className="w-3 h-3" />
                                  Download
                                </button>
                              </div>
                            )}
                          </div>
                          {logs?.exists ? (
                            <div className="space-y-2">
                              {/* Metadata */}
                              <div className="text-[10px] text-slate-500 grid grid-cols-2 md:grid-cols-4 gap-2 bg-slate-100 p-2 rounded">
                                {logs.command && (
                                  <div className="col-span-2 md:col-span-4">
                                    <span className="font-semibold">Command:</span>{' '}
                                    <code className="font-mono text-slate-700 break-all">{logs.command}</code>
                                  </div>
                                )}
                                {logs.returncode !== null && (
                                  <div>
                                    <span className="font-semibold">Return Code:</span>{' '}
                                    <span className={logs.returncode === '0' ? 'text-emerald-600' : 'text-red-600'}>
                                      {logs.returncode}
                                    </span>
                                  </div>
                                )}
                                {logs.started_at && (
                                  <div>
                                    <span className="font-semibold">Started:</span>{' '}
                                    {new Date(logs.started_at).toLocaleString()}
                                  </div>
                                )}
                                {logs.finished_at && (
                                  <div>
                                    <span className="font-semibold">Finished:</span>{' '}
                                    {new Date(logs.finished_at).toLocaleString()}
                                  </div>
                                )}
                              </div>
                              {logs.is_tail && (
                                <div className="text-[10px] text-amber-600 flex items-center gap-1">
                                  <AlertCircle className="w-3 h-3" />
                                  Showing last 200 lines. Use "View Full" to see complete log.
                                </div>
                              )}
                              {/* stdout */}
                              {logs.stdout_exists && (
                                <div>
                                  <span className="text-[10px] font-semibold text-slate-500 uppercase">stdout</span>
                                  <pre className="mt-1 text-[11px] font-mono bg-slate-900 text-slate-200 p-2 rounded max-h-40 overflow-y-auto">
                                    {logs.stdout || '(empty)'}
                                  </pre>
                                </div>
                              )}
                              {/* stderr */}
                              {logs.stderr_exists && (
                                <div>
                                  <span className="text-[10px] font-semibold text-slate-500 uppercase">stderr</span>
                                  <pre className="mt-1 text-[11px] font-mono bg-slate-900 text-red-300 p-2 rounded max-h-40 overflow-y-auto">
                                    {logs.stderr || '(empty)'}
                                  </pre>
                                </div>
                              )}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-400">No runner logs available yet.</p>
                          )}
                        </div>

                        {/* Output JSON */}
                        {item.output_json && Object.keys(item.output_json).length > 0 && (
                          <div>
                            <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-1 mb-2">
                              <FileJson className="w-3.5 h-3.5" /> Output JSON
                            </h4>
                            <pre className="text-[11px] font-mono bg-white border border-slate-200 p-2 rounded max-h-32 overflow-y-auto">
                              {JSON.stringify(item.output_json, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* MD Pilot Results */}
        {report && report.md_results.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-blue-500" /> MD Pilot Results
            </h2>
            <div className="space-y-2">
              {report.md_results.map(r => (
                <div key={r.item_id} className="border border-slate-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={r.status} />
                    <span className="text-xs font-medium text-slate-700">{r.candidate_id || '—'}</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    <FileStatusRow label="RMSD file" exists={r.rmsd_file_exists} path={r.rmsd_file_path} />
                    <FileStatusRow label="RMSF file" exists={r.rmsf_file_exists} path={r.rmsf_file_path} />
                    <FileStatusRow label="Rg file" exists={r.rg_file_exists} path={r.rg_file_path} />
                  </div>
                  {r.output_json && Object.keys(r.output_json).length > 0 && (
                    <pre className="mt-2 text-[11px] font-mono bg-slate-50 p-2 rounded max-h-24 overflow-y-auto">
                      {JSON.stringify(r.output_json, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* FlexPepDock Detail */}
        {report && report.flexpepdock_results.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
              <Zap className="w-4 h-4 text-amber-500" /> FlexPepDock Detail
            </h2>
            <div className="space-y-2">
              {report.flexpepdock_results.map(r => (
                <div key={r.item_id} className="border border-slate-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={r.status} />
                    <span className="text-xs font-medium text-slate-700">{r.candidate_id || '—'}</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    <FileStatusRow label="score.sc" exists={r.score_sc_exists} path={r.score_sc_path} />
                  </div>
                  {r.output_json && Object.keys(r.output_json).length > 0 && (
                    <pre className="mt-2 text-[11px] font-mono bg-slate-50 p-2 rounded max-h-24 overflow-y-auto">
                      {JSON.stringify(r.output_json, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MM-GBSA Detail */}
        {report && report.mmgbsa_results.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl p-5 mb-6">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-3">
              <FlaskConical className="w-4 h-4 text-emerald-500" /> MM-GBSA Detail
            </h2>
            <div className="space-y-2">
              {report.mmgbsa_results.map(r => (
                <div key={r.item_id} className="border border-slate-200 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <StatusBadge status={r.status} />
                    <span className="text-xs font-medium text-slate-700">{r.candidate_id || '—'}</span>
                  </div>
                  <div className="divide-y divide-slate-100">
                    <FileStatusRow label="ΔG result file" exists={r.dg_file_exists} path={r.dg_file_path} />
                  </div>
                  {r.output_json && Object.keys(r.output_json).length > 0 && (
                    <pre className="mt-2 text-[11px] font-mono bg-slate-50 p-2 rounded max-h-24 overflow-y-auto">
                      {JSON.stringify(r.output_json, null, 2)}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Scientific Boundary Footer */}
        <div className="text-center text-xs text-slate-400 py-4">
          Metrics are only shown when real output files exist. No fabricated data.
        </div>
      </div>
    </PlatformLayout>
  );
}
