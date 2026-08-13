import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useNavigate } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { pipelineRunsApi, type PipelineLogRecord, type PipelineRun, type PipelineStatus, type PipelineStepSummary } from '@/lib/api/pipelineRuns';
import { fetchClient } from '@/lib/api/client';
import { mockTargetProtein } from '@/data/platformMockData';
import {
  Play,
  RefreshCw,
  Download,
  Dna,
  Microscope,
  Atom,
  Beaker,
  Layers,
  Trophy,
  GitBranch,
  AlertTriangle,
  CheckCircle2,
  Clock,
  XCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FileSpreadsheet,
  ListOrdered,
  FileText,
  RotateCcw,
  Upload,
  FlaskConical,
  Zap,
  History,
  Lock,
  SlidersHorizontal,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const GOLDEN_RUN_ID = 'dcfeea4b-a51f-4963-af3f-1ea2364e6936';

const STEP_ICONS: Record<string, React.ElementType> = {
  TARGET_INPUT: Dna,
  EPITOPE_SCREENING: Microscope,
  PEPTIDE_GENERATION: Atom,
  PEPTIDE_OPTIMIZATION: Beaker,
  STAMP_ASSEMBLY: Layers,
  STRUCTURE_VALIDATION_READY: Trophy,
  FINAL_RANKING: ListOrdered,
  REPORT_EXPORT: FileText,
};

const STEP_LABELS: Record<string, string> = {
  TARGET_INPUT: '目标蛋白输入',
  EPITOPE_SCREENING: '表位筛选',
  PEPTIDE_GENERATION: '靶向肽生成',
  PEPTIDE_OPTIMIZATION: '靶向肽优化',
  STAMP_ASSEMBLY: 'STAMP 组装',
  STRUCTURE_VALIDATION_READY: '结构验证',
  FINAL_RANKING: '最终排序',
  REPORT_EXPORT: '报告导出',
};

const STATUS_COLORS: Record<string, string> = {
  PENDING: 'bg-gray-100 text-gray-600',
  RUNNING: 'bg-blue-100 text-blue-700 animate-pulse',
  SUCCEEDED: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-700',
  BLOCKED: 'bg-amber-100 text-amber-700',
};

const STATUS_ICONS: Record<string, React.ElementType> = {
  PENDING: Clock,
  RUNNING: RefreshCw,
  SUCCEEDED: CheckCircle2,
  FAILED: XCircle,
  BLOCKED: AlertTriangle,
};

const TARGET_TYPES = [
  { value: 'membrane', label: '膜蛋白' },
  { value: 'receptor', label: '受体' },
  { value: 'enzyme', label: '酶' },
  { value: 'pathogen_surface', label: '病原表面蛋白' },
] as const;

const INPUT_TABS = [
  { key: 'sequence', label: 'Protein Sequence', icon: FileText },
  { key: 'uniprot', label: 'UniProt ID', icon: Dna },
  { key: 'structure', label: 'PDB / CIF File', icon: Upload },
] as const;

// The 5 targeting-peptide generation models the workbench exposes.
// Real run-time status is fetched live from /api/v1/target-peptide-design/models.
const MODEL_DEFS: { id: string; label: string }[] = [
  { id: 'pepmlm', label: 'PepMLM' },
  { id: 'pepprclip', label: 'PepPrCLIP' },
  { id: 'evobind2', label: 'EvoBind2' },
  { id: 'pephar', label: 'PepHAR' },
  { id: 'pepflow', label: 'PepFlow' },
];

const STANDARD_AA = 'ACDEFGHIKLMNPQRSTVWY';

function modelStatusLabel(status: string | undefined): { text: string; runnable: boolean; tone: string } {
  if (!status) return { text: '暂未接通', runnable: false, tone: 'text-gray-500' };
  switch (status) {
    case 'available':
    case 'smoke_rerun_verified':
      return { text: '已注册（冒烟验证）· 真实运行未授权', runnable: false, tone: 'text-amber-600' };
    case 'closed':
    case 'controlled_smoke_verified':
      return { text: '已注册 · 真实运行门禁关闭（暂未接通）', runnable: false, tone: 'text-amber-600' };
    case 'backlog':
    case 'pending_probe':
      return { text: '暂未接通（依赖/许可证缺失）', runnable: false, tone: 'text-red-500' };
    case 'blocked_license':
      return { text: '暂未接通（许可证）', runnable: false, tone: 'text-red-500' };
    case 'disabled':
    case 'parked':
      return { text: '暂未接通（已停用）', runnable: false, tone: 'text-gray-500' };
    default:
      return { text: `暂未接通（${status}）`, runnable: false, tone: 'text-gray-500' };
  }
}

// ---------------------------------------------------------------------------
// Model registry fetch
// ---------------------------------------------------------------------------
interface ModelInfo {
  model_id: string;
  display_name: string;
  status: string;
  stage: string;
  description: string;
  requires_gpu: boolean;
}

// ---------------------------------------------------------------------------
// Generic result table (reused from original)
// ---------------------------------------------------------------------------
function ResultTable({ rows, columns }: { rows: Record<string, any>[]; columns: { key: string; label: string; width?: string }[] }) {
  if (!rows || rows.length === 0) return <p className="text-sm text-gray-500">暂无数据</p>;
  return (
    <div className="overflow-x-auto border rounded-lg">
      <table className="w-full text-sm">
        <thead className="bg-gray-50">
          <tr>
            {columns.map((c) => (
              <th key={c.key} className="px-3 py-2 text-left font-medium text-gray-700 text-xs" style={{ width: c.width }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-gray-50">
              {columns.map((c) => (
                <td key={c.key} className="px-3 py-2 text-gray-800 text-xs font-mono truncate max-w-[200px]">
                  {String(row[c.key] ?? '-')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Step result card (reused from original)
// ---------------------------------------------------------------------------
function StepResultCard({ step, runId }: { step: PipelineStepSummary; runId: string }) {
  const [open, setOpen] = useState(false);
  const out = step.output_summary || {};
  const hasData =
    out.candidates?.length > 0 ||
    out.peptides?.length > 0 ||
    out.optimized_peptides?.length > 0 ||
    out.stamp_candidates?.length > 0 ||
    out.batch_items?.length > 0 ||
    out.final_ranking?.length > 0 ||
    out.manifest != null;
  if (!hasData) return null;
  const artifactFiles: string[] = out.artifact_files || [];
  const csvFile = artifactFiles.find((f: string) => f.endsWith('.csv'));
  return (
    <div className="border rounded-xl bg-white">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
        <div className="flex items-center gap-3">
          <span className="text-sm font-medium text-gray-900">{STEP_LABELS[step.step_name] || step.step_name} 结果</span>
          <span className="text-xs text-gray-500">({out.record_count ?? 0} 条)</span>
        </div>
        <div className="flex items-center gap-2">
          {csvFile && (
            <a href={pipelineRunsApi.artifactUrl(runId, csvFile)} download onClick={(e) => e.stopPropagation()} className="text-xs flex items-center gap-1 text-[#156B98] hover:underline">
              <FileSpreadsheet className="w-3.5 h-3.5" /> CSV
            </a>
          )}
          {open ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </div>
      </button>
      {open && (
        <div className="px-4 pb-4">
          {step.step_name === 'EPITOPE_SCREENING' && out.candidates && (
            <ResultTable rows={out.candidates} columns={[{ key: 'rank', label: 'Rank', width: '50px' }, { key: 'start', label: 'Start', width: '60px' }, { key: 'end', label: 'End', width: '60px' }, { key: 'sequence', label: 'Sequence' }, { key: 'length', label: 'Len', width: '50px' }, { key: 'net_charge', label: 'Charge', width: '60px' }, { key: 'priority_score', label: 'Score', width: '70px' }]} />
          )}
          {step.step_name === 'PEPTIDE_GENERATION' && out.peptides && (
            <ResultTable rows={out.peptides} columns={[{ key: 'sequence', label: 'Sequence' }, { key: 'length', label: 'Len', width: '50px' }, { key: 'net_charge', label: 'Charge', width: '60px' }, { key: 'hydrophobic_ratio', label: 'Hydro', width: '70px' }, { key: 'pass_basic_filters', label: 'Pass', width: '60px' }]} />
          )}
          {step.step_name === 'PEPTIDE_OPTIMIZATION' && out.optimized_peptides && (
            <ResultTable rows={out.optimized_peptides} columns={[{ key: 'sequence', label: 'Sequence' }, { key: 'length', label: 'Len', width: '50px' }, { key: 'net_charge', label: 'Charge', width: '60px' }, { key: 'aggregation_risk_proxy', label: 'AggRisk', width: '70px' }, { key: 'synthesis_risk_proxy', label: 'SynthRisk', width: '80px' }, { key: 'rank_score', label: 'Score', width: '70px' }]} />
          )}
          {step.step_name === 'STAMP_ASSEMBLY' && out.stamp_candidates && (
            <ResultTable rows={out.stamp_candidates} columns={[{ key: 'stamp_sequence', label: 'STAMP Sequence' }, { key: 'targeting_peptide', label: 'Targeting' }, { key: 'linker', label: 'Linker', width: '80px' }, { key: 'functional_peptide', label: 'Functional', width: '100px' }, { key: 'total_length', label: 'Len', width: '50px' }, { key: 'rank_score', label: 'Score', width: '70px' }]} />
          )}
          {step.step_name === 'STRUCTURE_VALIDATION_READY' && out.manifest && (
            <div className="space-y-2">
              <p className="text-xs text-gray-600">状态: {out.manifest.status} · 候选数: {out.manifest.candidate_count}</p>
              <p className="text-xs text-gray-500">{out.manifest.note}</p>
            </div>
          )}
          {step.step_name === 'FINAL_RANKING' && out.final_ranking && (
            <ResultTable rows={out.final_ranking} columns={[{ key: 'rank', label: 'Rank', width: '40px' }, { key: 'stamp_sequence', label: 'STAMP Sequence' }, { key: 'targeting_peptide', label: 'Targeting', width: '100px' }, { key: 'linker', label: 'Linker', width: '70px' }, { key: 'functional_peptide', label: 'Functional', width: '90px' }, { key: 'total_length', label: 'Len', width: '45px' }, { key: 'final_rank_score', label: 'Score', width: '70px' }]} />
          )}
          {step.step_name === 'REPORT_EXPORT' && (
            <div className="space-y-2">
              <p className="text-xs text-gray-600">报告已生成</p>
              <div className="flex gap-2">
                <a href={pipelineRunsApi.artifactUrl(runId, 'REPORT_EXPORT/pipeline_report.md')} download className="text-xs flex items-center gap-1 text-[#156B98] hover:underline">
                  <FileText className="w-3.5 h-3.5" /> pipeline_report.md
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page — 全自动 / 半自动设计 统一工作台
// ---------------------------------------------------------------------------
export default function PipelineOrchestratorPage() {
  useLanguage();
  const navigate = useNavigate();

  // --- mode + input ---
  const [runMode, setRunMode] = useState<'auto' | 'semi_auto'>('auto');
  const [inputTab, setInputTab] = useState<(typeof INPUT_TABS)[number]['key']>('sequence');
  const [targetName, setTargetName] = useState('');
  const [species, setSpecies] = useState('');
  const [targetType, setTargetType] = useState<(typeof TARGET_TYPES)[number]['value']>('pathogen_surface');
  const [sequence, setSequence] = useState('');
  const [regionOfInterest, setRegionOfInterest] = useState('');
  const [notes, setNotes] = useState('');
  const [uniprotId, setUniprotId] = useState('');
  const [structureFileName, setStructureFileName] = useState('');
  const fastaInputRef = useRef<HTMLInputElement>(null);

  // --- run config ---
  const [epitopeType, setEpitopeType] = useState<'b_cell' | 't_cell'>('b_cell');
  const [selectedModels, setSelectedModels] = useState<string[]>(['pepmlm']);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);

  // 6-layer epitope filter
  const [epiFilter, setEpiFilter] = useState({
    lenMin: 8, lenMax: 25,
    chargeMin: -2, chargeMax: 3,
    hydroMin: -1.0, hydroMax: 1.0,
    antigenMin: 0.5,
    accessibilityMin: 0.4,
    compositeMin: 0.6,
  });

  // --- run execution / history ---
  const [creating, setCreating] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runs, setRuns] = useState<PipelineRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [runDetail, setRunDetail] = useState<PipelineStatus | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [polling, setPolling] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [runLogs, setRunLogs] = useState<PipelineLogRecord[]>([]);

  // --- models live fetch ---
  useEffect(() => {
    let cancelled = false;
    setModelsLoading(true);
    fetchClient<{ models: ModelInfo[] }>('/target-peptide-design/models')
      .then((res) => {
        if (!cancelled) setModels(res.models || []);
      })
      .catch((e: any) => {
        if (!cancelled) setModelsError(e?.message || '模型状态获取失败');
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const modelStatusMap = useMemo(() => {
    const m = new Map<string, ModelInfo>();
    for (const mo of models) m.set(mo.model_id, mo);
    return m;
  }, [models]);

  const loadRuns = useCallback(async () => {
    try {
      const res = await pipelineRunsApi.list({ limit: 20 });
      setRuns(res.items);
    } catch {
      // ignore
    }
  }, []);

  const loadRunLogs = useCallback(async (runId: string) => {
    try {
      const res = await pipelineRunsApi.getLogs(runId, 500);
      setRunLogs(res.records || []);
    } catch {
      setRunLogs([]);
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  // Poll selected run detail while running
  useEffect(() => {
    if (!selectedRunId || !polling) return;
    const interval = setInterval(async () => {
      try {
        const res = await pipelineRunsApi.get(selectedRunId);
        setRunDetail(res);
        await loadRunLogs(selectedRunId);
        if (res.status !== 'RUNNING') {
          setPolling(false);
          loadRuns();
        }
      } catch {
        setPolling(false);
      }
    }, 3000);
    return () => clearInterval(interval);
  }, [selectedRunId, polling, loadRuns, loadRunLogs]);

  // --- input helpers ---
  const loadExample = () => {
    setTargetName(mockTargetProtein.name);
    setSpecies(mockTargetProtein.species);
    setTargetType((mockTargetProtein.targetType as any) || 'pathogen_surface');
    setSequence(mockTargetProtein.sequence);
    setRegionOfInterest(mockTargetProtein.regionOfInterest || '');
    setNotes(mockTargetProtein.notes || '');
    setInputTab('sequence');
    setRunError(null);
  };

  const clearInput = () => {
    setTargetName('');
    setSpecies('');
    setTargetType('pathogen_surface');
    setSequence('');
    setRegionOfInterest('');
    setNotes('');
    setUniprotId('');
    setStructureFileName('');
    setRunError(null);
  };

  const importFasta = (file: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      const lines = text.split(/\r?\n/);
      let headerName = '';
      const seqParts: string[] = [];
      for (const raw of lines) {
        const line = raw.trim();
        if (!line) continue;
        if (line.startsWith('>')) {
          if (!headerName) headerName = line.slice(1).trim();
        } else {
          seqParts.push(line);
        }
      }
      const seq = seqParts.join('').replace(/\s/g, '').toUpperCase();
      if (headerName && !targetName) setTargetName(headerName.slice(0, 120));
      if (seq) {
        setSequence(seq);
        setInputTab('sequence');
        setRunError(null);
      } else {
        setRunError('FASTA 文件中未解析到有效序列。');
      }
    };
    reader.onerror = () => setRunError('读取 FASTA 文件失败。');
    reader.readAsText(file);
  };

  // --- model helpers ---
  const toggleModel = (id: string) => {
    setSelectedModels((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]));
  };
  const selectAllModels = () => setSelectedModels(MODEL_DEFS.map((m) => m.id));
  const clearAllModels = () => setSelectedModels([]);

  // --- sequence validation ---
  const cleanedSeq = useMemo(() => sequence.replace(/\s+/g, '').toUpperCase(), [sequence]);
  const seqValidation = useMemo(() => {
    if (!cleanedSeq) return { ok: false, reason: '未输入序列', illegal: [] as string[] };
    const illegal = sortedUnique(cleanedSeq.split('').filter((c) => !STANDARD_AA.includes(c)));
    if (illegal.length) return { ok: false, reason: `含非法字符: ${illegal.join('')}`, illegal };
    if (cleanedSeq.length < 10) return { ok: false, reason: `序列过短（${cleanedSeq.length}aa，需≥10）`, illegal: [] as string[] };
    return { ok: true, reason: '合法', illegal: [] as string[] };
  }, [cleanedSeq]);

  // --- preflight ---
  const preflight = useMemo(() => {
    const issues: string[] = [];
    if (!targetName.trim()) issues.push('未输入目标蛋白名称');
    if (!cleanedSeq) issues.push('未输入目标蛋白序列');
    else if (!seqValidation.ok) issues.push(`序列不合法：${seqValidation.reason}`);
    if (inputTab !== 'sequence') issues.push(`${INPUT_TABS.find((t) => t.key === inputTab)?.label || '当前输入方式'}：本轮仅 Protein Sequence 支持真实运行，请切换到 Protein Sequence 并加载序列`);
    if (selectedModels.length === 0) issues.push('未选择任何靶向肽生成模型');
    return issues;
  }, [targetName, cleanedSeq, seqValidation, inputTab, selectedModels]);

  const canRun = preflight.length === 0;

  // --- run actions ---
  const startRun = async (mode: 'auto' | 'semi_auto') => {
    setRunError(null);
    if (!canRun) {
      setRunError('预检未通过：' + preflight.join('；'));
      return;
    }
    setCreating(true);
    try {
      const res = await pipelineRunsApi.create({
        target_name: targetName.trim(),
        target_sequence: cleanedSeq,
        mode: 'run_all',
        top_epitopes: 20,
        peptides_per_epitope: 5,
        top_stamp_candidates: 100,
        selected_models: selectedModels,
        epitope_type: epitopeType,
        run_mode: mode,
        // 6-layer epitope filter config (sent in body; backend ignores extras, no 422).
        epitope_filters: epiFilter,
      } as any);
      setSelectedRunId(res.id);
      setPolling(true);
      setRunLogs([]);
      await loadRuns();
      const detail = await pipelineRunsApi.get(res.id);
      setRunDetail(detail);
      await loadRunLogs(res.id);
      if (mode === 'semi_auto') {
        // Semi-auto: jump to epitope screening so the user reviews candidates
        // before manually continuing to peptide generation.
        navigate(`/epitope-screening?pipeline_run_id=${res.id}`);
      }
    } catch (e: any) {
      setRunError(e?.message || '创建运行失败，请检查后端连接。');
    } finally {
      setCreating(false);
    }
  };

  const handleSelectRun = async (runId: string) => {
    setSelectedRunId(runId);
    setLoadingDetail(true);
    try {
      const res = await pipelineRunsApi.get(runId);
      setRunDetail(res);
      await loadRunLogs(runId);
      if (res.status === 'RUNNING') setPolling(true);
    } finally {
      setLoadingDetail(false);
    }
  };

  const handleRetry = async (fromStep: string) => {
    if (!selectedRunId) return;
    try {
      await pipelineRunsApi.retry(selectedRunId, fromStep);
      setPolling(true);
    } catch (e: any) {
      setRunError(e?.message || '重试失败');
    }
  };

  // --- sorted runs (Golden Run pinned to top, then newest) ---
  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const ag = a.id === GOLDEN_RUN_ID ? 0 : 1;
      const bg = b.id === GOLDEN_RUN_ID ? 0 : 1;
      if (ag !== bg) return ag - bg;
      return (b.created_at || '').localeCompare(a.created_at || '');
    });
  }, [runs]);

  const runnableCount = selectedModels.filter((id) => modelStatusMap.get(id)?.status === 'available').length;

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">全自动 / 半自动设计</h1>
        <p className="text-sm text-gray-500 mt-1">在同一入口完成目标蛋白输入、表位筛选类型选择与靶向肽模型配置</p>
      </div>

      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        {(['auto', 'semi_auto'] as const).map((m) => (
          <button
            key={m}
            onClick={() => setRunMode(m)}
            className={cn(
              'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border transition-colors',
              runMode === m ? 'bg-[#156B98] text-white border-[#156B98]' : 'bg-white text-gray-700 border-gray-200 hover:bg-gray-50'
            )}
          >
            {m === 'auto' ? <Zap className="w-4 h-4" /> : <FlaskConical className="w-4 h-4" />}
            {m === 'auto' ? '全自动模式' : '半自动模式'}
          </button>
        ))}
        <span className="text-xs text-gray-400 ml-2">
          {runMode === 'auto' ? '目标蛋白 → 表位筛选 → 靶向肽生成 → 优化 → 结构验证 → 最终排序（自动连续）' : '先运行表位筛选，确认候选表位后再继续生成靶向肽'}
        </span>
      </div>

      {/* Scientific boundary banner */}
      <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-sm text-amber-800 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
        <p>
          <span className="font-semibold">NOT_EXPERIMENTALLY_VALIDATED · COMPUTATIONAL_PREDICTION_ONLY</span>
          ：所有结果均为序列级计算优先级，未经实验验证。Pipeline 后端使用确定性 curated baseline 生成候选（非训练好的 ML 模型）；所选 ML 模型的真实运行门禁为关闭状态（REAL_RUN_GATE_CLOSED），不会在本轮被实际执行，请勿将计算预测写成实验验证结果。
        </p>
      </div>

      {/* Two-column workbench */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5">
        {/* ===== LEFT: target protein input ===== */}
        <div className="xl:col-span-7 space-y-4">
          <Card className="border-[#E5E7EB]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <Dna className="w-5 h-5 text-[#156B98]" />
                目标蛋白输入
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* input tabs */}
              <div className="flex items-center gap-2 border-b border-gray-100 pb-3">
                {INPUT_TABS.map((tab) => {
                  const Icon = tab.icon;
                  return (
                    <button
                      key={tab.key}
                      onClick={() => setInputTab(tab.key)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                        inputTab === tab.key ? 'bg-[#156B98] text-white' : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                      )}
                    >
                      <Icon className="w-4 h-4" />
                      {tab.label}
                    </button>
                  );
                })}
              </div>

              {inputTab === 'sequence' && (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">蛋白名称</label>
                      <Input value={targetName} onChange={(e) => setTargetName(e.target.value)} placeholder="例如：SARS-CoV-2 Spike Glycoprotein" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">物种 / 菌株</label>
                      <Input value={species} onChange={(e) => setSpecies(e.target.value)} placeholder="例如：SARS-CoV-2 (Wuhan-Hu-1)" />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">靶标类型</label>
                    <div className="flex flex-wrap gap-2">
                      {TARGET_TYPES.map((t) => (
                        <button
                          key={t.value}
                          onClick={() => setTargetType(t.value)}
                          className={cn(
                            'px-3 py-1.5 rounded-md text-xs font-medium border transition-colors',
                            targetType === t.value ? 'bg-[#156B98] text-white border-[#156B98]' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                          )}
                        >
                          {t.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">
                      蛋白质序列
                      <span className="ml-2 text-gray-400 font-normal">
                        长度 {cleanedSeq.length} aa · 行为 {Math.max(1, Math.ceil(cleanedSeq.length / 80))}
                      </span>
                    </label>
                    <Textarea
                      value={sequence}
                      onChange={(e) => setSequence(e.target.value)}
                      placeholder="MKKLLPTAAAGLLLLAAQPAMA...（支持 FASTA 或纯序列）"
                      className="w-full h-48 overflow-y-auto font-mono text-sm resize-none"
                    />
                    <p className="text-xs text-gray-400 mt-1">
                      序列过长时自动折叠为滚动显示，避免铺满页面。仅支持标准氨基酸（A-Z）。
                    </p>
                    {cleanedSeq && !seqValidation.ok && (
                      <p className="text-xs text-red-600 mt-1">序列校验：{seqValidation.reason}</p>
                    )}
                    {cleanedSeq && seqValidation.ok && (
                      <p className="text-xs text-green-600 mt-1">序列校验：合法（{cleanedSeq.length} aa）</p>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Region of Interest</label>
                      <Input value={regionOfInterest} onChange={(e) => setRegionOfInterest(e.target.value)} placeholder="例如：RBD (319-541)" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
                      <Input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="备注" />
                    </div>
                  </div>
                </>
              )}

              {inputTab === 'uniprot' && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-700 mb-1">UniProt ID</label>
                    <Input value={uniprotId} onChange={(e) => setUniprotId(e.target.value)} placeholder="例如：P0DTC2（本轮暂未接通自动拉取）" />
                  </div>
                  <p className="text-xs text-amber-600">UniProt 自动拉取暂未接通：请切换到 Protein Sequence 手动粘贴序列，或在序列框中粘贴 FASTA。</p>
                </div>
              )}

              {inputTab === 'structure' && (
                <div className="space-y-3">
                  <div
                    className="border-2 border-dashed border-gray-200 rounded-lg p-8 text-center cursor-pointer hover:border-[#156B98]"
                    onClick={() => fastaInputRef.current?.click()}
                  >
                    <Upload className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                    <p className="text-sm text-gray-700 font-medium">{structureFileName || '点击选择 FASTA / PDB / CIF 文件'}</p>
                    <p className="text-xs text-gray-400 mt-1">FASTA 会自动解析序列；PDB/CIF 结构输入本轮暂未接通</p>
                  </div>
                  <input
                    ref={fastaInputRef}
                    type="file"
                    accept=".fasta,.fa,.txt,.pdb,.cif"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        setStructureFileName(f.name);
                        if (/\.(fasta|fa|txt)$/i.test(f.name)) importFasta(f);
                      }
                    }}
                  />
                </div>
              )}

              {/* action buttons */}
              <div className="flex flex-wrap items-center gap-2 pt-3 border-t border-gray-100">
                <Button variant="outline" size="sm" onClick={loadExample} className="gap-1">
                  <Dna className="w-3.5 h-3.5" /> 加载示例蛋白
                </Button>
                <Button variant="outline" size="sm" onClick={clearInput} className="gap-1">
                  <RotateCcw className="w-3.5 h-3.5" /> 清空
                </Button>
                <Button variant="outline" size="sm" onClick={() => fastaInputRef.current?.click()} className="gap-1">
                  <Upload className="w-3.5 h-3.5" /> 导入 FASTA
                </Button>
              </div>

              {runError && (
                <div className="p-3 rounded-md border border-red-200 bg-red-50 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                  <p className="text-sm text-red-700">{runError}</p>
                </div>
              )}
            </CardContent>
          </Card>

        </div>

        {/* ===== RIGHT: run config ===== */}
        <div className="xl:col-span-5 space-y-4">
          <Card className="border-[#E5E7EB]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-gray-900 flex items-center gap-2">
                <SlidersHorizontal className="w-5 h-5 text-[#156B98]" />
                运行配置
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* epitope type */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">表位类型</label>
                <div className="flex gap-2">
                  {([['b_cell', 'B 细胞表位'], ['t_cell', 'T 细胞表位']] as const).map(([v, label]) => (
                    <button
                      key={v}
                      onClick={() => setEpitopeType(v)}
                      className={cn(
                        'px-3 py-1.5 rounded-md text-xs font-medium border transition-colors',
                        epitopeType === v ? 'bg-[#156B98] text-white border-[#156B98]' : 'bg-white text-gray-600 border-gray-200 hover:bg-gray-50'
                      )}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <p className="text-xs text-gray-400 mt-1">B 细胞表位（线性/构象）默认；T 细胞表位本轮后端仅记录，暂未接通 MHC 结合预测。</p>
              </div>

              {/* model selection */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-medium text-gray-700">靶向肽生成模型（{selectedModels.length} / {MODEL_DEFS.length}）</label>
                  <div className="flex gap-2">
                    <button onClick={selectAllModels} className="text-xs text-[#156B98] hover:underline">全选</button>
                    <button onClick={clearAllModels} className="text-xs text-gray-400 hover:underline">取消全选</button>
                  </div>
                </div>
                <div className="space-y-1.5">
                  {MODEL_DEFS.map((m) => {
                    const checked = selectedModels.includes(m.id);
                    const info = modelStatusMap.get(m.id);
                    const st = modelStatusLabel(info?.status);
                    return (
                      <label
                        key={m.id}
                        className={cn(
                          'flex items-center gap-2 px-3 py-2 rounded-md border cursor-pointer transition-colors',
                          checked ? 'border-[#156B98] bg-[#156B98]/5' : 'border-gray-200 bg-white hover:bg-gray-50'
                        )}
                      >
                        <input type="checkbox" checked={checked} onChange={() => toggleModel(m.id)} className="accent-[#156B98]" />
                        <span className="text-sm font-medium text-gray-800">{m.label}</span>
                        <span className={cn('text-[10px] ml-auto flex items-center gap-1', st.tone)}>
                          <Lock className="w-3 h-3" />
                          {info ? st.text : '暂未接通'}
                        </span>
                      </label>
                    );
                  })}
                </div>
                {modelsLoading && <p className="text-xs text-gray-400 mt-1">正在获取模型真实状态…</p>}
                {modelsError && <p className="text-xs text-red-500 mt-1">{modelsError}（回退为静态标注）</p>}
              </div>

              {/* 6-layer epitope filter */}
              <div className="border border-gray-200 rounded-md p-3 bg-gray-50/50">
                <div className="flex items-center gap-2 mb-2">
                  <Layers className="w-3.5 h-3.5 text-gray-500" />
                  <span className="text-xs font-semibold text-gray-700 uppercase tracking-wider">6 层表位筛选</span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <FilterRange label="① 长度" min={epiFilter.lenMin} max={epiFilter.lenMax} onMin={(v) => setEpiFilter((s) => ({ ...s, lenMin: v }))} onMax={(v) => setEpiFilter((s) => ({ ...s, lenMax: v }))} />
                  <FilterRange label="② 电荷" min={epiFilter.chargeMin} max={epiFilter.chargeMax} step={0.5} onMin={(v) => setEpiFilter((s) => ({ ...s, chargeMin: v }))} onMax={(v) => setEpiFilter((s) => ({ ...s, chargeMax: v }))} />
                  <FilterRange label="③ 疏水性" min={epiFilter.hydroMin} max={epiFilter.hydroMax} step={0.1} onMin={(v) => setEpiFilter((s) => ({ ...s, hydroMin: v }))} onMax={(v) => setEpiFilter((s) => ({ ...s, hydroMax: v }))} />
                  <FilterNumber label="④ 抗原性/免疫" value={epiFilter.antigenMin} step={0.05} onValue={(v) => setEpiFilter((s) => ({ ...s, antigenMin: v }))} />
                  <FilterNumber label="⑤ 可及性/结构" value={epiFilter.accessibilityMin} step={0.05} onValue={(v) => setEpiFilter((s) => ({ ...s, accessibilityMin: v }))} />
                  <FilterNumber label="⑥ 综合评分" value={epiFilter.compositeMin} step={0.05} onValue={(v) => setEpiFilter((s) => ({ ...s, compositeMin: v }))} />
                </div>
                <p className="text-[10px] text-gray-400 mt-2">本轮记录到请求预览，后端应用待后续接入。</p>
              </div>

              {/* run preview */}
              <div className="border border-gray-200 rounded-md p-3 bg-white">
                <div className="text-xs font-semibold text-gray-700 mb-2">运行预览</div>
                <dl className="text-xs space-y-1">
                  <PreviewRow k="当前模式" v={runMode === 'auto' ? '全自动' : '半自动'} />
                  <PreviewRow k="表位类型" v={epitopeType === 'b_cell' ? 'B 细胞表位' : 'T 细胞表位'} />
                  <PreviewRow k="已选模型" v={selectedModels.length ? selectedModels.map((id) => MODEL_DEFS.find((m) => m.id === id)?.label || id).join('、') : '未选择'} />
                  <PreviewRow k="目标蛋白状态" v={targetName.trim() ? `${targetName.trim()} · ${cleanedSeq.length}aa` : '未输入'} ok={!!targetName.trim() && seqValidation.ok} />
                  <PreviewRow k="蛋白长度" v={`${cleanedSeq.length} aa`} />
                  <PreviewRow k="可运行模型（真实 ML）" v={`${runnableCount} / ${selectedModels.length}（门禁关闭）`} warn />
                  <PreviewRow k="暂不可运行模型" v={`${selectedModels.length - runnableCount} / ${selectedModels.length}`} warn />
                </dl>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Flow preview + run buttons */}
      <Card className="border-[#E5E7EB]">
        <CardContent className="p-4 space-y-3">
          <div className="flex flex-wrap items-center gap-2 text-xs text-gray-600">
            {[['表位筛选', Microscope], ['靶向肽生成', Atom], ['优化', Beaker], ['结构验证', Trophy], ['最终排序', ListOrdered]].map(([label, Icon], i, arr) => {
              const I = Icon as React.ElementType;
              return (
                <span key={label as string} className="flex items-center gap-2">
                  <span className="flex items-center gap-1 px-2 py-1 rounded bg-gray-50 border border-gray-200">
                    <I className="w-3.5 h-3.5 text-[#156B98]" />
                    {label as string}
                  </span>
                  {i < arr.length - 1 && <span className="text-gray-300">→</span>}
                </span>
              );
            })}
          </div>

          {/* preflight */}
          {preflight.length > 0 && (
            <div className="p-2 rounded-md border border-amber-200 bg-amber-50 text-xs text-amber-800">
              预检未通过：{preflight.join('；')}
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            <Button onClick={() => startRun('auto')} disabled={!canRun || creating} className="bg-[#156B98] text-white hover:bg-[#125a80] gap-2">
              <Play className="w-4 h-4" />
              {creating ? '创建中...' : '开始自动运行'}
            </Button>
            <Button onClick={() => startRun('semi_auto')} disabled={!canRun || creating} variant="outline" className="gap-2">
              <FlaskConical className="w-4 h-4" />
              进入半自动流程
            </Button>
            <span className="text-xs text-gray-400 self-center">运行前预检：目标蛋白、序列合法性、表位类型、至少 1 个模型</span>
          </div>
        </CardContent>
      </Card>

      {/* Run detail (current or selected) */}
      {runDetail && (
        <div className="space-y-4">
          <Card className="border-[#E5E7EB]">
            <CardContent className="p-5">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-900">{runDetail.target_name}</h3>
                  <p className="text-xs text-gray-500 mt-1">Run ID: {runDetail.run_id}{runDetail.run_id === GOLDEN_RUN_ID && <span className="ml-2 text-amber-600 font-medium">· Golden Run</span>}</p>
                </div>
                <span className={cn('text-sm px-3 py-1 rounded-full font-medium', STATUS_COLORS[runDetail.status] || 'bg-gray-100 text-gray-600')}>{runDetail.status}</span>
              </div>
              {runDetail.error_message && <div className="mt-3 p-3 bg-red-50 rounded-lg text-sm text-red-700">{runDetail.error_message}</div>}
              <div className="mt-4 flex gap-2 flex-wrap">
                {runDetail.status === 'FAILED' && (
                  <Button size="sm" variant="outline" onClick={() => handleRetry(runDetail.current_step)} className="gap-1">
                    <RefreshCw className="w-3.5 h-3.5" /> 从当前步骤重试
                  </Button>
                )}
                <Button size="sm" variant="outline" onClick={() => window.open(pipelineRunsApi.download(runDetail.run_id), '_blank')} className="gap-1">
                  <Download className="w-3.5 h-3.5" /> 下载全部 Artifacts
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card className="border-[#E5E7EB]">
            <CardHeader className="pb-3"><CardTitle className="text-base font-semibold text-gray-900">步骤状态</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {runDetail.steps.map((step) => {
                const Icon = STEP_ICONS[step.step_name] || GitBranch;
                const StatusIcon = STATUS_ICONS[step.status] || Clock;
                return (
                  <div key={step.step_name} className={cn('flex items-center gap-3 p-3 rounded-xl border', step.status === 'SUCCEEDED' ? 'bg-green-50 border-green-100' : step.status === 'FAILED' ? 'bg-red-50 border-red-100' : step.status === 'RUNNING' ? 'bg-blue-50 border-blue-100' : 'bg-gray-50 border-gray-100')}>
                    <div className="w-9 h-9 rounded-lg bg-white flex items-center justify-center shrink-0"><Icon className="w-4 h-4 text-[#156B98]" /></div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-gray-900">{STEP_LABELS[step.step_name] || step.step_name}</span>
                        <span className={cn('text-[10px] px-1.5 py-0.5 rounded-full font-medium', STATUS_COLORS[step.status] || 'bg-gray-100 text-gray-600')}>{step.status}</span>
                      </div>
                      {step.method && <p className="text-xs text-gray-500 mt-0.5">方法: {step.method}</p>}
                      {step.output_summary?.record_count !== undefined && <p className="text-xs text-gray-600 mt-0.5">产出: {step.output_summary.record_count} 条记录</p>}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      {step.status === 'SUCCEEDED' && ['EPITOPE_SCREENING', 'PEPTIDE_GENERATION', 'PEPTIDE_OPTIMIZATION', 'STAMP_ASSEMBLY', 'FINAL_RANKING'].includes(step.step_name) && (
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs gap-1 text-[#156B98]" onClick={() => {
                          const pathMap: Record<string, string> = {
                            EPITOPE_SCREENING: `/epitope-screening?pipeline_run_id=${runDetail.run_id}`,
                            PEPTIDE_GENERATION: `/peptide-generation?pipeline_run_id=${runDetail.run_id}`,
                            PEPTIDE_OPTIMIZATION: `/peptide-optimization?pipeline_run_id=${runDetail.run_id}`,
                            STAMP_ASSEMBLY: `/stamp-hybrid-design?pipeline_run_id=${runDetail.run_id}`,
                            FINAL_RANKING: `/final-ranking?pipeline_run_id=${runDetail.run_id}`,
                          };
                          navigate(pathMap[step.step_name]);
                        }}>
                          <ExternalLink className="w-3 h-3" /> 查看
                        </Button>
                      )}
                      <StatusIcon className="w-4 h-4 text-gray-400" />
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>

          <Card className="border-[#E5E7EB]">
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-semibold text-gray-900 flex items-center justify-between">
                <span>运行日志</span>
                <Button size="sm" variant="ghost" className="h-7 gap-1" onClick={() => loadRunLogs(runDetail.run_id)}>
                  <RefreshCw className="w-3.5 h-3.5" /> 刷新
                </Button>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {runLogs.length === 0 ? (
                <p className="text-sm text-gray-500">日志正在生成；运行开始后会自动显示。</p>
              ) : (
                <div className="max-h-80 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-xs text-slate-200 space-y-1">
                  {runLogs.map((entry, index) => (
                    <div key={`${entry.timestamp}-${index}`} className={entry.level === 'ERROR' ? 'text-red-300' : entry.level === 'WARNING' ? 'text-amber-300' : ''}>
                      <span className="text-slate-500">{entry.timestamp ? entry.timestamp.replace('T', ' ').slice(0, 19) : '--'}</span>{' '}
                      <span className="font-semibold">{entry.level}</span>{' '}
                      {entry.step && <span className="text-cyan-300">[{entry.step}] </span>}
                      <span>{entry.message}</span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {runDetail.steps
            .filter((s) => s.status === 'SUCCEEDED' && (s.output_summary?.candidates?.length || s.output_summary?.peptides?.length || s.output_summary?.optimized_peptides?.length || s.output_summary?.stamp_candidates?.length || s.output_summary?.batch_items?.length || s.output_summary?.final_ranking?.length || s.output_summary?.manifest != null))
            .map((step) => <StepResultCard key={step.step_name} step={step} runId={runDetail.run_id} />)}
        </div>
      )}

      {/* ===== History Runs (collapsed, bottom) ===== */}
      <Card className="border-[#E5E7EB]">
        <button onClick={() => setShowHistory((v) => !v)} className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-[#156B98]" />
            <span className="text-sm font-medium text-gray-900">查看运行历史</span>
            <span className="text-xs text-gray-400">（{runs.length} 条，Golden Run 置顶）</span>
          </div>
          {showHistory ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
        </button>
        {showHistory && (
          <CardContent className="pt-0">
            {loadingDetail && <p className="text-sm text-gray-500">加载中...</p>}
            {runs.length === 0 ? (
              <p className="text-sm text-gray-500">暂无 Pipeline Run</p>
            ) : (
              <div className="overflow-x-auto border rounded-lg">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      {['Run ID', '目标蛋白', '状态', '时间', '来源'].map((h) => (
                        <th key={h} className="px-3 py-2 text-left font-medium text-gray-700 text-xs">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {sortedRuns.map((run) => {
                      const isGolden = run.id === GOLDEN_RUN_ID;
                      return (
                        <tr key={run.id} className={cn('cursor-pointer hover:bg-gray-50', selectedRunId === run.id && 'bg-[#156B98]/5')} onClick={() => handleSelectRun(run.id)}>
                          <td className="px-3 py-2 text-xs font-mono text-gray-700">{run.id.slice(0, 8)}</td>
                          <td className="px-3 py-2 text-xs text-gray-800 truncate max-w-[260px]">{run.target_name}</td>
                          <td className="px-3 py-2"><span className={cn('text-[10px] px-1.5 py-0.5 rounded-full font-medium', STATUS_COLORS[run.status] || 'bg-gray-100 text-gray-600')}>{run.status}</span></td>
                          <td className="px-3 py-2 text-xs text-gray-500">{(run.created_at || '').replace('T', ' ').slice(0, 19)}</td>
                          <td className="px-3 py-2 text-xs">
                            {isGolden ? <span className="text-amber-600 font-medium">Golden Run · 真实演示</span> : <span className="text-gray-400">历史 run</span>}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
            <p className="text-xs text-gray-400 mt-2">
              Golden Run 固定为 <span className="font-mono">dcfeea4b</span>（P11311 · ADP1_MYCPN），不可篡改；垃圾测试 run 不会抢占 Golden Run 置顶位置。
            </p>
          </CardContent>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------
function sortedUnique(arr: string[]): string[] {
  return Array.from(new Set(arr)).sort();
}

function PreviewRow({ k, v, ok, warn }: { k: string; v: string; ok?: boolean; warn?: boolean }) {
  return (
    <div className="flex items-start justify-between gap-2">
      <dt className="text-gray-500 shrink-0">{k}</dt>
      <dd className={cn('text-right font-medium', ok ? 'text-green-600' : warn ? 'text-amber-600' : 'text-gray-800')}>{v}</dd>
    </div>
  );
}

function FilterRange({ label, min, max, step = 1, onMin, onMax }: { label: string; min: number; max: number; step?: number; onMin: (v: number) => void; onMax: (v: number) => void }) {
  return (
    <div>
      <label className="block text-[10px] font-medium text-gray-500 mb-1">{label}</label>
      <div className="flex items-center gap-1">
        <input type="number" value={min} step={step} onChange={(e) => onMin(Number(e.target.value))} className="w-full px-1.5 py-1 rounded border border-gray-200 text-xs" />
        <span className="text-gray-400 text-xs">~</span>
        <input type="number" value={max} step={step} onChange={(e) => onMax(Number(e.target.value))} className="w-full px-1.5 py-1 rounded border border-gray-200 text-xs" />
      </div>
    </div>
  );
}

function FilterNumber({ label, value, step = 1, onValue }: { label: string; value: number; step?: number; onValue: (v: number) => void }) {
  return (
    <div>
      <label className="block text-[10px] font-medium text-gray-500 mb-1">{label} <span className="text-gray-400">(≥)</span></label>
      <input type="number" value={value} step={step} onChange={(e) => onValue(Number(e.target.value))} className="w-full px-1.5 py-1 rounded border border-gray-200 text-xs" />
    </div>
  );
}
