import { FlaskConical } from "lucide-react";

export function EmptyResultState() {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100 mb-4">
        <FlaskConical className="h-8 w-8 text-slate-400" />
      </div>
      <h3 className="text-lg font-semibold text-slate-900">等待开始</h3>
      <p className="text-sm text-slate-500 mt-2 max-w-sm">
        Configure the input parameters and click &quot;Run Prediction&quot; to start the peptide filtering pipeline.
      </p>
    </div>
  );
}
