import { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { experimentalValidationApi } from '@/lib/api/experimentalValidation';
import type { ProjectExperimentalValidationSummary, CsvImportResult } from '@/types/experimentalValidation';
import {
  FlaskConical,
  Upload,
  Download,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Info,
  BarChart3,
  Users,
  Activity,
  ShieldAlert,
  FileText,
} from 'lucide-react';

const VALIDATION_STATUS_ORDER = [
  'NOT_EXPERIMENTALLY_VALIDATED',
  'EXPERIMENT_PLANNED',
  'PARTIALLY_VALIDATED',
  'EXPERIMENTALLY_VALIDATED',
  'VALIDATION_FAILED',
] as const;

const STATUS_COLORS: Record<string, { bg: string; text: string; border: string; icon: string }> = {
  NOT_EXPERIMENTALLY_VALIDATED: { bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200', icon: 'text-gray-400' },
  EXPERIMENT_PLANNED: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200', icon: 'text-sky-500' },
  PARTIALLY_VALIDATED: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', icon: 'text-amber-500' },
  EXPERIMENTALLY_VALIDATED: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: 'text-emerald-500' },
  VALIDATION_FAILED: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', icon: 'text-red-500' },
};

export default function ExperimentalValidationDashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [summary, setSummary] = useState<ProjectExperimentalValidationSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [importResult, setImportResult] = useState<CsvImportResult | null>(null);
  const [importing, setImporting] = useState(false);

  const loadSummary = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await experimentalValidationApi.getProjectExperimentalValidationSummary(projectId);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || 'Failed to load project experimental validation summary');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setImporting(true);
    setImportResult(null);
    try {
      const result = await experimentalValidationApi.importMeasurementsCsv(projectId, file);
      setImportResult(result);
      await loadSummary();
    } catch (err: any) {
      setError(err.message || 'CSV import failed');
    } finally {
      setImporting(false);
      e.target.value = '';
    }
  };

  const [exporting, setExporting] = useState<string | null>(null);

  const handleExportReport = async (format: 'json' | 'markdown' | 'csv') => {
    if (!projectId) return;
    setExporting(format);
    try {
      const result = await experimentalValidationApi.exportWetlabValidationReport(projectId, format);
      const blob = new Blob([typeof result === 'string' ? result : JSON.stringify(result, null, 2)], {
        type: format === 'json' ? 'application/json' : format === 'csv' ? 'text/csv' : 'text/markdown',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = format === 'json' ? 'json' : format === 'csv' ? 'csv' : 'md';
      const dateStr = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      a.download = `STAMP_wetlab_validation_report_${projectId}_${dateStr}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      setError(err.message || `Failed to export ${format} report`);
    } finally {
      setExporting(null);
    }
  };

  const downloadTemplate = () => {
    const headers = 'candidate_id,experiment_type,organism,strain,protocol_name,experiment_date,metric_name,value,unit,replicate_id,quality_flag,condition_json,notes';
    const example = 'cand-001,MIC,Staphylococcus aureus,MSSA,CLSI M07-A10,2026-05-01,MIC_ug_ml,2.5,ug/ml,rep-A,PASS,"{\"temperature\":37,\"ph\":7.4}",Initial screening';
    const blob = new Blob([`${headers}\n${example}\n`], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'experimental_measurement_template.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (loading) {
    return (
      <PlatformLayout>
        <div className="p-8 text-center text-sm text-slate-500">Loading dashboard...</div>
      </PlatformLayout>
    );
  }

  if (error && !summary) {
    return (
      <PlatformLayout>
        <div className="p-8">
          <div className="bg-red-50 text-red-600 p-4 rounded-md border border-red-200">
            <h3 className="font-bold">Error</h3>
            <p>{error}</p>
          </div>
        </div>
      </PlatformLayout>
    );
  }

  const s = summary;
  const totalCandidates = s?.total_candidates ?? 0;
  const coveragePercent = s?.coverage?.experimental_coverage_percent ?? 0;

  return (
    <PlatformLayout>
      <div className="p-6 space-y-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <FlaskConical className="w-6 h-6 text-xh-primary" />
              Experimental Validation Dashboard
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Project: {projectId}
            </p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => navigate(`/projects/${projectId}/candidate-prioritization`)}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
            >
              Candidate Prioritization
            </button>
            <button
              onClick={() => navigate(`/projects/${projectId}/results`)}
              className="px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              Back to Results
            </button>
            <div className="flex items-center gap-1">
              <button
                onClick={() => handleExportReport('json')}
                disabled={!!exporting}
                className="px-2 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export JSON"
              >
                <FileText className="w-3 h-3 inline mr-1" />
                {exporting === 'json' ? '...' : 'JSON'}
              </button>
              <button
                onClick={() => handleExportReport('markdown')}
                disabled={!!exporting}
                className="px-2 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export Markdown"
              >
                {exporting === 'markdown' ? '...' : 'MD'}
              </button>
              <button
                onClick={() => handleExportReport('csv')}
                disabled={!!exporting}
                className="px-2 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export CSV"
              >
                {exporting === 'csv' ? '...' : 'CSV'}
              </button>
            </div>
          </div>
        </div>

        {/* Scientific Integrity Banner */}
        <div className="rounded-md bg-amber-50 border border-amber-200 p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-amber-800">Scientific Integrity Notice</h4>
            <p className="text-xs text-amber-700">
              Experimental measurements shown here must be manually entered or imported from real wet-lab records. Computational predictions (BepiPred3, PepMLM, ColabFold, pDockQ, FoldX) are <strong>not</strong> experimental validation.
            </p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <SummaryCard
            icon={<Users className="w-4 h-4" />}
            label="Total Candidates"
            value={String(totalCandidates)}
            color="blue"
          />
          <SummaryCard
            icon={<Activity className="w-4 h-4" />}
            label="With Measurements"
            value={String(s?.coverage?.candidates_with_any_measurement ?? 0)}
            color="emerald"
          />
          <SummaryCard
            icon={<BarChart3 className="w-4 h-4" />}
            label="Coverage"
            value={`${coveragePercent}%`}
            color="sky"
          />
          <SummaryCard
            icon={<ShieldAlert className="w-4 h-4" />}
            label="Fully Validated"
            value={String(s?.candidates_fully_validated ?? 0)}
            color="amber"
          />
        </div>

        {/* Validation Status Distribution */}
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-4">Validation Status Distribution</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {VALIDATION_STATUS_ORDER.map((status) => {
              const count = s?.validation_status_counts?.[status] ?? 0;
              const colors = STATUS_COLORS[status] || STATUS_COLORS.NOT_EXPERIMENTALLY_VALIDATED;
              return (
                <div key={status} className={`rounded-md ${colors.bg} border ${colors.border} p-3`}>
                  <div className="text-2xl font-bold ${colors.text}">{count}</div>
                  <div className={`text-[10px] font-medium uppercase tracking-wider mt-1 ${colors.text}`}>
                    {status.replace(/_/g, ' ')}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Measurement Counts & Coverage */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-3">Measurement Counts</h2>
            {Object.keys(s?.measurement_counts ?? {}).length === 0 ? (
              <p className="text-xs text-slate-400">No measurements recorded yet.</p>
            ) : (
              <div className="space-y-2">
                {Object.entries(s?.measurement_counts ?? {}).map(([metric, count]) => (
                  <div key={metric} className="flex justify-between text-xs">
                    <span className="text-slate-600">{metric}</span>
                    <span className="font-mono font-semibold text-slate-900">{count}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg border border-slate-200 p-5">
            <h2 className="text-sm font-semibold text-slate-900 mb-3">Coverage Breakdown</h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between">
                <span className="text-slate-600">Any measurement</span>
                <span className="font-mono">{s?.coverage?.candidates_with_any_measurement ?? 0} / {totalCandidates}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">MIC/MBC data</span>
                <span className="font-mono">{s?.coverage?.candidates_with_mic ?? 0} / {totalCandidates}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-600">Safety data</span>
                <span className="font-mono">{s?.coverage?.candidates_with_safety ?? 0} / {totalCandidates}</span>
              </div>
              <div className="mt-3 h-2 bg-slate-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-xh-primary rounded-full transition-all"
                  style={{ width: `${Math.min(100, coveragePercent)}%` }}
                />
              </div>
              <p className="text-[10px] text-slate-400 text-right">{coveragePercent}% coverage</p>
            </div>
          </div>
        </div>

        {/* Top Priority Candidates */}
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-3">Top Priority Candidates</h2>
          {(s?.top_priority_candidates?.length ?? 0) === 0 ? (
            <p className="text-xs text-slate-400">No validated candidates with priority scores yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    <th className="p-2 border-b">Candidate ID</th>
                    <th className="p-2 border-b">Sequence</th>
                    <th className="p-2 border-b">Validation Status</th>
                    <th className="p-2 border-b">Priority Score</th>
                    <th className="p-2 border-b">Priority Status</th>
                  </tr>
                </thead>
                <tbody>
                  {s?.top_priority_candidates?.map((c) => (
                    <tr key={c.candidate_id} className="border-b hover:bg-slate-50">
                      <td className="p-2 font-mono text-slate-700">{c.candidate_id.slice(0, 12)}...</td>
                      <td className="p-2 font-mono text-slate-600 max-w-[200px] truncate">{c.sequence}</td>
                      <td className="p-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${
                          STATUS_COLORS[c.validation_status]?.bg ?? 'bg-gray-50'
                        } ${STATUS_COLORS[c.validation_status]?.text ?? 'text-gray-600'} ${
                          STATUS_COLORS[c.validation_status]?.border ?? 'border-gray-200'
                        }`}>
                          {c.validation_status}
                        </span>
                      </td>
                      <td className="p-2 font-mono font-semibold text-emerald-700">
                        {c.experimental_priority_score?.toFixed(3) ?? 'N/A'}
                      </td>
                      <td className="p-2 text-slate-600">{c.priority_status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* CSV Import Panel */}
        <div className="bg-white rounded-lg border border-slate-200 p-5">
          <h2 className="text-sm font-semibold text-slate-900 mb-3 flex items-center gap-2">
            <Upload className="w-4 h-4" /> Batch Import Measurements (CSV)
          </h2>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90 cursor-pointer">
              <Upload className="w-3 h-3" />
              {importing ? 'Importing...' : 'Upload CSV'}
              <input
                type="file"
                accept=".csv"
                className="hidden"
                onChange={handleFileUpload}
                disabled={importing}
              />
            </label>
            <button
              onClick={downloadTemplate}
              className="flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              <Download className="w-3 h-3" /> Download Template
            </button>
          </div>

          {importResult && (
            <div className="mt-3 space-y-2">
              <div className={`rounded-md p-2 text-xs border ${
                importResult.failed_count === 0 ? 'bg-emerald-50 border-emerald-200' : 'bg-amber-50 border-amber-200'
              }`}>
                <div className="flex items-center gap-1.5">
                  {importResult.failed_count === 0 ? (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
                  ) : (
                    <Info className="w-3.5 h-3.5 text-amber-600" />
                  )}
                  <span className={importResult.failed_count === 0 ? 'text-emerald-700' : 'text-amber-700'}>
                    Imported {importResult.success_count} / {importResult.total_rows} rows
                    ({importResult.created_run_count} runs, {importResult.created_measurement_count} measurements)
                  </span>
                </div>
              </div>

              {importResult.errors.length > 0 && (
                <div className="rounded-md bg-red-50 border border-red-200 p-2 space-y-1">
                  <p className="text-xs font-semibold text-red-700 flex items-center gap-1">
                    <XCircle className="w-3 h-3" /> Row-level Errors ({importResult.errors.length})
                  </p>
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {importResult.errors.map((err, idx) => (
                      <div key={idx} className="text-[10px] text-red-700 font-mono">
                        Row {err.row}: {err.reason}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </PlatformLayout>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  color: 'blue' | 'emerald' | 'sky' | 'amber';
}) {
  const colorMap = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-700', border: 'border-blue-200', icon: 'text-blue-500' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: 'text-emerald-500' },
    sky: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200', icon: 'text-sky-500' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', icon: 'text-amber-500' },
  };
  const c = colorMap[color];

  return (
    <div className={`rounded-lg ${c.bg} border ${c.border} p-4`}>
      <div className={`${c.icon} mb-1`}>{icon}</div>
      <div className={`text-2xl font-bold ${c.text}`}>{value}</div>
      <div className={`text-[10px] font-medium uppercase tracking-wider mt-0.5 ${c.text}`}>{label}</div>
    </div>
  );
}
