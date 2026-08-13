import { usePeptideFilterStore } from "@/store/peptideFilterStore";

export function ModeStatusBar() {
  const status = usePeptideFilterStore((s) => s.status);
  const summary = usePeptideFilterStore((s) => s.summary);

  if (status !== "success" || !summary) return null;

  const mode = summary.mode ?? "DEMO_COMPATIBLE";
  const source = summary.source ?? "demo_fallback";
  const validationStatus = summary.validationStatus ?? "NOT_EXPERIMENTALLY_VALIDATED";

  const isReal = mode === "REAL_BEPIPRED3_ESM_SIDECAR";

  const modeLabel = isReal
    ? "真实 BepiPred3 + ESM-2 推理模式"
    : "Demo 回退模式";

  const note = isReal
    ? "当前结果为计算预测候选，尚未经过实验验证。"
    : "当前显示为预计算示例数据，真实 Sidecar 当前不可用。";

  return (
    <div
      className={`rounded-lg border px-4 py-3 text-sm ${
        isReal
          ? "border-emerald-200 bg-emerald-50"
          : "border-amber-200 bg-amber-50"
      }`}
    >
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex h-2 w-2 rounded-full ${
              isReal ? "bg-emerald-500" : "bg-amber-500"
            }`}
          />
          <span className="font-semibold text-slate-800">
            当前模式：{modeLabel}
          </span>
        </div>
        <div className="text-slate-600">
          <span className="font-medium">数据来源：</span>
          <code className="rounded bg-white/60 px-1 py-0.5 text-xs">{source}</code>
        </div>
        <div className="text-slate-600">
          <span className="font-medium">状态：</span>
          <span className="text-xs">{validationStatus}</span>
        </div>
      </div>
      <p className={`mt-1 text-xs ${isReal ? "text-emerald-700" : "text-amber-700"}`}>
        {note}
      </p>
    </div>
  );
}
