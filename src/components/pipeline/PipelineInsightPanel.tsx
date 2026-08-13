import { Info } from "lucide-react";
import type { PipelineStep } from "@/types";

type PipelineInsightPanelProps = {
  activeStep: PipelineStep | null;
};

export function PipelineInsightPanel({ activeStep }: PipelineInsightPanelProps) {
  if (!activeStep) {
    return (
      <div className="mt-4 rounded-xl bg-slate-50 border border-slate-200 p-4 flex items-start gap-3">
        <Info className="h-4 w-4 text-slate-400 mt-0.5 shrink-0" />
        <p className="text-sm text-slate-500">
          Click on a pipeline step above to view detailed filtering information.
        </p>
      </div>
    );
  }

  return (
    <div className="mt-4 rounded-xl bg-slate-50 border border-slate-200 p-4">
      <div className="flex items-center gap-2 mb-2">
        <Info className="h-4 w-4 text-slate-500" />
        <h4 className="text-sm font-medium text-slate-700">{activeStep.label}</h4>
      </div>
      <p className="text-sm text-slate-600 leading-relaxed">{activeStep.description}</p>

      {activeStep.mainExclusionReason && (
        <div className="mt-3 rounded-lg bg-rose-50 border border-rose-100 px-3 py-2">
          <p className="text-xs text-rose-700">
            <span className="font-medium">Main exclusion: </span>
            {activeStep.mainExclusionReason}
          </p>
        </div>
      )}

      <div className="mt-3 flex items-center gap-4 text-xs text-slate-500">
        <span>
          Input: <strong className="tabular-nums">{activeStep.inputCount}</strong>
        </span>
        <span>
          Output: <strong className="tabular-nums">{activeStep.outputCount}</strong>
        </span>
        <span>
          Pass rate: <strong className="tabular-nums">{activeStep.passRate.toFixed(1)}%</strong>
        </span>
      </div>
    </div>
  );
}
