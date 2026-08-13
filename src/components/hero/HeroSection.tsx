import { useCallback } from "react";
import { Beaker, Dna, Play, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { usePredictionRun } from "@/hooks/usePredictionRun";

export function HeroSection() {
  const { run, isRunning } = usePredictionRun();
  const status = usePeptideFilterStore((s) => s.status);

  const handleRun = useCallback(() => {
    void run();
  }, [run]);

  const isLoading = isRunning || status === "warming";

  return (
    <section className="py-8">
      <div className="max-w-3xl">
        <div className="flex items-center gap-2 mb-4">
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            <Beaker className="h-3.5 w-3.5" />
            Scientific Tool
          </span>
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-slate-900">
          Peptide Filter Pipeline <span className="text-amber-600 text-xl font-normal">(Demo)</span>
        </h1>
        <p className="text-lg text-slate-600 mt-3 leading-relaxed">
          从蛋白序列中发现更优候选肽段 — 通过多维度过滤与智能评分，
          快速筛选出最具潜力的肽段候选。当前为预计算示例数据演示模式。
        </p>
        <div className="mt-6 flex items-center gap-3">
          <Button
            size="lg"
            className="bg-slate-900 text-white hover:bg-slate-800 rounded-lg px-5 py-2.5 text-sm font-medium gap-2"
            onClick={handleRun}
            disabled={isLoading}
          >
            {isLoading ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            Run Prediction
          </Button>
          <Button
            variant="outline"
            size="lg"
            className="bg-white border border-slate-200 text-slate-700 hover:bg-slate-50 rounded-lg px-5 py-2.5 text-sm font-medium gap-2"
          >
            <FileText className="h-4 w-4" />
            View Docs
          </Button>
          <Button
            variant="ghost"
            size="lg"
            className="text-slate-600 hover:text-slate-900 hover:bg-slate-100 rounded-lg px-4 py-2.5 text-sm font-medium gap-2"
          >
            <Dna className="h-4 w-4" />
            Load Example
          </Button>
        </div>
      </div>
    </section>
  );
}
