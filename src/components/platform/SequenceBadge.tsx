interface SequenceBadgeProps {
  sequence: string;
  highlightRange?: [number, number];
  size?: 'sm' | 'md' | 'lg';
}

export function SequenceBadge({ sequence, highlightRange, size = 'md' }: SequenceBadgeProps) {
  const chars = sequence.split('');

  const sizeClasses = {
    sm: 'text-xs gap-0.5 p-1.5',
    md: 'text-sm gap-0.5 p-2',
    lg: 'text-base gap-1 p-3',
  };

  const charSizes = {
    sm: 'w-5 h-5',
    md: 'w-6 h-6',
    lg: 'w-7 h-7',
  };

  return (
    <div className={`inline-flex flex-wrap font-mono bg-gray-50 rounded-md border border-xh-border ${sizeClasses[size]}`}>
      {chars.map((char, i) => {
        const isHighlighted = highlightRange && i >= highlightRange[0] && i < highlightRange[1];
        return (
          <span
            key={i}
            className={`inline-flex items-center justify-center rounded ${charSizes[size]} ${
              isHighlighted ? 'bg-amber-100 text-amber-800 font-bold' : 'text-xh-text'
            }`}
          >
            {char}
          </span>
        );
      })}
    </div>
  );
}
