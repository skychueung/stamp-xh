import { useEffect, useState } from 'react';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { productionMdApi } from '@/lib/api/productionMd';
import { useAuth } from '@/contexts/AuthContext';
import type { ProductionMDJob, ProductionMDDurationInfo, MdPilotProbeResponse } from '@/types/productionMd';
import {
  Atom,
  Play,
  Loader2,
  AlertTriangle,
  Clock,
  CheckCircle2,
  XCircle,
  Activity,
  ShieldAlert,
  Info,
} from 'lucide-react';

const STATUS_STYLES: Record<string, { bg: string; text: string; icon: React.ReactNode; label: string }> = {
  PENDING: { bg: 'bg-amber-50', text: 'text-amber-700', icon: <Clock className="w-3 h-3" />, label: 'Pending' },
  RUNNING: { bg: 'bg-blue-50', text: 'text-blue-700', icon: <Activity className="w-3 h-3" />, label: 'Running' },
  SUCCEEDED: { bg: 'bg-emerald-50', text: 'text-emerald-700', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Succeeded' },
  FAILED: { bg: 'bg-red-50', text: 'text-red-700', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
  BLOCKED: { bg: 'bg-rose-50', text: 'text-rose-700', icon: <ShieldAlert className="w-3 h-3" />, label: 'Blocked' },
  CANCELLED: { bg: 'bg-slate-50', text: 'text-slate-600', icon: <XCircle className="w-3 h-3" />, label: 'Cancelled' },
};

export default function ProductionMDPage() {
  const { canSubmit } = useAuth();
  const [durations, setDurations] = useState<ProductionMDDurationInfo[]>([]);
  const [jobs, setJobs] = useState<ProductionMDJob[]>([]);
  const [isLoadingDurations, setIsLoadingDurations] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [probeResult, setProbeResult] = useState<MdPilotProbeResponse | null>(null);
  const [isProbing, setIsProbing] = useState(false);

  const [form, setForm] = useState({
    project_id: '',
    candidate_id: '',
    duration_ns: 10,
    topology_path: '',
    coordinates_path: '',
    server_host: '',
    priority: 0,
  });

  useEffect(() => {
    loadDurations();
    loadProbe();
  }, []);

  const loadDurations = async () => {
    try {
      setIsLoadingDurations(true);
      const resp = await productionMdApi.listDurations();
      setDurations(resp.details);
    } catch (err: any) {
      setError(err?.message || 'Failed to load durations');
    } finally {
      setIsLoadingDurations(false);
    }
  };

  const loadProbe = async () => {
    try {
      setIsProbing(true);
      const resp = await productionMdApi.probeEnvironment();
      setProbeResult(resp);
    } catch (err: any) {
      setProbeResult(null);
    } finally {
      setIsProbing(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.project_id.trim() || !form.candidate_id.trim() || !form.topology_path.trim() || !form.coordinates_path.trim()) {
      setError('Please fill in all required fields.');
      return;
    }
    try {
      setIsSubmitting(true);
      setError(null);
      setSuccess(null);
      const job = await productionMdApi.createJob({
        project_id: form.project_id,
        candidate_id: form.candidate_id,
        duration_ns: form.duration_ns,
        topology_path: form.topology_path,
        coordinates_path: form.coordinates_path,
        server_host: form.server_host || null,
        priority: form.priority,
      });

      // Optionally auto-submit to server
      const submitResp = await productionMdApi.submitJob(job.job_id);

      if (submitResp.status === 'BLOCKED') {
        setSuccess(`Job created (${job.duration_ns} ns) but blocked: ${submitResp.detail}`);
      } else {
        setSuccess(`Job created and submitted: ${job.job_id} (${job.duration_ns} ns)`);
      }

      setJobs((prev) => [job, ...prev]);
    } catch (err: any) {
      const msg = err?.message || 'Failed to submit job';
      if (msg.includes('422') || msg.includes('duration')) {
        setError(`Invalid parameters: unsupported duration or missing fields. Supported: 1, 5, 10, 50 ns.`);
      } else if (msg.includes('BLOCKED') || msg.includes('unreachable')) {
        setError(`Server or compute environment unreachable. Job queued as BLOCKED.`);
      } else {
        setError(msg);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PlatformLayout>
      <div className="max-w-5xl mx-auto px-6 py-8">
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-slate-900 flex items-center gap-2">
            <Atom className="w-6 h-6 text-xh-primary" />
            Production Molecular Dynamics
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Submit GROMACS production MD runs (1–50 ns). Results are parsed from real server artifacts only.
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

        {/* Scientific boundary notice */}
        <div className="mb-6 p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-700 flex items-start gap-2">
          <Info className="w-4 h-4 mt-0.5 shrink-0" />
          <div>
            <p className="font-medium">Scientific Boundary</p>
            <p className="text-xs mt-0.5 opacity-90">
              RMSD, RMSF, MM-GBSA, and ΔG values are only shown after real production MD completes.
              No fabricated metrics will be displayed.
            </p>
          </div>
        </div>

        {/* Environment Probe */}
        {probeResult && (
          <div className="mb-6 bg-white rounded-xl border border-slate-200 shadow-sm p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-slate-800">Compute Environment</h3>
              <button
                onClick={loadProbe}
                disabled={isProbing}
                className="text-xs px-2 py-1 bg-slate-100 hover:bg-slate-200 rounded text-slate-600 transition-colors disabled:opacity-50"
              >
                {isProbing ? 'Checking...' : 'Refresh'}
              </button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {[
                { name: 'stamp-md env', ok: probeResult.stamp_md_env_available },
                { name: 'GROMACS', ok: probeResult.gromacs_available, detail: probeResult.gromacs_version },
                { name: 'GPU', ok: probeResult.gpu_available },
                { name: 'MDAnalysis', ok: probeResult.mdanalysis_available },
                { name: 'OpenMM', ok: probeResult.openmm_available },
                { name: 'ParmEd', ok: probeResult.parmed_available },
                { name: 'Amber', ok: probeResult.amber_available },
                { name: 'MM-GBSA', ok: probeResult.mmgbsa_available, detail: probeResult.mmgbsa_version },
              ].map((tool) => (
                <div
                  key={tool.name}
                  className={`flex items-center gap-1.5 px-2 py-1.5 rounded text-xs font-medium ${
                    tool.ok
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                      : 'bg-red-50 text-red-700 border border-red-200'
                  }`}
                  title={tool.detail || undefined}
                >
                  {tool.ok ? (
                    <CheckCircle2 className="w-3 h-3 shrink-0" />
                  ) : (
                    <XCircle className="w-3 h-3 shrink-0" />
                  )}
                  <span className="truncate">{tool.name}</span>
                </div>
              ))}
            </div>
            {probeResult.blocking_reasons.length > 0 && (
              <div className="mt-3 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                {probeResult.blocking_reasons.map((r) => (
                  <p key={r} className="flex items-start gap-1">
                    <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                    <span>{r}</span>
                  </p>
                ))}
              </div>
            )}
            {probeResult.next_actions.length > 0 && probeResult.blocking_reasons.length === 0 && (
              <div className="mt-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-700">
                {probeResult.next_actions.map((r) => (
                  <p key={r} className="flex items-start gap-1">
                    <Info className="w-3 h-3 mt-0.5 shrink-0" />
                    <span>{r}</span>
                  </p>
                ))}
              </div>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Submit form */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-5 sticky top-6">
              <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
                <Play className="w-4 h-4" /> New MD Run
              </h2>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Project ID *</label>
                  <input
                    type="text"
                    value={form.project_id}
                    onChange={(e) => setForm({ ...form, project_id: e.target.value })}
                    placeholder="e.g., proj-001"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Candidate ID *</label>
                  <input
                    type="text"
                    value={form.candidate_id}
                    onChange={(e) => setForm({ ...form, candidate_id: e.target.value })}
                    placeholder="e.g., cand-001"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Duration *</label>
                  <select
                    value={form.duration_ns}
                    onChange={(e) => setForm({ ...form, duration_ns: Number(e.target.value) })}
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  >
                    {isLoadingDurations ? (
                      <option>Loading...</option>
                    ) : (
                      durations.map((d) => (
                        <option key={d.duration_ns} value={d.duration_ns}>
                          {d.duration_ns} ns ({d.nsteps.toLocaleString()} steps)
                        </option>
                      ))
                    )}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Topology Path *</label>
                  <input
                    type="text"
                    value={form.topology_path}
                    onChange={(e) => setForm({ ...form, topology_path: e.target.value })}
                    placeholder="/data/topol.tpr"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Coordinates Path *</label>
                  <input
                    type="text"
                    value={form.coordinates_path}
                    onChange={(e) => setForm({ ...form, coordinates_path: e.target.value })}
                    placeholder="/data/conf.gro"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">Server Host (optional)</label>
                  <input
                    type="text"
                    value={form.server_host}
                    onChange={(e) => setForm({ ...form, server_host: e.target.value })}
                    placeholder="192.168.31.218"
                    className="w-full text-sm px-3 py-2 border border-slate-300 rounded-md focus:ring-2 focus:ring-xh-primary focus:border-xh-primary outline-none"
                  />
                </div>
                <button
                  type="submit"
                  disabled={isSubmitting || !canSubmit}
                  className="w-full flex items-center justify-center gap-2 bg-xh-primary text-white py-2 px-4 rounded-md text-sm font-medium hover:bg-xh-primary/90 disabled:opacity-50 transition-colors"
                >
                  {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {canSubmit ? 'Submit MD Job' : 'View Only'}
                </button>
              </form>
            </div>
          </div>

          {/* Recent jobs */}
          <div className="lg:col-span-2">
            <h2 className="text-sm font-semibold text-slate-800 flex items-center gap-2 mb-4">
              <Atom className="w-4 h-4" /> Recent Production MD Jobs
            </h2>

            {jobs.length === 0 ? (
              <div className="text-center py-12 bg-slate-50 border border-slate-200 border-dashed rounded-xl">
                <Atom className="w-8 h-8 text-slate-300 mx-auto mb-2" />
                <p className="text-sm text-slate-500">No production MD jobs yet. Submit one to get started.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map((job) => {
                  const style = STATUS_STYLES[job.status] || STATUS_STYLES.PENDING;
                  return (
                    <div
                      key={job.job_id}
                      className="bg-white border border-slate-200 rounded-xl p-4 hover:shadow-sm transition-shadow"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <h3 className="text-sm font-bold text-slate-900 font-mono">{job.job_id.slice(0, 8)}...</h3>
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-slate-100 text-slate-600">
                              {job.duration_ns} ns
                            </span>
                          </div>
                          <p className="text-xs text-slate-500 mt-1">
                            Project: {job.project_id} · Candidate: {job.candidate_id}
                          </p>
                          <div className="flex items-center gap-2 mt-2">
                            <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium ${style.bg} ${style.text}`}>
                              {style.icon}
                              {style.label}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              {new Date(job.created_at).toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      </div>
    </PlatformLayout>
  );
}
