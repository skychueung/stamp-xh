import { useState } from 'react';
import type { ReactNode, SVGProps } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { evobind2Api } from '@/lib/api/evobind2';
import { useAuth } from '@/contexts/AuthContext';
import type {
  EvoBind2DryRunResponse,
  EvoBind2JobResponse,
  EvoBind2ArtifactResponse,
  EvoBind2ArtifactItem,
  EvoBind2SafetyFlags,
  EvoBind2ProbeResponse,
  EvoBind2ProbeCheck,
} from '@/types/evobind2';
import {
  Atom,
  Play,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Activity,
  ShieldAlert,
  Ban,
  Info,
  Terminal,
  Code,
  FileText,
  FlaskConical,
  Folder,
  Cpu,
  Search,
  Download,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: ReactNode; label: string }> = {
  pending: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
  running: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Activity className="w-3 h-3" />, label: 'Running' },
  succeeded: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Succeeded' },
  failed: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
  blocked: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <ShieldAlert className="w-3 h-3" />, label: 'Blocked' },
  cancelled: { bg: 'bg-slate-50', text: 'text-slate-600', icon: <Ban className="w-3 h-3" />, label: 'Cancelled' },
  ready_for_dry_run: { bg: 'bg-violet-50', text: 'text-violet-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Ready for dry-run' },
  READY: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Ready' },
  BLOCKED: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <ShieldAlert className="w-3 h-3" />, label: 'Blocked' },
};

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  metrics: 'Metrics',
  pdb: 'Structure',
  log: 'Log',
  manifest: 'Manifest',
  input: 'Input',
  other: 'Other',
};

function SafetyFlagBadge({ name, value }: { name: string; value: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${
        value
          ? 'bg-amber-50 text-amber-700 border-amber-200'
          : 'bg-emerald-50 text-emerald-700 border-emerald-200'
      }`}
    >
      {value ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
      {name}: {value ? 'Yes' : 'No'}
    </span>
  );
}

function SafetyFlagsPanel({ flags }: { flags: EvoBind2SafetyFlags }) {
  return (
    <div className="flex flex-wrap gap-2">
      <SafetyFlagBadge name="Candidate generation" value={flags.is_candidate_generation} />
      <SafetyFlagBadge name="Scientific result" value={flags.is_scientific_result} />
      <SafetyFlagBadge name="Uses UniRef30" value={flags.uses_uniref30} />
      {typeof flags.requires_manual_review === 'boolean' && (
        <SafetyFlagBadge name="Requires manual review" value={flags.requires_manual_review} />
      )}
      {typeof flags.requires_real_validation === 'boolean' && (
        <SafetyFlagBadge name="Requires real validation" value={flags.requires_real_validation} />
      )}
    </div>
  );
}

function groupArtifactsByType(artifacts: EvoBind2ArtifactItem[]) {
  return artifacts.reduce<Record<string, EvoBind2ArtifactItem[]>>((acc, art) => {
    const type = art.artifact_type || 'other';
    acc[type] = acc[type] || [];
    acc[type].push(art);
    return acc;
  }, {});
}

export default function EvoBind2Page() {
  const { canSubmit } = useAuth();

  const [form, setForm] = useState({
    project_id: '',
    target_sequence: '',
    peptide_length: 10,
    peptide_sequence: '',
    model_name: 'model_1_ptm',
    msa_mode: 'single_sequence',
    max_recycles: 1,
    num_iterations: 1,
    use_gpu: true,
    selected_gpu: 'auto',
    receptor_msa_a3m: '',
  });

  const [dryRunResult, setDryRunResult] = useState<EvoBind2DryRunResponse | null>(null);
  const [jobResult, setJobResult] = useState<EvoBind2JobResponse | null>(null);
  const [artifacts, setArtifacts] = useState<EvoBind2ArtifactResponse | null>(null);

  const [isSubmittingDryRun, setIsSubmittingDryRun] = useState(false);
  const [isSubmittingJob, setIsSubmittingJob] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isLoadingArtifacts, setIsLoadingArtifacts] = useState(false);

  const [probe, setProbe] = useState<EvoBind2ProbeResponse | null>(null);
  const [isProbing, setIsProbing] = useState(false);
  const [probeError, setProbeError] = useState<string | null>(null);

  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const makeDryRunPayload = (): Parameters<typeof evobind2Api.createDryRun>[0] => ({
    run_id: `evobind2-${Date.now()}`,
    receptor_fasta: form.target_sequence,
    peptide_length: form.peptide_length,
    mode: 'predict_only',
    peptide_sequence: form.peptide_sequence.trim() || null,
    model_name: form.model_name,
    max_recycles: form.max_recycles,
    num_iterations: form.num_iterations,
    use_gpu: form.use_gpu,
    selected_gpu: form.selected_gpu,
    msa_mode: form.msa_mode,
    receptor_msa_a3m: form.receptor_msa_a3m.trim() || null,
  });

  const makeJobPayload = (): Parameters<typeof evobind2Api.submitJob>[0] => ({
    project_id: form.project_id,
    target_sequence: form.target_sequence,
    peptide_sequence: form.peptide_sequence.trim() || null,
    mode: 'predict_only',
    model_name: form.model_name,
    msa_mode: form.msa_mode,
    dry_run: false,
    max_recycles: form.max_recycles,
    num_iterations: form.num_iterations,
    use_gpu: form.use_gpu,
    selected_gpu: form.selected_gpu,
    receptor_msa_a3m: form.receptor_msa_a3m.trim() || null,
  });

  const handleProbe = async () => {
    try {
      setIsProbing(true);
      setProbeError(null);
      setProbe(null);
      const result = await evobind2Api.getProbe();
      setProbe(result);
    } catch (err: any) {
      setProbeError(err?.message || 'Probe failed.');
      setProbe(null);
    } finally {
      setIsProbing(false);
    }
  };

  const handleDryRun = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.target_sequence.trim()) {
      setError('Please enter a target protein sequence.');
      return;
    }
    try {
      setIsSubmittingDryRun(true);
      setError(null);
      setSuccess(null);
      setDryRunResult(null);
      const result = await evobind2Api.createDryRun(makeDryRunPayload());
      setDryRunResult(result);
      if (result.status === 'BLOCKED') {
        setSuccess('Dry-run planned but blocked — no commands were executed.');
      } else {
        setSuccess('Dry-run planned successfully — no commands were executed.');
      }
    } catch (err: any) {
      setDryRunResult(null);
      setError(err?.message || 'Failed to run dry-run.');
    } finally {
      setIsSubmittingDryRun(false);
    }
  };

  const handleSubmitJob = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.project_id.trim() || !form.target_sequence.trim()) {
      setError('Project ID and target sequence are required.');
      return;
    }
    try {
      setIsSubmittingJob(true);
      setError(null);
      setSuccess(null);
      setJobResult(null);
      setArtifacts(null);
      const job = await evobind2Api.submitJob(makeJobPayload());
      setJobResult(job);
      setSuccess(`Job submitted: ${job.job_id} — status is ${job.status}. Real execution is not enabled.`);
      loadArtifacts(job.job_id);
    } catch (err: any) {
      setJobResult(null);
      if (err?.status === 403) {
        setError(
          'EvoBind2 job endpoints are disabled in public-demo mode. Dry-run is still available below.'
        );
      } else {
        setError(err?.message || 'Failed to submit job.');
      }
    } finally {
      setIsSubmittingJob(false);
    }
  };

  const loadArtifacts = async (jobId: string) => {
    try {
      setIsLoadingArtifacts(true);
      const resp = await evobind2Api.getArtifacts(jobId);
      setArtifacts(resp);
    } catch (err: any) {
      // Artifact endpoint is also gated by compute endpoints; 403 is expected in public-demo.
      setArtifacts(null);
    } finally {
      setIsLoadingArtifacts(false);
    }
  };

  const handleCancel = async () => {
    if (!jobResult) return;
    if (!confirm(`Cancel job ${jobResult.job_id.slice(0, 8)}...?`)) return;
    try {
      setIsCancelling(true);
      setError(null);
      const resp = await evobind2Api.cancelJob(jobResult.job_id);
      setSuccess(`Job cancelled (was ${resp.previous_status}).`);
      const updated = await evobind2Api.getJob(jobResult.job_id);
      setJobResult(updated);
      loadArtifacts(updated.job_id);
    } catch (err: any) {
      setError(err?.message || 'Cancel failed.');
    } finally {
      setIsCancelling(false);
    }
  };

  const canCancel =
    jobResult && ['pending', 'running', 'blocked', 'ready_for_dry_run'].includes(jobResult.status) && canSubmit;

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Atom className="w-6 h-6 text-xh-primary" />
            EvoBind2 Targeted Peptide Design Dry-run
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Engineering dry-run for the EvoBind2 binder prediction pipeline. No real model is executed.
          </p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {success && (
          <div className="mb-6 p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-sm text-emerald-700 flex items-start gap-2">
            <CheckCircle2 className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {/* Probe Environment panel */}
        <div className="mb-6 bg-white rounded-xl border border-slate-200 shadow-sm p-5">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-xh-primary" />
              <h2 className="text-sm font-semibold text-slate-800">Probe Environment</h2>
            </div>
            <button
              type="button"
              onClick={handleProbe}
              disabled={isProbing}
              className="flex items-center gap-2 bg-white border border-xh-primary text-xh-primary py-1.5 px-3 rounded-md text-xs font-medium hover:bg-xh-primary/5 disabled:opacity-50 transition-colors"
            >
              {isProbing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
              Probe EvoBind2 Environment
            </button>
          </div>

          <p className="text-xs text-slate-500 mb-3">
            Probe performs read-only environment checks. It does not run EvoBind2, HHblits, MSA generation, candidate
            peptide generation, or PDB generation. Real-run remains blocked.
          </p>

          {probeError && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{probeError}</span>
            </div>
          )}

          {probe && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-500">Status</span>
                  <p className={`font-medium ${probe.status === 'AVAILABLE' ? 'text-emerald-700' : probe.status === 'DEGRADED' ? 'text-amber-700' : 'text-red-700'}`}>
                    {probe.status}
                  </p>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-500">Dry-run</span>
                  <p className={`font-medium ${probe.dry_run_status === 'READY_FOR_DRY_RUN' ? 'text-emerald-700' : 'text-rose-700'}`}>
                    {probe.dry_run_status}
                  </p>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-500">Real-run</span>
                  <p className="font-medium text-rose-700">{probe.real_run_status}</p>
                </div>
                <div className="bg-slate-50 rounded p-2">
                  <span className="text-slate-500">Install</span>
                  <p className="font-medium text-slate-700">{probe.install_status}</p>
                </div>
              </div>

              {probe.warnings.length > 0 && (
                <div className="bg-amber-50 rounded-lg p-3 border border-amber-200">
                  <h4 className="text-xs font-semibold text-amber-800 mb-1 flex items-center gap-1">
                    <AlertTriangle className="w-3.5 h-3.5" /> Warnings
                  </h4>
                  <ul className="list-disc list-inside text-xs text-amber-700 space-y-0.5">
                    {probe.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {probe.errors.length > 0 && (
                <div className="bg-red-50 rounded-lg p-3 border border-red-200">
                  <h4 className="text-xs font-semibold text-red-800 mb-1 flex items-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> Errors
                  </h4>
                  <ul className="list-disc list-inside text-xs text-red-700 space-y-0.5">
                    {probe.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div>
                <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> Checks ({probe.checks.length})
                </h4>
                <div className="overflow-x-auto rounded-lg border border-slate-200">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50 text-slate-600">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">Name</th>
                        <th className="text-left px-3 py-2 font-medium">Status</th>
                        <th className="text-left px-3 py-2 font-medium">Message</th>
                        <th className="text-left px-3 py-2 font-medium">Detail</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {probe.checks.map((check: EvoBind2ProbeCheck, idx: number) => (
                        <tr key={idx} className="hover:bg-slate-50">
                          <td className="px-3 py-2 font-mono text-slate-700">{check.name}</td>
                          <td className="px-3 py-2">
                            <span
                              className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium border ${
                                check.status === 'PASS'
                                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                                  : check.status === 'DEGRADED'
                                  ? 'bg-amber-50 text-amber-700 border-amber-200'
                                  : 'bg-red-50 text-red-700 border-red-200'
                              }`}
                            >
                              {check.status === 'PASS' ? <CheckCircle2 className="w-3 h-3" /> : check.status === 'DEGRADED' ? <AlertTriangle className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                              {check.status}
                            </span>
                          </td>
                          <td className="px-3 py-2 text-slate-600">{check.message}</td>
                          <td className="px-3 py-2 font-mono text-slate-500 break-all">{check.detail || '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {probe.gpu_devices.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                    <Cpu className="w-3.5 h-3.5" /> GPU Devices
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {probe.gpu_devices.map((gpu) => (
                      <span
                        key={gpu.id}
                        className="inline-flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium bg-slate-100 text-slate-700 border border-slate-200"
                      >
                        {gpu.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              <div>
                <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                  <ShieldAlert className="w-3.5 h-3.5" /> Safety Flags
                </h4>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(probe.safety_flags).map(([key, value]) => (
                    <span
                      key={key}
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium border ${
                        value
                          ? 'bg-amber-50 text-amber-700 border-amber-200'
                          : 'bg-emerald-50 text-emerald-700 border-emerald-200'
                      }`}
                    >
                      {value ? <AlertTriangle className="w-3 h-3" /> : <CheckCircle2 className="w-3 h-3" />}
                      {key}: {value ? 'Yes' : 'No'}
                    </span>
                  ))}
                </div>
                <p className="text-[10px] text-slate-400 mt-1">
                  All execution flags are expected to be No in this read-only probe.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Scientific boundary notice */}
        <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700 flex items-start gap-2">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Engineering dry-run only</p>
            <p className="text-xs mt-0.5 opacity-90">
              This page does not run the EvoBind2 model, does not generate candidate peptides, and does not
              produce experimental validation results. No Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF values
              are shown. Command and environment previews are internal engineering previews only.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Submit form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <FlaskConical className="w-4 h-4" /> EvoBind2 Input
              </h2>
              <form onSubmit={handleDryRun} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Project ID <span className="text-slate-400">(for job submit)</span>
                  </label>
                  <input
                    type="text"
                    value={form.project_id}
                    onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                    placeholder="e.g., proj-001"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Target protein sequence / FASTA *
                  </label>
                  <textarea
                    value={form.target_sequence}
                    onChange={(e) => setForm({ ...form, target_sequence: e.target.value })}
                    placeholder=">target
MTEYKLVVVGAGGVGKSALTIQLIQNHFVDEYDPTIEDSYRKQVVIDGETCLLDILDTAGQEEYSAMRDQYMRTGEGFLCVFAINNTKSFEDIHQYREQIKRVKDSDDVPMVLVGNKCDLAARTVESRQAQDLARSYGIPYIETSAKTRQGVEDAFYTLVREIRQHKLRKLNPPDESGPGCMSCKCVLS"
                    rows={6}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none font-mono"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Peptide length</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={form.peptide_length}
                      onChange={(e) => setForm({ ...form, peptide_length: Number(e.target.value) })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Model</label>
                    <select
                      value={form.model_name}
                      onChange={(e) => setForm({ ...form, model_name: e.target.value })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    >
                      <option value="model_1_ptm">model_1_ptm</option>
                      <option value="model_1">model_1</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Known peptide sequence <span className="text-slate-400">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={form.peptide_sequence}
                    onChange={(e) => setForm({ ...form, peptide_sequence: e.target.value })}
                    placeholder="Leave empty for de novo design preview"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">MSA mode</label>
                    <select
                      value={form.msa_mode}
                      onChange={(e) => setForm({ ...form, msa_mode: e.target.value })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    >
                      <option value="single_sequence">single_sequence</option>
                      <option value="precomputed_a3m">precomputed_a3m</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">GPU</label>
                    <select
                      value={form.selected_gpu}
                      onChange={(e) => setForm({ ...form, selected_gpu: e.target.value })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    >
                      <option value="auto">auto</option>
                      <option value="0">0</option>
                      <option value="1">1</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Max recycles</label>
                    <input
                      type="number"
                      min={1}
                      max={10}
                      value={form.max_recycles}
                      onChange={(e) => setForm({ ...form, max_recycles: Number(e.target.value) })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-700 mb-1">Iterations</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={form.num_iterations}
                      onChange={(e) => setForm({ ...form, num_iterations: Number(e.target.value) })}
                      className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Precomputed MSA (a3m) <span className="text-slate-400">(optional)</span>
                  </label>
                  <textarea
                    value={form.receptor_msa_a3m}
                    onChange={(e) => setForm({ ...form, receptor_msa_a3m: e.target.value })}
                    placeholder="Paste MSA content if msa_mode is precomputed_a3m"
                    rows={3}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none font-mono"
                  />
                </div>

                <div className="pt-2 space-y-2">
                  <button
                    type="submit"
                    disabled={isSubmittingDryRun}
                    className="w-full flex items-center justify-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
                  >
                    {isSubmittingDryRun ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                    Submit Dry-Run
                  </button>

                  <button
                    type="button"
                    onClick={handleSubmitJob}
                    disabled={isSubmittingJob || !canSubmit || !form.project_id.trim()}
                    className="w-full flex items-center justify-center gap-2 bg-white border border-xh-primary text-xh-primary py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/5 disabled:opacity-50 transition-colors"
                  >
                    {isSubmittingJob ? <Loader2 className="w-4 h-4 animate-spin" /> : <Atom className="w-4 h-4" />}
                    {canSubmit ? 'Submit as Job' : 'View Only'}
                  </button>
                </div>
              </form>
            </div>
          </div>

          {/* Results */}
          <div className="lg:col-span-2 space-y-6">
            {/* Dry-run result */}
            {dryRunResult && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                    <Terminal className="w-4 h-4" /> Dry-Run Plan
                  </h3>
                  {(() => {
                    const style = STATUS_STYLES[dryRunResult.status] || STATUS_STYLES.BLOCKED;
                    return (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                        {style.icon}
                        {style.label}
                      </span>
                    );
                  })()}
                </div>

                <div className="space-y-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">Run ID</span>
                      <p className="font-mono text-slate-700 truncate">{dryRunResult.run_id}</p>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">Mode</span>
                      <p className="text-slate-700">{dryRunResult.mode}</p>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">Model</span>
                      <p className="text-slate-700">{dryRunResult.model_name}</p>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">GPU</span>
                      <p className="text-slate-700">{dryRunResult.used_gpu ? dryRunResult.selected_gpu ?? 'auto' : 'CPU'}</p>
                    </div>
                  </div>

                  {dryRunResult.error_message && (
                    <div className="p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                      {dryRunResult.error_message}
                    </div>
                  )}

                  <div>
                    <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                      <Code className="w-3.5 h-3.5" /> Command Preview
                    </h4>
                    {dryRunResult.command_preview && dryRunResult.command_preview.length > 0 ? (
                      <div className="bg-slate-900 rounded-lg p-3 overflow-x-auto">
                        <code className="text-[11px] text-slate-100 font-mono whitespace-pre">
                          {dryRunResult.command_preview.join(' \\\n')}
                        </code>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">No command preview available.</p>
                    )}
                    <p className="text-[10px] text-slate-400 mt-1">Internal engineering preview only — not executed.</p>
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                      <Terminal className="w-3.5 h-3.5" /> Environment Preview
                    </h4>
                    {Object.keys(dryRunResult.env_preview).length > 0 ? (
                      <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                        <dl className="grid grid-cols-1 gap-1 text-[11px]">
                          {Object.entries(dryRunResult.env_preview).map(([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <dt className="font-mono text-slate-500 shrink-0">{k}=</dt>
                              <dd className="font-mono text-slate-700 break-all">{v}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">No environment preview available.</p>
                    )}
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                      <Folder className="w-3.5 h-3.5" /> Planned Artifacts
                    </h4>
                    {Object.keys(dryRunResult.artifacts).length > 0 ? (
                      <div className="bg-slate-50 rounded-lg p-3 border border-slate-200 space-y-1">
                        {Object.entries(dryRunResult.artifacts).map(([name, path]) => (
                          <div key={name} className="flex items-start gap-2 text-[11px]">
                            <FileText className="w-3 h-3 text-slate-400 mt-0.5 shrink-0" />
                            <div>
                              <span className="font-medium text-slate-700">{name}</span>
                              <p className="font-mono text-slate-500 break-all">{path || '-'}</p>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-slate-500">No artifact paths planned.</p>
                    )}
                    <p className="text-[10px] text-slate-400 mt-1">
                      These paths are planned only; no files are created in this skeleton phase.
                    </p>
                  </div>

                  <div>
                    <h4 className="text-xs font-semibold text-slate-700 mb-2 flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5" /> Safety Flags
                    </h4>
                    <SafetyFlagsPanel flags={dryRunResult.safety_flags} />
                  </div>
                </div>
              </div>
            )}

            {/* Job result */}
            {jobResult && (
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
                    <BriefcaseIcon className="w-4 h-4" /> Submitted Job
                  </h3>
                  {(() => {
                    const style = STATUS_STYLES[jobResult.status] || STATUS_STYLES.pending;
                    return (
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                        {style.icon}
                        {style.label}
                      </span>
                    );
                  })()}
                </div>

                <div className="space-y-3 text-xs">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">Job ID</span>
                      <p className="font-mono text-slate-700 break-all">{jobResult.job_id}</p>
                    </div>
                    <div className="bg-slate-50 rounded p-2">
                      <span className="text-slate-500">Project</span>
                      <p className="text-slate-700">{jobResult.project_id}</p>
                    </div>
                  </div>
                  {jobResult.message && (
                    <p className="text-slate-600">{jobResult.message}</p>
                  )}
                  {jobResult.error_message && (
                    <p className="text-red-600">{jobResult.error_message}</p>
                  )}
                  <div>
                    <span className="text-slate-500 block mb-1">Safety Flags</span>
                    <SafetyFlagsPanel flags={jobResult.safety_flags} />
                  </div>
                  {canCancel && (
                    <button
                      onClick={handleCancel}
                      disabled={isCancelling}
                      className="flex items-center gap-1 text-xs px-2 py-1 rounded border border-red-200 text-red-600 hover:bg-red-50 disabled:opacity-50"
                    >
                      {isCancelling ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
                      Cancel Job
                    </button>
                  )}
                </div>

                {isLoadingArtifacts && (
                  <div className="mt-4 flex items-center gap-2 text-xs text-slate-500">
                    <Loader2 className="w-3 h-3 animate-spin" /> Loading artifacts...
                  </div>
                )}

                {artifacts && (
                  <div className="mt-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="text-xs font-semibold text-slate-700 flex items-center gap-1">
                        <Folder className="w-3.5 h-3.5" /> Artifacts
                      </h4>
                      <span className="text-[10px] text-slate-500">
                        {artifacts.artifacts.filter((a) => a.exists).length} / {artifacts.artifacts.length} on disk
                      </span>
                    </div>

                    <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-[11px] text-amber-800">
                      <strong>{artifacts.validation_status}</strong> — {artifacts.safety_note}
                    </div>

                    {artifacts.artifacts.length === 0 ? (
                      <p className="text-xs text-slate-500">No artifacts exist on disk yet.</p>
                    ) : (
                      <div className="space-y-3">
                        {Object.entries(groupArtifactsByType(artifacts.artifacts)).map(([type, typeArtifacts]) => (
                          <div key={type}>
                            <h5 className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-1">
                              {ARTIFACT_TYPE_LABELS[type] || type}
                            </h5>
                            <div className="space-y-1">
                              {typeArtifacts.map((art) => (
                                <div
                                  key={art.name}
                                  className="flex items-start gap-2 text-[11px] bg-slate-50 rounded p-2 border border-slate-200"
                                >
                                  <FileText className="w-3 h-3 text-slate-400 mt-0.5 shrink-0" />
                                  <div className="flex-1 min-w-0">
                                    <p className="font-medium text-slate-700">{art.name}</p>
                                    <p className="font-mono text-slate-500 break-all">{art.path}</p>
                                  </div>
                                  <div className="flex items-center gap-2 shrink-0">
                                    <span
                                      className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                        art.exists
                                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                                          : 'bg-slate-100 text-slate-600 border border-slate-200'
                                      }`}
                                    >
                                      {art.exists ? 'Exists' : 'Planned'}
                                    </span>
                                    {art.exists && art.download_url && (
                                      <a
                                        href={art.download_url}
                                        download
                                        className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium bg-xh-primary/10 text-xh-primary border border-xh-primary/20 hover:bg-xh-primary/20"
                                      >
                                        <Download className="w-3 h-3" />
                                        Download
                                      </a>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                    <p className="text-[10px] text-slate-400 mt-2">
                      Only files that actually exist on the server are shown as Exists. Paths are internal relative
                      paths; server absolute paths are never exposed.
                    </p>
                  </div>
                )}
              </div>
            )}

            {!dryRunResult && !jobResult && (
              <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
                <Atom className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">Submit a dry-run to see the planned command and artifacts.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}

function BriefcaseIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <rect width="20" height="14" x="2" y="7" rx="2" ry="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  );
}
