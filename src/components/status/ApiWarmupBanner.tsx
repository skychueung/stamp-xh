import { Loader2, Info } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";

export function ApiWarmupBanner() {
  const status = usePeptideFilterStore((s) => s.status);

  if (status !== "warming") return null;

  return (
    <div className="rounded-xl border border-blue-200 bg-blue-50 p-4 flex items-center gap-3">
      <Loader2 className="h-5 w-5 text-blue-600 shrink-0 animate-spin" />
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-blue-800">运行示例表位筛选流程 / Running Demo Filter</h4>
        <p className="text-sm text-blue-700 mt-1">
          正在返回预计算示例数据，用于展示五层筛选与排序效果。真实 BepiPred 3.0 / ESM 推理将在后续版本接入。
        </p>
      </div>
      <Info className="h-5 w-5 text-blue-500 shrink-0" />
    </div>
  );
}
