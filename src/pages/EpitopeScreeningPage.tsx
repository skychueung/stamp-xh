import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { MetricCard } from '@/components/platform/MetricCard';
import { ScoreBar } from '@/components/platform/ScoreBar';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { DataTableShell } from '@/components/platform/DataTableShell';
import { epitopeScansApi } from '@/lib/api/epitopeScans';
import { jobsApi } from '@/lib/api/jobs';
import { getStoredEpitopeScan, storeSelectedEpitope, exportCandidatesCSV } from '@/lib/realEpitopeApi';
import { demoApi, type DemoOverview } from '@/lib/api/demoApi';
import type { EpitopeScanResponse, EpitopeCandidate } from '@/types/realEpitope';
import type { EpitopeScan } from '@/types/epitope';
import { Loader2, AlertTriangle, Database, Download, Send, Zap } from 'lucide-react';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';

function getStatusColor(status: string): string {
  if (status === 'Pass') return 'text-green-600 bg-green-50';
  if (status === 'Warning') return 'text-amber-600 bg-amber-50';
  return 'text-red-600 bg-red-50';
}

/**
 * MOCK / DEMO DATA — Explicitly labeled for UI demonstration only.
 * Not returned by P5-lite backend. Used when no SQLite or localStorage data exists.
 */
const mockEpitopeCandidates: EpitopeCandidate[] = [
  {
    candidate_id: 'ep-001',
    start: 453,
    end: 505,
    sequence: 'YGVYQPYRVVVLSFELLHAPATVCGPKKSTNLVKNKCVNFNFNGLTGTGVLTESNKKFLPFQQFGRDIADTTDAVRDPQTLEILDITPCSFGGVSVITPGTNTSNQVAVLYQDVNCTEVPVAIHADQLTPTWRVYSTGSNVFQTRAGCLIGAEHVNNSYECDIPIGAGICASYQTQTNSPRRARSVASQSIIAYTMSLGAENSVAYSNNSIAIPTNFTISVTTEILPVSMTKTSVDCTMYICGDSTECSNLLLQYGSFCTQLNRALTGIAVEQDKNTQEVFAQVKQIYKTPPIKDFGGFNFSQILPDPSKPSKRSFIEDLLFNKVTLADAGFIKQYGDCLGDIAARDLICAQKFNGLTVLPPLLTDEMIAQYTSALLAGTITSGWTFGAGAALQIPFAMQMAYRFNGIGVTQNVLYENQKLIANQFNSAIGKIQDSLSSTASALGKLQDVVNQNAQALNTLVKQLSSNFGAISSVLNDILSRLDKVEAEVQIDRLITGRLQSLQTYVTQQLIRAAEIRASANLAATKMSECVLGQSKRVDFCGKGYHLMSFPQSAPHGVVFLHVTYPAQEKNFTTAPAICHDGKAHFPREGVFVSNGTHWFVTQRNFYEPQIITTDNTFVSGNCDVVIGIVNNTVYDPLQPELDSFKEELDKYFKNHTSPDVDLGDISGINASVVNIQKEIDRLNEVAKNLNESLIDLQELGKYEQYIKWPWYIWLGFIAGLIAIVMVTIMLCCMTSCCSCLKGCCSCGSCCKFDEDDSEPVLKGVKLHYT',
    length: 53,
    net_charge: 2,
    pI: 6.8,
    GRAVY: -0.35,
    cys_count: 1,
    disulfide_risk: 'Low',
    hydrophobicity_class: 'Moderate',
    filter_status: 'Pass',
    ranking_score: 0.94,
    risk_notes: null,
    recommendation_reason: 'High surface exposure, critical ACE2 contact residues, low off-target risk.',
  },
  {
    candidate_id: 'ep-002',
    start: 331,
    end: 365,
    sequence: 'NSTFNGTFTSDVYRYNSTNTNVAQYNTRELQLSLTE',
    length: 35,
    net_charge: -1,
    pI: 5.4,
    GRAVY: -0.52,
    cys_count: 0,
    disulfide_risk: 'None',
    hydrophobicity_class: 'Hydrophilic',
    filter_status: 'Pass',
    ranking_score: 0.87,
    risk_notes: null,
    recommendation_reason: 'Surface-exposed NTD region with moderate flexibility.',
  },
];

/**
 * Adapter: maps backend epitope candidate fields to frontend EpitopeCandidate.
 * Computes display-only fields (length, hydrophobicity_class, disulfide_risk)
 * from real backend properties (sequence, hydrophobicity, cys_count).
 * Does NOT fabricate surface_exposure_score.
 */
function adaptEpitopeCandidate(c: any): EpitopeCandidate {
  const sequence = c.sequence || '';
  const hydrophobicity = c.hydrophobicity ?? 0;
  const cysCount = c.cys_count ?? 0;

  // Display-only: classify hydrophobicity
  let hydrophobicity_class = 'Unknown';
  if (hydrophobicity < -0.5) hydrophobicity_class = 'Hydrophilic';
  else if (hydrophobicity < 0) hydrophobicity_class = 'Moderate';
  else hydrophobicity_class = 'Hydrophobic';

  // Display-only: classify disulfide risk from cysteine count
  let disulfide_risk = 'Unknown';
  if (cysCount === 0) disulfide_risk = 'None';
  else if (cysCount <= 2) disulfide_risk = 'Low';
  else disulfide_risk = 'High';

  return {
    candidate_id: c.candidate_id || c.id || `epi_${c.start}_${c.end}`,
    start: c.start,
    end: c.end,
    sequence,
    length: sequence.length,
    net_charge: c.net_charge ?? 0,
    pI: c.pi ?? 0,
    GRAVY: hydrophobicity,
    cys_count: cysCount,
    disulfide_risk,
    hydrophobicity_class,
    filter_status: c.filter_status || 'Pass',
    ranking_score: c.ranking_score ?? 0,
    risk_notes: c.risk_notes ?? null,
    recommendation_reason: c.recommendation_reason ?? null,
    source: c.metrics?.source || c.algorithm || 'unknown',
  };
}

export default function EpitopeScreeningPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const scanId = searchParams.get('scan_id');
  // 止血 demo mainline: ?demo=golden&run_id=<golden> loads REAL pipeline-run data.
  const demoMode = searchParams.get('demo') === 'golden';
  const demoRunId = searchParams.get('run_id');

  const [scanResult, setScanResult] = useState<EpitopeScanResponse | null>(null);
  const [scanTask, setScanTask] = useState<EpitopeScan | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [dataSource, setDataSource] = useState<'sqlite' | 'localStorage' | 'mock' | 'real_db'>('mock');
  const [demoInfo, setDemoInfo] = useState<{ run_id?: string; target_name?: string; source_models?: DemoOverview['source_models'] } | null>(null);
  const [pepmlmLoadingId, setPepmlmLoadingId] = useState<string | null>(null);

  useEffect(() => {
    async function loadData() {
      setIsLoading(true);

      // --- 止血 demo mainline: load REAL golden-run epitope candidates ---
      if (demoMode) {
        try {
          const overview = await demoApi.getOverview({ run_id: demoRunId || undefined });
          if (overview.data_source === 'real_db') {
            const mappedCandidates = overview.epitope_candidates.map(adaptEpitopeCandidate);
            mappedCandidates.forEach((c) => { (c as any).source = 'real_db'; });
            const mappedResult: EpitopeScanResponse = {
              code: 200,
              message: 'success',
              mode: 'GOLDEN_RUN_PIPELINE',
              validation_status: overview.validation_status,
              input_summary: {
                target_name: overview.target_name || 'P11311 · ADP1_MYCPN',
                species: 'Mycoplasma pneumoniae (ADP1)',
                sequence_length: overview.target_sequence_length || 0,
                window_size: 15,
                total_windows: overview.epitope_candidate_count,
              },
              filtering_summary: {
                total_windows: overview.epitope_candidate_count,
                passed: mappedCandidates.length,
                warning: 0,
                failed: 0,
                returned: mappedCandidates.length,
              },
              candidates: mappedCandidates,
            };
            setScanResult(mappedResult);
            setDemoInfo({ run_id: overview.run_id, target_name: overview.target_name, source_models: overview.source_models });
            setDataSource('real_db');
            setIsLoading(false);
            return;
          } else {
            setDemoInfo({ run_id: overview.run_id });
            setDataSource('mock');
            setIsLoading(false);
            return;
          }
        } catch (error) {
          console.error('Failed to load demo golden-run overview, falling back:', error);
        }
      }

      if (scanId) {
        try {
          const [scanTask, candidates] = await Promise.all([
            epitopeScansApi.getById(scanId),
            epitopeScansApi.getCandidates(scanId)
          ]);

          const mappedResult: EpitopeScanResponse = {
            code: 200,
            message: 'success',
            mode: scanTask.algorithm === 'bepipred3_sidecar' ? 'BEPIPRED3_HTTP_SIDECAR' : 'REAL_BIOPHYSICS_SLIDING_WINDOW',
            validation_status: 'NOT_EXPERIMENTALLY_VALIDATED',
            input_summary: {
              target_name: 'Target Protein',
              species: 'Unknown',
              sequence_length: 0,
              window_size: scanTask.parameters?.window_size || 15,
              total_windows: candidates.length,
            },
            filtering_summary: {
              total_windows: candidates.length,
              passed: candidates.filter((c: any) => c.filter_status === 'Pass').length,
              warning: candidates.filter((c: any) => c.filter_status === 'Warning').length,
              failed: candidates.filter((c: any) => c.filter_status === 'Fail').length,
              returned: candidates.length,
            },
            candidates: candidates.map(adaptEpitopeCandidate),
          };

          setScanTask(scanTask);
          setScanResult(mappedResult);
          setDataSource('sqlite');
          setIsLoading(false);
          return;
        } catch (error) {
          console.error('Failed to fetch from SQLite, falling back to localStorage...', error);
        }
      }

      const stored = getStoredEpitopeScan();
      if (stored) {
        setScanResult(stored);
        setDataSource('localStorage');
      } else {
        setDataSource('mock');
      }
      setIsLoading(false);
    }

    loadData();
  }, [scanId, demoMode, demoRunId]);

  const handleSelectEpitope = (candidate: EpitopeCandidate) => {
    storeSelectedEpitope({
      candidate_id: candidate.candidate_id,
      sequence: candidate.sequence,
      start: candidate.start,
      end: candidate.end,
      length: candidate.length,
      net_charge: candidate.net_charge,
      pI: candidate.pI,
      GRAVY: candidate.GRAVY,
      cys_count: candidate.cys_count,
      disulfide_risk: candidate.disulfide_risk,
      hydrophobicity_class: candidate.hydrophobicity_class,
      filter_status: candidate.filter_status,
      ranking_score: candidate.ranking_score,
      target_name: scanResult?.input_summary.target_name || 'Unknown',
      species: scanResult?.input_summary.species || 'Unknown',
    });
    // 止血 demo mainline: carry run_id forward so the next page reads the same golden run.
    navigate(demoMode && demoInfo?.run_id
      ? `/peptide-generation?demo=golden&run_id=${demoInfo.run_id}`
      : '/peptide-generation');
  };

  const handleGenerateWithPepMLM = async (candidate: EpitopeCandidate) => {
    if (!scanTask) return;
    const projectId = scanTask.project_id;
    const epitopeId = candidate.candidate_id;
    setPepmlmLoadingId(candidate.candidate_id);
    try {
      // 1. Create PepMLM job
      const job = await jobsApi.createJob({
        project_id: projectId,
        job_type: 'pepmlm_generation',
        input_json: {
          project_id: projectId,
          epitope_id: epitopeId,
          sidecar_url: 'http://127.0.0.1:5011',
          top_k: 5,
          linker_seq: 'GGGGS',
        },
      });
      // 2. Run synchronously (blocks until done)
      const updated = await jobsApi.runReal(job.id);
      if (updated.status !== 'succeeded') {
        alert(`PepMLM job failed: ${updated.error_message || 'Unknown error'}`);
        return;
      }
      // 3. Persist results
      await jobsApi.persistPepMLMResults(job.id);
      // 4. Navigate to project results
      navigate(`/projects/${projectId}/results`);
    } catch (error) {
      console.error('PepMLM generation failed:', error);
      alert(`PepMLM generation failed: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setPepmlmLoadingId(null);
    }
  };

  if (isLoading) {
    return (
      <PlatformLayout>
        <div className="flex flex-col items-center justify-center h-[60vh] gap-4">
          <Loader2 className="w-10 h-10 text-xh-primary animate-spin" />
          <p className="text-sm text-slate-500 font-medium">Fetching candidates from {scanId ? 'SQLite' : 'Local Cache'}...</p>
        </div>
      </PlatformLayout>
    );
  }

  const candidates = scanResult?.candidates ?? mockEpitopeCandidates;
  const mode = scanResult?.mode ?? 'MOCK_DATA';
  const validationStatus = scanResult?.validation_status ?? 'NOT_EXPERIMENTALLY_VALIDATED';
  const inputSummary = scanResult?.input_summary ?? { target_name: 'Unknown', species: 'Unknown', sequence_length: 0, window_size: 15, total_windows: 0 };
  const filteringSummary = scanResult?.filtering_summary ?? { total_windows: 0, passed: 0, warning: 0, failed: 0, returned: 0 };

  return (
    <PlatformLayout>
      <div className="max-w-7xl mx-auto px-4 py-6">
        <PipelineRunBanner />
        <PipelineProgress currentStep={1} />

        <div className="mb-6 space-y-2">
          <div className={`flex items-center gap-2 px-4 py-2 rounded-lg border ${
            dataSource === 'sqlite' || dataSource === 'real_db' ? 'bg-green-50 border-green-100 text-green-700' : 'bg-amber-50 border-amber-100 text-amber-700'
          }`}>
            <Database className="w-4 h-4" />
            <span className="text-xs font-bold uppercase tracking-wider">
              Data Source: {dataSource === 'real_db'
                ? `Real DB · Golden run${demoInfo?.run_id ? ` ${demoInfo.run_id.slice(0, 8)}` : ''}`
                : dataSource === 'sqlite' ? `SQLite Backend (Scan: ${scanId})`
                : dataSource === 'localStorage' ? 'Local History'
                : 'Mock · 示例数据 (Demo placeholder)'}
            </span>
          </div>

          {dataSource === 'real_db' && (
            <div className="flex items-center gap-2 px-4 py-2 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-800">
              <Database className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">
                Pipeline-run data · Real DB · {demoInfo?.target_name || 'Golden run'}
              </span>
            </div>
          )}

          <div className="flex items-center gap-2 px-4 py-3 bg-slate-900 text-slate-200 rounded-lg border border-slate-800 shadow-sm">
            <AlertTriangle className="w-4 h-4 text-xh-primary" />
            <p className="text-xs font-medium">
              <span className="text-xh-primary font-bold">NOT_EXPERIMENTALLY_VALIDATED</span> —
              <span className="text-amber-400 font-bold"> COMPUTATIONAL_PREDICTION_ONLY</span> —
              Candidates are ranked by sequence-derived biophysical metrics (Charge, pI, GRAVY).
              No structural binding data or toxicity assays have been performed.
            </p>
          </div>

          {mode === 'BEPIPRED3_HTTP_SIDECAR' && (
            <div className="flex items-center gap-2 px-4 py-2 bg-blue-50 border border-blue-100 rounded-lg text-blue-700">
              <Database className="w-4 h-4" />
              <span className="text-xs font-bold uppercase tracking-wider">Source: BepiPred3 HTTP Sidecar</span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <SectionCard
              title={t.epitopeScreening.candidatesTitle}
              action={
                <button
                  onClick={() => exportCandidatesCSV(candidates, inputSummary, mode, validationStatus)}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Download className="w-3.5 h-3.5" />
                  {t.common.export} CSV
                </button>
              }
            >
              {candidates.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 gap-2">
                  <AlertTriangle className="w-8 h-8 text-slate-300" />
                  <p className="text-sm text-slate-500 font-medium">No epitope candidates found for this scan.</p>
                  <p className="text-xs text-slate-400">Candidate count: 0</p>
                  <p className="text-xs text-slate-400">The BepiPred3 sidecar returned no ranked peptides above threshold.</p>
                </div>
              ) : (
                <DataTableShell
                  data={candidates}
                  columns={[
                  {
                    header: 'Pos',
                    render: (c: EpitopeCandidate) => <span className="font-mono text-xs text-slate-500">{c.start}-{c.end}</span>
                  },
                  {
                    header: 'Sequence',
                    render: (c: EpitopeCandidate) => <SequenceBadge sequence={c.sequence} size="sm" />
                  },
                  {
                    header: 'Charge',
                    render: (c: EpitopeCandidate) => <span className="font-mono text-xs">{typeof c.net_charge === 'number' ? c.net_charge.toFixed(1) : 'N/A'}</span>
                  },
                  {
                    header: 'pI',
                    render: (c: EpitopeCandidate) => <span className="font-mono text-xs">{typeof c.pI === 'number' ? c.pI.toFixed(1) : 'N/A'}</span>
                  },
                  {
                    header: 'GRAVY',
                    render: (c: EpitopeCandidate) => <span className="font-mono text-xs">{typeof c.GRAVY === 'number' ? c.GRAVY.toFixed(2) : 'N/A'}</span>
                  },
                  {
                    header: 'Cys',
                    render: (c: EpitopeCandidate) => <span className="font-mono text-xs">{typeof c.cys_count === 'number' ? c.cys_count : 'N/A'}</span>
                  },
                  {
                    header: 'Score',
                    render: (c: EpitopeCandidate) => <ScoreBar score={c.ranking_score} showValue />
                  },
                  {
                    header: 'Source',
                    render: (c: EpitopeCandidate) => (
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[10px] font-mono uppercase">
                        {c.source || '—'}
                      </span>
                    )
                  },
                  {
                    header: 'Status',
                    render: (c: EpitopeCandidate) => (
                      <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${getStatusColor(c.filter_status)}`}>
                        {c.filter_status}
                      </span>
                    )
                  },
                  {
                    header: 'Action',
                    render: (c: EpitopeCandidate) => (
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleSelectEpitope(c)}
                          className="flex items-center gap-1 text-xh-primary hover:underline font-bold text-[10px] uppercase tracking-tight"
                        >
                          <Send className="w-3 h-3" />
                          Select
                        </button>
                        {dataSource === 'sqlite' && (
                          <button
                            onClick={() => handleGenerateWithPepMLM(c)}
                            disabled={pepmlmLoadingId === c.candidate_id}
                            className="flex items-center gap-1 text-blue-600 hover:text-blue-700 font-bold text-[10px] uppercase tracking-tight disabled:opacity-50"
                            title="Generate targeting peptides with PepMLM REAL_MODEL"
                          >
                            {pepmlmLoadingId === c.candidate_id ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Zap className="w-3 h-3" />
                            )}
                            {pepmlmLoadingId === c.candidate_id ? 'Running…' : 'PepMLM'}
                          </button>
                        )}
                      </div>
                    )
                  }
                  ]}
                />
              )}
            </SectionCard>
          </div>

          <div className="space-y-6">
            <SectionCard title={t.epitopeScreening.scanSummary}>
              <div className="grid grid-cols-2 gap-3">
                <MetricCard label="Total Windows" value={filteringSummary.total_windows} />
                <MetricCard label="Passed" value={filteringSummary.passed} />
                <MetricCard label="Warning" value={filteringSummary.warning} />
                <MetricCard label="Failed" value={filteringSummary.failed} />
              </div>
            </SectionCard>

            <SectionCard title="Target Info">
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500 font-medium">Protein Name</span>
                  <span className="text-xs font-bold text-slate-900">{inputSummary.target_name}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500 font-medium">Organism</span>
                  <span className="text-xs font-mono text-slate-900">{inputSummary.species}</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-xs text-slate-500 font-medium">Scan Algorithm</span>
                  <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-700 text-[10px] font-bold uppercase tracking-tighter border border-blue-100">
                    {mode}
                  </span>
                </div>
              </div>
            </SectionCard>

            {demoMode && demoInfo?.run_id && (
              <SectionCard title="演示流程 · 半自动">
                <p className="text-xs text-slate-600 mb-3">
                  表位筛选已完成（Real DB · Golden run）。点击下方按钮继续生成靶向肽，run_id 将贯穿后续页面，刷新可追溯。
                </p>
                <button
                  onClick={() => navigate(`/peptide-generation?demo=golden&run_id=${demoInfo.run_id}`)}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-bold bg-xh-primary text-white hover:bg-xh-primary/90 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  继续生成靶向肽 →
                </button>
              </SectionCard>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
