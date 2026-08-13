import { useMemo } from "react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";

export function usePipelineState() {
  const pipelineSteps = usePeptideFilterStore((s) => s.pipelineSteps);
  const activePipelineStepKey = usePeptideFilterStore((s) => s.activePipelineStepKey);

  const currentStep = useMemo(() => {
    return pipelineSteps.find((s) => s.key === activePipelineStepKey) ?? null;
  }, [pipelineSteps, activePipelineStepKey]);

  const stepStatuses = useMemo(() => {
    return pipelineSteps.map((s) => ({
      key: s.key,
      label: s.label,
      status: s.status,
    }));
  }, [pipelineSteps]);

  const overallStatus = useMemo(() => {
    if (pipelineSteps.length === 0) return "idle";
    if (pipelineSteps.some((s) => s.status === "error")) return "error";
    if (pipelineSteps.some((s) => s.status === "processing")) return "processing";
    if (pipelineSteps.every((s) => s.status === "done")) return "done";
    return "idle";
  }, [pipelineSteps]);

  return { currentStep, stepStatuses, overallStatus };
}
