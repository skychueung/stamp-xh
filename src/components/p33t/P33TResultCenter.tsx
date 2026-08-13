import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Beaker,
  Download,
  FileJson,
  Filter,
  FolderArchive,
  List,
  Package,
  RefreshCw,
  ScrollText,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  createP33TDeliveryBundle,
  downloadP33TArtifact,
  downloadP33TBundle,
  fetchP33TCandidate,
  fetchP33TCandidateManifest,
  fetchP33TCandidateMetrics,
  fetchP33TCandidates,
  filterP33TCandidates,
} from '@/lib/api/p33t';
import type { P33TCandidate, P33TCandidateMetric } from '@/types/p33t';

const SOURCE_MODELS = [
  { value: '', label: 'All models' },
  { value: 'pepmlm', label: 'PepMLM' },
  { value: 'evobind2', label: 'EvoBind2' },
  { value: 'diffpepbuilder', label: 'DiffPepBuilder' },
  { value: 'pepflow', label: 'PepFlow' },
  { value: 'pephar', label: 'PepHAR' },
  { value: 'ppflow', label: 'PPFlow' },
];

// P33U-D11: protocol target length for Mhp Eno A0A223MA21 peptide design.
const TARGET_LENGTH = 12;

type LengthFilter = 'all' | '12aa' | '22aa';

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}

function formatMetricValue(metric: P33TCandidateMetric): string {
  if (metric.unavailable_with_reason) {
    return 'unavailable';
  }
  if (metric.metric_value === null || metric.metric_value === undefined) {
    return '—';
  }
  const suffix = metric.unit ? ` ${metric.unit}` : '';
  return `${metric.metric_value}${suffix}`;
}

export function P33TResultCenter() {
  const [candidates, setCandidates] = useState<P33TCandidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<P33TCandidateMetric[]>([]);
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);

  const [manifest, setManifest] = useState<Record<string, unknown> | null>(null);
  const [manifestLoading, setManifestLoading] = useState(false);
  const [manifestError, setManifestError] = useState<string | null>(null);

  const [filterSequence, setFilterSequence] = useState('');
  const [filterModel, setFilterModel] = useState('');
  // P33U-D11: quick length-compliance filter (client-side).
  const [lengthFilter, setLengthFilter] = useState<LengthFilter>('all');
  // P33U-D12: scope filter disambiguates P33U vs legacy p33t_ P33S-C demo candidates.
  const [scope, setScope] = useState<'all' | 'P33U' | 'legacy'>('P33U');
  // P33U-D12: Top4 wet-lab shortlist filter + candidate detail (pLDDT/scoring).
  const [top4Only, setTop4Only] = useState(false);
  const [candidateDetail, setCandidateDetail] = useState<Record<string, unknown> | null>(null);

  const [bundleId, setBundleId] = useState<string | null>(null);
  const [bundleLoading, setBundleLoading] = useState(false);
  const [bundleError, setBundleError] = useState<string | null>(null);

  const [downloadingArtifact, setDownloadingArtifact] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const loadCandidates = async (opts?: { scope?: 'all' | 'P33U' | 'legacy'; model?: string; top4?: boolean }) => {
    const s = opts?.scope ?? scope;
    const m = opts?.model ?? filterModel;
    const t4 = opts?.top4 ?? top4Only;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchP33TCandidates(1, 100, m || undefined, s, t4);
      setCandidates(data.items);
      if (data.items.length > 0 && !selectedCandidateId) {
        setSelectedCandidateId(data.items[0].candidate_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load candidates');
    } finally {
      setLoading(false);
    }
  };

  const applyFilter = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await filterP33TCandidates({
        sequence_contains: filterSequence || undefined,
        source_model_id: filterModel || undefined,
        scope,
        top4: top4Only || undefined,
      });
      setCandidates(data.items);
      setSelectedCandidateId(data.items[0]?.candidate_id ?? null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadCandidates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // P33U-D11: client-side length-compliance filtering on top of server filter.
  const visibleCandidates = useMemo(() => {
    if (lengthFilter === '12aa') return candidates.filter((c) => c.length === TARGET_LENGTH);
    if (lengthFilter === '22aa') return candidates.filter((c) => c.length !== TARGET_LENGTH);
    return candidates;
  }, [candidates, lengthFilter]);

  const selectedCandidate = useMemo(
    () => candidates.find((c) => c.candidate_id === selectedCandidateId) ?? null,
    [candidates, selectedCandidateId]
  );

  useEffect(() => {
    if (!selectedCandidateId) {
      setMetrics([]);
      setManifest(null);
      setCandidateDetail(null);
      return;
    }
    let cancelled = false;

    async function loadDetail() {
      try {
        const d = await fetchP33TCandidate(selectedCandidateId!);
        if (!cancelled) setCandidateDetail(d as unknown as Record<string, unknown>);
      } catch {
        if (!cancelled) setCandidateDetail(null);
      }
    }

    async function loadMetrics() {
      setMetricsLoading(true);
      setMetricsError(null);
      try {
        const data = await fetchP33TCandidateMetrics(selectedCandidateId!);
        if (!cancelled) setMetrics(data.metrics);
      } catch (err) {
        if (!cancelled) setMetricsError(err instanceof Error ? err.message : 'Failed to load metrics');
      } finally {
        if (!cancelled) setMetricsLoading(false);
      }
    }

    async function loadManifest() {
      setManifestLoading(true);
      setManifestError(null);
      try {
        const data = await fetchP33TCandidateManifest(selectedCandidateId!);
        if (!cancelled) setManifest(data);
      } catch (err) {
        if (!cancelled) setManifestError(err instanceof Error ? err.message : 'Failed to load manifest');
      } finally {
        if (!cancelled) setManifestLoading(false);
      }
    }

    void loadDetail();
    void loadMetrics();
    void loadManifest();

    return () => {
      cancelled = true;
    };
  }, [selectedCandidateId]);

  const handleCreateBundle = async () => {
    setBundleLoading(true);
    setBundleError(null);
    try {
      const bundle = await createP33TDeliveryBundle();
      setBundleId(bundle.bundle_id);
      const blob = await downloadP33TBundle(bundle.bundle_id);
      downloadBlob(blob, `${bundle.bundle_id}.zip`);
    } catch (err) {
      setBundleError(err instanceof Error ? err.message : 'Bundle creation failed');
    } finally {
      setBundleLoading(false);
    }
  };

  const handleDownloadArtifact = async (artifactId: string) => {
    if (!selectedCandidateId) return;
    setDownloadingArtifact(artifactId);
    setDownloadError(null);
    try {
      const blob = await downloadP33TArtifact(selectedCandidateId, artifactId);
      downloadBlob(blob, artifactId);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : 'Download failed');
    } finally {
      setDownloadingArtifact(null);
    }
  };

  const availableMetrics = useMemo(
    () => metrics.filter((m) => !m.unavailable_with_reason),
    [metrics]
  );
  const unavailableMetrics = useMemo(
    () => metrics.filter((m) => !!m.unavailable_with_reason),
    [metrics]
  );

  const safeArtifacts = useMemo(() => {
    if (!manifest || typeof manifest !== 'object') return [];
    const outputArtifacts = manifest.output_artifacts;
    if (!Array.isArray(outputArtifacts)) return [];
    return outputArtifacts.filter((a: unknown) => {
      if (typeof a !== 'object' || a === null) return false;
      const name = (a as { name?: string }).name;
      return typeof name === 'string' && name.length > 0;
    }) as Array<{ name: string; sha256?: string; path?: string }>;
  }, [manifest]);

  const isPpflowBlocked = filterModel === 'ppflow';

  return (
    <section className="space-y-6" aria-label="P33T result delivery center">
      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="p-4">
          <div className="flex flex-wrap items-start gap-3">
            <AlertTriangle className="h-5 w-5 shrink-0 text-amber-700" />
            <div className="flex-1 space-y-1">
              <p className="text-sm font-semibold text-amber-900">
                NOT_EXPERIMENTALLY_VALIDATED — Computational predictions only
              </p>
              <p className="text-sm text-amber-800">
                The candidate peptides and scientific metrics below are generated by computational
                models and scorers. They are intended for computational prediction and candidate
                prioritization only; they do not represent experimental validation, clinical
                efficacy, or manufacturing conclusions.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* P33U-D11: PPFlow license-blocked compliance banner. */}
      {isPpflowBlocked && (
        <Card className="border-rose-200 bg-rose-50" data-testid="ppflow-license-blocked-banner">
          <CardContent className="p-4">
            <div className="flex flex-wrap items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0 text-rose-700" />
              <div className="flex-1 space-y-1">
                <p className="text-sm font-semibold text-rose-900">
                  PPFlow ⚠️ License Blocked
                </p>
                <p className="text-sm text-rose-800">
                  PPFlow is not executed because no upstream LICENSE or explicit authorization is
                  available. It is retained in the six-model framework as a blocked model and will
                  not load checkpoints, use GPU, or generate candidates until license clearance is
                  obtained.
                </p>
                <p className="text-sm text-rose-800">
                  PPFlow 因上游无 LICENSE 或授权不明确，当前不运行、不加载模型、不占用 GPU、不生成候选。该模型仅作为六模型框架中的合规阻塞项保留，待获得明确授权后再解除。
                </p>
                <p className="text-xs text-rose-700">
                  Gate: P33U_D10_PPFLOW_BLOCKED_LICENSE_CONFIRMED · PPFLOW_BLOCKED_LICENSE
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_1.35fr]">
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <List className="h-4 w-4" />
              Candidate peptides
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-2">
              <div className="flex items-center gap-2">
                <Filter className="h-4 w-4 text-slate-500" />
                <Input
                  value={filterSequence}
                  onChange={(e) => setFilterSequence(e.target.value)}
                  placeholder="Sequence contains..."
                  className="h-9 w-40"
                />
              </div>
              <select
                value={filterModel}
                onChange={(e) => setFilterModel(e.target.value)}
                className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm"
              >
                {SOURCE_MODELS.map((m) => (
                  <option key={m.value} value={m.value}>
                    {m.label}
                  </option>
                ))}
              </select>
              {/* P33U-D12: scope filter (P33U vs legacy vs all). Defaults to P33U. */}
              <select
                value={scope}
                onChange={(e) => {
                  const newScope = e.target.value as 'all' | 'P33U' | 'legacy';
                  setScope(newScope);
                  void loadCandidates({ scope: newScope });
                }}
                data-testid="p33t-scope-select"
                className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm"
                title="P33U = current pipeline candidates; legacy = P33S-C demo candidates; all = both"
              >
                <option value="P33U">Scope: P33U</option>
                <option value="legacy">Scope: legacy demo</option>
                <option value="all">Scope: all</option>
              </select>
              <Button variant="outline" size="sm" onClick={() => void applyFilter()}>
                Filter
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  setFilterSequence('');
                  setFilterModel('');
                  setLengthFilter('all');
                  setScope('P33U');
                  setTop4Only(false);
                  void loadCandidates({ scope: 'P33U', model: '', top4: false });
                }}
              >
                Reset
              </Button>
            </div>

            {/* P33U-D11: quick length-compliance / blocked-license filter chips. */}
            <div className="flex flex-wrap items-center gap-1.5" data-testid="p33t-quick-filters">
              {([
                { v: 'all', label: 'All lengths' },
                { v: '12aa', label: '12 aa compliant' },
                { v: '22aa', label: '22 aa deviation' },
              ] as const).map((opt) => (
                <Button
                  key={opt.v}
                  variant={lengthFilter === opt.v ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setLengthFilter(opt.v)}
                  data-testid={`p33t-length-filter-${opt.v}`}
                >
                  {opt.label}
                </Button>
              ))}
              <Button
                variant={isPpflowBlocked ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  setFilterModel('ppflow');
                  setLengthFilter('all');
                }}
                data-testid="p33t-blocked-license-filter"
              >
                Blocked License
              </Button>
              {/* P33U-D12: Top4 wet-lab shortlist filter. */}
              <Button
                variant={top4Only ? 'default' : 'outline'}
                size="sm"
                onClick={() => {
                  const next = !top4Only;
                  setTop4Only(next);
                  void loadCandidates({ top4: next });
                }}
                data-testid="p33t-top4-filter"
              >
                Top4 wet-lab
              </Button>
            </div>

            {error && (
              <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                {error}
              </div>
            )}

            {loading ? (
              <div className="space-y-2">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-full" />
              </div>
            ) : isPpflowBlocked ? (
              <p className="text-sm text-rose-700">
                No candidates available — PPFlow is license-blocked and does not generate candidates.
              </p>
            ) : visibleCandidates.length === 0 ? (
              <p className="text-sm text-slate-500">No candidates available.</p>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="p33t-candidate-table">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-slate-50 text-xs font-medium text-slate-500 uppercase">
                      <th className="px-3 py-2 text-left">ID</th>
                      <th className="px-3 py-2 text-left">Sequence</th>
                      <th className="px-3 py-2 text-right">Len</th>
                      <th className="px-3 py-2 text-left">Source</th>
                      <th className="px-3 py-2 text-left">Wet-lab</th>
                      <th className="px-3 py-2 text-right">Rank</th>
                      <th className="px-3 py-2 text-right">Score</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleCandidates.map((c) => (
                      <tr
                        key={c.candidate_id}
                        data-testid={`p33t-candidate-row-${c.candidate_id}`}
                        data-candidate-id={c.candidate_id}
                        onClick={() => setSelectedCandidateId(c.candidate_id)}
                        className={`cursor-pointer border-b border-slate-100 transition-colors ${
                          selectedCandidateId === c.candidate_id
                            ? 'bg-sky-50'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        <td className="px-3 py-2 text-xs font-mono text-slate-500">
                          {c.candidate_id}
                        </td>
                        <td className="px-3 py-2 font-mono font-medium text-slate-800">
                          {c.sequence}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                          {c.length}
                          {c.length !== TARGET_LENGTH && (
                            <Badge
                              variant="outline"
                              className="ml-1 text-xs border-amber-300 text-amber-700"
                              title={`protocol_length_deviation: actual ${c.length} aa, target ${TARGET_LENGTH} aa`}
                            >
                              len≠12
                            </Badge>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          <Badge variant="outline" className="text-xs">
                            {c.source_model_id}
                          </Badge>
                        </td>
                        <td className="px-3 py-2">
                          {c.wetlab_planned_status === 'PLANNED_WETLAB' ? (
                            <Badge
                              className="bg-sky-100 text-sky-800 text-xs"
                              data-testid={`p33t-wetlab-badge-${c.candidate_id}`}
                            >
                              PLANNED WETLAB
                            </Badge>
                          ) : (
                            <span className="text-xs text-slate-400">&mdash;</span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                          {c.generation_rank ?? '—'}
                        </td>
                        <td className="px-3 py-2 text-right tabular-nums text-slate-600">
                          {c.generation_score !== null && c.generation_score !== undefined
                            ? Number(c.generation_score).toFixed(4)
                            : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base font-semibold">
              <Beaker className="h-4 w-4" />
              Candidate details
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!selectedCandidate ? (
              <p className="text-sm text-slate-500">Select a candidate to view details.</p>
            ) : (
              <>
                {/* P33U-D11: explicit protocol-length fields for compliance audit. */}
                <div
                  className="mb-4 grid grid-cols-2 gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs sm:grid-cols-3"
                  data-testid="p33t-candidate-meta"
                >
                  <div>
                    <span className="text-slate-500">model:</span>{' '}
                    <span className="font-mono text-slate-800">{selectedCandidate.source_model_id}</span>
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <span className="text-slate-500">candidate_id:</span>{' '}
                    <span className="font-mono text-slate-800">{selectedCandidate.candidate_id}</span>
                  </div>
                  <div className="col-span-2 sm:col-span-1">
                    <span className="text-slate-500">sequence:</span>{' '}
                    <span className="font-mono text-slate-800">{selectedCandidate.sequence}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">actual_length:</span>{' '}
                    <span className="tabular-nums text-slate-800">{selectedCandidate.length}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">target_length:</span>{' '}
                    <span className="tabular-nums text-slate-800">{TARGET_LENGTH}</span>
                  </div>
                  <div>
                    <span className="text-slate-500">protocol_length_deviation:</span>{' '}
                    <Badge
                      variant="outline"
                      className={
                        selectedCandidate.length !== TARGET_LENGTH
                          ? 'ml-1 border-amber-300 text-amber-700'
                          : 'ml-1 border-emerald-300 text-emerald-700'
                      }
                    >
                      {selectedCandidate.length !== TARGET_LENGTH ? 'true' : 'false'}
                    </Badge>
                  </div>
                </div>

                {/* P33U-D12: pLDDT normalization + scoring summary + Top4 flag. */}
                {candidateDetail && (
                  <div className="mb-4 rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs" data-testid="p33t-d12-scoring">
                    {(() => {
                      const pn = candidateDetail.plddt_normalization as Record<string, unknown> | undefined;
                      const sc = candidateDetail.d12_scoring as Record<string, unknown> | undefined;
                      const isTop4 = candidateDetail.top4_wetlab_shortlist as boolean | undefined;
                      return (
                        <div className="space-y-1">
                          <p className="font-semibold text-sky-900">D12 scoring summary</p>
                          {pn ? (
                            <p className="text-slate-700">
                              pLDDT: raw {String(pn.plddt_raw)} ({String(pn.plddt_raw_scale)}) → normalized{' '}
                              <span className="font-mono font-medium">{String(pn.plddt_normalized_0_100)}</span>/100
                              {' '}({String(pn.plddt_source)})
                            </p>
                          ) : (
                            <p className="text-slate-500">pLDDT: not available (no per-residue confidence)</p>
                          )}
                          {sc && (
                            <p className="text-slate-700">
                              PRODIGY binding:{' '}
                              {sc.prodigy_binding_kcal_mol != null ? (
                                <span className="font-mono font-medium text-emerald-700">{String(sc.prodigy_binding_kcal_mol)} kcal/mol</span>
                              ) : (
                                <span className="text-amber-700">unavailable — {String(sc.prodigy_unavailable_with_reason)}</span>
                              )}
                            </p>
                          )}
                          {sc && (
                            <p className="text-slate-500">
                              scoring status: <span className="font-mono">{String(sc.scoring_status)}</span>
                              {' · '}MM/GBSA: {String(sc.mmgbsa_unavailable_with_reason)}
                            </p>
                          )}
                          <p>
                            Top4 wet-lab shortlist:{' '}
                            <Badge variant="outline" className={isTop4 ? 'border-emerald-300 text-emerald-700' : 'border-slate-300 text-slate-500'}>
                              {isTop4 ? 'YES' : 'no'}
                            </Badge>
                          </p>
                        </div>
                      );
                    })()}
                  </div>
                )}

                {/* P33U-D16: wet-lab plan (PLANNED WETLAB) for Top4 candidates. */}
                {candidateDetail && (() => {
                  const plan = candidateDetail.d16_wetlab_plan as Record<string, unknown> | undefined;
                  if (!plan || plan.wetlab_planned_status !== 'PLANNED_WETLAB') return null;
                  const assay = (plan.assay_status as Record<string, string>) ?? {};
                  return (
                    <div
                      className="mb-4 rounded-xl border border-sky-300 bg-sky-50 p-3 text-xs"
                      data-testid="p33t-d16-wetlab-plan"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <Beaker className="h-4 w-4 text-sky-700" />
                        <p className="font-semibold text-sky-900">
                          D16 wet-lab plan &mdash; PLANNED WETLAB
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sky-900 sm:grid-cols-3">
                        <div>tracking_status: <span className="font-mono">{String(plan.tracking_status)}</span></div>
                        <div>order_status: <span className="font-mono">{String(plan.order_status)}</span></div>
                        <div>sample_status: <span className="font-mono">{String(plan.sample_status)}</span></div>
                        <div>binding: <span className="font-mono">{String(assay.binding_assay_status)}</span></div>
                        <div>activity: <span className="font-mono">{String(assay.activity_assay_status)}</span></div>
                        <div>safety: <span className="font-mono">{String(assay.safety_assay_status)}</span></div>
                      </div>
                      <p className="mt-2 text-amber-800">
                        experimental_validation=false; pending_experiment=true; all assay fields not_started.
                        NOT_EXPERIMENTALLY_VALIDATED &middot; COMPUTATIONAL_PREDICTION_ONLY &middot; WETLAB_VALIDATION_PLANNED.
                      </p>
                    </div>
                  );
                })()}

                {/* P33U-D19: computational scoring capability (per-candidate). */}
                {candidateDetail && (() => {
                  const sc = candidateDetail.d19_scoring as Record<string, unknown> | undefined;
                  if (!sc) return null;
                  const scores = (sc.scores as Record<string, unknown>) ?? {};
                  const unavailable = (sc.unavailable as Record<string, string>) ?? {};
                  const fmt = (v: unknown) => (v === null || v === undefined || v === '') ? 'unavailable' : String(v);
                  return (
                    <div
                      className="mb-4 rounded-xl border border-violet-300 bg-violet-50 p-3 text-xs"
                      data-testid="p33t-d19-scoring"
                    >
                      <div className="mb-2 flex items-center gap-2">
                        <ScrollText className="h-4 w-4 text-violet-700" />
                        <p className="font-semibold text-violet-900">
                          D19 computational scoring &mdash; COMPUTATIONAL_PREDICTION_ONLY
                        </p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-violet-900 sm:grid-cols-3">
                        <div>PRODIGY &Delta;G: <span className="font-mono">{fmt(scores.prodigy_deltaG_kcal_mol)}</span> kcal/mol</div>
                        <div>Vina pose: <span className="font-mono">{fmt(scores.vina_pose_score_kcal_mol)}</span></div>
                        <div>OpenMM E: <span className="font-mono">{fmt(scores.openmm_final_energy_kj_mol)}</span> kJ/mol</div>
                        <div>MM-GBSA &Delta;G: <span className="font-mono">{fmt(scores.mmgbsa_deltaG_kcal_mol)}</span> kcal/mol</div>
                        <div>AF2 pLDDT: <span className="font-mono">{fmt(scores.af2_plddt)}</span></div>
                        <div>AF2 ipTM: <span className="font-mono">{fmt(scores.af2_iptm)}</span></div>
                      </div>
                      <p className="mt-2 text-violet-800">
                        Unavailable scorers: GNINA ({unavailable.gnina || 'unavailable_with_reason'}), PyRosetta ({unavailable.pyrosetta || 'blocked_license'}), HADDOCK/HDOCK ({unavailable.haddock || 'unavailable_with_reason'}), MIC ({unavailable.mic || 'unavailable_with_reason'}).
                      </p>
                      <p className="mt-1 text-amber-800">
                        Provenance: {String(sc.provenance || 'see /api/v1/p33s/scorer-availability')}. Docking score != Kd; pLDDT != affinity; PRODIGY &Delta;G predicted not measured; MM-GBSA rescoring not Kd. NOT_EXPERIMENTALLY_VALIDATED.
                      </p>
                    </div>
                  );
                })()}

                <Tabs defaultValue="metrics">
                  <TabsList className="mb-4">
                    <TabsTrigger value="metrics">
                      <ScrollText className="mr-1 h-3.5 w-3.5" />
                      Metrics
                    </TabsTrigger>
                    <TabsTrigger value="manifest">
                      <FileJson className="mr-1 h-3.5 w-3.5" />
                      Manifest
                    </TabsTrigger>
                    <TabsTrigger value="artifacts">
                      <FolderArchive className="mr-1 h-3.5 w-3.5" />
                      Artifacts
                    </TabsTrigger>
                    <TabsTrigger value="bundle">
                      <Package className="mr-1 h-3.5 w-3.5" />
                      Bundle
                    </TabsTrigger>
                  </TabsList>

                  <TabsContent value="metrics" className="space-y-4">
                    {metricsLoading ? (
                      <div className="space-y-2">
                        <Skeleton className="h-8 w-full" />
                        <Skeleton className="h-8 w-full" />
                        <Skeleton className="h-8 w-full" />
                      </div>
                    ) : metricsError ? (
                      <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                        {metricsError}
                      </div>
                    ) : metrics.length === 0 ? (
                      <p className="text-sm text-slate-500">No metrics recorded for this candidate.</p>
                    ) : (
                      <>
                        {availableMetrics.length > 0 && (
                          <div className="overflow-x-auto rounded-xl border border-slate-200" data-testid="p33t-metrics-table">
                            <table className="w-full text-sm">
                              <thead>
                                <tr className="bg-slate-50 text-xs font-medium text-slate-500 uppercase">
                                  <th className="px-3 py-2 text-left">Metric</th>
                                  <th className="px-3 py-2 text-right">Value</th>
                                  <th className="px-3 py-2 text-left">Scorer</th>
                                  <th className="px-3 py-2 text-left">License</th>
                                </tr>
                              </thead>
                              <tbody>
                                {availableMetrics.map((m) => (
                                  <tr key={m.metric_id} className="border-b border-slate-100">
                                    <td className="px-3 py-2 font-medium text-slate-800">
                                      {m.metric_name}
                                    </td>
                                    <td className="px-3 py-2 text-right tabular-nums text-slate-700">
                                      {formatMetricValue(m)}
                                    </td>
                                    <td className="px-3 py-2 text-slate-600">
                                      {m.scorer_name ?? '—'}
                                      {m.scorer_version ? ` (${m.scorer_version})` : ''}
                                    </td>
                                    <td className="px-3 py-2 text-slate-600">
                                      {m.scorer_license ?? '—'}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        )}

                        {unavailableMetrics.length > 0 && (
                          <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                            <p className="mb-2 text-sm font-semibold text-amber-900">
                              Unavailable metrics
                            </p>
                            <ul className="space-y-1">
                              {unavailableMetrics.map((m) => (
                                <li
                                  key={m.metric_id}
                                  className="flex items-start gap-2 text-sm text-amber-800"
                                >
                                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                                  <span>
                                    <span className="font-medium">{m.metric_name}</span>:{' '}
                                    {m.unavailable_with_reason}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </>
                    )}
                  </TabsContent>

                  <TabsContent value="manifest" className="space-y-4">
                    {manifestLoading ? (
                      <Skeleton className="h-40 w-full" />
                    ) : manifestError ? (
                      <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                        {manifestError}
                      </div>
                    ) : !manifest ? (
                      <p className="text-sm text-slate-500">No manifest available.</p>
                    ) : (
                      <>
                        <div className="flex flex-wrap gap-2 text-xs text-slate-600">
                          <Badge variant="outline">validation_status: {String(manifest.validation_status ?? 'NOT_EXPERIMENTALLY_VALIDATED')}</Badge>
                          <Badge variant="outline">
                            computational_prediction_only:{' '}
                            {String(manifest.computational_prediction_only ?? true)}
                          </Badge>
                          <Badge variant="outline">
                            experimental_validation: {String(manifest.experimental_validation ?? false)}
                          </Badge>
                        </div>
                        <pre className="max-h-96 overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700">
                          {JSON.stringify(manifest, null, 2)}
                        </pre>
                      </>
                    )}
                  </TabsContent>

                  <TabsContent value="artifacts" className="space-y-4">
                    {downloadError && (
                      <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                        {downloadError}
                      </div>
                    )}
                    {safeArtifacts.length === 0 ? (
                      <p className="text-sm text-slate-500">No whitelisted artifacts for this candidate.</p>
                    ) : (
                      <div className="space-y-2" data-testid="p33t-artifact-list">
                        {safeArtifacts.map((a) => (
                          <div
                            key={a.name}
                            data-testid={`p33t-artifact-row-${a.name}`}
                            className="flex items-center justify-between rounded-xl border border-slate-200 p-3"
                          >
                            <div className="min-w-0">
                              <p className="truncate text-sm font-medium text-slate-800">{a.name}</p>
                              {a.sha256 && (
                                <p className="truncate text-xs font-mono text-slate-500">
                                  {a.sha256}
                                </p>
                              )}
                            </div>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={downloadingArtifact === a.name}
                              onClick={() => void handleDownloadArtifact(a.name)}
                            >
                              {downloadingArtifact === a.name ? (
                                <RefreshCw className="mr-1 h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Download className="mr-1 h-3.5 w-3.5" />
                              )}
                              Download
                            </Button>
                          </div>
                        ))}
                      </div>
                    )}
                  </TabsContent>

                  <TabsContent value="bundle" className="space-y-4">
                    {bundleError && (
                      <div role="alert" className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                        {bundleError}
                      </div>
                    )}
                    <p className="text-sm text-slate-600">
                      Generate and download a delivery bundle containing selected candidates, metrics,
                      provenance, run manifests, and boundary notices. The bundle does not include
                      checkpoints, environments, or source code.
                    </p>
                    <Button
                      onClick={() => void handleCreateBundle()}
                      disabled={bundleLoading}
                    >
                      {bundleLoading ? (
                        <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                      ) : (
                        <Package className="mr-2 h-4 w-4" />
                      )}
                      Generate & download bundle
                    </Button>
                    {bundleId && (
                      <p className="text-xs text-slate-500">Last bundle: {bundleId}</p>
                    )}
                  </TabsContent>
                </Tabs>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
