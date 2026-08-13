export type PipelineStepKey = "fragment" | "charge" | "gravy" | "pi" | "cysteine";

export type PipelineStep = {
  key: PipelineStepKey;
  label: string;
  description: string;
  inputCount: number;
  outputCount: number;
  passRate: number;
  status: "idle" | "processing" | "done" | "error";
  mainExclusionReason?: string;
};
