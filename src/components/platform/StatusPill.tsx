import type { StatusType } from '@/types/platform';
import { useLanguage } from '@/i18n/LanguageContext';

interface StatusPillProps {
  status: StatusType;
  label?: string;
}

export function StatusPill({ status, label }: StatusPillProps) {
  const { t } = useLanguage();

  const statusMap: Record<StatusType, { bg: string; text: string; border: string }> = {
    pass: { bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200' },
    warning: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
    fail: { bg: 'bg-red-50', text: 'text-red-700', border: 'border-red-200' },
    pending: { bg: 'bg-gray-50', text: 'text-gray-500', border: 'border-gray-200' },
    processing: { bg: 'bg-sky-50', text: 'text-sky-700', border: 'border-sky-200' },
  };

  const defaultLabels: Record<StatusType, string> = {
    pass: t.common.passed,
    warning: t.common.warningStatus,
    fail: t.common.failedStatus,
    pending: t.common.pending,
    processing: t.common.processing,
  };

  const style = statusMap[status];

  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${style.bg} ${style.text} ${style.border}`}>
      {label ?? defaultLabels[status]}
    </span>
  );
}
