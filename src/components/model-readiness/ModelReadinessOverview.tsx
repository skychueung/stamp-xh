import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Beaker,
  Clock,
  Eye,
  FileText,
  Filter,
  Gauge,
  Lock,
  Play,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from 'lucide-react';
import { modelRegistryApi } from '@/lib/api/modelRegistry';
import type {
  KnownEvidenceId,
  ModelDryRunResult,
  ModelEvidenceResponse,
  ModelProbeResult,
  ModelRegistryEntry,
} from '@/types/modelRegistry';

interface ModelReadinessOverviewProps {
  models: ModelRegistryEntry[];
  loading: boolean;
  error: string | null;
  onRefresh: () => void;
}

interface Filters {
  search: string;
  status: string;
  category: string;
  blocker: string;
}

const STATUS_TONE: Record<string, string> = {
  available: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  probed: 'bg-sky-50 text-sky-700 border-sky-200',
  installed: 'bg-violet-50 text-violet-700 border-violet-200',
  not_connected: 'bg-rose-50 text-rose-700 border-rose-200',
  planned: 'bg-slate-100 text-slate-700 border-slate-200',
  disabled: 'bg-gray-100 text-gray-600 border-gray-200',
  parked: 'bg-amber-50 text-amber-700 border-amber-200',
  pending_probe: 'bg-blue-50 text-blue-700 border-blue-200',
  pending_registry: 'bg-purple-50 text-purple-700 border-purple-200',
  smoke_rerun_verified: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  controlled_smoke_verified: 'bg-emerald-50 text-emerald-700 border-emerald-200',
};

const BLOCKER_TONE: Record<string, string> = {
  REAL_RUN_GATE_CLOSED: 'bg-amber-50 text-amber-700 border-amber-200',
  REAL_RUN_PUBLIC_DEMO_403: 'bg-rose-50 text-rose-700 border-rose-200',
  MINICLIP_CHECKPOINT_LICENSE_TOKEN: 'bg-rose-50 text-rose-700 border-rose-200',
  RUNNER_ADAPTER_PENDING: 'bg-slate-100 text-slate-700 border-slate-200',
  RUNNER_PENDING_REASONIX_DELTA_AUTH: 'bg-blue-50 text-blue-700 border-blue-200',
  P29G_C_SMOKE_AUTH_PENDING: 'bg-blue-50 text-blue-700 border-blue-200',
  EXPLICIT_REAL_RUN_AUTH_REQUIRED: 'bg-amber-50 text-amber-700 border-amber-200',
};

const READINESS_TONE: Record<string, string> = {
  smoke_rerun_verified: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  controlled_smoke_verified: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  adapter_retained_probe_ready: 'bg-sky-50 text-sky-700 border-sky-200',
  preflight_import_ok: 'bg-blue-50 text-blue-700 border-blue-200',
  preflight_import_checkpoint_ok: 'bg-blue-50 text-blue-700 border-blue-200',
  server_preflight_ready: 'bg-blue-50 text-blue-700 border-blue-200',
  lane_b_ready: 'bg-amber-50 text-amber-700 border-amber-200',
  pending_probe: 'bg-slate-100 text-slate-700 border-slate-200',
  pending_registry: 'bg-slate-100 text-slate-700 border-slate-200',
};

const GROUP_ORDER: Array<ModelRegistryEntry['product_group']> = [
  'available_five',
  'blocked',
  'backlog',
];

const GROUP_LABEL: Record<ModelRegistryEntry['product_group'], string> = {
  available_five: 'Available Models: 5',
  blocked: 'Blocked Models: 1',
  backlog: 'Roadmap / Backlog Models: 3',
  unknown: 'Unknown Group',
};

const GROUP_NOTE: Record<ModelRegistryEntry['product_group'], string> = {
  available_five: 'D18 authoritative status: closed and available for evidence/result viewing.',
  blocked: 'PPFlow: no upstream LICENSE / authorization unclear. No execution or checkpoint load.',
  backlog: 'Not closed. Roadmap display only.',
  unknown: '',
};

function formatTime(iso: string | null | undefined) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function getExecutionLockReason(model: ModelRegistryEntry) {
  if (model.real_run_enabled && !model.execution_locked) return 'Unlocked';
  if (model.blocker_code) return `Locked: ${model.blocker_code}`;
  if (model.product_group === 'blocked') return 'License blocked: no execution permitted';
  if (model.product_group === 'backlog') return 'Backlog: not closed';
  return 'Locked: real_run_enabled=false / execution_locked=true';
}

function capabilityList(model: ModelRegistryEntry) {
  const caps: { label: string; active: boolean }[] = [
    { label: 'Probe', active: model.supports_probe },
    { label: 'Dry Run', active: model.supports_dry_run },
    { label: 'Real Run', active: model.supports_real_run },
    { label: 'Structure', active: model.supports_structure_output },
    { label: 'Sequence', active: model.supports_sequence_output },
    { label: 'Ranking', active: model.supports_ranking },
  ];
  return caps;
}

function isModelSelectable(model: ModelRegistryEntry) {
  return model.ui_selectable && model.product_group === 'available_five';
}

export default function ModelReadinessOverview({
  models,
  loading,
  error,
  onRefresh,
}: ModelReadinessOverviewProps) {
  const [filters, setFilters] = useState<Filters>({
    search: '',
    status: 'all',
    category: 'all',
    blocker: 'all',
  });
  const [selectedModel, setSelectedModel] = useState<ModelRegistryEntry | null>(null);
  const [probeResult, setProbeResult] = useState<ModelProbeResult | null>(null);
  const [dryRunResult, setDryRunResult] = useState<ModelDryRunResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [dryRunning, setDryRunning] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [modelEvidence, setModelEvidence] = useState<ModelEvidenceResponse | null>(null);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const [evidenceError, setEvidenceError] = useState<string | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const canRealRun = selectedModel
    ? selectedModel.supports_real_run &&
      selectedModel.real_run_enabled &&
      !selectedModel.execution_locked
    : false;

  /** P33Q: only these evidence ids may be rendered/downloaded; unknown ids are dropped. */
  const KNOWN_EVIDENCE_IDS: readonly KnownEvidenceId[] = [
    'success_report',
    'execution_manifest',
    'result_manifest',
    'status',
    'reasonix_review',
    'artifacts_index',
    'delivery_manifest',
    'p3b_report',
    'p3c_report',
  ];

  const categories = useMemo(
    () => Array.from(new Set(models.map((m) => m.category))),
    [models]
  );
  const blockers = useMemo(
    () => Array.from(new Set(models.map((m) => m.blocker_code).filter(Boolean))) as string[],
    [models]
  );
  const statuses = useMemo(
    () => Array.from(new Set(models.map((m) => m.status))),
    [models]
  );

  const filteredModels = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return models.filter((m) => {
      if (q && !m.display_name.toLowerCase().includes(q) && !m.model_id.toLowerCase().includes(q)) {
        return false;
      }
      if (filters.status !== 'all' && m.status !== filters.status) return false;
      if (filters.category !== 'all' && m.category !== filters.category) return false;
      if (filters.blocker !== 'all' && m.blocker_code !== filters.blocker) return false;
      return true;
    });
  }, [models, filters]);

  const groupedModels = useMemo(() => {
    const map = new Map<ModelRegistryEntry['product_group'], ModelRegistryEntry[]>();
    GROUP_ORDER.forEach((g) => map.set(g, []));
    filteredModels.forEach((m) => {
      const group = m.product_group ?? 'unknown';
      if (!map.has(group)) map.set(group, []);
      map.get(group)!.push(m);
    });
    return Array.from(map.entries()).filter(([, list]) => list.length > 0);
  }, [filteredModels]);

  const handleProbe = async (modelId: string) => {
    setProbing(true);
    setDetailError(null);
    try {
      const result = await modelRegistryApi.probeModel(modelId);
      setProbeResult(result);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Probe failed');
    } finally {
      setProbing(false);
    }
  };

  const handleDryRun = async (model: ModelRegistryEntry) => {
    setDryRunning(true);
    setDetailError(null);
    try {
      const payload = {
        target_sequence: model.supports_structure_output
          ? '>target\nMKTIIALSYIFCLVFADYKDDDDK'
          : 'MKTIIALSYIFCLVFADYKDDDDK',
        peptide_length: 12,
        model_name: 'model_1_ptm',
        max_recycles: 1,
        num_iterations: 1,
        num_candidates: 3,
        max_length: 12,
        top_k: 3,
        device: 'auto' as const,
        seed: null,
        candidate_peptides: ['AAAAAA', 'GGGGGG'],
        target_pdb_path: undefined,
        pocket_residues: undefined,
        dry_run: true,
      };
      const result = await modelRegistryApi.dryRunModel(model.model_id, payload);
      setDryRunResult(result);
    } catch (err) {
      setDetailError(err instanceof Error ? err.message : 'Dry-run failed');
    } finally {
      setDryRunning(false);
    }
  };

  const openDetail = (model: ModelRegistryEntry) => {
    setSelectedModel(model);
    setProbeResult(null);
    setDryRunResult(null);
    setDetailError(null);
  };

  const closeDetail = () => {
    setSelectedModel(null);
    setProbeResult(null);
    setDryRunResult(null);
    setDetailError(null);
    setModelEvidence(null);
    setEvidenceLoading(false);
    setEvidenceError(null);
    setDownloadError(null);
  };

  useEffect(() => {
    if (!selectedModel) {
      setModelEvidence(null);
      setEvidenceLoading(false);
      setEvidenceError(null);
      setDownloadError(null);
      setDownloadingId(null);
      return;
    }
    let mounted = true;
    setEvidenceLoading(true);
    setEvidenceError(null);
    setModelEvidence(null);
    setDownloadError(null);
    modelRegistryApi
      .getModelEvidence(selectedModel.model_id)
      .then((resp) => {
        if (!mounted) return;
        setModelEvidence(resp);
        setEvidenceError(null);
      })
      .catch((err: unknown) => {
        if (!mounted) return;
        const e = err as { status?: number; message?: string };
        const detail = e?.message || 'Failed to load evidence.';
        setEvidenceError(e?.status ? `HTTP ${e.status}: ${detail}` : detail);
        setModelEvidence(null);
      })
      .finally(() => {
        if (mounted) setEvidenceLoading(false);
      });
    return () => { mounted = false; };
  }, [selectedModel]);

  const handleDownloadEvidence = async (evidenceId: string) => {
    if (!selectedModel) return;
    const modelId = selectedModel.model_id;
    setDownloadError(null);
    setDownloadingId(evidenceId);
    let objectUrl: string | null = null;
    try {
      const blob = await modelRegistryApi.downloadEvidenceBlob(modelId, evidenceId);
      objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `${modelId}_${evidenceId}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: unknown) {
      const e = err as { status?: number; message?: string };
      const detail = e?.message || 'Download failed.';
      setDownloadError(e?.status ? `HTTP ${e.status}: ${detail}` : detail);
    } finally {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setDownloadingId(null);
    }
  };

  const renderModelCard = (model: ModelRegistryEntry) => {
    const caps = capabilityList(model);
    const selectable = isModelSelectable(model);
    const locked = model.execution_locked || !model.real_run_enabled;

    return (
      <div
        key={model.model_id}
        className={`group relative rounded-3xl border bg-white p-5 shadow-sm transition ${
          selectable
            ? 'border-slate-200 hover:shadow-md'
            : 'border-slate-200 opacity-80'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{model.display_name}</h3>
            <p className="text-xs text-slate-500">{model.category}</p>
          </div>
          <span
            className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
              STATUS_TONE[model.status] ?? STATUS_TONE.disabled
            }`}
          >
            {model.status}
          </span>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2">
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              READINESS_TONE[model.readiness_level ?? ''] ??
              'bg-slate-100 text-slate-700 border-slate-200'
            }`}
          >
            {model.readiness_level ?? model.stage}
          </span>
          <span
            className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              BLOCKER_TONE[model.blocker_code ?? ''] ??
              'bg-slate-100 text-slate-700 border-slate-200'
            }`}
          >
            {model.blocker_code ?? 'No blocker recorded'}
          </span>
        </div>

        <div className="mt-4 grid grid-cols-3 gap-2">
          {caps.map(({ label, active }) => (
            <div
              key={label}
              className={`rounded-xl border px-2 py-1.5 text-center text-xs ${
                active
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-slate-200 bg-slate-50 text-slate-500'
              }`}
              title={label}
            >
              {label}
            </div>
          ))}
        </div>

        <div className="mt-4 space-y-1.5 text-xs text-slate-600">
          <div className="flex items-center gap-2">
            <Clock className="h-3.5 w-3.5 text-slate-400" />
            <span>Verified: {formatTime(model.last_verified_at)}</span>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="h-3.5 w-3.5 text-slate-400" />
            <span className="truncate" title={model.evidence_ref ?? ''}>
              {model.evidence_ref ?? 'No evidence ref'}
            </span>
          </div>
        </div>

        <div
          className={`mt-4 flex items-center gap-2 rounded-xl border px-3 py-2 text-xs ${
            locked
              ? 'border-rose-200 bg-rose-50 text-rose-700'
              : 'border-emerald-200 bg-emerald-50 text-emerald-700'
          }`}
        >
          <Lock className="h-3.5 w-3.5 shrink-0" />
          <span className="font-medium">Execution locked:</span>
          <span className="truncate">{getExecutionLockReason(model)}</span>
        </div>

        {!selectable && (
          <p className="mt-3 text-xs font-medium text-amber-700">
            {model.product_group === 'blocked'
              ? 'PPFlow ⚠ License Blocked — no upstream LICENSE / authorization unclear'
              : model.product_group === 'backlog'
              ? 'Roadmap / Backlog — no Run / Submit / Execute'
              : 'Not selectable'}
          </p>
        )}

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => openDetail(model)}
            className="inline-flex items-center gap-1.5 rounded-full bg-xh-primary px-3 py-1.5 text-xs font-medium text-white transition hover:bg-xh-primary/90"
          >
            <Eye className="h-3.5 w-3.5" />
            Details
          </button>
          <button
            type="button"
            onClick={() => handleProbe(model.model_id)}
            disabled={!model.supports_probe || probing || !selectable}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Search className="h-3.5 w-3.5" />
            Probe
          </button>
          <button
            type="button"
            onClick={() => handleDryRun(model)}
            disabled={!model.supports_dry_run || dryRunning || !selectable}
            className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Beaker className="h-3.5 w-3.5" />
            Dry Run
          </button>
        </div>

        <p className="mt-3 text-[10px] font-medium uppercase tracking-wider text-slate-400">
          Computational readiness only / NOT_EXPERIMENTALLY_VALIDATED
        </p>
      </div>
    );
  };

  return (
    <section className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Model Readiness Overview</h2>
            <p className="mt-1 text-sm text-slate-500">
              Live status of registered peptide design models. Real execution is locked for all
              models in this phase.
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? (
              <RefreshCw className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Refresh
          </button>
        </div>

        {error && (
          <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <span>Failed to load model registry: {error}</span>
            </div>
          </div>
        )}

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search model name..."
              value={filters.search}
              onChange={(e) => setFilters((f) => ({ ...f, search: e.target.value }))}
              className="w-full rounded-2xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
            />
          </div>

          <div className="relative">
            <Filter className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <select
              value={filters.status}
              onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value }))}
              className="w-full appearance-none rounded-2xl border border-slate-200 bg-white py-2.5 pl-9 pr-8 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
            >
              <option value="all">All statuses</option>
              {statuses.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Gauge className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <select
              value={filters.category}
              onChange={(e) => setFilters((f) => ({ ...f, category: e.target.value }))}
              className="w-full appearance-none rounded-2xl border border-slate-200 bg-white py-2.5 pl-9 pr-8 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
            >
              <option value="all">All categories</option>
              {categories.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <select
              value={filters.blocker}
              onChange={(e) => setFilters((f) => ({ ...f, blocker: e.target.value }))}
              className="w-full appearance-none rounded-2xl border border-slate-200 bg-white py-2.5 pl-9 pr-8 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
            >
              <option value="all">All blockers</option>
              {blockers.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-slate-500">
          <ShieldAlert className="h-3.5 w-3.5" />
          <span>All model outputs are computational predictions only.</span>
          <span className="font-medium text-rose-600">NOT_EXPERIMENTALLY_VALIDATED.</span>
        </div>
      </div>

      {loading && models.length === 0 && (
        <div className="flex items-center justify-center py-12 text-sm text-slate-500">
          <RefreshCw className="mr-2 h-4 w-4 animate-spin" />
          Loading model registry...
        </div>
      )}

      {!loading && filteredModels.length === 0 && (
        <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-500">
          No models match the current filters.
        </div>
      )}

      <div className="space-y-8">
        {groupedModels.map(([group, list]) => (
          <div key={group} className="space-y-4">
            <div className="flex flex-col gap-1 border-b border-slate-200 pb-2">
              <h3 className="text-base font-semibold text-slate-900">{GROUP_LABEL[group]}</h3>
              {GROUP_NOTE[group] && (
                <p className="text-xs text-slate-500">{GROUP_NOTE[group]}</p>
              )}
            </div>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {list.map((model) => renderModelCard(model))}
            </div>
          </div>
        ))}
      </div>

      {selectedModel && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center">
          <div className="max-h-[90vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-slate-200 bg-white shadow-2xl">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-100 bg-white px-6 py-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900">
                  {selectedModel.display_name}
                </h3>
                <p className="text-xs text-slate-500">{selectedModel.model_id}</p>
              </div>
              <button
                type="button"
                onClick={closeDetail}
                className="rounded-full p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-6 p-6">
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                <div className="flex items-start gap-2">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Scientific boundary</p>
                    <p>
                      {selectedModel.safety_note} Computational readiness only /{' '}
                      <span className="font-semibold">NOT_EXPERIMENTALLY_VALIDATED</span>.
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Product group</p>
                  <p className="text-sm font-medium text-slate-900">{selectedModel.product_group}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">UI execution state</p>
                  <p className="text-sm font-medium text-slate-900">{selectedModel.ui_execution_state}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Live status</p>
                  <p className="text-sm font-medium text-slate-900">{selectedModel.status}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Live stage</p>
                  <p className="text-sm font-medium text-slate-900">{selectedModel.stage}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Readiness gate</p>
                  <p className="text-sm font-medium text-slate-900">
                    {selectedModel.readiness_gate ?? '—'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Readiness level</p>
                  <p className="text-sm font-medium text-slate-900">
                    {selectedModel.readiness_level ?? '—'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Execution locked</p>
                  <p className="text-sm font-medium text-rose-700">
                    {selectedModel.execution_locked ? 'Yes' : 'No'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Real-run enabled</p>
                  <p className="text-sm font-medium text-slate-900">
                    {selectedModel.real_run_enabled ? 'Yes' : 'No'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Blocker code</p>
                  <p className="text-sm font-medium text-slate-900">
                    {selectedModel.blocker_code ?? '—'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Delivery status</p>
                  <p className="text-sm font-medium text-slate-900">
                    {selectedModel.delivery_status ?? '—'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Last verified</p>
                  <p className="text-sm font-medium text-slate-900">
                    {formatTime(selectedModel.last_verified_at)}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-xs text-slate-500">Evidence ref</p>
                  <p className="text-sm font-medium text-slate-900 break-all">
                    {selectedModel.evidence_ref ?? '—'}
                  </p>
                </div>
              </div>

              {(evidenceLoading || evidenceError || modelEvidence) && (
                <div className="rounded-xl border border-sky-200 bg-sky-50 p-3 text-sm text-slate-800">
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-slate-900">
                      Evidence center (computational only)
                    </p>
                    {modelEvidence && (
                      <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] font-medium uppercase text-slate-600">
                        {modelEvidence.availability}
                      </span>
                    )}
                  </div>
                  {evidenceLoading && (
                    <p className="mt-2 text-xs text-slate-500">Loading evidence…</p>
                  )}
                  {evidenceError && (
                    <p role="alert" className="mt-2 text-xs text-red-700">
                      Evidence load failed: {evidenceError}
                    </p>
                  )}
                  {downloadError && (
                    <p role="alert" className="mt-2 text-xs text-red-700">
                      Download failed: {downloadError}
                    </p>
                  )}
                  {modelEvidence && !evidenceLoading && !evidenceError && (
                    <>
                      {modelEvidence.evidence_ref && (
                        <p className="mt-2 break-all text-xs text-slate-600">
                          Evidence ref: {modelEvidence.evidence_ref}
                        </p>
                      )}
                      {modelEvidence.availability === 'unavailable' ||
                      modelEvidence.availability === 'pending' ? (
                        <p className="mt-2 text-xs text-slate-500">
                          No downloadable evidence bundle for this model in this phase.
                        </p>
                      ) : (
                        <>
                          {modelEvidence.stats && (
                            <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                              {Object.entries(modelEvidence.stats).map(([k, v]) => (
                                <span key={k}>
                                  {k}: {typeof v === 'number' ? v.toLocaleString() : String(v)}
                                </span>
                              ))}
                            </div>
                          )}
                          <div className="mt-2 space-y-1 text-xs break-all">
                            {modelEvidence.artifacts
                              .filter((a) => (KNOWN_EVIDENCE_IDS as readonly string[]).includes(a.id))
                              .map((a) => (
                                <p key={a.id}>{a.id} SHA: {a.sha256}</p>
                              ))}
                          </div>
                          <div className="mt-2 flex flex-wrap gap-2">
                            {modelEvidence.downloadable_ids
                              .filter((id): id is KnownEvidenceId =>
                                (KNOWN_EVIDENCE_IDS as readonly string[]).includes(id)
                              )
                              .map((id) => (
                                <button
                                  key={id}
                                  type="button"
                                  disabled={downloadingId === id}
                                  onClick={() => handleDownloadEvidence(id)}
                                  className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                                >
                                  {downloadingId === id ? 'Downloading…' : `Download ${id}`}
                                </button>
                              ))}
                          </div>
                        </>
                      )}
                      <p className="mt-2 text-xs text-amber-700">
                        NOT_EXPERIMENTALLY_VALIDATED. Execution locked; Real Run remains disabled.
                      </p>
                    </>
                  )}
                </div>
              )}

              <div>
                <p className="text-xs text-slate-500">Supported capabilities</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {capabilityList(selectedModel).map(({ label, active }) => (
                    <span
                      key={label}
                      className={`rounded-full border px-2.5 py-1 text-xs ${
                        active
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          : 'border-slate-200 bg-slate-50 text-slate-500'
                      }`}
                    >
                      {label}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <p className="text-xs text-slate-500">Output artifact types</p>
                <p className="mt-1 text-sm text-slate-700">
                  {selectedModel.output_artifact_types.length > 0
                    ? selectedModel.output_artifact_types.join(', ')
                    : 'None declared in this phase'}
                </p>
              </div>

              <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                <p className="font-medium">Next authorization required</p>
                <p>{selectedModel.next_authorization ?? selectedModel.activation_requirements ?? 'Explicit authorization required'}</p>
              </div>

              {detailError && (
                <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                  {detailError}
                </div>
              )}

              <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  onClick={() => handleProbe(selectedModel.model_id)}
                  disabled={!selectedModel.supports_probe || probing || !isModelSelectable(selectedModel)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-xh-primary px-3 py-2 text-xs font-medium text-white transition hover:bg-xh-primary/90 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  <Search className="h-3.5 w-3.5" />
                  {probing ? 'Probing...' : 'Run Probe'}
                </button>
                <button
                  type="button"
                  onClick={() => handleDryRun(selectedModel)}
                  disabled={!selectedModel.supports_dry_run || dryRunning || !isModelSelectable(selectedModel)}
                  className="inline-flex items-center gap-1.5 rounded-full bg-xh-primary px-3 py-2 text-xs font-medium text-white transition hover:bg-xh-primary/90 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  <Beaker className="h-3.5 w-3.5" />
                  {dryRunning ? 'Planning...' : 'Zero-Write Dry Run'}
                </button>
                <button
                  type="button"
                  disabled={!canRealRun}
                  className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-2 text-xs font-medium text-slate-400 disabled:cursor-not-allowed"
                >
                  <Play className="h-3.5 w-3.5" />
                  {canRealRun ? 'Real Run' : 'Real Run Locked'}
                </button>
                <button
                  type="button"
                  onClick={() =>
                    navigator.clipboard.writeText(
                      `Authorization request for ${selectedModel.display_name} (${selectedModel.model_id}): ${
                        selectedModel.next_authorization ??
                        selectedModel.activation_requirements ??
                        'explicit authorization required'
                      }`
                    )
                  }
                  className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-700 transition hover:bg-slate-50"
                >
                  <FileText className="h-3.5 w-3.5" />
                  Copy Auth Request ID
                </button>
              </div>

              {probeResult && probeResult.model_id === selectedModel.model_id && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-medium text-slate-700">Probe result</p>
                  <div className="mt-2 space-y-1 text-sm text-slate-700">
                    <p>
                      <span className="font-medium">Status:</span> {probeResult.status}
                    </p>
                    <p>{probeResult.message}</p>
                    <p className="text-xs text-slate-500">Probe time: {probeResult.probe_time}</p>
                  </div>
                  {Array.isArray(probeResult.detail?.checks) && (
                    <ul className="mt-3 space-y-1">
                      {(probeResult.detail?.checks as Array<{ name: string; status: string; message: string }>).map(
                        (check) => (
                          <li key={check.name} className="flex items-center gap-2 text-xs">
                            <span
                              className={`h-2 w-2 rounded-full ${
                                check.status === 'PASS' ? 'bg-emerald-500' : 'bg-rose-500'
                              }`}
                            />
                            <span className="text-slate-700">{check.message}</span>
                          </li>
                        )
                      )}
                    </ul>
                  )}
                  {selectedModel.model_id === 'pepflow' || selectedModel.model_id === 'pephar' ? (
                    probeResult.status !== 'controlled_smoke_verified' ? (
                      <p className="mt-2 text-xs font-medium text-amber-700">
                        Probe result is a preflight/import placeholder; it does not indicate a
                        successful model forward/sample run.
                      </p>
                    ) : (
                      <p className="mt-2 text-xs font-medium text-emerald-700">
                        P32B controlled smoke verified. Dummy sample/forward completed; outputs are
                        NOT_EXPERIMENTALLY_VALIDATED and real execution remains locked.
                      </p>
                    )
                  ) : null}
                </div>
              )}

              {dryRunResult && dryRunResult.model_id === selectedModel.model_id && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-xs font-medium text-slate-700">Zero-write dry-run result</p>
                  <div className="mt-2 space-y-1 text-sm text-slate-700">
                    <p>
                      <span className="font-medium">Status:</span> {dryRunResult.status}
                    </p>
                    {selectedModel.model_id === 'pepflow' ? (
                      <div className="space-y-1.5">
                        <p className="text-xs font-medium text-slate-600">Dummy 3-step sample</p>
                        <div className="flex flex-wrap gap-2">
                          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs">Step 1</span>
                          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs">Step 2</span>
                          <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs">Step 3</span>
                        </div>
                        <p className="text-xs text-slate-400">Sequence text hidden.</p>
                      </div>
                    ) : (
                      <p>{dryRunResult.message}</p>
                    )}
                    <p className="text-xs text-slate-500">
                      Validation: {dryRunResult.validation_status}
                    </p>
                  </div>
                  {dryRunResult.blocked_reasons && dryRunResult.blocked_reasons.length > 0 && (
                    <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
                      <p className="font-medium">Blocked reasons</p>
                      <ul className="mt-1 list-disc pl-4">
                        {dryRunResult.blocked_reasons.map((reason, idx) => (
                          <li key={idx}>{reason}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
