import { useMemo } from "react";
import { ArrowRight, GitBranch } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { STEP_DEFINITIONS } from "@/lib/constants";
import type { PipelineStep } from "@/types";
import { PipelineStepCard } from "./PipelineStepCard";
import { PipelineInsightPanel } from "./PipelineInsightPanel";

function generateDefaultSteps(): PipelineStep[] {
  return STEP_DEFINITIONS.map((def) => ({
    ...def,
    inputCount: 0,
    outputCount: 0,
    passRate: 0,
    status: "idle" as const,
  }));
}

export function PipelineSection() {
  const storeSteps = usePeptideFilterStore((s) => s.pipelineSteps);
  const activePipelineStepKey = usePeptideFilterStore((s) => s.activePipelineStepKey);
  const setActivePipelineStep = usePeptideFilterStore((s) => s.setActivePipelineStep);

  const steps = useMemo(() => {
    return storeSteps.length > 0 ? storeSteps : generateDefaultSteps();
  }, [storeSteps]);

  const activeStep = useMemo(() => {
    return steps.find((s) => s.key === activePipelineStepKey) ?? null;
  }, [steps, activePipelineStepKey]);

  return (
    <Card className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <CardHeader className="p-0 mb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold text-slate-900">
          <GitBranch className="h-5 w-5 text-slate-600" />
          Filtering Pipeline
        </CardTitle>
        <p className="text-sm text-slate-600 mt-1">
          5-step filtering process from extraction to final candidate selection
        </p>
      </CardHeader>
      <CardContent className="p-0">
        {/* Pipeline flow - horizontal on desktop, vertical on mobile */}
        <div className="flex flex-col md:flex-row gap-2 md:gap-1 items-stretch">
          {steps.map((step, index) => (
            <div key={step.key} className="flex items-center gap-1 flex-1">
              <PipelineStepCard
                step={step}
                isActive={step.key === activePipelineStepKey}
                onClick={() =>
                  setActivePipelineStep(step.key === activePipelineStepKey ? null : step.key)
                }
              />
              {index < steps.length - 1 && (
                <ArrowRight className="hidden md:block h-4 w-4 text-slate-300 shrink-0" />
              )}
            </div>
          ))}
        </div>

        <PipelineInsightPanel activeStep={activeStep} />
      </CardContent>
    </Card>
  );
}
