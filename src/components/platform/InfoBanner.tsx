import { AlertTriangle } from 'lucide-react';

export function InfoBanner() {
  return (
    <div className="mt-8 bg-sky-50 border border-sky-200 rounded-lg p-4 flex items-start gap-3">
      <AlertTriangle className="w-4 h-4 text-sky-600 mt-0.5 shrink-0" />
      <div className="text-sm text-sky-800">
        <p className="font-medium">Research Use Only</p>
        <p className="text-sky-700 mt-0.5">
          Results are intended for computational candidate screening only. Final targeting peptides require experimental validation.
        </p>
      </div>
    </div>
  );
}
