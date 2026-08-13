import { AlertCircle, X } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { Button } from "@/components/ui/button";

export function ErrorBanner() {
  const status = usePeptideFilterStore((s) => s.status);
  const errorMessage = usePeptideFilterStore((s) => s.errorMessage);
  const setStatus = usePeptideFilterStore((s) => s.setStatus);
  const setErrorMessage = usePeptideFilterStore((s) => s.setErrorMessage);

  if (status !== "error" || !errorMessage) return null;

  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3">
      <AlertCircle className="h-5 w-5 text-rose-600 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-semibold text-rose-800">Error</h4>
        <p className="text-sm text-rose-700 mt-1">{errorMessage}</p>
      </div>
      <Button
        variant="ghost"
        size="sm"
        className="shrink-0 h-7 w-7 p-0 text-rose-600 hover:text-rose-800 hover:bg-rose-100 rounded-md"
        onClick={() => {
          setStatus("idle");
          setErrorMessage(null);
        }}
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
}
