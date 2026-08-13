import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { MetricCard } from '@/components/platform/MetricCard';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { StatusPill } from '@/components/platform/StatusPill';
import { DataTableShell } from '@/components/platform/DataTableShell';
import { ScoreBar } from '@/components/platform/ScoreBar';
import { mockRankedPeptides } from '@/data/platformMockData';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';
import { projectResultsApi } from '@/lib/api/projectResults';
import { experimentalValidationApi } from '@/lib/api/experimentalValidation';
import { demoApi, type DemoOverview, type DemoStampCandidate } from '@/lib/api/demoApi';
import type { StampCandidateDetail } from '@/types/projectResults';
import type {
  ExperimentalValidationSummary,
  CandidateExperimentalPriority,
  ExperimentType,
  MetricName,
  QualityFlag,
} from '@/types/experimentalValidation';
import {
  gatherRealCandidates,
  computeFinalRanking,
  storeSelectedForValidation,
  exportFinalRankingAsCsv,
  exportFinalRankingAsJson,
} from '@/lib/finalRankingApi';
import type { EnrichedCandidate, DataProvenance } from '@/lib/finalRankingApi';
import type { FinalRankingCandidateOutput } from '@/types/finalRanking';
import {
  Accordion,
  AccordionItem,
  AccordionTrigger,
  AccordionContent,
} from '@/components/ui/accordion';
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet';
import {
  Box,
  FileSpreadsheet,
  FileText,
  Info,
  Send,
  AlertTriangle,
  CheckCircle2,
  Download,
  FlaskConical,
  Plus,
} from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';

const HEURISTIC_WEIGHTS = [
  { label: 'Length', key: 'length', value: 0.20 },
  { label: 'Net Charge', key: 'net_charge', value: 0.25 },
  { label: 'pI', key: 'pI', value: 0.20 },
  { label: 'GRAVY', key: 'GRAVY', value: 0.20 },
  { label: 'Cys Count', key: 'cys_count', value: 0.15 },
];

function getValidationStatusUI(status: string) {
  switch (status) {
    case 'EXPERIMENTALLY_VALIDATED':
      return {
        bg: 'bg-emerald-50',
        border: 'border-emerald-200',
        iconColor: 'text-emerald-600',
        titleColor: 'text-emerald-800',
        textColor: 'text-emerald-700',
        icon: CheckCircle2,
        message: 'Experimental validation complete. This candidate has wet-lab assay data (MIC, MBC, hemolysis, etc.).',
      };
    case 'EXPERIMENT_PLANNED':
      return {
        bg: 'bg-sky-50',
        border: 'border-sky-200',
        iconColor: 'text-sky-600',
        titleColor: 'text-sky-800',
        textColor: 'text-sky-700',
        icon: Info,
        message: 'Wet-lab experiment has been planned. Awaiting experimental results.',
      };
    case 'PARTIALLY_VALIDATED':
      return {
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        iconColor: 'text-amber-600',
        titleColor: 'text-amber-800',
        textColor: 'text-amber-700',
        icon: AlertTriangle,
        message: 'Partial experimental data available. Additional assays may be pending.',
      };
    case 'VALIDATION_FAILED':
      return {
        bg: 'bg-red-50',
        border: 'border-red-200',
        iconColor: 'text-red-600',
        titleColor: 'text-red-800',
        textColor: 'text-red-700',
        icon: AlertTriangle,
        message: 'Experimental validation failed. Review data quality or repeat assays.',
      };
    default:
      return {
        bg: 'bg-amber-50',
        border: 'border-amber-200',
        iconColor: 'text-amber-600',
        titleColor: 'text-amber-800',
        textColor: 'text-amber-700',
        icon: AlertTriangle,
        message: 'No experimental or structural validation has been performed.',
      };
  }
}

/**
 * Map a backend StampCandidateDetail to the EnrichedCandidate shape used by the UI.
 * Biophysical properties are extracted from metrics if present; otherwise default to 0.
 * amp is not stored separately in P5-lite schema, so it defaults to '-'.
 */
function mapStampDetailToEnriched(candidate: StampCandidateDetail, provenance: DataProvenance): EnrichedCandidate {
  const metrics = candidate.metrics || {};
  const seq = candidate.full_sequence || '';

  return {
    candidate_id: candidate.id,
    full_sequence: candidate.full_sequence,
    targeting_peptide: candidate.targeting_peptide_seq,
    linker: candidate.linker_seq,
    amp: (metrics.amp_sequence as string) || '-',
    length: seq.length,
    net_charge: (metrics.net_charge as number) ?? (metrics.charge as number) ?? 0,
    pI: (metrics.pI as number) ?? (metrics.pi as number) ?? 0,
    GRAVY: (metrics.GRAVY as number) ?? (metrics.gravy as number) ?? 0,
    cys_count: (metrics.cys_count as number) ?? 0,
    composite_score: candidate.composite_score ?? 0,
    mode: (metrics.mode as string) || 'P5_LITE_BACKEND',
    validation_status: candidate.validation_status || 'NOT_EXPERIMENTALLY_VALIDATED',
    created_at: candidate.created_at || null,
    provenance,
    // PepMLM-specific fields (stored in metrics for UI display)
    ppl: (metrics.ppl as number) ?? undefined,
    source: (metrics.source as string) ?? undefined,
    real_model_loaded: (metrics.real_model_loaded as boolean) ?? false,
    generation_status: (metrics.generation_status as string) ?? undefined,
    warnings: (metrics.warnings as string) ?? undefined,
    // Structure prediction metrics (v0.10-P6e)
    structure_prediction: (metrics.structure_prediction as Record<string, unknown>) ?? undefined,
    // Interface quality metrics (v0.10-P6k)
    interface_quality: (metrics.interface_quality as Record<string, unknown>) ?? undefined,
    // Energy quality metrics (v0.10-P6m)
    energy_quality: (metrics.energy_quality as Record<string, unknown>) ?? undefined,
  };
}

export default function FinalRankingPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { projectId } = useParams<{ projectId: string }>();
  const [searchParams] = useSearchParams();
  // 止血 demo mainline: ?demo=golden&run_id=<golden>&source_model=<all|generator>
  const demoMode = searchParams.get('demo') === 'golden';
  const demoRunId = searchParams.get('run_id');

  const [candidates, setCandidates] = useState<EnrichedCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isMock, setIsMock] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<EnrichedCandidate | null>(null);
  const [reportExporting, setReportExporting] = useState(false);

  // v0.11-P2: Experimental validation state
  const [expSummary, setExpSummary] = useState<ExperimentalValidationSummary | null>(null);
  const [expPriority, setExpPriority] = useState<CandidateExperimentalPriority | null>(null);
  const [expLoading, setExpLoading] = useState(false);
  const [createRunOpen, setCreateRunOpen] = useState(false);
  const [addMeasurementOpen, setAddMeasurementOpen] = useState(false);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);

  const [runForm, setRunForm] = useState({
    experiment_type: 'MIC' as ExperimentType,
    organism: '',
    strain: '',
    protocol_name: '',
    experiment_date: '',
    notes: '',
  });

  const [measurementForm, setMeasurementForm] = useState({
    metric_name: 'MIC_ug_ml' as MetricName,
    value: '',
    unit: '',
    replicate_id: '',
    quality_flag: 'PASS' as QualityFlag,
    condition_json: '{}',
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [formSubmitting, setFormSubmitting] = useState(false);

  // --- demo mainline state ---
  const [demoOverview, setDemoOverview] = useState<DemoOverview | null>(null);
  const [demoSourceModel, setDemoSourceModel] = useState<string>('all');
  const [demoLoading, setDemoLoading] = useState(false);
  const PLATFORM_MODELS: { id: string; label: string }[] = [
    { id: 'pepmlm', label: 'PepMLM' },
    { id: 'diffpepbuilder', label: 'DiffPepBuilder' },
    { id: 'pephar', label: 'PepHAR' },
    { id: 'evobind2', label: 'EvoBind2' },
    { id: 'pepflow', label: 'PepFlow (历史 artifact 解析)' },
  ];

  function demoStampToEnriched(c: DemoStampCandidate): EnrichedCandidate {
    const seq = c.full_sequence || '';
    return {
      candidate_id: c.id,
      full_sequence: seq,
      targeting_peptide: c.targeting_peptide_seq || '',
      linker: c.linker_seq || '-',
      amp: '-',
      length: c.length ?? seq.length,
      net_charge: c.net_charge ?? 0,
      pI: 0,
      GRAVY: c.hydrophobicity ?? 0,
      cys_count: 0,
      composite_score: c.composite_score ?? 0,
      mode: 'GOLDEN_RUN_PIPELINE',
      validation_status: c.validation_status || 'NOT_EXPERIMENTALLY_VALIDATED',
      created_at: c.created_at || null,
      provenance: 'stamp_history',
      source: c.source_model || 'golden_run',
      real_model_loaded: false,
    };
  }

  const reloadDemo = async (runId: string | null, sourceModel: string) => {
    setDemoLoading(true);
    // 模型切换 bug 修复：先清空上一轮候选，杜绝残留旧模型结果。
    setCandidates([]);
    try {
      const overview = await demoApi.getOverview({ run_id: runId || undefined, source_model: sourceModel });
      setDemoOverview(overview);
      if (overview.data_source === 'real_db') {
        setCandidates(overview.stamp_candidates.map(demoStampToEnriched));
        setIsMock(false);
      } else {
        setCandidates([]);
        setIsMock(false);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDemoLoading(false);
      setLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);

      // Priority 0 (止血 demo mainline): REAL golden-run data from /demo/overview.
      if (demoMode) {
        await reloadDemo(demoRunId, 'all');
        return;
      }

      // Priority 1: Backend stamp-results if projectId is available in URL/route
      if (projectId) {
        try {
          const stampResults = await projectResultsApi.getProjectStampResults(projectId, {
            top_k: 10,
            include_metrics: true,
          });
          if (!cancelled) {
            const enriched: EnrichedCandidate[] = stampResults.candidates.map((c) =>
              mapStampDetailToEnriched(c, 'stamp_history')
            );
            setCandidates(enriched);
            setIsMock(false);
            setLoading(false);
            return;
          }
        } catch (err: any) {
          console.warn('Backend stamp-results failed, falling back to localStorage:', err);
          if (!cancelled) {
            setError(`Backend stamp-results unavailable (${err.message}). Falling back to local workflow data.`);
          }
        }
      }

      // Priority 2: localStorage v0.7 pipeline data (preserved, not deleted)
      const { inputs, provenance } = await gatherRealCandidates(projectId);

      if (inputs.length === 0) {
        // Fallback to mock data (explicitly labeled)
        const mockEnriched: EnrichedCandidate[] = mockRankedPeptides.map((p) => ({
          candidate_id: p.id,
          full_sequence: p.peptideSequence,
          targeting_peptide: p.peptideSequence,
          linker: '-',
          amp: '-',
          length: p.length,
          net_charge: p.netCharge,
          pI: p.pI,
          GRAVY: p.hydrophobicity,
          cys_count: 0,
          composite_score: p.overallScore,
          mode: 'MOCK_FALLBACK',
          validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
          created_at: null,
          provenance: 'mock',
        }));
        if (!cancelled) {
          setCandidates(mockEnriched);
          setIsMock(true);
          setLoading(false);
        }
        return;
      }

      const result = await computeFinalRanking(inputs);
      if (cancelled) return;

      if (result.error || !result.data) {
        setError(result.error ?? 'Failed to compute ranking');
        setLoading(false);
        return;
      }

      const enriched: EnrichedCandidate[] = result.data.ranked_candidates.map((c) => ({
        ...c,
        provenance,
      }));

      setCandidates(enriched);
      setIsMock(false);
      setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [projectId, demoMode, demoRunId]);

  // demo: reload when source_model selector changes (model-switch fix).
  useEffect(() => {
    if (demoMode && demoOverview) {
      reloadDemo(demoRunId, demoSourceModel);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoSourceModel]);

  const top3 = useMemo(() => candidates.slice(0, 3), [candidates]);
  const total = candidates.length;
  const avgScore = useMemo(
    () => (total > 0 ? candidates.reduce((s, c) => s + c.composite_score, 0) / total : 0),
    [candidates, total],
  );

  const handleExportCsv = () => {
    exportFinalRankingAsCsv(candidates);
  };

  const handleExportJson = () => {
    exportFinalRankingAsJson(candidates);
  };

  const handleExportReport = async (format: 'json' | 'markdown' | 'csv') => {
    if (!projectId) return;
    setReportExporting(true);
    try {
      const { content, format: fmt } = await projectResultsApi.exportCandidateReport(projectId, format);
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
      alert(err.message || 'Report export failed');
    } finally {
      setReportExporting(false);
    }
  };

  const handleSendToValidation = (candidate: FinalRankingCandidateOutput) => {
    storeSelectedForValidation(candidate);
    navigate('/structure-validation');
  };

  const openDrawer = async (candidate: EnrichedCandidate) => {
    setSelectedCandidate(candidate);
    setDrawerOpen(true);
    setExpLoading(true);
    try {
      const [summary, priority] = await Promise.all([
        experimentalValidationApi.getCandidateExperimentalValidation(candidate.candidate_id),
        experimentalValidationApi.getCandidateExperimentalPriority(candidate.candidate_id),
      ]);
      setExpSummary(summary);
      setExpPriority(priority);
    } catch (err: any) {
      console.warn('Failed to load experimental validation data:', err);
      setExpSummary(null);
      setExpPriority(null);
    } finally {
      setExpLoading(false);
    }
  };

  const resetRunForm = () => {
    setRunForm({
      experiment_type: 'MIC',
      organism: '',
      strain: '',
      protocol_name: '',
      experiment_date: '',
      notes: '',
    });
  };

  const resetMeasurementForm = () => {
    setMeasurementForm({
      metric_name: 'MIC_ug_ml',
      value: '',
      unit: '',
      replicate_id: '',
      quality_flag: 'PASS',
      condition_json: '{}',
    });
  };

  const validateMeasurementForm = (): string | null => {
    const val = parseFloat(measurementForm.value);
    if (isNaN(val)) return 'Value must be a number';
    if (['MIC_ug_ml', 'MBC_ug_ml'].includes(measurementForm.metric_name) && val < 0) {
      return `${measurementForm.metric_name} must be >= 0`;
    }
    if (['hemolysis_percent', 'cell_viability_percent'].includes(measurementForm.metric_name) && (val < 0 || val > 100)) {
      return `${measurementForm.metric_name} must be between 0 and 100`;
    }
    if (!measurementForm.unit.trim()) return 'Unit is required';
    return null;
  };

  const handleCreateRun = async () => {
    if (!selectedCandidate || !projectId) return;
    setFormSubmitting(true);
    setFormError(null);
    try {
      await experimentalValidationApi.createValidationRun({
        project_id: projectId,
        candidate_id: selectedCandidate.candidate_id,
        experiment_type: runForm.experiment_type,
        organism: runForm.organism || undefined,
        strain: runForm.strain || undefined,
        protocol_name: runForm.protocol_name || undefined,
        experiment_date: runForm.experiment_date || undefined,
        notes: runForm.notes || undefined,
      });
      setCreateRunOpen(false);
      resetRunForm();
      // Refresh summary
      const summary = await experimentalValidationApi.getCandidateExperimentalValidation(selectedCandidate.candidate_id);
      const priority = await experimentalValidationApi.getCandidateExperimentalPriority(selectedCandidate.candidate_id);
      setExpSummary(summary);
      setExpPriority(priority);
    } catch (err: any) {
      setFormError(err.message || 'Failed to create validation run');
    } finally {
      setFormSubmitting(false);
    }
  };

  const handleAddMeasurement = async () => {
    if (!selectedCandidate || !activeRunId) return;
    const validationError = validateMeasurementForm();
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setFormSubmitting(true);
    setFormError(null);
    try {
      let conditionJson: Record<string, unknown> = {};
      try {
        conditionJson = JSON.parse(measurementForm.condition_json);
      } catch {
        conditionJson = {};
      }
      await experimentalValidationApi.addMeasurement(activeRunId, {
        validation_run_id: activeRunId,
        candidate_id: selectedCandidate.candidate_id,
        metric_name: measurementForm.metric_name,
        value: parseFloat(measurementForm.value),
        unit: measurementForm.unit,
        replicate_id: measurementForm.replicate_id || undefined,
        quality_flag: measurementForm.quality_flag,
        condition_json: conditionJson,
      });
      setAddMeasurementOpen(false);
      resetMeasurementForm();
      setActiveRunId(null);
      // Refresh summary
      const summary = await experimentalValidationApi.getCandidateExperimentalValidation(selectedCandidate.candidate_id);
      const priority = await experimentalValidationApi.getCandidateExperimentalPriority(selectedCandidate.candidate_id);
      setExpSummary(summary);
      setExpPriority(priority);
    } catch (err: any) {
      setFormError(err.message || 'Failed to add measurement');
    } finally {
      setFormSubmitting(false);
    }
  };

  return (
    <PlatformLayout>
      <PipelineRunBanner />
      <PipelineProgress currentStep={9} />

      <header className="mb-6">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold text-xh-text tracking-tight">
              {t.pageTitle.finalRanking}
            </h1>
            <p className="text-sm text-xh-muted mt-1">{t.pageSubtitle.finalRanking}</p>
          </div>
          {projectId && (
            <button
              type="button"
              onClick={() => navigate(`/projects/${projectId}/experimental-validation`)}
              className="flex items-center gap-1.5 px-3 py-2 rounded-md text-[10px] font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
            >
              <FlaskConical className="w-3 h-3" /> Exp. Validation
            </button>
          )}
        </div>

        {isMock ? (
          <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
            <p className="text-xs text-amber-700 leading-relaxed">
              <strong>DEMO / MOCK DATA</strong>
              {' — '}No real STAMP pipeline data was found in localStorage or backend. Displaying mock ranking placeholders for UI demonstration. No MIC, MBC, hemolysis, toxicity, ipTM, pDockQ, or ΔG values are experimentally validated.
            </p>
          </div>
        ) : (
          <div className="mt-3 bg-emerald-50 border border-emerald-200 rounded-lg p-3 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
            <p className="text-xs text-emerald-700 leading-relaxed">
              <strong>{demoMode ? `Real DB · Golden run${demoOverview?.run_id ? ` ${demoOverview.run_id.slice(0, 8)}` : ''} · ${demoOverview?.target_name || 'Pipeline-run data'}` : projectId ? `Real Candidates from P5-lite Backend (Project: ${projectId})` : 'Real Candidates from v0.7 Pipeline'}</strong>
              {' — '}Ranking is based solely on sequence-derived biophysical properties (length, net charge, pI, GRAVY, Cys count) using a heuristic weighted formula. <strong>NOT_EXPERIMENTALLY_VALIDATED.</strong>
            </p>
          </div>
        )}
      </header>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <MetricCard label="Total Candidates" value={total} />
        <MetricCard label="Avg Composite Score" value={avgScore.toFixed(2)} />
        <MetricCard label="Top Candidate Score" value={top3[0]?.composite_score.toFixed(2) ?? '-'} highlight />
        <MetricCard label="Validation Status" value="NOT_EXPERIMENTALLY_VALIDATED" />
      </div>

      {/* Top 3 Cards */}
      {!isMock && top3.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {top3.map((pep, idx) => (
            <div
              key={pep.candidate_id}
              className={`rounded-lg border p-5 ${
                idx === 0 ? 'border-xh-primary bg-xh-primary-light' : 'border-xh-border bg-white'
              }`}
            >
              <div className="flex items-center justify-between mb-3">
                <span className={`text-xs font-bold uppercase tracking-wider ${idx === 0 ? 'text-xh-primary' : 'text-xh-muted'}`}>
                  Top {idx + 1}
                </span>
                <span className={`text-2xl font-bold ${idx === 0 ? 'text-xh-primary' : 'text-xh-text'}`}>
                  {pep.composite_score.toFixed(2)}
                </span>
              </div>
              <SequenceBadge sequence={pep.full_sequence} />
              <div className="mt-3 text-xs text-xh-muted space-y-1">
                <div className="flex justify-between">
                  <span>Length</span>
                  <span className="font-medium text-xh-text">{pep.length}</span>
                </div>
                <div className="flex justify-between">
                  <span>Net Charge</span>
                  <span className="font-medium text-xh-text">{pep.net_charge}</span>
                </div>
                <div className="flex justify-between">
                  <span>pI</span>
                  <span className="font-medium text-xh-text">{pep.pI.toFixed(1)}</span>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 mt-4">
                <button
                  type="button"
                  onClick={() => openDrawer(pep)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[10px] font-medium border border-xh-border text-xh-text hover:bg-gray-50"
                >
                  <Box className="w-3 h-3" /> Details
                </button>
                <button
                  type="button"
                  onClick={() => handleSendToValidation(pep)}
                  className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-[10px] font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
                >
                  <Send className="w-3 h-3" /> Validate
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-9 space-y-6">
          {demoMode && (
            <SectionCard title="来源模型 (source_model) · 演示模型切换">
              <p className="text-xs text-slate-600 mb-3">
                Golden run 真实生成器：<span className="font-mono text-emerald-700">{demoOverview?.source_models.map((sm) => `${sm.name} (${sm.count})`).join('，') || '加载中…'}</span>。
                切换模型重新筛选真实候选；无真实数据的模型显示空状态，<strong>不回退 mock</strong>。
              </p>
              <div className="flex flex-wrap items-center gap-3">
                <label className="text-xs font-semibold text-slate-600">Source model</label>
                <select
                  value={demoSourceModel}
                  onChange={(e) => setDemoSourceModel(e.target.value)}
                  className="rounded border border-slate-300 px-2 py-1 text-sm bg-white"
                >
                  <option value="all">全部真实候选 (all)</option>
                  {(demoOverview?.source_models || []).map((sm) => (
                    <option key={sm.name} value={sm.name}>{sm.name} · 真实 {sm.count} 候选</option>
                  ))}
                  <optgroup label="平台模型 (Golden run 无真实数据)">
                    {PLATFORM_MODELS.filter((pm) => !(demoOverview?.source_models || []).some((sm) => sm.name === pm.id)).map((pm) => (
                      <option key={pm.id} value={pm.id}>{pm.label} · 无真实数据</option>
                    ))}
                  </optgroup>
                </select>
                {demoLoading && <span className="text-[11px] text-slate-500">重新加载…</span>}
                <span className="text-[11px] text-slate-500">当前：{demoSourceModel} · 候选 {candidates.length}</span>
              </div>
            </SectionCard>
          )}

          {/* Ranking Table */}
          <SectionCard title="STAMP Candidate Ranking">
            {loading ? (
              <div className="p-8 text-center text-sm text-xh-muted">Loading ranking data…</div>
            ) : error ? (
              <div className="p-8 text-center text-sm text-red-600">{error}</div>
            ) : demoMode && candidates.length === 0 ? (
              <div className="p-8 text-center text-sm text-slate-600">
                <AlertTriangle className="w-6 h-6 text-amber-400 mx-auto mb-2" />
                暂无该模型真实数据 (Golden run 未包含 source_model=<span className="font-mono">{demoSourceModel}</span> 的结果)。不显示 mock / 示例数据。
              </div>
            ) : (
              <DataTableShell>
                <thead>
                  <tr className="bg-gray-50 border-b border-xh-border">
                    {[
                      'Rank',
                      'Candidate ID',
                      'Full Sequence',
                      'Length',
                      'Net Charge',
                      'pI',
                      'GRAVY',
                      'Cys Count',
                      'Composite Score',
                      'Mode',
                      'Source',
                      'PPL',
                      'Validation Status',
                      'Action',
                    ].map((h) => (
                      <th key={h} className="px-2 py-2 text-[10px] font-semibold text-xh-muted whitespace-nowrap uppercase tracking-wider">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((pep, idx) => (
                    <tr key={pep.candidate_id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                      <td className="px-2 py-2 text-xs font-medium text-xh-text">{idx + 1}</td>
                      <td className="px-2 py-2 text-xs font-mono text-xh-text">{pep.candidate_id}</td>
                      <td className="px-2 py-2 text-xs font-mono text-xh-text max-w-[200px] truncate">{pep.full_sequence}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.length}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.net_charge.toFixed(1)}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.pI.toFixed(1)}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.GRAVY.toFixed(2)}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.cys_count}</td>
                      <td className="px-2 py-2 text-xs font-bold text-xh-primary">{pep.composite_score.toFixed(2)}</td>
                      <td className="px-2 py-2 text-xs text-xh-muted">{pep.mode}</td>
                      <td className="px-2 py-2 text-xs font-mono text-xh-muted">
                        {pep.source ? (
                          <span className={pep.real_model_loaded ? 'text-blue-600 font-semibold' : 'text-slate-500'}>
                            {pep.source}
                          </span>
                        ) : (
                          '-'
                        )}
                      </td>
                      <td className="px-2 py-2 text-xs font-mono text-xh-muted">
                        {pep.ppl != null ? pep.ppl.toFixed(2) : '-'}
                      </td>
                      <td className="px-2 py-2">
                        <StatusPill status="warning" label={pep.validation_status ?? 'NOT_EXPERIMENTALLY_VALIDATED'} />
                      </td>
                      <td className="px-2 py-2">
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => openDrawer(pep)}
                            className="text-[10px] text-xh-primary hover:underline font-medium flex items-center gap-0.5"
                          >
                            <Box className="w-3 h-3" /> View
                          </button>
                          <button
                            type="button"
                            onClick={() => handleSendToValidation(pep)}
                            className="text-[10px] text-xh-primary hover:underline font-medium flex items-center gap-0.5"
                          >
                            <Send className="w-3 h-3" /> Validate
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </DataTableShell>
            )}
          </SectionCard>

          {/* Ranking Methodology */}
          <SectionCard title="Ranking Methodology">
            <Accordion type="single" collapsible defaultValue="methodology">
              <AccordionItem value="methodology">
                <AccordionTrigger className="text-sm font-medium text-xh-text">
                  <span className="flex items-center gap-2">
                    <Info className="w-4 h-4 text-xh-primary" />
                    Heuristic Composite Scoring (v0.7)
                  </span>
                </AccordionTrigger>
                <AccordionContent>
                  <div className="space-y-3 text-xs text-xh-muted leading-relaxed">
                    <p>
                      The composite score is a <strong>heuristic weighted sum</strong> computed solely from
                      sequence-derived biophysical properties. It is <strong>not</strong> a prediction of
                      antimicrobial efficacy, binding affinity, or developability.
                    </p>
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                      {HEURISTIC_WEIGHTS.map((w) => (
                        <div key={w.key} className="bg-gray-50 rounded-md p-2 text-center">
                          <div className="text-lg font-bold text-xh-text">{(w.value * 100).toFixed(0)}%</div>
                          <div className="text-[10px] text-xh-muted mt-0.5">{w.label}</div>
                        </div>
                      ))}
                    </div>
                    <p>
                      <strong>Ideal values used:</strong> Length ≈ 35 aa, |Net Charge| ≈ 5, pI ≈ 8.5,
                      GRAVY ≈ -0.2, Cys Count = 0 or 2.
                    </p>
                    <p>
                      Scoring method: Gaussian deviation from ideal values, clamped to [0, 1].
                    </p>
                    <div className="bg-amber-50 border border-amber-200 rounded-md p-2 flex items-start gap-2">
                      <AlertTriangle className="w-3.5 h-3.5 text-amber-600 mt-0.5 shrink-0" />
                      <p className="text-amber-700">
                        <strong>Experimental validation:</strong> None. All candidates are
                        NOT_EXPERIMENTALLY_VALIDATED. No MIC, MBC, hemolysis, toxicity, ipTM,
                        pDockQ, or ΔG data is available.
                      </p>
                    </div>
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </SectionCard>
        </div>

        {/* Sidebar */}
        <div className="xl:col-span-3 space-y-6">
          <SectionCard title="Export & Decision Support">
            <div className="flex flex-col gap-2.5">
              <button
                type="button"
                onClick={handleExportCsv}
                className="flex items-center gap-2 w-full px-3 py-2.5 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50"
              >
                <FileSpreadsheet className="w-4 h-4 text-emerald-600" />
                Export Ranking CSV
              </button>
              <button
                type="button"
                onClick={handleExportJson}
                className="flex items-center gap-2 w-full px-3 py-2.5 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50"
              >
                <FileText className="w-4 h-4 text-blue-500" />
                Export Ranking JSON
              </button>
              <div className="border-t border-xh-border pt-2.5 mt-1">
                <p className="text-[10px] text-xh-muted mb-1.5 font-medium uppercase tracking-wider">Candidate Report</p>
                <button
                  type="button"
                  onClick={() => handleExportReport('markdown')}
                  disabled={reportExporting}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50 disabled:opacity-50"
                >
                  <FileText className="w-4 h-4 text-slate-500" />
                  Export Report (MD)
                </button>
                <button
                  type="button"
                  onClick={() => handleExportReport('csv')}
                  disabled={reportExporting}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50 disabled:opacity-50 mt-1.5"
                >
                  <FileSpreadsheet className="w-4 h-4 text-slate-500" />
                  Export Report (CSV)
                </button>
                <button
                  type="button"
                  onClick={() => handleExportReport('json')}
                  disabled={reportExporting}
                  className="flex items-center gap-2 w-full px-3 py-2 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50 disabled:opacity-50 mt-1.5"
                >
                  <Download className="w-4 h-4 text-slate-500" />
                  Export Report (JSON)
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Ranking Weights">
            <div className="space-y-3">
              {HEURISTIC_WEIGHTS.map((w) => (
                <ScoreBar key={w.key} label={w.label} value={w.value} color="blue" />
              ))}
            </div>
          </SectionCard>
        </div>
      </div>

      {/* Detail Drawer */}
      <Sheet open={drawerOpen} onOpenChange={setDrawerOpen}>
        <SheetContent className="w-[min(520px,90vw)] overflow-y-auto">
          {selectedCandidate && (
            <>
              <SheetHeader className="pb-4">
                <SheetTitle className="flex items-center gap-2 text-lg">
                  <Box className="h-5 w-5 text-slate-600" />
                  Candidate Detail
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
                      {selectedCandidate.full_sequence}
                    </span>
                  </div>
                </div>

                {/* Components */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900">Components</h4>
                  <ComponentRow label="Targeting Peptide" value={selectedCandidate.targeting_peptide} />
                  <ComponentRow label="Linker" value={selectedCandidate.linker} />
                  <ComponentRow label="AMP" value={selectedCandidate.amp} />
                </div>

                {/* Biophysical Properties */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-900">Biophysical Properties</h4>
                  <div className="grid grid-cols-2 gap-2">
                    <MetricCell label="Length" value={String(selectedCandidate.length)} />
                    <MetricCell label="Net Charge" value={selectedCandidate.net_charge.toFixed(1)} />
                    <MetricCell label="pI" value={selectedCandidate.pI.toFixed(1)} />
                    <MetricCell label="GRAVY" value={selectedCandidate.GRAVY.toFixed(2)} />
                    <MetricCell label="Cys Count" value={String(selectedCandidate.cys_count)} />
                    <MetricCell label="Composite Score" value={selectedCandidate.composite_score.toFixed(2)} highlight />
                  </div>
                </div>

                {/* Data Provenance */}
                <div className="rounded-md bg-blue-50 border border-blue-200 p-3">
                  <h4 className="text-xs font-semibold text-blue-800 mb-1">Data Provenance</h4>
                  <p className="text-xs text-blue-700 capitalize">{selectedCandidate.provenance.replace(/_/g, ' ')}</p>
                  <p className="text-xs text-blue-700 mt-1">Mode: {selectedCandidate.mode}</p>
                  {selectedCandidate.source && (
                    <p className="text-xs text-blue-700 mt-1">
                      Source: <span className={selectedCandidate.real_model_loaded ? 'text-blue-800 font-semibold' : ''}>{selectedCandidate.source}</span>
                      {selectedCandidate.real_model_loaded && ' (REAL_MODEL)'}
                    </p>
                  )}
                  {selectedCandidate.generation_status && (
                    <p className="text-xs text-blue-700 mt-1">Status: {selectedCandidate.generation_status}</p>
                  )}
                </div>

                {/* Computational Structure Validation — Unified Display */}
                <div className="space-y-3">
                  <h4 className="text-sm font-semibold text-slate-900">Computational Structure Validation</h4>
                  <div className="rounded-md bg-amber-50 border border-amber-200 p-3 flex items-start gap-2">
                    <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
                    <p className="text-[10px] text-amber-700 leading-relaxed">
                      These structure, interface, and energy metrics are <strong>computational estimates only</strong>. They are not wet-lab validation and should not be interpreted as MIC, docking_score, MM-GBSA ΔG, or experimentally validated binding affinity.
                    </p>
                  </div>

                  {/* A. Structure Prediction */}
                  <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
                    <h4 className="text-xs font-semibold text-slate-800 mb-2">A. Structure Prediction</h4>
                  {selectedCandidate.structure_prediction ? (
                    <div className="space-y-1 text-xs text-slate-700">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Source</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.model_source ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">mean pLDDT</span>
                        <span className="font-mono font-semibold">{selectedCandidate.structure_prediction.mean_plddt != null ? selectedCandidate.structure_prediction.mean_plddt.toFixed(2) : 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">pTM</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.ptm != null ? selectedCandidate.structure_prediction.ptm.toFixed(2) : 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">ipTM</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.iptm != null ? selectedCandidate.structure_prediction.iptm.toFixed(2) : 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Status</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.prediction_status ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Validation</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.validation_status ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Metrics are real</span>
                        <span className="font-mono">{selectedCandidate.structure_prediction.metrics_are_real ? 'true' : 'false'}</span>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">No structure prediction result available</p>
                  )}
                </div>

                {/* B. Interface Quality */}
                <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
                  <h4 className="text-xs font-semibold text-slate-800 mb-2">B. Interface Quality (pDockQ)</h4>
                  {selectedCandidate.interface_quality ? (
                    <div className="space-y-1 text-xs text-slate-700">
                      <div className="flex justify-between">
                        <span className="text-slate-500">pDockQ</span>
                        <span className="font-mono font-semibold">
                          {selectedCandidate.interface_quality.pdockq != null
                            ? (selectedCandidate.interface_quality.pdockq as number).toFixed(3)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Interface contacts</span>
                        <span className="font-mono">
                          {selectedCandidate.interface_quality.input_features?.interface_contact_count ?? 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Interface pLDDT mean</span>
                        <span className="font-mono">
                          {selectedCandidate.interface_quality.input_features?.interface_residue_plddt_mean != null
                            ? (selectedCandidate.interface_quality.input_features.interface_residue_plddt_mean as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Interface PAE mean</span>
                        <span className="font-mono">
                          {selectedCandidate.interface_quality.pae_interface_mean != null
                            ? (selectedCandidate.interface_quality.pae_interface_mean as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Interface residues</span>
                        <span className="font-mono">
                          target {selectedCandidate.interface_quality.interface_residue_count_A ?? 'N/A'} / peptide {selectedCandidate.interface_quality.interface_residue_count_B ?? 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Algorithm</span>
                        <span className="font-mono">{selectedCandidate.interface_quality.algorithm ?? 'N/A'} {selectedCandidate.interface_quality.algorithm_version ? `(${selectedCandidate.interface_quality.algorithm_version})` : ''}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Status</span>
                        <span className="font-mono">{selectedCandidate.interface_quality.prediction_status ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Validation</span>
                        <span className="font-mono">{selectedCandidate.interface_quality.validation_status ?? 'N/A'}</span>
                      </div>
                      <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-500">ΔG</span>
                          <span className="font-mono text-slate-400">Not computed (FoldX AnalyseComplex provides interaction energy, not ΔG)</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Docking score</span>
                          <span className="font-mono text-slate-400">Not available (FlexPepDock not integrated)</span>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">No interface quality result available. Run complex structure prediction and persist interface quality to see pDockQ.</p>
                  )}
                </div>

                {/* C. FoldX Energy Quality */}
                <div className="rounded-md bg-slate-50 border border-slate-200 p-3">
                  <h4 className="text-xs font-semibold text-slate-800 mb-2">C. FoldX Energy Quality</h4>
                  {selectedCandidate.energy_quality ? (
                    <div className="space-y-1 text-xs text-slate-700">
                      <div className="flex justify-between">
                        <span className="text-slate-500">Source</span>
                        <span className="font-mono">{selectedCandidate.energy_quality.source ?? 'N/A'}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Interaction energy</span>
                        <span className="font-mono font-semibold">
                          {selectedCandidate.energy_quality.interaction_energy_kcal_mol != null
                            ? `${(selectedCandidate.energy_quality.interaction_energy_kcal_mol as number).toFixed(2)} kcal/mol`
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">VdW clashes</span>
                        <span className="font-mono">
                          {selectedCandidate.energy_quality.energy_terms?.vdw_clashes != null
                            ? (selectedCandidate.energy_quality.energy_terms.vdw_clashes as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Backbone H-bond</span>
                        <span className="font-mono">
                          {selectedCandidate.energy_quality.energy_terms?.backbone_hbond != null
                            ? (selectedCandidate.energy_quality.energy_terms.backbone_hbond as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Sidechain H-bond</span>
                        <span className="font-mono">
                          {selectedCandidate.energy_quality.energy_terms?.sidechain_hbond != null
                            ? (selectedCandidate.energy_quality.energy_terms.sidechain_hbond as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Van der Waals</span>
                        <span className="font-mono">
                          {selectedCandidate.energy_quality.energy_terms?.van_der_waals != null
                            ? (selectedCandidate.energy_quality.energy_terms.van_der_waals as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-500">Electrostatics</span>
                        <span className="font-mono">
                          {selectedCandidate.energy_quality.energy_terms?.electrostatics != null
                            ? (selectedCandidate.energy_quality.energy_terms.electrostatics as number).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                      {selectedCandidate.energy_quality.quality_flags && (
                        <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                          {selectedCandidate.energy_quality.quality_flags.unfavorable_interaction_energy && (
                            <div className="flex items-start gap-1.5">
                              <AlertTriangle className="w-3 h-3 text-amber-600 mt-0.5 shrink-0" />
                              <span className="text-amber-700">Unfavorable interaction energy</span>
                            </div>
                          )}
                          {selectedCandidate.energy_quality.quality_flags.high_vdw_clashes && (
                            <div className="flex items-start gap-1.5">
                              <AlertTriangle className="w-3 h-3 text-amber-600 mt-0.5 shrink-0" />
                              <span className="text-amber-700">High VdW clashes</span>
                            </div>
                          )}
                          {selectedCandidate.energy_quality.quality_flags.interpretation && (
                            <p className="text-[10px] text-slate-500 leading-relaxed mt-1">
                              {selectedCandidate.energy_quality.quality_flags.interpretation}
                            </p>
                          )}
                        </div>
                      )}
                      <div className="mt-2 pt-2 border-t border-slate-100 space-y-1">
                        <div className="flex justify-between">
                          <span className="text-slate-500">Status</span>
                          <span className="font-mono">{selectedCandidate.energy_quality.prediction_status ?? 'N/A'}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-slate-500">Validation</span>
                          <span className="font-mono">{selectedCandidate.energy_quality.validation_status ?? 'N/A'}</span>
                        </div>
                        <div className="mt-1 text-[10px] text-slate-400">
                          Not a docking score. Not MM-GBSA ΔG. Not experimentally validated binding affinity.
                        </div>
                      </div>
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500">No FoldX energy quality result available. Run FoldX AnalyseComplex and persist energy quality to see interaction energy.</p>
                  )}
                  </div>
                </div>

                {/* Experimental Validation — v0.11-P2 */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-slate-900">Experimental Validation</h4>
                    <button
                      type="button"
                      onClick={() => { resetRunForm(); setFormError(null); setCreateRunOpen(true); }}
                      className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
                    >
                      <Plus className="w-3 h-3" /> Create Run
                    </button>
                  </div>

                  {expLoading ? (
                    <p className="text-xs text-slate-400">Loading experimental data...</p>
                  ) : expSummary && expSummary.measurements.length > 0 ? (
                    <div className="space-y-2">
                      <div className="rounded-md bg-slate-50 border border-slate-200 p-2">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-slate-500">Status</span>
                          <span className="font-mono font-semibold">{expSummary.overall_validation_status}</span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-slate-500">Runs</span>
                          <span className="font-mono">{expSummary.run_count} ({expSummary.completed_run_count} completed)</span>
                        </div>
                      </div>
                      <div className="space-y-1">
                        {expSummary.measurements.map((m) => (
                          <div key={m.id} className="rounded-md bg-white border border-slate-100 p-2 text-xs">
                            <div className="flex justify-between">
                              <span className="font-medium text-slate-700">{m.metric_name}</span>
                              <span className={`font-mono ${m.quality_flag === 'FAILED' ? 'text-red-600' : m.quality_flag === 'WARNING' ? 'text-amber-600' : 'text-emerald-600'}`}>{m.quality_flag}</span>
                            </div>
                            <div className="flex justify-between mt-0.5">
                              <span className="text-slate-500">Value</span>
                              <span className="font-mono">{m.value ?? 'N/A'} {m.unit}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                      {expPriority && (
                        <div className={`rounded-md p-2 text-xs border ${expPriority.has_experimental_data ? 'bg-emerald-50 border-emerald-200' : 'bg-gray-50 border-gray-200'}`}>
                          <div className="flex justify-between">
                            <span className={expPriority.has_experimental_data ? 'text-emerald-700' : 'text-gray-600'}>Priority Score</span>
                            <span className="font-mono font-semibold">
                              {expPriority.experimental_priority_score != null ? expPriority.experimental_priority_score.toFixed(3) : 'PENDING'}
                            </span>
                          </div>
                          <p className={`mt-0.5 ${expPriority.has_experimental_data ? 'text-emerald-600' : 'text-gray-500'}`}>
                            {expPriority.priority_status}
                          </p>
                        </div>
                      )}
                      {expSummary.measurements.length > 0 && (
                        <button
                          type="button"
                          onClick={() => {
                            const runId = expSummary.measurements[0]?.validation_run_id;
                            if (runId) {
                              setActiveRunId(runId);
                              resetMeasurementForm();
                              setFormError(null);
                              setAddMeasurementOpen(true);
                            }
                          }}
                          className="flex items-center gap-1 px-2 py-1 rounded-md text-[10px] font-medium border border-slate-200 text-slate-600 hover:bg-slate-50 w-full justify-center"
                        >
                          <Plus className="w-3 h-3" /> Add Measurement
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="rounded-md bg-gray-50 border border-gray-200 p-3">
                      <p className="text-xs text-gray-600">
                        No wet-lab measurements recorded.
                      </p>
                      <p className="text-xs text-gray-500 mt-1">
                        Computational predictions (BepiPred3, PepMLM, ColabFold, pDockQ, FoldX) are <strong>not</strong> experimental validation.
                      </p>
                    </div>
                  )}
                </div>

                {/* Validation Warning */}
                {(() => {
                  const vs = getValidationStatusUI(selectedCandidate.validation_status ?? 'NOT_EXPERIMENTALLY_VALIDATED');
                  const Icon = vs.icon;
                  return (
                    <div className={`rounded-md ${vs.bg} border ${vs.border} p-3 flex items-start gap-2`}>
                      <Icon className={`w-4 h-4 ${vs.iconColor} mt-0.5 shrink-0`} />
                      <div>
                        <h4 className={`text-xs font-semibold ${vs.titleColor}`}>Validation Status</h4>
                        <p className={`text-xs ${vs.textColor}`}>
                          {selectedCandidate.validation_status ?? 'NOT_EXPERIMENTALLY_VALIDATED'}. {vs.message}
                        </p>
                      </div>
                    </div>
                  );
                })()}

                {/* Actions */}
                <div className="flex items-center gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => handleSendToValidation(selectedCandidate)}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90"
                  >
                    <Send className="w-4 h-4" />
                    Send to Structure Validation
                  </button>
                </div>
              </div>
            </>
          )}
        </SheetContent>
      </Sheet>

      {/* Create Validation Run Dialog */}
      <Dialog open={createRunOpen} onOpenChange={setCreateRunOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <FlaskConical className="w-4 h-4" /> Create Validation Run
            </DialogTitle>
            <DialogDescription className="text-xs">
              Record a wet-lab experiment plan. Status defaults to PLANNED.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {formError && (
              <div className="rounded-md bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                {formError}
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-xs">Experiment Type *</Label>
              <select
                value={runForm.experiment_type}
                onChange={(e) => setRunForm({ ...runForm, experiment_type: e.target.value as ExperimentType })}
                className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs"
              >
                <option value="MIC">MIC</option>
                <option value="MBC">MBC</option>
                <option value="HEMOLYSIS">HEMOLYSIS</option>
                <option value="CYTOTOXICITY">CYTOTOXICITY</option>
                <option value="SERUM_STABILITY">SERUM_STABILITY</option>
                <option value="PROTEASE_STABILITY">PROTEASE_STABILITY</option>
                <option value="SALT_STABILITY">SALT_STABILITY</option>
                <option value="BIOFILM">BIOFILM</option>
                <option value="RESISTANCE_INDUCTION">RESISTANCE_INDUCTION</option>
                <option value="OTHER">OTHER</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Organism</Label>
                <Input value={runForm.organism} onChange={(e) => setRunForm({ ...runForm, organism: e.target.value })} className="text-xs h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Strain</Label>
                <Input value={runForm.strain} onChange={(e) => setRunForm({ ...runForm, strain: e.target.value })} className="text-xs h-8" />
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Protocol Name</Label>
              <Input value={runForm.protocol_name} onChange={(e) => setRunForm({ ...runForm, protocol_name: e.target.value })} className="text-xs h-8" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Experiment Date</Label>
              <Input type="date" value={runForm.experiment_date} onChange={(e) => setRunForm({ ...runForm, experiment_date: e.target.value })} className="text-xs h-8" />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Notes</Label>
              <Textarea value={runForm.notes} onChange={(e) => setRunForm({ ...runForm, notes: e.target.value })} className="text-xs min-h-[60px]" />
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setCreateRunOpen(false)}
              className="px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreateRun}
              disabled={formSubmitting}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-50"
            >
              {formSubmitting ? 'Creating...' : 'Create Run'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Add Measurement Dialog */}
      <Dialog open={addMeasurementOpen} onOpenChange={setAddMeasurementOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <FlaskConical className="w-4 h-4" /> Add Measurement
            </DialogTitle>
            <DialogDescription className="text-xs">
              Record a wet-lab measurement. Values must come from real assays.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-2">
            {formError && (
              <div className="rounded-md bg-red-50 border border-red-200 p-2 text-xs text-red-700">
                {formError}
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-xs">Metric Name *</Label>
              <select
                value={measurementForm.metric_name}
                onChange={(e) => setMeasurementForm({ ...measurementForm, metric_name: e.target.value as MetricName })}
                className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs"
              >
                <option value="MIC_ug_ml">MIC_ug_ml</option>
                <option value="MBC_ug_ml">MBC_ug_ml</option>
                <option value="hemolysis_percent">hemolysis_percent</option>
                <option value="HC50_ug_ml">HC50_ug_ml</option>
                <option value="IC50_ug_ml">IC50_ug_ml</option>
                <option value="cell_viability_percent">cell_viability_percent</option>
                <option value="serum_half_life_min">serum_half_life_min</option>
                <option value="protease_remaining_percent">protease_remaining_percent</option>
                <option value="biofilm_inhibition_percent">biofilm_inhibition_percent</option>
              </select>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Value *</Label>
                <Input type="number" step="any" value={measurementForm.value} onChange={(e) => setMeasurementForm({ ...measurementForm, value: e.target.value })} className="text-xs h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Unit *</Label>
                <Input value={measurementForm.unit} onChange={(e) => setMeasurementForm({ ...measurementForm, unit: e.target.value })} className="text-xs h-8" placeholder="e.g. ug/ml" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">Replicate ID</Label>
                <Input value={measurementForm.replicate_id} onChange={(e) => setMeasurementForm({ ...measurementForm, replicate_id: e.target.value })} className="text-xs h-8" />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Quality Flag</Label>
                <select
                  value={measurementForm.quality_flag}
                  onChange={(e) => setMeasurementForm({ ...measurementForm, quality_flag: e.target.value as QualityFlag })}
                  className="w-full rounded-md border border-slate-200 bg-white px-2 py-1.5 text-xs"
                >
                  <option value="PASS">PASS</option>
                  <option value="WARNING">WARNING</option>
                  <option value="FAILED">FAILED</option>
                  <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
                </select>
              </div>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Conditions (JSON)</Label>
              <Textarea value={measurementForm.condition_json} onChange={(e) => setMeasurementForm({ ...measurementForm, condition_json: e.target.value })} className="text-xs min-h-[60px] font-mono" placeholder='{"temperature": 37, "ph": 7.4}' />
            </div>
          </div>
          <DialogFooter>
            <button
              type="button"
              onClick={() => setAddMeasurementOpen(false)}
              className="px-3 py-1.5 rounded-md text-xs font-medium border border-slate-200 text-slate-600 hover:bg-slate-50"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleAddMeasurement}
              disabled={formSubmitting}
              className="px-3 py-1.5 rounded-md text-xs font-medium bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-50"
            >
              {formSubmitting ? 'Adding...' : 'Add Measurement'}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </PlatformLayout>
  );
}

function ComponentRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-xs">
      <span className="text-xh-muted">{label}</span>
      <span className="font-mono text-xh-text max-w-[200px] truncate">{value}</span>
    </div>
  );
}

function MetricCell({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className={`flex items-center justify-between rounded-md px-3 py-2 ${highlight ? 'bg-xh-primary-light border border-xh-primary/20' : 'bg-slate-50'}`}>
      <span className="text-xs text-xh-muted">{label}</span>
      <span className={`text-sm font-semibold tabular-nums ${highlight ? 'text-xh-primary' : 'text-xh-text'}`}>{value}</span>
    </div>
  );
}
