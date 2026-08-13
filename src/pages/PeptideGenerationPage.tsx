import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { MetricCard } from '@/components/platform/MetricCard';
import { ScoreBar } from '@/components/platform/ScoreBar';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { StatusPill } from '@/components/platform/StatusPill';
import { DataTableShell } from '@/components/platform/DataTableShell';
import { fetchClient } from '@/lib/api/client';
import { epitopeScansApi } from '@/lib/api/epitopeScans';
import { demoApi, type DemoOverview, type DemoStampCandidate } from '@/lib/api/demoApi';
import { getSelectedEpitope } from '@/lib/realEpitopeApi';
import type { SelectedEpitope } from '@/types/realEpitope';
import {
  generateTargetingPeptides,
  storeSelectedTargetingPeptide
} from '@/lib/targetingPeptideApi';
import type { TargetingPeptideCandidate } from '@/types/targetingPeptide';
import {
  assembleStamp,
  storeAssembledStamp
} from '@/lib/stampAssemblyApi';
import {
  Database,
  AlertTriangle,
  Zap,
  Dna,
  ArrowRight,
  Loader2,
  CheckCircle
} from 'lucide-react';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';

const mockSelectedEpitope: SelectedEpitope = {
  candidate_id: 'ep-001',
  sequence: 'YGVYQPYRVVVLSFELLHAPATVCGPKKSTNLVKNKCVNFNFNGLTGTGVLTESNKKFLPFQQFGRDIADTTDAVRDPQTLEILDITPCSFGGVSVITPGTNTSNQVAVLYQDVNCTEVPVAIHADQLTPTWRVYSTGSNVFQTRAGCLIGAEHVNNSYECDIPIGAGICASYQTQTNSPRRARSVASQSIIAYTMSLGAENSVAYSNNSIAIPTNFTISVTTEILPVSMTKTSVDCTMYICGDSTECSNLLLQYGSFCTQLNRALTGIAVEQDKNTQEVFAQVKQIYKTPPIKDFGGFNFSQILPDPSKPSKRSFIEDLLFNKVTLADAGFIKQYGDCLGDIAARDLICAQKFNGLTVLPPLLTDEMIAQYTSALLAGTITSGWTFGAGAALQIPFAMQMAYRFNGIGVTQNVLYENQKLIANQFNSAIGKIQDSLSSTASALGKLQDVVNQNAQALNTLVKQLSSNFGAISSVLNDILSRLDKVEAEVQIDRLITGRLQSLQTYVTQQLIRAAEIRASANLAATKMSECVLGQSKRVDFCGKGYHLMSFPQSAPHGVVFLHVTYVPAQEKNFTTAPAICHDGKAHFPREGVFVSNGTHWFVTQRNFYEPQIITTDNTFVSGNCDVVIGIVNNTVYDPLQPELDSFKEELDKYFKNHTSPDVDLGDISGINASVVNIQKEIDRLNEVAKNLNESLIDLQELGKYEQYIKWPWYIWLGFIAGLIAIVMVTIMLCCMTSCCSCLKGCCSCGSCCKFDEDDSEPVLKGVKLHYT',
  start: 453,
  end: 505,
  length: 53,
  net_charge: 2,
  pI: 6.8,
  GRAVY: -0.35,
  cys_count: 1,
  disulfide_risk: 'Low',
  hydrophobicity_class: 'Moderate',
  filter_status: 'Pass',
  ranking_score: 0.94,
  target_name: 'SARS-CoV-2 Spike Glycoprotein',
  species: 'SARS-CoV-2 (Wuhan-Hu-1)',
};

export default function PeptideGenerationPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const urlEpitopeId = searchParams.get('epitope_id');
  const urlScanId = searchParams.get('scan_id');
  // 止血 demo mainline: ?demo=golden&run_id=<golden>&source_model=<all|generator>
  const demoMode = searchParams.get('demo') === 'golden';
  const demoRunId = searchParams.get('run_id');

  const [isLoading, setIsLoading] = useState(true);
  const [dataSource, setDataSource] = useState<'sqlite' | 'localStorage' | 'mock' | 'real_db'>('mock');
  const [selectedEpitope, setSelectedEpitopeState] = useState<SelectedEpitope | null>(null);
  const [candidates, setCandidates] = useState<TargetingPeptideCandidate[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);

  // --- demo mainline state ---
  const [demoOverview, setDemoOverview] = useState<DemoOverview | null>(null);
  const [demoSourceModel, setDemoSourceModel] = useState<string>('all');
  const [demoLoading, setDemoLoading] = useState(false);
  const [demoError, setDemoError] = useState('');

  // Platform models exposed in the demo selector. Only those present in
  // demoOverview.source_models have REAL data; the rest are shown but yield an
  // empty state (never a silent mock fallback).
  const PLATFORM_MODELS: { id: string; label: string }[] = [
    { id: 'pepmlm', label: 'PepMLM' },
    { id: 'diffpepbuilder', label: 'DiffPepBuilder' },
    { id: 'pephar', label: 'PepHAR' },
    { id: 'evobind2', label: 'EvoBind2' },
    { id: 'pepflow', label: 'PepFlow (历史 artifact 解析)' },
  ];

  const reloadDemo = async (runId: string | null, sourceModel: string) => {
    setDemoLoading(true);
    setDemoError('');
    // 模型切换 bug 修复：先清空上一轮候选，杜绝残留旧模型结果。
    setDemoOverview((prev) => prev ? { ...prev, stamp_candidates: [], selected_source_model: sourceModel } : prev);
    try {
      const overview = await demoApi.getOverview({ run_id: runId || undefined, source_model: sourceModel });
      setDemoOverview(overview);
      setDataSource(overview.data_source === 'real_db' ? 'real_db' : 'mock');
      if (overview.data_source !== 'real_db') {
        setDemoError(overview.message || '未找到匹配的 pipeline run。');
      }
    } catch (e) {
      setDemoError(e instanceof Error ? e.message : String(e));
    } finally {
      setDemoLoading(false);
    }
  };

  const mapBackendToSelectedEpitope = (c: any): SelectedEpitope => ({
    candidate_id: c.id || c.candidate_id || `epi_${c.start}_${c.end}`,
    sequence: c.sequence,
    start: c.start,
    end: c.end,
    length: c.sequence?.length || 0,
    net_charge: c.net_charge ?? 0,
    pI: c.pi ?? c.pI ?? 0,
    GRAVY: c.hydrophobicity ?? c.GRAVY ?? 0,
    cys_count: c.cys_count ?? 0,
    disulfide_risk: c.disulfide_risk ?? 'Unknown',
    hydrophobicity_class: c.hydrophobicity_class ?? 'Unknown',
    filter_status: c.filter_status || 'Pass',
    ranking_score: c.ranking_score ?? 0,
    target_name: c.target_name || 'Target Protein from DB',
    species: c.species || 'Unknown',
  });

  useEffect(() => {
    async function loadSourceData() {
      setIsLoading(true);

      // 止血 demo mainline: load REAL golden-run stamp candidates.
      if (demoMode) {
        await reloadDemo(demoRunId, 'all');
        setIsLoading(false);
        return;
      }

      try {
        if (urlEpitopeId) {
          const data = await fetchClient<any>(`/epitope-candidates/${urlEpitopeId}`);
          if (data) {
            setSelectedEpitopeState(mapBackendToSelectedEpitope(data));
            setDataSource('sqlite');
            setIsLoading(false);
            return;
          }
        }

        if (urlScanId) {
          const candidates = await epitopeScansApi.getCandidates(urlScanId);
          if (candidates && candidates.length > 0) {
            setSelectedEpitopeState(mapBackendToSelectedEpitope(candidates[0]));
            setDataSource('sqlite');
            setIsLoading(false);
            return;
          }
        }
      } catch (error) {
        console.warn('Backend API request failed, moving to fallback:', error);
      }

      const stored = getSelectedEpitope();
      if (stored) {
        setSelectedEpitopeState(stored);
        setDataSource('localStorage');
      } else {
        setSelectedEpitopeState(mockSelectedEpitope);
        setDataSource('mock');
      }
      setIsLoading(false);
    }

    loadSourceData();
  }, [urlEpitopeId, urlScanId, demoMode, demoRunId]);

  // demo: reload when source_model selector changes (model-switch fix).
  useEffect(() => {
    if (demoMode && demoOverview) {
      reloadDemo(demoRunId, demoSourceModel);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [demoSourceModel]);

  const handleGenerate = async () => {
    if (!selectedEpitope) return;
    setIsGenerating(true);

    try {
      const response = await generateTargetingPeptides({
        source_epitope: {
          candidate_id: selectedEpitope.candidate_id,
          sequence: selectedEpitope.sequence,
          start: selectedEpitope.start,
          end: selectedEpitope.end,
          target_name: selectedEpitope.target_name,
          species: selectedEpitope.species,
        }
      });
      setCandidates(response.data?.candidates || []);
    } catch (error) {
      console.error('Generation failed:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleProceed = async (peptide: TargetingPeptideCandidate) => {
    storeSelectedTargetingPeptide(peptide);
    const response = await assembleStamp({
      targeting_peptide: {
        candidate_id: peptide.candidate_id,
        sequence: peptide.sequence,
      },
      terminal_modification: '-NH2'
    });
    if (response.data) {
      storeAssembledStamp(response.data);
    }
    navigate('/final-ranking');
  };

  if (isLoading) {
    return (
      <PlatformLayout>
        <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
          <Loader2 className="w-10 h-10 text-xh-primary animate-spin" />
          <p className="text-sm text-slate-500">Loading source epitope...</p>
        </div>
      </PlatformLayout>
    );
  }

  return (
    <PlatformLayout>
      <div className="max-w-7xl mx-auto px-4 py-6">
        <PipelineRunBanner />
        <PipelineProgress currentStep={2} />

        <div className="mb-6 space-y-2">
          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${
            dataSource === 'sqlite' || dataSource === 'real_db' ? 'bg-green-50 border-green-100 text-green-700' : 'bg-amber-50 border-amber-100 text-amber-700'
          }`}>
            <Database className="w-4 h-4" />
            <span className="text-xs font-bold uppercase">
              Source: {dataSource === 'real_db'
                ? `Real DB · Golden run${demoOverview?.run_id ? ` ${demoOverview.run_id.slice(0, 8)}` : ''}`
                : dataSource === 'sqlite' ? `SQLite DB`
                : dataSource === 'localStorage' ? 'Local History Fallback'
                : 'Mock · 示例数据 (Demo placeholder)'}
            </span>
          </div>

          {dataSource === 'real_db' && (
            <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800">
              <Database className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">
                Pipeline-run data · Real DB · {demoOverview?.target_name || 'Golden run'} · {demoOverview?.stamp_candidate_total_for_run || 0} 真实候选
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 px-4 py-3 bg-slate-900 text-slate-200 rounded-lg border border-slate-800 shadow-sm">
            <AlertTriangle className="w-4 h-4 text-xh-primary" />
            <p className="text-xs font-medium">
              <span className="text-xh-primary font-bold">NOT_EXPERIMENTALLY_VALIDATED</span> —
              Targeting peptides are currently generated via biophysical complementarity rules.
              Real ML model (PepMLM) integration is scheduled for v0.8 production.
            </p>
          </div>
        </div>

        {demoMode ? (
          <div className="space-y-6">
            <SectionCard title="来源模型 (source_model) · 演示模型切换">
              <p className="text-xs text-slate-600 mb-3">
                Golden run 真实生成器：<span className="font-mono text-emerald-700">{demoOverview?.source_models.map((sm) => `${sm.name} (${sm.count})`).join('，') || '加载中…'}</span>。
                切换模型将重新筛选对应 <span className="font-mono">source_model</span> 的真实候选；无真实数据的模型显示空状态，<strong>不回退 mock</strong>。
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
                    <option key={sm.name} value={sm.name}>
                      {sm.name} · 真实 {sm.count} 候选
                    </option>
                  ))}
                  <optgroup label="平台模型 (Golden run 无真实数据)">
                    {PLATFORM_MODELS.filter((pm) => !(demoOverview?.source_models || []).some((sm) => sm.name === pm.id)).map((pm) => (
                      <option key={pm.id} value={pm.id}>
                        {pm.label} · 无真实数据
                      </option>
                    ))}
                  </optgroup>
                </select>
                {demoLoading && <Loader2 className="w-4 h-4 animate-spin text-xh-primary" />}
                <span className="text-[11px] text-slate-500">当前选择：{demoSourceModel}</span>
              </div>
            </SectionCard>

            <SectionCard
              title={`STAMP 候选肽 (Real DB · ${demoOverview?.stamp_candidates.length || 0})`}
              action={demoOverview?.stamp_candidates.length ? (
                <span className="text-[10px] font-mono text-emerald-700">source_model: {demoOverview?.selected_source_model}</span>
              ) : undefined}
            >
              {demoError && (
                <div className="mb-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{demoError}</div>
              )}
              {demoLoading ? (
                <div className="flex items-center justify-center py-10 gap-2 text-slate-500 text-sm">
                  <Loader2 className="w-4 h-4 animate-spin" /> 重新加载真实候选…
                </div>
              ) : (demoOverview?.stamp_candidates.length || 0) === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-2">
                  <AlertTriangle className="w-8 h-8 text-amber-300" />
                  <p className="text-sm text-slate-700 font-medium">暂无该模型真实数据</p>
                  <p className="text-xs text-slate-500">
                    Golden run {demoOverview?.run_id?.slice(0, 8) || ''} 未包含 source_model=<span className="font-mono">{demoSourceModel}</span> 的结果。
                  </p>
                  <p className="text-[11px] text-slate-400">不显示 mock / 示例数据。请选择“全部真实候选”或真实生成器。</p>
                </div>
              ) : (
                <DataTableShell
                  data={demoOverview?.stamp_candidates || []}
                  columns={[
                    {
                      header: '序列 (full_sequence)',
                      render: (c: DemoStampCandidate) => <SequenceBadge sequence={c.full_sequence || ''} size="sm" />,
                    },
                    {
                      header: '来源模型',
                      render: (c: DemoStampCandidate) => (
                        <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 text-[10px] font-mono">{c.source_model || '-'}</span>
                      ),
                    },
                    {
                      header: '长度',
                      render: (c: DemoStampCandidate) => <span className="text-xs">{c.length ?? '未计算'} aa</span>,
                    },
                    {
                      header: '电荷',
                      render: (c: DemoStampCandidate) => <span className="text-xs font-mono">{c.net_charge ?? '未计算'}</span>,
                    },
                    {
                      header: '疏水性',
                      render: (c: DemoStampCandidate) => <span className="text-xs font-mono">{c.hydrophobicity ?? '未计算'}</span>,
                    },
                    {
                      header: '综合评分',
                      render: (c: DemoStampCandidate) => <ScoreBar score={c.composite_score ?? 0} showValue />,
                    },
                  ]}
                />
              )}
            </SectionCard>

            <SectionCard title="演示流程 · 半自动">
              <p className="text-xs text-slate-600 mb-3">
                已展示 Real DB · Golden run 的 STAMP 候选肽（source_model={demoOverview?.source_models[0]?.name || '-'}，curated baseline，非 ML）。点击下方继续候选排序，run_id 贯穿后续页面。
              </p>
              <button
                onClick={() => navigate(`/final-ranking?demo=golden&run_id=${demoRunId || demoOverview?.run_id || ''}`)}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-bold bg-xh-primary text-white hover:bg-xh-primary/90 transition-colors"
              >
                <ArrowRight className="w-4 h-4" />
                继续候选排序 →
              </button>
            </SectionCard>
          </div>
        ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <SectionCard title={t.peptideGeneration.sourceEpitopeTitle}>
              <div className="bg-slate-50 rounded-xl p-4 border border-slate-200">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-sm font-bold text-slate-900 mb-1 flex items-center gap-2">
                      <Dna className="w-4 h-4 text-xh-primary" />
                      {selectedEpitope?.target_name}
                    </h3>
                    <p className="text-[10px] text-slate-500 font-mono uppercase tracking-widest">
                      Position: {selectedEpitope?.start}-{selectedEpitope?.end} | {selectedEpitope?.species}
                    </p>
                  </div>
                  <StatusPill status="pass" />
                </div>
                <SequenceBadge sequence={selectedEpitope?.sequence || ''} size="lg" />
              </div>

              <div className="mt-6 flex justify-center">
                <button
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="flex items-center gap-2 px-8 py-3 bg-xh-primary text-white rounded-full text-sm font-bold shadow-lg shadow-xh-primary/20 hover:scale-105 transition-transform disabled:opacity-50"
                >
                  {isGenerating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                  {isGenerating ? 'Designing...' : 'Generate Complementary Peptides'}
                </button>
              </div>
            </SectionCard>

            {candidates.length > 0 && (
              <SectionCard title={t.peptideGeneration.candidatesTitle}>
                <DataTableShell
                  data={candidates}
                  columns={[
                    {
                      header: 'ID',
                      render: (c: TargetingPeptideCandidate) => <span className="font-mono text-[10px]">{c.candidate_id}</span>
                    },
                    {
                      header: 'Targeting Sequence',
                      render: (c: TargetingPeptideCandidate) => <SequenceBadge sequence={c.sequence} size="sm" />
                    },
                    {
                      header: 'Length',
                      render: (c: TargetingPeptideCandidate) => <span className="text-xs">{c.length} aa</span>
                    },
                    {
                      header: 'Charge',
                      render: (c: TargetingPeptideCandidate) => <span className="text-xs font-mono">{c.net_charge.toFixed(1)}</span>
                    },
                    {
                      header: 'Score',
                      render: (c: TargetingPeptideCandidate) => <ScoreBar score={c.ranking_score} showValue />
                    },
                    {
                      header: 'Action',
                      render: (c: TargetingPeptideCandidate) => (
                        <button
                          onClick={() => handleProceed(c)}
                          className="flex items-center gap-1 text-xh-primary hover:underline font-bold text-[10px] uppercase"
                        >
                          Assemble <ArrowRight className="w-3 h-3" />
                        </button>
                      )
                    }
                  ]}
                />
              </SectionCard>
            )}
          </div>

          <div className="space-y-6">
            <SectionCard title={t.peptideGeneration.designRulesTitle}>
              <ul className="space-y-3">
                {[
                  'Charge Complementarity (Electrostatic Matching)',
                  'Hydrophobicity Optimization (GRAVY Control)',
                  'Cys-Free Design (Disulfide Prevention)',
                  'Length Constraints (8-15 amino acids)'
                ].map((rule, idx) => (
                  <li key={idx} className="flex items-start gap-2 text-xs text-slate-600">
                    <CheckCircle className="w-3.5 h-3.5 text-green-500 mt-0.5 shrink-0" />
                    {rule}
                  </li>
                ))}
              </ul>
            </SectionCard>

            <SectionCard title="Generation Summary">
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Candidates" value={candidates.length || 0} />
                <MetricCard label="Algorithm" value="Rule-V1" />
              </div>
            </SectionCard>
          </div>
        </div>
        )}
      </div>
    </PlatformLayout>
  );
}
