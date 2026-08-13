import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Atom,
  Beaker,
  Code,
  Download,
  Eye,
  FileDown,
  FlaskConical,
  Gauge,
  GitBranch,
  Loader2,
  Play,
  Search,
  ShieldAlert,
  Table,
  Terminal,
  Workflow,
} from 'lucide-react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { modelRegistryApi } from '@/lib/api/modelRegistry';
import { normalizeApiUrl } from '@/lib/api/normalizeUrl';
import ModelReadinessOverview from '@/components/model-readiness/ModelReadinessOverview';
import { P33TResultCenter } from '@/components/p33t/P33TResultCenter';
import { RunConsole } from '@/components/p33u/RunConsole';
import { StructureViewerPanel } from '@/components/structure/StructureViewerPanel';
import type {
  ModelArtifactItem,
  ModelDryRunResult,
  ModelJobStatus,
  ModelProbeResult,
  ModelRegistryEntry,
  ModelSubmitResponse,
  PepmlmCandidate,
  TargetDesignWorkflowPayload,
  TargetDesignWorkflowResult,
  WorkflowArtifactReference,
  WorkflowStep,
} from '@/types/modelRegistry';

const P3B_JOB_ID = 'b8ab6d11-5762-4bdf-a9db-6d30602637fd';

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
};

interface FormState {
  target_sequence: string;
  peptide_length: number;
  model_name: string;
  max_recycles: number;
  num_iterations: number;
  num_candidates: number;
  seed: number | '';
  device: 'auto' | 'cpu' | 'cuda';
  dry_run: boolean;
  candidate_peptides: string;
  top_k: number;
  generator_model: string;
  ranker_model: string;
  structure_model: string;
  target_pdb_path: string;
  pocket_residues: string;
}

const baseInitialForm: FormState = {
  target_sequence: '',
  peptide_length: 12,
  model_name: 'model_1_ptm',
  max_recycles: 1,
  num_iterations: 1,
  num_candidates: 3,
  seed: '',
  device: 'auto',
  dry_run: true,
  candidate_peptides: '',
  top_k: 3,
  generator_model: 'pepmlm',
  ranker_model: 'pepprclip',
  structure_model: 'evobind2',
  target_pdb_path: '',
  pocket_residues: '',
};

function getDefaultFormForModel(modelId: string): FormState {
  switch (modelId) {
    case 'pepmlm':
      return {
        ...baseInitialForm,
        target_sequence: '',
        peptide_length: 12,
        num_candidates: 3,
        seed: '',
        device: 'auto',
        dry_run: true,
      };
    case 'evobind2':
      return {
        ...baseInitialForm,
        target_sequence: '',
        peptide_length: 12,
        model_name: 'model_1_ptm',
        max_recycles: 1,
        num_iterations: 1,
        dry_run: true,
      };
    case 'diffpepbuilder':
    case 'pepflow':
    case 'pephar':
    case 'ppflow':
      return {
        ...baseInitialForm,
        target_sequence: '',
        peptide_length: 12,
        num_candidates: 3,
        num_iterations: 1,
        seed: '',
        device: 'auto',
        dry_run: true,
      };
    case 'pepprclip':
      return {
        ...baseInitialForm,
        target_sequence: '',
        candidate_peptides: '',
        top_k: 3,
        device: 'auto',
        dry_run: true,
      };
    case 'pepglad':
      return {
        ...baseInitialForm,
        target_sequence: '',
        target_pdb_path: '',
        pocket_residues: '',
        peptide_length: 12,
        num_candidates: 3,
        dry_run: true,
      };
    case 'rfpeptides':
    default:
      return { ...baseInitialForm, dry_run: true };
  }
}

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

const GROUP_DESCRIPTION: Record<ModelRegistryEntry['product_group'], string> = {
  available_five: 'D18 closed models. PepFlow is a 22aa deviation and is excluded from the 12aa main ranking.',
  blocked: 'PPFlow is display-only: no upstream LICENSE / authorization unclear. It cannot run or load a checkpoint.',
  backlog: 'Not closed. Roadmap display only; no Run / Submit / Execute controls.',
  unknown: '',
};

const ARTIFACT_LABEL: Record<string, string> = {
  'input/target.fasta': 'Target sequence input',
  'input/candidate_peptides.csv': 'Candidate peptides (CSV)',
  'input/target.pdb': 'Target structure (PDB)',
  'input/pocket.json': 'Pocket definition (JSON)',
  'output/candidate_sequences.csv': 'Candidate sequences (CSV)',
  'output/candidate_sequences.json': 'Candidate sequences (JSON)',
  'output/ranking.csv': 'PepPrCLIP ranking (CSV)',
  'output/scores.json': 'PepPrCLIP scores (JSON)',
  'output/generated_peptides.csv': 'Generated peptides (CSV)',
  'output/generated_structures': 'Generated structures (directory)',
  'output/pepglad_summary.json': 'PepGLAD summary (JSON)',
  'logs/run_stdout_stderr.log': 'Run log',
  'manifest/manifest_pre.json': 'Pre-run manifest',
  'manifest/manifest_post.json': 'Post-run manifest',
};

const WORKFLOW_SAFETY_NOTES = [
  'dry-run only',
  'no new peptide generated',
  'no real ranking generated',
  'no new structure generated',
  'computational prediction only',
  'NOT_EXPERIMENTALLY_VALIDATED',
];

const artifactStatusClass = (status: string) => {
  if (status === 'Exists') return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  if (status === 'Blocked') return 'border-rose-200 bg-rose-50 text-rose-700';
  return 'border-amber-200 bg-amber-50 text-amber-700';
};

const artifactActionLabel = (status: string) => {
  if (status === 'Exists') return 'Existing artifact';
  if (status === 'Blocked') return 'Blocked';
  if (status === 'Expected') return 'Expected / Not generated';
  return status;
};

function groupModelsByProductGroup(models: ModelRegistryEntry[]) {
  const map = new Map<ModelRegistryEntry['product_group'], ModelRegistryEntry[]>();
  GROUP_ORDER.forEach((g) => map.set(g, []));
  models.forEach((m) => {
    const group = m.product_group ?? 'unknown';
    if (!map.has(group)) map.set(group, []);
    map.get(group)!.push(m);
  });
  return Array.from(map.entries()).filter(([, list]) => list.length > 0);
}

export default function TargetedPeptideDesignCenterPage() {
  const [models, setModels] = useState<ModelRegistryEntry[]>([]);
  const [loadingModels, setLoadingModels] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);

  const [selectedModelId, setSelectedModelId] = useState<string>('pepmlm');
  const [probeResult, setProbeResult] = useState<ModelProbeResult | null>(null);
  const [probing, setProbing] = useState(false);
  const [probeError, setProbeError] = useState<string | null>(null);

  const [form, setForm] = useState<FormState>(baseInitialForm);
  const [dryRunResult, setDryRunResult] = useState<ModelDryRunResult | null>(null);
  const [dryRunning, setDryRunning] = useState(false);
  const [dryRunError, setDryRunError] = useState<string | null>(null);

  const [realRunResult, setRealRunResult] = useState<ModelSubmitResponse | null>(null);
  const [realRunning, setRealRunning] = useState(false);
  const [realRunError, setRealRunError] = useState<string | null>(null);

  const [workflowResult, setWorkflowResult] = useState<TargetDesignWorkflowResult | null>(null);
  const [workflowRunning, setWorkflowRunning] = useState(false);
  const [workflowError, setWorkflowError] = useState<string | null>(null);
  const [workflowExportError, setWorkflowExportError] = useState<string | null>(null);
  const [workflowDownloadError, setWorkflowDownloadError] = useState<string | null>(null);
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [downloadingRef, setDownloadingRef] = useState<string | null>(null);

  const [jobStatus, setJobStatus] = useState<ModelJobStatus | null>(null);
  const [pollingJob, setPollingJob] = useState(false);

  const [artifacts, setArtifacts] = useState<ModelArtifactItem[]>([]);
  const [artifactsStatus, setArtifactsStatus] = useState<string | null>(null);
  const [loadingArtifacts, setLoadingArtifacts] = useState(false);
  const [artifactsError, setArtifactsError] = useState<string | null>(null);
  const [candidates, setCandidates] = useState<PepmlmCandidate[]>([]);

  const selectedModel = useMemo(
    () => models.find((m) => m.model_id === selectedModelId) ?? null,
    [models, selectedModelId]
  );

  // Load models on mount.
  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      setLoadingModels(true);
      setModelsError(null);
      try {
        const response = await modelRegistryApi.getModels();
        if (cancelled) return;
        setModels(response.models);
      } catch (error) {
        if (cancelled) return;
        setModelsError(error instanceof Error ? error.message : 'Failed to load models');
      } finally {
        if (!cancelled) setLoadingModels(false);
      }
    }
    void loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  // Restore selected model from URL query string once models are loaded.
  useEffect(() => {
    if (models.length === 0) return;
    const params = new URLSearchParams(window.location.search);
    const modelFromUrl = params.get('model');
    if (modelFromUrl && models.some((m) => m.model_id === modelFromUrl)) {
      setSelectedModelId(modelFromUrl);
    }
  }, [models]);

  // Persist selected model in URL query string.
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    params.set('model', selectedModelId);
    window.history.replaceState(
      {},
      '',
      `${window.location.pathname}?${params.toString()}`
    );
  }, [selectedModelId]);

  // Reset form to sensible defaults whenever the selected model changes.
  useEffect(() => {
    setForm(getDefaultFormForModel(selectedModelId));
    // Clear stale results so the user does not see a different model's output.
    setProbeResult(null);
    setProbeError(null);
    setDryRunResult(null);
    setDryRunError(null);
    setRealRunResult(null);
    setRealRunError(null);
    setArtifacts([]);
    setArtifactsError(null);
    setCandidates([]);
  }, [selectedModelId]);

  const isActionable = Boolean(
    selectedModel &&
      selectedModel.ui_selectable &&
      selectedModel.product_group === 'available_five' &&
      (selectedModel.supports_probe || selectedModel.supports_dry_run)
  );
  const canProbe = Boolean(
    selectedModel &&
      selectedModel.ui_selectable &&
      selectedModel.product_group === 'available_five' &&
      selectedModel.supports_probe
  );
  const canDryRun = Boolean(
    selectedModel &&
      selectedModel.ui_selectable &&
      selectedModel.product_group === 'available_five' &&
      selectedModel.supports_dry_run &&
      form.dry_run
  );
  // P33K: real runs are gated unless both flags are explicitly true (never in this phase).
  const canRealRun = Boolean(
    selectedModel &&
      selectedModel.real_run_enabled === true &&
      selectedModel.execution_locked === false
  );

  const isPepMLM = selectedModelId === 'pepmlm';
  const isEvoBind2 = selectedModelId === 'evobind2';
  const isPepPrCLIP = selectedModelId === 'pepprclip';
  const isPepGLAD = selectedModelId === 'pepglad';
  const isAvailableSix = selectedModel?.product_group === 'available_five';
  const currentJobId = realRunResult?.job_id || dryRunResult?.run_id || null;

  const handleSelectModel = (modelId: string) => {
    setSelectedModelId(modelId);
  };

  const handleModelCardKeyDown = (
    event: React.KeyboardEvent<HTMLDivElement>,
    modelId: string
  ) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleSelectModel(modelId);
    }
  };

  const handleProbe = async () => {
    setProbing(true);
    setProbeError(null);
    setProbeResult(null);
    try {
      const result = await modelRegistryApi.probeModel(selectedModelId);
      setProbeResult(result);
    } catch (error) {
      setProbeError(error instanceof Error ? error.message : 'Probe failed');
    } finally {
      setProbing(false);
    }
  };

  const handleDryRun = async () => {
    setDryRunning(true);
    setDryRunError(null);
    setDryRunResult(null);
    try {
      const payload = {
        ...form,
        seed: form.seed === '' ? null : form.seed,
        target_pdb_path: form.target_pdb_path || undefined,
        pocket_residues: form.pocket_residues
          ? form.pocket_residues.split(/\r?\n|,/).map((s) => s.trim()).filter(Boolean)
          : undefined,
      };
      const result = await modelRegistryApi.dryRunModel(selectedModelId, payload);
      setDryRunResult(result);
    } catch (error) {
      setDryRunError(error instanceof Error ? error.message : 'Dry-run failed');
    } finally {
      setDryRunning(false);
    }
  };

  const handleWorkflowDryRun = async () => {
    setWorkflowRunning(true);
    setWorkflowError(null);
    setWorkflowResult(null);
    setWorkflowExportError(null);
    setWorkflowDownloadError(null);
    try {
      const { target_pdb_path, pocket_residues, ...rest } = form;
      const payload: TargetDesignWorkflowPayload = {
        target_sequence: rest.target_sequence,
        generator_model: rest.generator_model,
        ranker_model: rest.ranker_model,
        structure_model: rest.structure_model,
        num_candidates: rest.num_candidates,
        peptide_length: rest.peptide_length,
        top_k: rest.top_k,
        dry_run: true,
      };
      const result = await modelRegistryApi.workflowDryRun(payload);
      setWorkflowResult(result);
    } catch (error) {
      setWorkflowError(error instanceof Error ? error.message : 'Workflow dry-run failed');
    } finally {
      setWorkflowRunning(false);
    }
  };

  const downloadBlob = (blob: Blob, filename: string) => {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const handleExportJson = async () => {
    setWorkflowExportError(null);
    setExportingFormat('json');
    try {
      const workflowId = workflowResult?.workflow_id ?? 'latest';
      const response = await modelRegistryApi.exportWorkflowReportJson(workflowId);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Export failed (${response.status}): ${text}`);
      }
      const blob = await response.blob();
      const filename = workflowResult
        ? `${workflowResult.workflow_id}_dryrun_report.json`
        : 'target_design_dryrun_report.json';
      downloadBlob(blob, filename);
    } catch (error) {
      setWorkflowExportError(error instanceof Error ? error.message : 'Export JSON failed');
    } finally {
      setExportingFormat(null);
    }
  };

  const handleExportMarkdown = async () => {
    setWorkflowExportError(null);
    setExportingFormat('md');
    try {
      const workflowId = workflowResult?.workflow_id ?? 'latest';
      const response = await modelRegistryApi.exportWorkflowReportMarkdown(workflowId);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Export failed (${response.status}): ${text}`);
      }
      const blob = await response.blob();
      const filename = workflowResult
        ? `${workflowResult.workflow_id}_dryrun_report.md`
        : 'target_design_dryrun_report.md';
      downloadBlob(blob, filename);
    } catch (error) {
      setWorkflowExportError(error instanceof Error ? error.message : 'Export Markdown failed');
    } finally {
      setExportingFormat(null);
    }
  };

  const handleDownloadArtifact = async (artifactRef: string, filename: string) => {
    setWorkflowDownloadError(null);
    setDownloadingRef(artifactRef);
    try {
      const response = await modelRegistryApi.downloadWorkflowArtifact(artifactRef);
      if (!response.ok) {
        const text = await response.text();
        throw new Error(`Download failed (${response.status}): ${text}`);
      }
      const blob = await response.blob();
      downloadBlob(blob, filename);
    } catch (error) {
      setWorkflowDownloadError(error instanceof Error ? error.message : 'Download failed');
    } finally {
      setDownloadingRef(null);
    }
  };

  const loadArtifacts = async (jobId: string) => {
    if (!selectedModel) return;
    setLoadingArtifacts(true);
    setArtifactsError(null);
    setArtifacts([]);
    setArtifactsStatus(null);
    setCandidates([]);
    try {
      const response = await modelRegistryApi.getModelArtifacts(selectedModelId, jobId);
      setArtifacts(response.artifacts);
      setArtifactsStatus(response.status);
      await loadCandidates(response.artifacts);
    } catch (error) {
      setArtifactsError(error instanceof Error ? error.message : 'Failed to load artifacts');
    } finally {
      setLoadingArtifacts(false);
    }
  };

  const loadCandidates = async (artifactList: ModelArtifactItem[]) => {
    if (!isPepMLM) return;
    const jsonArtifact = artifactList.find(
      (a) => a.name === 'candidate_sequences.json' && a.exists
    );
    if (!jsonArtifact?.download_url) return;
    try {
      const url = normalizeApiUrl(jsonArtifact.download_url);
      if (!url) return;
      const response = await fetch(url);
      if (!response.ok) return;
      const data = (await response.json()) as { candidates?: PepmlmCandidate[] };
      setCandidates(data.candidates || []);
    } catch {
      setCandidates([]);
    }
  };

  const pollJobStatus = async (jobId: string) => {
    setPollingJob(true);
    try {
      const status = await modelRegistryApi.getModelJobStatus(selectedModelId, jobId);
      setJobStatus(status);
      if (status.status === 'succeeded' || status.status === 'failed') {
        await loadArtifacts(jobId);
      }
    } catch (error) {
      setRealRunError(error instanceof Error ? error.message : 'Failed to poll job status');
    } finally {
      setPollingJob(false);
    }
  };

  const handleRealRun = async () => {
    setRealRunning(true);
    setRealRunError(null);
    setRealRunResult(null);
    setJobStatus(null);
    try {
      const { target_pdb_path, pocket_residues, ...rest } = form;
      const payload = {
        ...rest,
        dry_run: false,
        seed: form.seed === '' ? null : form.seed,
      };
      const result = await modelRegistryApi.submitRealRun(selectedModelId, payload, true);
      setRealRunResult(result);
      if (result.job_id) {
        await pollJobStatus(result.job_id);
      }
    } catch (error) {
      setRealRunError(error instanceof Error ? error.message : 'Real run failed');
    } finally {
      setRealRunning(false);
    }
  };
  // Kept as an internal gated implementation only; D19-A intentionally exposes no Run control.
  void handleRealRun;
  void canRealRun;
  void realRunning;

  const handleViewArtifacts = async () => {
    const jobId = currentJobId || (isEvoBind2 ? P3B_JOB_ID : null);
    if (!jobId) {
      setArtifactsError('No job id available. Run a dry-run or real-run first.');
      return;
    }
    await loadArtifacts(jobId);
  };

  const pdbArtifact = useMemo(
    () => artifacts.find((a) => a.artifact_type === 'pdb' && a.exists) ?? null,
    [artifacts]
  );

  const pdbUrl = useMemo(() => {
    if (pdbArtifact?.download_url) {
      return normalizeApiUrl(pdbArtifact.download_url);
    }
    return null;
  }, [pdbArtifact]);

  const probeChecks = useMemo(() => {
    const raw = probeResult?.detail?.checks;
    if (Array.isArray(raw)) {
      return raw as Array<{ name: string; status: string; message: string }>;
    }
    return [];
  }, [probeResult]);

  const groupedModels = useMemo(() => groupModelsByProductGroup(models), [models]);

  const renderModelCard = (model: ModelRegistryEntry) => {
    const selected = model.model_id === selectedModelId;
    const selectable = model.ui_selectable && model.product_group === 'available_five';
    return (
      <div
        key={model.model_id}
        role="button"
        tabIndex={selectable ? 0 : -1}
        aria-pressed={selected}
        onClick={() => selectable && handleSelectModel(model.model_id)}
        onKeyDown={(e) => selectable && handleModelCardKeyDown(e, model.model_id)}
        className={`relative rounded-2xl border p-4 transition outline-none focus-visible:ring-2 focus-visible:ring-xh-primary/40 ${
          selected
            ? 'border-xh-primary bg-sky-50/60 ring-1 ring-xh-primary/30'
            : selectable
            ? 'border-slate-200 bg-white hover:border-xh-primary/50 hover:shadow-sm cursor-pointer'
            : 'border-slate-200 bg-slate-50 opacity-70 cursor-not-allowed'
        }`}
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">{model.display_name}</h3>
            <p className="text-xs text-slate-500">{model.category}</p>
          </div>
          <span
            className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${
              STATUS_TONE[model.status] ?? STATUS_TONE.disabled
            }`}
          >
            {model.status}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-1.5">
          {[
            { key: 'supports_probe', label: 'Probe' },
            { key: 'supports_dry_run', label: 'Dry' },
            { key: 'supports_real_run', label: 'Real' },
            { key: 'supports_sequence_output', label: 'Seq' },
            { key: 'supports_structure_output', label: 'Struct' },
            { key: 'supports_ranking', label: 'Rank' },
          ].map(({ key, label }) => {
            const active = Boolean(model[key as keyof ModelRegistryEntry]);
            return (
              <div
                key={key}
                className={`rounded-lg border px-1.5 py-1 text-center text-[10px] ${
                  active
                    ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                    : 'border-slate-200 bg-slate-50 text-slate-500'
                }`}
              >
                {label}
              </div>
            );
          })}
        </div>

        {model.product_group === 'backlog' && (
          <p className="mt-3 text-xs font-medium text-amber-700">
            Roadmap / Backlog — not closed
          </p>
        )}
        {model.product_group === 'blocked' && (
          <p className="mt-3 text-xs font-medium text-rose-700">
            PPFlow ⚠ License Blocked — Reason: no upstream LICENSE / authorization unclear
          </p>
        )}

        {selected && (
          <div className="absolute right-2 top-2 h-2 w-2 rounded-full bg-xh-primary" aria-hidden="true" />
        )}
      </div>
    );
  };

  return (
    <PlatformLayout>
      <div className="space-y-8 pb-12">
        { /* Header */ }
        <section className="relative overflow-hidden rounded-3xl border border-slate-200 bg-gradient-to-br from-[#0B1E2D] via-[#12354A] to-[#1F6C8B] text-white shadow-xl">
          <div className="absolute inset-0 opacity-20 bg-[radial-gradient(circle_at_top_right,_rgba(255,255,255,0.35),_transparent_40%),radial-gradient(circle_at_bottom_left,_rgba(255,255,255,0.12),_transparent_35%)]" />
          <div className="relative grid gap-6 p-8 lg:grid-cols-[1.4fr_0.8fr] lg:p-10">
            <div className="space-y-4">
              <div className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-xs font-medium uppercase tracking-[0.2em] text-white/80">
                <FlaskConical className="h-3.5 w-3.5" />
                P5C Model Registry
              </div>
              <div className="space-y-3">
                <h1 className="text-3xl font-semibold tracking-tight lg:text-4xl">
                  Unified Design Center
                </h1>
                <p className="max-w-3xl text-sm leading-6 text-white/80 lg:text-base">
                  Select a registered peptide design model, probe its environment, plan a dry-run,
                  run a gated real execution, and inspect computational artifacts.
                </p>
              </div>
            </div>
            <div className="rounded-3xl border border-white/15 bg-white/10 p-5 backdrop-blur-sm">
              <div className="flex items-center gap-2 text-sm font-semibold">
                <AlertTriangle className="h-4 w-4 text-amber-200" />
                Scientific Boundary
              </div>
              <p className="mt-3 text-sm leading-6 text-white/80">
                Real model execution is gated and disabled by default. All displayed sequences and
                artifacts are computational predictions only and NOT_EXPERIMENTALLY_VALIDATED.
              </p>
            </div>
          </div>
        </section>

        { /* Safety banner */ }
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
          <div className="flex flex-wrap items-center gap-3">
            <ShieldAlert className="h-5 w-5 shrink-0" />
            <div className="flex-1">
              <p className="font-medium">Safety notice</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-4">
                <li>Real-run is gated and disabled by default.</li>
                <li>
                  Available Models: 5 — PepMLM, DiffPepBuilder, PepHAR, PepFlow, EvoBind2.
                </li>
                <li>Blocked Models: 1 — PPFlow (no upstream LICENSE / authorization unclear).</li>
                <li>Backlog Models: 3 — PepPrCLIP, RFpeptides, PepGLAD.</li>
                <li>PepFlow is a closed 22aa deviation: viewable/queryable, but excluded from the 12aa main ranking.</li>
                <li>Dry-run mode plans the command but does not generate peptide candidates or write real artifacts.</li>
                <li>No Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF is reported as experimental validation.</li>
                <li>All result areas display NOT_EXPERIMENTALLY_VALIDATED.</li>
              </ul>
            </div>
          </div>
        </div>

        { /* P33U D20A Dev Run Console */ }
        <RunConsole />

        { /* P33T result delivery center */ }
        <P33TResultCenter />

        { /* Model Readiness Overview */ }
        <ModelReadinessOverview
          models={models}
          loading={loadingModels}
          error={modelsError}
          onRefresh={() => {
            setLoadingModels(true);
            setModelsError(null);
            modelRegistryApi
              .getModels()
              .then((response) => setModels(response.models))
              .catch((error) =>
                setModelsError(error instanceof Error ? error.message : 'Failed to load models')
              )
              .finally(() => setLoadingModels(false));
          }}
        />

        { /* One-click model switcher + capability panel + input panel */ }
        <section className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">One-click Model Switcher</h2>
              <p className="mt-1 text-sm text-slate-500">
                Click a card to switch the active model. The form resets to that model's defaults.
              </p>

              <div className="mt-4 space-y-6">
                {loadingModels && models.length === 0 && (
                  <p className="text-sm text-slate-500">Loading models...</p>
                )}
                {groupedModels.map(([group, list]) => (
                  <div key={group} className="space-y-3">
                    <div className="border-b border-slate-100 pb-1">
                      <h3 className="text-sm font-semibold text-slate-800">{GROUP_LABEL[group]}</h3>
                      <p className="text-xs text-slate-500">{GROUP_DESCRIPTION[group]}</p>
                    </div>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {list.map((model) => renderModelCard(model))}
                    </div>
                  </div>
                ))}
              </div>

              {modelsError && (
                <p className="mt-3 text-sm text-rose-600">{modelsError}</p>
              )}

              {selectedModel && (
                <div className="mt-5 space-y-4 rounded-2xl border border-slate-100 bg-slate-50 p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Status</span>
                    <span
                      className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                        STATUS_TONE[selectedModel.status] ?? STATUS_TONE.disabled
                      }`}
                    >
                      {selectedModel.status}
                    </span>
                  </div>
                  {selectedModel.status_reason && (
                    <p className="text-xs text-amber-700">Reason: {selectedModel.status_reason}</p>
                  )}
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Product group</span>
                    <span className="text-sm text-slate-600">{selectedModel.product_group}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Category</span>
                    <span className="text-sm text-slate-600">{selectedModel.category}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">Adapter</span>
                    <span className="text-sm text-slate-600">{selectedModel.adapter_id}</span>
                  </div>
                  <p className="text-sm text-slate-600">{selectedModel.description}</p>
                </div>
              )}
            </div>

            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">Capabilities</h2>
              {selectedModel ? (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {[
                    { key: 'supports_probe', label: 'Probe', icon: Search },
                    { key: 'supports_dry_run', label: 'Dry Run', icon: Beaker },
                    { key: 'supports_real_run', label: 'Real Run', icon: Play },
                    { key: 'supports_structure_output', label: 'Structure', icon: Atom },
                    { key: 'supports_sequence_output', label: 'Sequence', icon: Code },
                    { key: 'supports_ranking', label: 'Ranking', icon: Gauge },
                  ].map(({ key, label, icon: Icon }) => {
                    const active = Boolean(
                      selectedModel[key as keyof ModelRegistryEntry]
                    );
                    const gated = key === 'supports_real_run' && active && !selectedModel?.real_run_enabled;
                    const excluded = selectedModel.product_group !== 'available_five';
                    return (
                      <div
                        key={key}
                        className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-sm ${
                          active && !excluded
                            ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                            : 'border-slate-200 bg-slate-50 text-slate-500'
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                        {gated ? `${label} (gated)` : label}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-3 text-sm text-slate-500">Select a model to see capabilities.</p>
              )}

              {selectedModel && (
                <div className="mt-5 space-y-2 text-xs text-slate-600">
                  <p>
                    <span className="font-medium">Validation policy: </span>
                    {selectedModel.validation_policy}
                  </p>
                  <p>
                    <span className="font-medium">Real-run enabled: </span>
                    {selectedModel?.real_run_enabled ? 'Yes' : 'No'}
                  </p>
                  <p>
                    <span className="font-medium">Execution locked: </span>
                    {selectedModel?.execution_locked ? 'Yes' : 'No'}
                  </p>
                  <p>
                    <span className="font-medium">UI selectable: </span>
                    {selectedModel?.ui_selectable ? 'Yes' : 'No'}
                  </p>
                </div>
              )}
            </div>
          </div>

          { /* Input panel */ }
          <div className="space-y-6">
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="text-lg font-semibold text-slate-900">Unified Input Panel</h2>
              <p className="mt-1 text-sm text-slate-500">
                {isPepMLM
                  ? 'PepMLM dry-run preview and gated real-run: configure target and generation parameters.'
                  : isEvoBind2
                  ? 'EvoBind2 predict-only dry-run.'
                  : isPepPrCLIP
                  ? 'PepPrCLIP is excluded: ranking is blocked until the MiniCLIP checkpoint is available.'
                  : isPepGLAD
                  ? 'PepGLAD is a reserved placeholder: structure-conditioned codesign requires authorization and Reasonix GO.'
                  : isAvailableSix
                  ? `${selectedModel?.display_name} dry-run preview: configure target and generation parameters.`
                  : 'Select a supported model to configure inputs.'}
              </p>

              <div className="mt-5 grid gap-5">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-700">Target sequence (FASTA)</label>
                  <textarea
                    value={form.target_sequence}
                    onChange={(e) => setForm((f) => ({ ...f, target_sequence: e.target.value }))}
                    rows={4}
                    disabled={!isActionable}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100 disabled:text-slate-400"
                  />
                </div>

                {isPepMLM && (
                  <>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Number of candidates</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.num_candidates}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, num_candidates: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Peptide length</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.peptide_length}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, peptide_length: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Seed (optional)</label>
                        <input
                          type="number"
                          min={0}
                          value={form.seed}
                          onChange={(e) => {
                            const value = e.target.value;
                            setForm((f) => ({
                              ...f,
                              seed: value === '' ? '' : Number(value),
                            }));
                          }}
                          disabled={!isActionable}
                          placeholder="Leave empty for random"
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Device</label>
                        <select
                          value={form.device}
                          onChange={(e) =>
                            setForm((f) => ({
                              ...f,
                              device: e.target.value as FormState['device'],
                            }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        >
                          <option value="auto">auto</option>
                          <option value="cpu">cpu</option>
                          <option value="cuda">cuda</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}

                {isEvoBind2 && (
                  <>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Peptide length</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.peptide_length}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, peptide_length: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Model name</label>
                        <select
                          value={form.model_name}
                          onChange={(e) => setForm((f) => ({ ...f, model_name: e.target.value }))}
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        >
                          <option value="model_1_ptm">model_1_ptm</option>
                          <option value="model_1">model_1</option>
                        </select>
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Max recycles</label>
                        <input
                          type="number"
                          min={1}
                          max={10}
                          value={form.max_recycles}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, max_recycles: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Iterations</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.num_iterations}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, num_iterations: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>
                    </div>
                  </>
                )}

                {isAvailableSix && !isPepMLM && !isEvoBind2 && (
                  <>
                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Peptide length</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.peptide_length}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, peptide_length: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Number of candidates</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.num_candidates}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, num_candidates: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Iterations</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.num_iterations}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, num_iterations: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Seed (optional)</label>
                        <input
                          type="number"
                          min={0}
                          value={form.seed}
                          onChange={(e) => {
                            const value = e.target.value;
                            setForm((f) => ({
                              ...f,
                              seed: value === '' ? '' : Number(value),
                            }));
                          }}
                          disabled={!isActionable}
                          placeholder="Leave empty for random"
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Device</label>
                        <select
                          value={form.device}
                          onChange={(e) =>
                            setForm((f) => ({
                              ...f,
                              device: e.target.value as FormState['device'],
                            }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        >
                          <option value="auto">auto</option>
                          <option value="cpu">cpu</option>
                          <option value="cuda">cuda</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}

                {isPepPrCLIP && (
                  <>
                    <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
                      <p className="font-medium">缺少授权 checkpoint</p>
                      <p className="text-xs">
                        PepPrCLIP is excluded from the P33K product surface. Real ranking is gated
                        until the MiniCLIP checkpoint and license/token are available.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Candidate peptides (one per line or comma separated)
                      </label>
                      <textarea
                        value={form.candidate_peptides}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, candidate_peptides: e.target.value }))
                        }
                        rows={4}
                        disabled={!isActionable}
                        placeholder="Enter candidate peptides (one per line or comma separated)"
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100 disabled:text-slate-400"
                      />
                    </div>

                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Top-k ranked peptides</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.top_k}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, top_k: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Device</label>
                        <select
                          value={form.device}
                          onChange={(e) =>
                            setForm((f) => ({
                              ...f,
                              device: e.target.value as FormState['device'],
                            }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        >
                          <option value="auto">auto</option>
                          <option value="cpu">cpu</option>
                          <option value="cuda">cuda</option>
                        </select>
                      </div>
                    </div>
                  </>
                )}

                {isPepGLAD && (
                  <>
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
                      <p className="font-medium">Reserved placeholder</p>
                      <p className="text-xs">
                        PepGLAD requires new authorization and Reasonix GO before it can be used.
                        Inputs are shown for planning only.
                      </p>
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Target PDB path
                      </label>
                      <input
                        type="text"
                        value={form.target_pdb_path}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, target_pdb_path: e.target.value }))
                        }
                        disabled={!isActionable}
                        placeholder="Enter target PDB path (no server absolute path)"
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100 disabled:text-slate-400"
                      />
                    </div>

                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-700">
                        Pocket residues (one per line, e.g. A:45)
                      </label>
                      <textarea
                        value={form.pocket_residues}
                        onChange={(e) =>
                          setForm((f) => ({ ...f, pocket_residues: e.target.value }))
                        }
                        rows={3}
                        disabled={!isActionable}
                        placeholder="Enter pocket residues (one per line, e.g. A:45)"
                        className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100 disabled:text-slate-400"
                      />
                    </div>

                    <div className="grid gap-5 sm:grid-cols-2">
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Peptide length</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.peptide_length}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, peptide_length: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>

                      <div className="space-y-1.5">
                        <label className="text-sm font-medium text-slate-700">Number of samples</label>
                        <input
                          type="number"
                          min={1}
                          max={100}
                          value={form.num_candidates}
                          onChange={(e) =>
                            setForm((f) => ({ ...f, num_candidates: Number(e.target.value) }))
                          }
                          disabled={!isActionable}
                          className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20 disabled:bg-slate-100"
                        />
                      </div>
                    </div>
                  </>
                )}

                {!isAvailableSix && !isPepPrCLIP && !isPepGLAD && selectedModel && (
                  <p className="text-sm text-slate-500">
                    {selectedModel.display_name} is {selectedModel.product_group} and does not accept
                    inputs in this phase.
                  </p>
                )}

                <label className="flex items-center gap-2 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={form.dry_run}
                    onChange={(e) => setForm((f) => ({ ...f, dry_run: e.target.checked }))}
                    disabled={!isActionable}
                    className="h-4 w-4 rounded border-slate-300 text-xh-primary focus:ring-xh-primary"
                  />
                  Dry-run only (no real execution)
                </label>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <button
                  type="button"
                  onClick={handleProbe}
                  disabled={!canProbe || probing}
                  className="inline-flex items-center gap-2 rounded-full bg-xh-primary px-4 py-2.5 text-sm font-medium text-white transition hover:bg-xh-primary/90 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {probing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                  Probe
                </button>

                <button
                  type="button"
                  onClick={handleDryRun}
                  disabled={!canDryRun || dryRunning}
                  className="inline-flex items-center gap-2 rounded-full bg-xh-primary px-4 py-2.5 text-sm font-medium text-white transition hover:bg-xh-primary/90 disabled:cursor-not-allowed disabled:bg-slate-300"
                >
                  {dryRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <Beaker className="h-4 w-4" />}
                  Dry Run
                </button>

                <button
                  type="button"
                  onClick={handleViewArtifacts}
                  disabled={!isActionable || loadingArtifacts}
                  className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100"
                >
                  {loadingArtifacts ? <Loader2 className="h-4 w-4 animate-spin" /> : <Eye className="h-4 w-4" />}
                  View Artifacts
                </button>

                {selectedModel?.product_group === 'available_five' && (
                  <div className="flex flex-wrap gap-2 text-xs text-slate-700">
                    {['View candidates', 'View evidence', 'View scoring', 'View wet-lab plan'].map((label) => (
                      <span key={label} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2">{label}</span>
                    ))}
                  </div>
                )}
              </div>

              {!isActionable && selectedModel && (
                <p className="mt-3 text-sm text-rose-600">
                  {selectedModel.display_name} is {selectedModel.status}
                  {selectedModel.status_reason ? ` (${selectedModel.status_reason})` : ''} and{' '}
                  {selectedModel.product_group === 'blocked'
                    ? 'license blocked; no checkpoint load or execution is permitted'
                    : selectedModel.product_group === 'backlog'
                    ? 'is roadmap-only until closed'
                    : 'is not selectable'}. Select one of the five D18 closed models.
                </p>
              )}
              <p className="mt-3 text-xs text-amber-700">
                Run controls are intentionally hidden. Any future enablement requires: dev only, auth required,
                no PPFlow, no production 8001/8080, GPU usage warning, and a run_id plus gate JSON.
              </p>
            </div>
          </div>
        </section>

        { /* Results */ }
        <section className="grid gap-6 xl:grid-cols-2">
          {probeResult && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-2">
                <Search className="h-5 w-5 text-xh-primary" />
                <h3 className="text-lg font-semibold text-slate-900">Probe Result</h3>
              </div>
              <div className="mt-4 space-y-2 text-sm">
                <p>
                  <span className="font-medium">Status: </span>
                  {probeResult.status}
                </p>
                <p className="text-slate-600">{probeResult.message}</p>
                <p className="text-xs text-slate-400">Probe time: {probeResult.probe_time}</p>
                <p className="text-xs text-slate-500">Real-run gate: {selectedModel?.real_run_enabled ? 'Open' : 'Closed'}</p>
              </div>
              {probeChecks.length > 0 && (
                <ul className="mt-4 space-y-1.5">
                  {probeChecks.map((check) => (
                    <li key={check.name} className="flex items-center gap-2 text-xs">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          check.status === 'PASS' ? 'bg-emerald-500' : 'bg-rose-500'
                        }`}
                      />
                      <span className="text-slate-700">{check.message}</span>
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                <span className="font-semibold">NOT_EXPERIMENTALLY_VALIDATED</span> — Probe results
                are environment/readiness checks only and do not imply a successful model forward run.
              </div>
              {probeError && <p className="mt-3 text-sm text-rose-600">{probeError}</p>}
            </div>
          )}

          {dryRunResult && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-2">
                <Beaker className="h-5 w-5 text-xh-primary" />
                <h3 className="text-lg font-semibold text-slate-900">Dry-Run Result</h3>
              </div>
              <div className="mt-4 space-y-2 text-sm">
                <p>
                  <span className="font-medium">Status: </span>
                  {dryRunResult.status}
                </p>
                <p className="text-slate-600">{dryRunResult.message}</p>
                <p className="text-xs text-slate-500">
                  Validation: {dryRunResult.validation_status}
                </p>
              </div>

              <div className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
                <div className="flex items-start gap-2">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Dry-run only / NOT_EXPERIMENTALLY_VALIDATED</p>
                    <p>
                      No peptide candidates are generated in dry-run mode. The command preview and
                      artifact paths are for planning only.
                    </p>
                  </div>
                </div>
              </div>

              {dryRunResult.command_preview && dryRunResult.command_preview.length > 0 && (
                <div className="mt-4 rounded-xl bg-slate-900 p-4 text-xs text-slate-50">
                  <div className="mb-2 flex items-center gap-1 text-slate-400">
                    <Terminal className="h-3 w-3" /> Command preview
                  </div>
                  <code className="block whitespace-pre-wrap break-all">
                    {dryRunResult.command_preview.join(' ')}
                  </code>
                </div>
              )}

              {dryRunResult.env_preview && Object.keys(dryRunResult.env_preview).length > 0 && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-medium text-slate-700">Environment preview</p>
                  <dl className="mt-2 grid gap-1 text-xs text-slate-600">
                    {Object.entries(dryRunResult.env_preview).map(([key, value]) => (
                      <div key={key} className="grid grid-cols-[1fr_2fr] gap-2">
                        <dt className="font-medium">{key}</dt>
                        <dd className="break-all">{value}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {dryRunResult.blocked_reasons && dryRunResult.blocked_reasons.length > 0 && (
                <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                  <p className="font-medium">Blocked reasons</p>
                  <ul className="mt-1 list-disc space-y-0.5 pl-4">
                    {dryRunResult.blocked_reasons.map((reason, idx) => (
                      <li key={idx}>{reason}</li>
                    ))}
                  </ul>
                </div>
              )}

              {dryRunResult.environment_summary && Object.keys(dryRunResult.environment_summary).length > 0 && (
                <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xs font-medium text-slate-700">Environment summary</p>
                  <dl className="mt-2 grid gap-1 text-xs text-slate-600">
                    {Object.entries(dryRunResult.environment_summary).map(([key, value]) => (
                      <div key={key} className="grid grid-cols-[1fr_2fr] gap-2">
                        <dt className="font-medium">{key}</dt>
                        <dd className="break-all">{String(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </div>
              )}

              {dryRunResult.artifacts && Object.keys(dryRunResult.artifacts).length > 0 && (
                <div className="mt-5">
                  <h4 className="text-sm font-medium text-slate-900">Expected artifacts (dry-run preview)</h4>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    {Object.entries(dryRunResult.artifacts).map(([key, path]) => (
                      <div
                        key={key}
                        className="flex flex-col gap-1 rounded-2xl border border-slate-200 bg-slate-50 p-4"
                      >
                        <span className="text-xs font-medium text-slate-700">
                          {ARTIFACT_LABEL[key] ?? key}
                        </span>
                        <span className="break-all text-[10px] text-slate-500">{path}</span>
                        <span className="mt-1 w-fit rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                          Not generated in dry-run
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {dryRunError && <p className="mt-3 text-sm text-rose-600">{dryRunError}</p>}
            </div>
          )}

          {realRunResult && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center gap-2">
                <Play className="h-5 w-5 text-rose-600" />
                <h3 className="text-lg font-semibold text-slate-900">Real-Run Result</h3>
              </div>
              <div className="mt-4 space-y-2 text-sm">
                <p>
                  <span className="font-medium">Status: </span>
                  {realRunResult.status}
                </p>
                <p className="text-slate-600">{realRunResult.message}</p>
                {realRunResult.job_id && (
                  <p className="text-xs text-slate-500">Job ID: {realRunResult.job_id}</p>
                )}
                {jobStatus?.status && (
                  <p className="text-xs text-slate-500">Worker status: {jobStatus.status}</p>
                )}
              </div>

              <div className="mt-4 rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                <div className="flex items-start gap-2">
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <div>
                    <p className="font-medium">Computational prediction only / NOT_EXPERIMENTALLY_VALIDATED</p>
                    <p>
                      These candidate sequences are model outputs and are
                      NOT_EXPERIMENTALLY_VALIDATED. They must not be interpreted as
                      experimentally confirmed binding peptides.
                    </p>
                  </div>
                </div>
              </div>

              {pollingJob && (
                <div className="mt-4 flex items-center gap-2 text-xs text-slate-600">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Updating artifacts...
                </div>
              )}
              {realRunError && <p className="mt-3 text-sm text-rose-600">{realRunError}</p>}
            </div>
          )}
        </section>

        { /* Structure viewer */ }
        <StructureViewerPanel
          title="P3B EvoBind2 Structure"
          pdbUrl={pdbUrl}
          pdbArtifact={pdbArtifact}
        />

        { /* Candidate sequences */ }
        {isPepMLM && candidates.length > 0 && (
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-2">
              <Table className="h-5 w-5 text-xh-primary" />
              <h3 className="text-lg font-semibold text-slate-900">Candidate Sequences</h3>
            </div>
            <p className="mt-1 text-xs text-slate-500">Job ID: {currentJobId}</p>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="border-b border-slate-200">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">candidate_id</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">sequence</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">length</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">source_model</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">job_id</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">validation_status</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-700">safety_note</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {candidates.map((candidate, idx) => (
                    <tr key={candidate.candidate_id || idx}>
                      <td className="px-3 py-2 font-mono text-xs text-slate-700">
                        {candidate.candidate_id}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-900">
                        {candidate.sequence}
                      </td>
                      <td className="px-3 py-2 text-slate-600">
                        {candidate.length ?? candidate.peptide_length}
                      </td>
                      <td className="px-3 py-2 text-slate-600">{candidate.source_model}</td>
                      <td className="px-3 py-2 font-mono text-xs text-slate-500">{candidate.job_id}</td>
                      <td className="px-3 py-2">
                        <span className="rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-medium text-amber-700">
                          {candidate.validation_status}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-xs text-slate-500">{candidate.safety_note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        { /* Artifacts */ }
        {(artifacts.length > 0 || loadingArtifacts || artifactsError) && (
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center gap-2">
              <Download className="h-5 w-5 text-xh-primary" />
              <h3 className="text-lg font-semibold text-slate-900">Artifacts</h3>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              Job ID: {currentJobId || (isEvoBind2 ? P3B_JOB_ID : 'none')} · Status: {artifactsStatus ?? 'unknown'}
            </p>

            {artifactsError && <p className="mt-3 text-sm text-rose-600">{artifactsError}</p>}

            <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {artifacts.map((artifact) => (
                <div
                  key={artifact.name}
                  className="flex flex-col gap-2 rounded-2xl border border-slate-200 p-4"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-900">{artifact.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                        artifact.exists
                          ? 'bg-emerald-50 text-emerald-700'
                          : 'bg-rose-50 text-rose-700'
                      }`}
                    >
                      {artifact.exists ? 'Exists' : 'Missing'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500">{artifact.path}</p>
                  <p className="text-xs text-slate-400">{artifact.size_bytes.toLocaleString()} bytes</p>
                  {artifact.download_url && artifact.exists && (
                    <a
                      href={normalizeApiUrl(artifact.download_url) ?? '#'}
                      download
                      className="mt-1 inline-flex items-center gap-1 text-xs font-medium text-xh-primary hover:underline"
                    >
                      <Download className="h-3 w-3" /> Download
                    </a>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Workflow dry-run section (P7B/P7C) */}
        <section className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <div className="flex items-center gap-2">
                <Workflow className="h-5 w-5 text-xh-primary" />
                <h2 className="text-lg font-semibold text-slate-900">Workflow Plan</h2>
              </div>
              <p className="mt-1 text-sm text-slate-500">
                PepMLM → PepPrCLIP → EvoBind2 → Molstar dry-run planning only.
                No model is executed; command previews are shown for operator review.
              </p>
              <p className="mt-2 text-xs text-slate-500">
                <span className="font-medium text-amber-700">Checkpoint blocked:</span>{' '}
                PepPrCLIP MiniCLIP checkpoint is missing (license/token required). Real ranking is gated.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {WORKFLOW_SAFETY_NOTES.map((note) => (
                <span
                  key={note}
                  className="rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-800"
                >
                  {note}
                </span>
              ))}
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="space-y-1">
              <label className="text-xs font-medium text-slate-600">target_sequence</label>
              <textarea
                value={form.target_sequence}
                onChange={(e) => setForm((f) => ({ ...f, target_sequence: e.target.value }))}
                rows={4}
                className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">num_candidates</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={form.num_candidates}
                  onChange={(e) => setForm((f) => ({ ...f, num_candidates: Number(e.target.value) }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">peptide_length</label>
                <input
                  type="number"
                  min={1}
                  max={200}
                  value={form.peptide_length}
                  onChange={(e) => setForm((f) => ({ ...f, peptide_length: Number(e.target.value) }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">top_k</label>
                <input
                  type="number"
                  min={1}
                  max={100}
                  value={form.top_k}
                  onChange={(e) => setForm((f) => ({ ...f, top_k: Number(e.target.value) }))}
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-xh-primary focus:ring-2 focus:ring-xh-primary/20"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium text-slate-600">models</label>
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                  {form.generator_model} → {form.ranker_model} → {form.structure_model}
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={handleWorkflowDryRun}
              disabled={workflowRunning}
              className="inline-flex items-center gap-2 rounded-xl bg-xh-primary px-4 py-2 text-sm font-medium text-white hover:bg-xh-primary/90 disabled:opacity-50"
            >
              {workflowRunning ? <Loader2 className="h-4 w-4 animate-spin" /> : <GitBranch className="h-4 w-4" />}
              Dry-run workflow
            </button>

            <button
              type="button"
              onClick={handleExportJson}
              disabled={exportingFormat === 'json'}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {exportingFormat === 'json' ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="h-4 w-4" />
              )}
              Export JSON
            </button>

            <button
              type="button"
              onClick={handleExportMarkdown}
              disabled={exportingFormat === 'md'}
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
            >
              {exportingFormat === 'md' ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <FileDown className="h-4 w-4" />
              )}
              Export Markdown
            </button>
          </div>

          <p className="text-xs text-slate-500">
            Export JSON/Markdown generates a dry-run report. No ranking score, Kd, MIC, or experimental metric is included.
          </p>

          {workflowError && <p className="text-sm text-rose-600">{workflowError}</p>}
          {workflowExportError && <p className="text-sm text-rose-600">{workflowExportError}</p>}

          {workflowResult && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-medium ${
                      workflowResult.status === 'READY'
                        ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                        : 'border-amber-200 bg-amber-50 text-amber-700'
                    }`}
                  >
                    {workflowResult.status}
                  </span>
                  <span className="font-mono text-xs text-slate-500">{workflowResult.workflow_id}</span>
                  <span className="rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-600">
                    {workflowResult.validation_status}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-700">{workflowResult.message}</p>
                {workflowResult.blocked_reasons.length > 0 && (
                  <p className="mt-2 text-sm font-medium text-amber-800">
                    MiniCLIP checkpoint missing / BLOCKED_LICENSE_OR_TOKEN_REQUIRED
                  </p>
                )}
              </div>

              <div>
                <p className="text-sm font-medium text-slate-700">Workflow steps</p>
                <div className="mt-3 grid gap-3 lg:grid-cols-2">
                  {workflowResult.steps.map((step: WorkflowStep) => (
                    <div key={step.step_id} className="rounded-2xl border border-slate-200 p-4 text-sm">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <p className="font-medium text-slate-900">{step.name}</p>
                          <p className="font-mono text-xs text-slate-500">{step.model_id}</p>
                        </div>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${
                            step.status === 'READY'
                              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                              : 'border-rose-200 bg-rose-50 text-rose-700'
                          }`}
                        >
                          {step.status}
                        </span>
                      </div>
                      <p className="mt-2 text-slate-600">{step.message}</p>
                      {step.blocked_reason && (
                        <p className="mt-2 rounded-xl border border-rose-200 bg-rose-50 p-2 text-xs font-medium text-rose-700">
                          {step.blocked_reason}
                        </p>
                      )}
                      {step.command_preview && step.command_preview.length > 0 && (
                        <div className="mt-3 rounded-xl bg-slate-900 p-3 text-xs text-slate-50">
                          <div className="mb-1 flex items-center gap-1 text-slate-400">
                            <Terminal className="h-3 w-3" /> command_preview
                          </div>
                          <code className="block whitespace-pre-wrap break-all">
                            {step.command_preview.join(' ')}
                          </code>
                        </div>
                      )}
                      <div className="mt-3 space-y-1">
                        <p className="text-xs font-medium text-slate-700">expected_artifacts</p>
                        {Object.entries(step.expected_artifacts || step.artifacts).map(([key, value]) => (
                          <div key={key} className="rounded-xl bg-slate-50 p-2 text-xs">
                            <span className="font-medium text-slate-700">{key}</span>
                            {value && <span className="block break-all text-slate-500">{value}</span>}
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <Download className="h-5 w-5 text-xh-primary" />
                    <h3 className="text-lg font-semibold text-slate-900">Result Center Lineage</h3>
                  </div>
                </div>
                <p className="mt-1 text-sm text-slate-500">
                  Existing historical artifacts are marked Exists; dry-run outputs are Expected or Blocked.
                </p>
                <p className="mt-2 text-xs text-slate-500">
                  A safe export bundle (README + reports + whitelisted artifacts + checksums) is available on the server;
                  see the P7D report for path and manifest.
                </p>

                {workflowDownloadError && (
                  <div className="mt-3 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-700">
                    {workflowDownloadError}
                  </div>
                )}

                <div className="mt-3 grid gap-3 lg:grid-cols-3">
                  {workflowResult.artifact_references.map((artifact: WorkflowArtifactReference) => {
                    const downloadable = artifact.status === 'Exists' && artifact.download_url;
                    const artifactRef = artifact.download_url
                      ? artifact.download_url.split('/artifacts/')[1]?.split('/download')[0]
                      : null;
                    const filenameMap: Record<string, string> = {
                      'p5c-candidates-csv': 'P5C_candidate_sequences.csv',
                      'p5c-candidates-json': 'P5C_candidate_sequences.json',
                      'p3b-pdb': 'P3B_unrelaxed_true.pdb',
                    };
                    return (
                      <div
                        key={`${artifact.model_id}-${artifact.artifact_name}-${artifact.status}`}
                        className="rounded-2xl border border-slate-200 p-4"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-medium text-slate-900">{artifact.label}</p>
                            <p className="font-mono text-xs text-slate-500">{artifact.model_id}</p>
                          </div>
                          <span className={`rounded-full border px-2 py-0.5 text-[10px] font-medium ${artifactStatusClass(artifact.status)}`}>
                            {artifactActionLabel(artifact.status)}
                          </span>
                        </div>
                        {artifact.job_id && <p className="mt-2 font-mono text-xs text-slate-500">job_id: {artifact.job_id}</p>}
                        {artifact.artifact_path && <p className="mt-2 break-all text-xs text-slate-500">{artifact.artifact_path}</p>}
                        {artifact.reason && <p className="mt-2 text-xs text-slate-600">{artifact.reason}</p>}
                        <p className="mt-2 text-[11px] font-medium text-amber-700">{artifact.validation_status}</p>

                        {downloadable && artifactRef && (
                          <button
                            type="button"
                            onClick={() =>
                              handleDownloadArtifact(
                                artifactRef,
                                filenameMap[artifactRef] || artifact.artifact_name
                              )
                            }
                            disabled={downloadingRef === artifactRef}
                            className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-xh-primary hover:underline disabled:text-slate-400"
                          >
                            {downloadingRef === artifactRef ? (
                              <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                              <Download className="h-3 w-3" />
                            )}
                            Download {artifact.artifact_name}
                          </button>
                        )}

                        {artifact.status === 'Blocked' && (
                          <p
                            className="mt-3 text-[11px] font-medium text-rose-600"
                            title="PepPrCLIP real ranking is blocked because the MiniCLIP checkpoint is not available (HuggingFace license/token required). ranking.csv and scores.json are not generated."
                          >
                            Download blocked: MiniCLIP checkpoint missing
                          </p>
                        )}

                        {artifact.status === 'Expected' && (
                          <p className="mt-3 text-[11px] font-medium text-amber-700">
                            Not generated in dry-run
                          </p>
                        )}

                        {artifact.download_url && artifact.status === 'Exists' && artifact.model_id === 'evobind2' && (
                          <a
                            href={normalizeApiUrl(artifact.download_url) ?? '#'}
                            className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-xh-primary hover:underline"
                          >
                            <Eye className="h-3 w-3" /> View in Molstar
                          </a>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <p className="text-sm font-medium text-slate-700">Workflow expected lineage</p>
                <div className="mt-2 grid gap-2 sm:grid-cols-2">
                  {Object.entries(workflowResult.expected_artifacts).map(([key, value]) => (
                    <div key={key} className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-xs">
                      <div className="flex items-center gap-2 font-medium text-slate-700">
                        <Code className="h-3.5 w-3.5" />
                        {key}
                      </div>
                      {value && <p className="mt-1 break-all text-slate-500">{value}</p>}
                      <span className="mt-2 inline-flex rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-800">
                        Expected / Not generated
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-rose-300 bg-white px-2 py-0.5 text-[10px] font-semibold text-rose-700">
                    NOT_EXPERIMENTALLY_VALIDATED
                  </span>
                  <p className="font-medium">Scientific boundary</p>
                </div>
                <p className="mt-1">
                  No PepMLM rerun, no PepPrCLIP ranking, no EvoBind2 run, no ranking.csv, no scores.json,
                  no new PDB, and no Kd / MIC / MM-GBSA / ipTM / pLDDT / RMSD / RMSF is produced or implied.
                  Computational prediction only.
                </p>
              </div>
            </div>
          )}
        </section>
      </div>
    </PlatformLayout>
  );
}
