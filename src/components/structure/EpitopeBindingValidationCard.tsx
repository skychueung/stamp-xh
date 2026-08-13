import type { StructureMetrics } from '@/types/platform';
import { StatusPill } from '@/components/platform/StatusPill';
import { AlertTriangle } from 'lucide-react';

interface EpitopeBindingValidationCardProps {
  metrics: StructureMetrics;
}

export function EpitopeBindingValidationCard({ metrics }: EpitopeBindingValidationCardProps) {
  const ratio = metrics.epitopeContactRatio;
  let status: 'pass' | 'warning' | 'fail' = 'pass';
  let statusLabel = 'Passed';
  let statusColor = 'text-emerald-600';

  if (ratio < 0.5) {
    status = 'fail';
    statusLabel = 'Failed';
    statusColor = 'text-red-600';
  } else if (ratio < 0.75) {
    status = 'warning';
    statusLabel = 'Warning';
    statusColor = 'text-amber-600';
  }

  return (
    <div className="bg-white rounded-lg border border-xh-border p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-xh-text">Epitope Binding Validation</h3>
        <StatusPill status={status} label={statusLabel} />
      </div>

      <div className="mb-4">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-xs text-xh-muted">Epitope Contact Ratio</span>
          <span className={`text-2xl font-bold ${statusColor}`}>{ratio.toFixed(2)}</span>
        </div>
        <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all ${
              status === 'pass' ? 'bg-emerald-500' : status === 'warning' ? 'bg-amber-500' : 'bg-red-500'
            }`}
            style={{ width: `${Math.min(100, ratio * 100)}%` }}
          />
        </div>
        <p className="text-[11px] text-xh-muted mt-1.5 leading-relaxed">
          Measures whether the targeting peptide truly contacts the selected epitope instead of binding to unrelated regions.
        </p>
      </div>

      <div className="space-y-2.5">
        <div className="flex items-center justify-between text-sm">
          <span className="text-xh-muted">Off-epitope Binding Risk</span>
          <span className={`font-medium capitalize ${
            metrics.offEpitopeBindingRisk === 'low' ? 'text-emerald-600' :
            metrics.offEpitopeBindingRisk === 'medium' ? 'text-amber-600' : 'text-red-600'
          }`}>
            {metrics.offEpitopeBindingRisk}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-xh-muted">Distance to Selected Epitope</span>
          <span className="font-medium text-xh-text">{metrics.distanceToEpitope} Å</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-xh-muted">Binding Site Match</span>
          <span className={`font-medium ${status === 'pass' ? 'text-emerald-600' : 'text-amber-600'}`}>
            {status === 'pass' ? 'Passed' : status === 'warning' ? 'Marginal' : 'Failed'}
          </span>
        </div>
      </div>

      {status === 'fail' && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-md p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
          <p className="text-xs text-red-700 font-medium">
            Potential off-epitope binding detected. The peptide may bind to non-target regions.
          </p>
        </div>
      )}

      {status === 'warning' && (
        <div className="mt-4 bg-amber-50 border border-amber-200 rounded-md p-3 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700 font-medium">
            Partial epitope contact. Consider re-design or extended sampling.
          </p>
        </div>
      )}
    </div>
  );
}
