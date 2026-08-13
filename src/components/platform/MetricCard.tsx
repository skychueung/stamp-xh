interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  subtext?: string;
  highlight?: boolean;
}

export function MetricCard({ label, value, unit, subtext, highlight }: MetricCardProps) {
  return (
    <div className={`rounded-lg border p-4 ${highlight ? 'border-xh-primary bg-xh-primary-light' : 'border-xh-border bg-white'}`}>
      <p className="text-xs text-xh-muted mb-1">{label}</p>
      <div className="flex items-baseline gap-1">
        <span className={`text-2xl font-bold ${highlight ? 'text-xh-primary' : 'text-xh-text'}`}>
          {value}
        </span>
        {unit && <span className="text-sm text-xh-muted">{unit}</span>}
      </div>
      {subtext && <p className="text-xs text-xh-muted mt-1">{subtext}</p>}
    </div>
  );
}
