import type { ReactNode } from 'react';

interface SectionCardProps {
  title?: string;
  subtitle?: string;
  children: ReactNode;
  className?: string;
  action?: ReactNode;
}

export function SectionCard({ title, subtitle, children, className = '', action }: SectionCardProps) {
  return (
    <div className={`bg-white rounded-lg border border-xh-border p-5 ${className}`}>
      {title && (
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-xh-text">{title}</h3>
            {subtitle && <p className="text-xs text-xh-muted mt-0.5">{subtitle}</p>}
          </div>
          {action && <div>{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}
