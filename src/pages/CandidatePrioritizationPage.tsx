import { useEffect, useState, useMemo, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { experimentalValidationApi } from '@/lib/api/experimentalValidation';
import type { ProjectCandidatePrioritization, CandidatePrioritizationItem, PriorityDecisionPayload } from '@/types/experimentalValidation';
import {
  LayoutList,
  Filter,
  CheckCircle2,
  AlertTriangle,
  Info,
  Clock,
  ShieldAlert,
  Save,
  FileText,
} from 'lucide-react';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

const PRIORITY_STATUS_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  READY_FOR_REVIEW: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
  NEEDS_MORE_DATA: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  SAFETY_CONCERN: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
  VALIDATION_FAILED: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  SHORTLISTED: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200' },
  REJECTED: { bg: 'bg-gray-50', text: 'text-gray-600', border: 'border-gray-200' },
};

const DECISION_OPTIONS = [
  { value: 'SHORTLIST', label: 'Shortlist', color: 'bg-purple-600' },
  { value: 'HOLD', label: 'Hold', color: 'bg-amber-500' },
  { value: 'REJECT', label: 'Reject', color: 'bg-red-500' },
  { value: 'NEEDS_REPEAT_EXPERIMENT', label: 'Needs Repeat', color: 'bg-sky-500' },
];

export default function CandidatePrioritizationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [data, setData] = useState<ProjectCandidatePrioritization | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [filterStatus, setFilterStatus] = useState<string>('ALL');
  const [filterDecision, setFilterDecision] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<CandidatePrioritizationItem | null>(null);

  const [decisionForm, setDecisionForm] = useState({
    decision: 'SHORTLIST' as PriorityDecisionPayload['decision'],
    decision_reason: '',
    reviewer: '',
    notes: '',
  });
  const [savingDecision, setSavingDecision] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
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

  const loadData = useCallback(async () => {
    if (!projectId) return;
    setLoading(true);
    setError(null);
    try {
      const result = await experimentalValidationApi.getProjectCandidatePrioritization(projectId);
      setData(result);
    } catch (err: any) {
      setError(err.message || 'Failed to load prioritization data');
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const filteredCandidates = useMemo(() => {
    if (!data) return [];
    return data.candidates.filter((c) => {
      if (filterStatus !== 'ALL' && c.priority_status !== filterStatus) return false;
      if (filterDecision !== 'ALL') {
        const hasDecision = c.decision?.decision === filterDecision;
        if (!hasDecision) return false;
      }
      if (searchQuery) {
        const q = searchQuery.toLowerCase();
        return (
          c.candidate_id.toLowerCase().includes(q) ||
          c.sequence.toLowerCase().includes(q)
        );
      }
      return true;
    });
  }, [data, filterStatus, filterDecision, searchQuery]);

  const openDrawer = (candidate: CandidatePrioritizationItem) => {
    setSelectedCandidate(candidate);
    setDecisionForm({
      decision: (candidate.decision?.decision as PriorityDecisionPayload['decision']) || 'SHORTLIST',
      decision_reason: candidate.decision?.decision_reason || '',
      reviewer: candidate.decision?.reviewer || '',
      notes: candidate.decision?.notes || '',
    });
    setSaveError(null);
    setDrawerOpen(true);
  };

  const handleSaveDecision = async () => {
    if (!selectedCandidate) return;
    if (!decisionForm.decision_reason.trim()) {
      setSaveError('Decision reason is required');
      return;
    }
    setSavingDecision(true);
    setSaveError(null);
    try {
      await experimentalValidationApi.savePriorityDecision(selectedCandidate.candidate_id, {
        decision: decisionForm.decision,
        decision_reason: decisionForm.decision_reason.trim(),
        reviewer: decisionForm.reviewer.trim() || undefined,
        notes: decisionForm.notes.trim() || undefined,
      });
      setDrawerOpen(false);
      await loadData();
    } catch (err: any) {
      setSaveError(err.message || 'Failed to save decision');
    } finally {
      setSavingDecision(false);
    }
  };

  if (loading) {
    return (
      <PlatformLayout>
        <div className="p-8 text-center text-sm text-slate-500">Loading prioritization data...</div>
      </PlatformLayout>
    );
  }

  if (error && !data) {
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

  const summary = data?.summary;

  return (
    <PlatformLayout>
      <div className="p-6 space-y-6 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
              <LayoutList className="w-6 h-6 text-xh-primary" />
              Candidate Prioritization
            </h1>
            <p className="text-sm text-slate-500 mt-1">Project: {projectId}</p>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <button
              onClick={() => navigate(`/projects/${projectId}/experimental-validation`)}
              className="px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              Back to Dashboard
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
        <div className="rounded-md bg-blue-50 border border-blue-200 p-3 flex items-start gap-2">
          <Info className="w-4 h-4 text-blue-600 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-blue-800">Decision-Support View</h4>
            <p className="text-xs text-blue-700">
              Candidate prioritization combines computational metrics and user-entered wet-lab measurements. It is a <strong>decision-support view</strong>, not an experimental validation claim. Computational predictions (pLDDT, pDockQ, FoldX) are not wet-lab results.
            </p>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          <SummaryCard icon={<LayoutList className="w-4 h-4" />} label="Total" value={String(summary?.candidate_count ?? 0)} color="slate" />
          <SummaryCard icon={<CheckCircle2 className="w-4 h-4" />} label="Ready" value={String(summary?.ready_for_review ?? 0)} color="emerald" />
          <SummaryCard icon={<Clock className="w-4 h-4" />} label="Needs Data" value={String(summary?.needs_more_data ?? 0)} color="sky" />
          <SummaryCard icon={<ShieldAlert className="w-4 h-4" />} label="Safety" value={String(summary?.safety_concern ?? 0)} color="red" />
          <SummaryCard icon={<AlertTriangle className="w-4 h-4" />} label="Failed" value={String(summary?.validation_failed ?? 0)} color="amber" />
          <SummaryCard icon={<CheckCircle2 className="w-4 h-4" />} label="Shortlisted" value={String(summary?.shortlisted ?? 0)} color="purple" />
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg border border-slate-200 p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Filter className="w-3.5 h-3.5" />
              <span className="font-medium">Filters:</span>
            </div>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
            >
              <option value="ALL">All Statuses</option>
              <option value="READY_FOR_REVIEW">Ready for Review</option>
              <option value="NEEDS_MORE_DATA">Needs More Data</option>
              <option value="SAFETY_CONCERN">Safety Concern</option>
              <option value="VALIDATION_FAILED">Validation Failed</option>
            </select>
            <select
              value={filterDecision}
              onChange={(e) => setFilterDecision(e.target.value)}
              className="rounded-md border border-slate-200 bg-white px-2 py-1 text-xs"
            >
              <option value="ALL">All Decisions</option>
              <option value="SHORTLIST">Shortlisted</option>
              <option value="HOLD">Hold</option>
              <option value="REJECT">Rejected</option>
              <option value="NEEDS_REPEAT_EXPERIMENT">Needs Repeat</option>
              <option value="NONE">No Decision</option>
            </select>
            <Input
              placeholder="Search candidate ID or sequence..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="text-xs h-8 w-56"
            />
          </div>
        </div>

        {/* Main Table */}
        <div className="bg-white rounded-lg border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="p-2.5 border-b">Candidate</th>
                  <th className="p-2.5 border-b">Priority Status</th>
                  <th className="p-2.5 border-b">Validation</th>
                  <th className="p-2.5 border-b text-right">Comp. Score</th>
                  <th className="p-2.5 border-b text-right">Exp. Priority</th>
                  <th className="p-2.5 border-b text-right">MIC</th>
                  <th className="p-2.5 border-b text-right">Hemolysis</th>
                  <th className="p-2.5 border-b text-right">pLDDT</th>
                  <th className="p-2.5 border-b text-right">pDockQ</th>
                  <th className="p-2.5 border-b text-right">FoldX</th>
                  <th className="p-2.5 border-b">Decision</th>
                  <th className="p-2.5 border-b text-right">Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredCandidates.map((c) => {
                  const colors = PRIORITY_STATUS_COLORS[c.priority_status] || PRIORITY_STATUS_COLORS.NEEDS_MORE_DATA;
                  const exp = c.experimental_summary || {};
                  const comp = c.computational_summary || {};
                  return (
                    <tr key={c.candidate_id} className="border-b hover:bg-slate-50">
                      <td className="p-2.5">
                        <div className="font-mono text-slate-700 text-[10px]">{c.candidate_id.slice(0, 12)}...</div>
                        <div className="font-mono text-slate-500 text-[10px] max-w-[120px] truncate">{c.sequence}</div>
                      </td>
                      <td className="p-2.5">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${colors.bg} ${colors.text} ${colors.border}`}>
                          {c.priority_status}
                        </span>
                      </td>
                      <td className="p-2.5">
                        <span className="text-[10px] text-slate-500">{c.validation_status}</span>
                      </td>
                      <td className="p-2.5 text-right font-mono">{c.composite_score?.toFixed(3) ?? 'N/A'}</td>
                      <td className="p-2.5 text-right font-mono font-semibold text-emerald-700">
                        {c.experimental_priority_score?.toFixed(3) ?? 'N/A'}
                      </td>
                      <td className="p-2.5 text-right font-mono">{exp.MIC_ug_ml != null ? String(exp.MIC_ug_ml) : '—'}</td>
                      <td className="p-2.5 text-right font-mono">{exp.hemolysis_percent != null ? `${exp.hemolysis_percent}%` : '—'}</td>
                      <td className="p-2.5 text-right font-mono">{comp.mean_plddt != null ? comp.mean_plddt.toFixed(1) : '—'}</td>
                      <td className="p-2.5 text-right font-mono">{comp.pdockq != null ? comp.pdockq.toFixed(3) : '—'}</td>
                      <td className="p-2.5 text-right font-mono">{comp.interaction_energy_kcal_mol != null ? comp.interaction_energy_kcal_mol.toFixed(1) : '—'}</td>
                      <td className="p-2.5">
                        {c.decision ? (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold text-white ${
                            DECISION_OPTIONS.find(d => d.value === c.decision?.decision)?.color || 'bg-slate-400'
                          }`}>
                            {c.decision.decision}
                          </span>
                        ) : (
                          <span className="text-[10px] text-slate-400">—</span>
                        )}
                      </td>
                      <td className="p-2.5 text-right">
                        <button
                          onClick={() => openDrawer(c)}
                          className="text-[10px] text-xh-primary hover:underline font-medium"
                        >
                          Review
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {filteredCandidates.length === 0 && (
            <div className="p-6 text-center text-xs text-slate-400">No candidates match the current filters.</div>
          )}
        </div>
      </div>

      {/* Detail Drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent className="w-[min(520px,90vw)] overflow-y-auto">
          {selectedCandidate && (
            <>
              <SheetHeader className="pb-4">
                <SheetTitle className="flex items-center gap-2 text-lg">
                  <LayoutList className="h-5 w-5 text-slate-600" />
                  Review Candidate
                </SheetTitle>
                <SheetDescription className="text-xs text-xh-muted">
                  {selectedCandidate.candidate_id}
                </SheetDescription>
              </SheetHeader>

              <div className="space-y-5">
                {/* Sequence */}
                <div className="rounded-xl bg-slate-50 border border-slate-200 p-4">
                  <span className="text-xs text-xh-muted block mb-1">Full Sequence</span>
                  <div className="rounded-lg bg-white px-3 py-2 border border-slate-100">
                    <span className="font-mono text-sm font-bold text-slate-900 break-all">
                      {selectedCandidate.sequence}
                    </span>
                  </div>
                </div>

                {/* Computational Metrics */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900">Computational Metrics</h4>
                  <div className="rounded-md bg-slate-50 border border-slate-200 p-3 space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-slate-500">Composite Score</span>
                      <span className="font-mono font-semibold">{selectedCandidate.composite_score?.toFixed(3) ?? 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">Source</span>
                      <span className="font-mono">{selectedCandidate.computational_summary.pepmlm_source ?? 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">mean pLDDT</span>
                      <span className="font-mono">{selectedCandidate.computational_summary.mean_plddt != null ? selectedCandidate.computational_summary.mean_plddt.toFixed(2) : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">pDockQ</span>
                      <span className="font-mono">{selectedCandidate.computational_summary.pdockq != null ? selectedCandidate.computational_summary.pdockq.toFixed(3) : 'N/A'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-slate-500">FoldX Interaction Energy</span>
                      <span className="font-mono">{selectedCandidate.computational_summary.interaction_energy_kcal_mol != null ? `${selectedCandidate.computational_summary.interaction_energy_kcal_mol.toFixed(2)} kcal/mol` : 'N/A'}</span>
                    </div>
                  </div>
                  <p className="text-[10px] text-slate-400">
                    These are <strong>computational estimates</strong>, not experimental validation.
                  </p>
                </div>

                {/* Experimental Measurements */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900">Experimental Measurements</h4>
                  {Object.keys(selectedCandidate.experimental_summary).length <= 1 ? (
                    <p className="text-xs text-slate-400">No wet-lab measurements recorded.</p>
                  ) : (
                    <div className="rounded-md bg-slate-50 border border-slate-200 p-3 space-y-1 text-xs">
                      {Object.entries(selectedCandidate.experimental_summary)
                        .filter(([k]) => k !== 'quality_flag')
                        .map(([key, value]) => (
                          <div key={key} className="flex justify-between">
                            <span className="text-slate-500">{key}</span>
                            <span className="font-mono">{value != null ? String(value) : 'N/A'}</span>
                          </div>
                        ))}
                      {(() => {
                        const qf = selectedCandidate.experimental_summary.quality_flag as string | undefined;
                        if (!qf) return null;
                        return (
                          <div className="flex justify-between pt-1 border-t border-slate-100">
                            <span className="text-slate-500">Quality Flag</span>
                            <span className={`font-mono font-semibold ${
                              qf === 'FAILED' ? 'text-red-600' :
                              qf === 'WARNING' ? 'text-amber-600' : 'text-emerald-600'
                            }`}>
                              {qf}
                            </span>
                          </div>
                        );
                      })()}
                    </div>
                  )}
                </div>

                {/* Decision Form */}
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-slate-900">Manual Decision</h4>
                  {saveError && (
                    <div className="rounded-md bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                      {saveError}
                    </div>
                  )}
                  <div className="space-y-1">
                    <Label className="text-xs">Decision *</Label>
                    <select
                      value={decisionForm.decision}
                      onChange={(e) => setDecisionForm({ ...decisionForm, decision: e.target.value as PriorityDecisionPayload['decision'] })}
                      className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs"
                    >
                      {DECISION_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>{d.label}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Decision Reason *</Label>
                    <Textarea
                      value={decisionForm.decision_reason}
                      onChange={(e) => setDecisionForm({ ...decisionForm, decision_reason: e.target.value })}
                      className="text-xs min-h-[60px]"
                      placeholder="Why this decision? E.g. Low MIC and acceptable hemolysis."
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-xs">Reviewer</Label>
                      <Input
                        value={decisionForm.reviewer}
                        onChange={(e) => setDecisionForm({ ...decisionForm, reviewer: e.target.value })}
                        className="text-xs h-8"
                        placeholder="Your name"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-xs">Notes</Label>
                      <Input
                        value={decisionForm.notes}
                        onChange={(e) => setDecisionForm({ ...decisionForm, notes: e.target.value })}
                        className="text-xs h-8"
                        placeholder="Additional notes"
                      />
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleSaveDecision}
                    disabled={savingDecision}
                    className="flex items-center gap-1.5 px-3 py-2 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-50 w-full justify-center"
                  >
                    <Save className="w-3 h-3" />
                    {savingDecision ? 'Saving...' : 'Save Decision'}
                  </button>
                </div>

                {/* Integrity Notice */}
                <div className="rounded-md bg-amber-50 border border-amber-200 p-3">
                  <p className="text-[10px] text-amber-700">
                    <strong>Boundary:</strong> This decision is a manual review annotation. It does NOT modify the composite_score, does NOT change validation_status, and does NOT fabricate experimental data.
                  </p>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>
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
  color: 'slate' | 'emerald' | 'sky' | 'red' | 'amber' | 'purple';
}) {
  const colorMap = {
    slate: { bg: 'bg-slate-50', text: 'text-slate-700', border: 'border-slate-200', icon: 'text-slate-500' },
    emerald: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', icon: 'text-emerald-500' },
    sky: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200', icon: 'text-sky-500' },
    red: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200', icon: 'text-red-500' },
    amber: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200', icon: 'text-amber-500' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-700', border: 'border-purple-200', icon: 'text-purple-500' },
  };
  const c = colorMap[color];

  return (
    <div className={`rounded-lg ${c.bg} border ${c.border} p-3`}>
      <div className={`${c.icon} mb-1`}>{icon}</div>
      <div className={`text-xl font-bold ${c.text}`}>{value}</div>
      <div className={`text-[10px] font-medium uppercase tracking-wider mt-0.5 ${c.text}`}>{label}</div>
    </div>
  );
}
