import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { projectResultsApi } from '@/lib/api/projectResults';
import type { ProjectSummaryResponse, ProjectStampResultsResponse } from '@/types/projectResults';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { AlertTriangle, Database, FileText, FileSpreadsheet, Download, FlaskConical } from 'lucide-react';

export default function ProjectResultsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ProjectSummaryResponse | null>(null);
  const [results, setResults] = useState<ProjectStampResultsResponse | null>(null);

  const [topK, _setTopK] = useState(10);
  const [includeMetrics, setIncludeMetrics] = useState(true);
  const [exporting, setExporting] = useState(false);

  const handleExport = async (format: 'json' | 'markdown' | 'csv') => {
    if (!projectId) return;
    setExporting(true);
    try {
      const { content, format: fmt } = await projectResultsApi.exportCandidateReport(projectId, format, topK);
      const blob = new Blob([content], {
        type: fmt === 'csv' ? 'text/csv' : fmt === 'markdown' ? 'text/markdown' : 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      const ext = fmt === 'markdown' ? 'md' : fmt;
      const date = new Date().toISOString().slice(0, 10).replace(/-/g, '');
      a.download = `STAMP_candidate_report_${projectId}_${date}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      alert(err.message || 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  useEffect(() => {
    if (!projectId) {
      setError('No Project ID provided in URL.');
      setLoading(false);
      return;
    }

    async function loadData() {
      try {
        setLoading(true);
        const [summaryData, resultsData] = await Promise.all([
          projectResultsApi.getProjectSummary(projectId!),
          projectResultsApi.getProjectStampResults(projectId!, { top_k: topK, include_metrics: includeMetrics })
        ]);
        setSummary(summaryData);
        setResults(resultsData);
      } catch (err: any) {
        setError(err.message || 'Failed to fetch project results from backend.');
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, [projectId, topK, includeMetrics]);

  if (loading) return <PlatformLayout><div className="p-8 text-center">Loading project data...</div></PlatformLayout>;
  if (error) return (
    <PlatformLayout>
      <div className="p-8">
        <div className="bg-red-50 text-red-600 p-4 rounded-md border border-red-200">
          <h3 className="font-bold">Error Loading Results</h3>
          <p>{error}</p>
          <p className="mt-2 text-sm">Fallback: You can still use the local workflow via <a href="/design" className="underline">Design Page</a>.</p>
        </div>
      </div>
    </PlatformLayout>
  );

  return (
    <PlatformLayout>
      <div className="p-6 space-y-6">
        {/* Header & Scientific Boundary Warning */}
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{summary?.project_name || 'Project Results'}</h1>
            <div className="text-gray-500 mt-1 text-sm space-y-0.5">
              <p>Target Proteins: {summary?.target_protein_count ?? 0} | Epitope Scans: {summary?.epitope_scan_count ?? 0}</p>
              <p>STAMP Candidates: {summary?.stamp_candidate_count ?? 0} | Ranked: {summary?.ranked_candidate_count ?? 0}</p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="bg-amber-100 border border-amber-300 text-amber-800 px-4 py-2 rounded flex items-center gap-2 font-mono text-sm font-bold shadow-sm">
              <AlertTriangle className="w-5 h-5 text-amber-600" />
              NOT_EXPERIMENTALLY_VALIDATED
            </div>
            {projectId && (
              <button
                onClick={() => navigate(`/projects/${projectId}/experimental-validation`)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded text-[10px] font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
              >
                <FlaskConical className="w-3 h-3" /> Experimental Validation Dashboard
              </button>
            )}
            <div className="flex gap-1.5">
              <button
                onClick={() => handleExport('markdown')}
                disabled={exporting}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export Markdown report"
              >
                <FileText className="w-3 h-3" /> MD
              </button>
              <button
                onClick={() => handleExport('csv')}
                disabled={exporting}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export CSV"
              >
                <FileSpreadsheet className="w-3 h-3" /> CSV
              </button>
              <button
                onClick={() => handleExport('json')}
                disabled={exporting}
                className="flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                title="Export JSON"
              >
                <Download className="w-3 h-3" /> JSON
              </button>
            </div>
          </div>
        </div>

        {/* Results Table Section */}
        <div className="bg-white rounded-lg shadow border border-gray-200 overflow-hidden">
          <div className="p-4 border-b border-gray-200 flex justify-between items-center bg-slate-50">
            <h2 className="font-semibold flex items-center gap-2"><Database className="w-4 h-4"/> Top {results?.returned_count ?? 0} Candidates (of {results?.total_count ?? 0})</h2>
            <div className="flex gap-2 text-sm">
               <label className="flex items-center gap-1 cursor-pointer">
                 <input type="checkbox" checked={includeMetrics} onChange={e => setIncludeMetrics(e.target.checked)} />
                 Include Metrics
               </label>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-100 text-slate-600">
                <tr>
                  <th className="p-3 border-b">ID</th>
                  <th className="p-3 border-b">Full Sequence</th>
                  <th className="p-3 border-b">Targeting Peptide</th>
                  <th className="p-3 border-b">Linker</th>
                  <th className="p-3 border-b">Composite Score</th>
                  <th className="p-3 border-b">Validation Status</th>
                  {includeMetrics && (
                    <>
                      <th className="p-3 border-b">Source</th>
                      <th className="p-3 border-b">Model</th>
                      <th className="p-3 border-b">PPL</th>
                      <th className="p-3 border-b">Charge</th>
                      <th className="p-3 border-b">pI</th>
                      <th className="p-3 border-b">pLDDT</th>
                      <th className="p-3 border-b">pTM</th>
                      <th className="p-3 border-b">pDockQ</th>
                      <th className="p-3 border-b">Interface Contacts</th>
                      <th className="p-3 border-b">FoldX Energy</th>
                    </>
                  )}
                  {/* DO NOT ADD MIC, MBC, HEMOLYSIS, TOXICITY, pDockQ, or ipTM here */}
                  <th className="p-3 border-b text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {results?.candidates.map(candidate => (
                  <tr key={candidate.id} className="border-b hover:bg-slate-50">
                    <td className="p-3 font-mono text-xs">{candidate.id.slice(0, 8)}...</td>
                    <td className="p-3 font-mono text-blue-600 font-medium max-w-[200px] truncate" title={candidate.full_sequence}>{candidate.full_sequence}</td>
                    <td className="p-3 font-mono text-xs max-w-[120px] truncate" title={candidate.targeting_peptide_seq}>{candidate.targeting_peptide_seq}</td>
                    <td className="p-3 font-mono text-xs max-w-[80px] truncate" title={candidate.linker_seq}>{candidate.linker_seq}</td>
                    <td className="p-3 font-bold">{candidate.composite_score?.toFixed(3) ?? 'N/A'}</td>
                    <td className="p-3">
                      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase bg-amber-50 text-amber-700 border border-amber-100">
                        {candidate.validation_status}
                      </span>
                    </td>
                    {includeMetrics && (
                      <>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {String(candidate.metrics?.source ?? 'N/A')}
                        </td>
                        <td className="p-3 text-xs">
                          {candidate.metrics?.real_model_loaded ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-50 text-blue-700 border border-blue-100">REAL</span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-slate-50 text-slate-600 border border-slate-100">STUB</span>
                          )}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {candidate.metrics?.ppl != null ? Number(candidate.metrics.ppl as number).toFixed(2) : 'N/A'}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {candidate.metrics?.charge != null ? String(candidate.metrics.charge) : 'N/A'}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {candidate.metrics?.pi != null ? String(candidate.metrics.pi) : 'N/A'}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {(() => {
                            const sp = candidate.metrics?.structure_prediction as Record<string, unknown> | undefined;
                            if (sp?.mean_plddt != null) return Number(sp.mean_plddt).toFixed(2);
                            return 'N/A';
                          })()}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {(() => {
                            const sp = candidate.metrics?.structure_prediction as Record<string, unknown> | undefined;
                            if (sp?.ptm != null) return Number(sp.ptm).toFixed(2);
                            return 'N/A';
                          })()}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {(() => {
                            const iq = candidate.metrics?.interface_quality as Record<string, unknown> | undefined;
                            if (iq?.pdockq != null) return Number(iq.pdockq).toFixed(3);
                            return 'N/A';
                          })()}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {(() => {
                            const iq = candidate.metrics?.interface_quality as Record<string, unknown> | undefined;
                            const inp = iq?.input_features as Record<string, unknown> | undefined;
                            if (inp?.interface_contact_count != null) return String(inp.interface_contact_count);
                            return 'N/A';
                          })()}
                        </td>
                        <td className="p-3 text-xs font-mono text-slate-600">
                          {(() => {
                            const eq = candidate.metrics?.energy_quality as Record<string, unknown> | undefined;
                            if (eq?.interaction_energy_kcal_mol != null) return `${Number(eq.interaction_energy_kcal_mol).toFixed(1)}`;
                            return 'N/A';
                          })()}
                        </td>
                      </>
                    )}
                    <td className="p-3 text-right">
                      <button
                        onClick={() => navigate(`/stamp-candidates/${candidate.id}`)}
                        className="text-indigo-600 hover:text-indigo-800 text-xs font-semibold"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
