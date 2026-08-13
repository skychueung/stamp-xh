interface ScoreBarProps {
  label?: string;
  value?: number;
  score?: number;
  showValue?: boolean;
  max?: number;
  color?: 'blue' | 'green' | 'amber' | 'red';
}

export function ScoreBar({ label, value, score, showValue, max = 1, color = 'blue' }: ScoreBarProps) {
  const actualValue = score !== undefined ? score : (value ?? 0);
  const percentage = Math.min(100, Math.max(0, (actualValue / max) * 100));
  const colorMap = {
    blue: 'bg-xh-primary',
    green: 'bg-emerald-500',
    amber: 'bg-amber-500',
    red: 'bg-red-500',
  };

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        {label && <span className="text-xs text-xh-text font-medium">{label}</span>}
        {showValue !== false && (
          <span className="text-xs text-xh-muted">{typeof actualValue === 'number' ? actualValue.toFixed(2) : actualValue}</span>
        )}
      </div>
      <div className="w-full h-2 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${colorMap[color]}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
    </div>
  );
}
