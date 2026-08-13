import { Info, AlertTriangle } from 'lucide-react';
import { SectionCard } from './SectionCard';
import { StatusPill } from './StatusPill';
import { MetricCard } from './MetricCard';

export interface MmgbsaReadinessData {
  run_type: string;
  convergence_status: string;
  frames_used?: number | null;
  frames_available?: number | null;
  trajectory_length_ns?: number | null;
  pilot_delta_total_kcal_mol?: number | null;
  official_mm_gbsa_delta_g?: number | null;
  warnings?: string[];
  parser_version?: string;
  components?: {
    vdW?: number | null;
    electrostatic?: number | null;
    polar_solvation?: number | null;
    nonpolar_solvation?: number | null;
  };
}

interface MmgbsaReadinessCardProps {
  data?: MmgbsaReadinessData | null;
}

export function MmgbsaReadinessCard({ data }: MmgbsaReadinessCardProps) {
  if (!data) {
    return (
      <SectionCard title="MM-GBSA / MD Readiness" subtitle="Computational binding free energy estimate">
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4">
          <p className="text-sm text-slate-600">
            No MM-GBSA data available. Production MD and MM-GBSA calculation have not been run for this candidate.
          </p>
        </div>
      </SectionCard>
    );
  }

  const isPilotOrSmoke = data.run_type === 'PILOT' || data.run_type === 'SMOKE';
  const isProductionReady = data.run_type === 'PRODUCTION' &&
    (data.convergence_status === 'CONVERGED' || data.convergence_status === 'PARTIAL_CONVERGENCE');

  const statusLabel = isProductionReady
    ? 'PRODUCTION_READY'
    : isPilotOrSmoke
    ? 'PILOT_ONLY_NOT_PRODUCTION_MMGBSA'
    : data.convergence_status;

  const statusVariant = isProductionReady
    ? 'pass'
    : isPilotOrSmoke
    ? 'warning'
    : 'pending';

  const hasComponents = data.components &&
    (data.components.vdW !== null || data.components.electrostatic !== null ||
     data.components.polar_solvation !== null || data.components.nonpolar_solvation !== null);

  return (
    <SectionCard title="MM-GBSA / MD Readiness" subtitle="Computational binding free energy estimate">
      <div className="space-y-3">
        {/* Status Banner */}
        <div className={`rounded-lg p-3 border flex items-start gap-2 ${
          isPilotOrSmoke
            ? 'bg-amber-50 border-amber-200'
            : isProductionReady
            ? 'bg-emerald-50 border-emerald-200'
            : 'bg-slate-50 border-slate-200'
        }`}>
          {isPilotOrSmoke ? (
            <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          ) : (
            <Info className="w-4 h-4 text-slate-600 mt-0.5 shrink-0" />
          )}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <StatusPill status={statusVariant} label={statusLabel} />
            </div>
            <p className="text-xs text-slate-700 leading-relaxed">
              <strong>official ΔG: {data.official_mm_gbsa_delta_g !== null && data.official_mm_gbsa_delta_g !== undefined
                ? `${data.official_mm_gbsa_delta_g.toFixed(2)} kcal/mol`
                : 'Not available'}</strong>
            </p>
            {isPilotOrSmoke && (
              <p className="text-xs text-amber-700 leading-relaxed">
                This is a <strong>{data.run_type.toLowerCase()}-only</strong> result. It is <strong>not a production MM-GBSA binding free energy</strong> and <strong>must not be used for candidate ranking</strong>. Production MD (≥10 ns, ≥200 frames, convergence verified) is required before an official ΔG can be reported.
              </p>
            )}
          </div>
        </div>

        {/* Metrics */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <MetricCard
            label="Run Type"
            value={data.run_type}
          />
          <MetricCard
            label="Convergence"
            value={data.convergence_status}
          />
          <MetricCard
            label="Frames Used"
            value={data.frames_used?.toString() ?? 'N/A'}
          />
          <MetricCard
            label="Trajectory"
            value={data.trajectory_length_ns !== undefined && data.trajectory_length_ns !== null
              ? `${data.trajectory_length_ns} ns`
              : 'N/A'}
          />
        </div>

        {/* Energy Components */}
        {hasComponents && (
          <div className="bg-white border border-slate-200 rounded-lg p-3">
            <p className="text-xs text-slate-600 font-medium mb-2">MM-GBSA Energy Components (Δ)</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <MetricCard
                label="vdW"
                value={data.components?.vdW != null ? `${data.components.vdW.toFixed(2)}` : 'N/A'}
              />
              <MetricCard
                label="Electrostatic"
                value={data.components?.electrostatic != null ? `${data.components.electrostatic.toFixed(2)}` : 'N/A'}
              />
              <MetricCard
                label="Polar Solv."
                value={data.components?.polar_solvation != null ? `${data.components.polar_solvation.toFixed(2)}` : 'N/A'}
              />
              <MetricCard
                label="Nonpolar Solv."
                value={data.components?.nonpolar_solvation != null ? `${data.components.nonpolar_solvation.toFixed(2)}` : 'N/A'}
              />
            </div>
          </div>
        )}

        {/* Pilot Delta (if present) */}
        {data.pilot_delta_total_kcal_mol !== null && data.pilot_delta_total_kcal_mol !== undefined && (
          <div className="bg-slate-50 border border-slate-200 rounded-lg p-3">
            <p className="text-xs text-slate-600 font-medium mb-1">Pilot ΔTOTAL (non-production)</p>
            <p className="text-lg font-mono font-semibold text-slate-800">
              {data.pilot_delta_total_kcal_mol.toFixed(4)} kcal/mol
            </p>
            <p className="text-xs text-slate-500 mt-1">
              This value is for workflow validation only. It does not represent a converged binding free energy.
            </p>
          </div>
        )}

        {/* Warnings */}
        {data.warnings && data.warnings.length > 0 && (
          <div className="space-y-1">
            {data.warnings.map((w, i) => (
              <div key={i} className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded px-2 py-1.5">
                <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                <span>{w}</span>
              </div>
            ))}
          </div>
        )}

        {/* Scientific Boundary Footer */}
        <div className="text-xs text-slate-500 border-t border-slate-100 pt-2 mt-2">
          <p>
            <strong>Scientific boundary:</strong> MM-GBSA ΔG values shown here are <strong>computational estimates</strong>, not experimentally validated binding affinities. Candidate ranking should not rely on pilot/smoke MM-GBSA values. Production MD with convergence checks (RMSD, RMSF, density, energy drift) is required before MM-GBSA can support ranking decisions.
          </p>
        </div>
      </div>
    </SectionCard>
  );
}
