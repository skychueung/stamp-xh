import { Loader2 } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";

export function LoadingOverlay() {
  const status = usePeptideFilterStore((s) => s.status);

  if (status !== "loading") return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-900/40 backdrop-blur-sm transition-opacity duration-200">
      <div className="rounded-2xl bg-white p-8 shadow-lg flex flex-col items-center gap-4">
        <Loader2 className="h-8 w-8 text-slate-600 animate-spin" />
        <div className="text-center">
          <p className="text-sm font-semibold text-slate-900">Processing...</p>
          <p className="text-xs text-slate-500 mt-1">Running peptide prediction pipeline</p>
        </div>
      </div>
    </div>
  );
}
