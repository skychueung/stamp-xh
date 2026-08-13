import { Zap, Droplets, FlaskConical, Shield, Scissors } from "lucide-react";
import type { PipelineStep } from "@/types";
import { Badge } from "@/components/ui/badge";

const STEP_ICONS: Record<string, React.ReactNode> = {
  fragment: <Scissors className="h-4 w-4" />,
  charge: <Zap className="h-4 w-4" />,
  gravy: <Droplets className="h-4 w-4" />,
  pi: <FlaskConical className="h-4 w-4" />,
  cysteine: <Shield className="h-4 w-4" />,
};

const STATUS_STYLES: Record<string, { bg: string; border: string; badge: string }> = {
  idle: { bg: "bg-slate-50", border: "border-slate-200", badge: "bg-slate-100 text-slate-500" },
  processing: { bg: "bg-blue-50", border: "border-blue-300", badge: "bg-blue-100 text-blue-700" },
  done: { bg: "bg-emerald-50", border: "border-emerald-300", badge: "bg-emerald-100 text-emerald-700" },
  error: { bg: "bg-rose-50", border: "border-rose-300", badge: "bg-rose-100 text-rose-700" },
};

const STATUS_LABELS: Record<string, string> = {
  idle: "等待",
  processing: "处理中",
  done: "完成",
  error: "错误",
};

type PipelineStepCardProps = {
  step: PipelineStep;
  isActive: boolean;
  onClick: () => void;
};

export function PipelineStepCard({ step, isActive, onClick }: PipelineStepCardProps) {
  const style = STATUS_STYLES[step.status] ?? STATUS_STYLES.idle;
  const isProcessing = step.status === "processing";

  return (
    <button
      onClick={onClick}
      className={`relative flex-1 min-w-0 rounded-xl border-2 p-3 text-left transition-all duration-200 ${style.bg} ${style.border} ${
        isActive ? "ring-2 ring-slate-400 ring-offset-1" : ""
      } hover:shadow-md`}
    >
      {/* Animated flow bar for processing state */}
      {isProcessing && (
        <div className="absolute inset-x-0 top-0 h-0.5 pipeline-gradient-bar animate-pipeline-flow rounded-t-xl" />
      )}

      <div className="flex items-center gap-2 mb-2">
        <span className="text-slate-500">{STEP_ICONS[step.key]}</span>
        <span className="text-xs font-medium text-slate-600 truncate">{step.label}</span>
      </div>

      <Badge className={`${style.badge} text-[10px] font-medium border-0`}>
        {isProcessing && (
          <span className="mr-1 inline-block h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
        )}
        {STATUS_LABELS[step.status] ?? step.status}
      </Badge>

      <div className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-[10px] text-slate-500">
        <div>
          <span className="text-slate-400">In:</span>{" "}
          <span className="font-medium tabular-nums">{step.inputCount}</span>
        </div>
        <div>
          <span className="text-slate-400">Out:</span>{" "}
          <span className="font-medium tabular-nums">{step.outputCount}</span>
        </div>
      </div>

      {step.passRate > 0 && (
        <div className="mt-2">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-slate-400">Pass rate</span>
            <span className="font-medium tabular-nums">{step.passRate.toFixed(1)}%</span>
          </div>
          <div className="mt-1 h-1 rounded-full bg-slate-200 overflow-hidden">
            <div
              className="h-full rounded-full bg-slate-500 transition-all duration-500"
              style={{ width: `${step.passRate}%` }}
            />
          </div>
        </div>
      )}

      {step.mainExclusionReason && (
        <p className="mt-2 text-[10px] text-rose-600 leading-tight">
          {step.mainExclusionReason}
        </p>
      )}
    </button>
  );
}
