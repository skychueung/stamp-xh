import { useMemo } from "react";
import { BarChart3, Star, TrendingDown, Award } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { formatNumber, formatScore, formatPercent } from "@/lib/format";

type MetricCardProps = {
  label: string;
  value: string;
  icon: React.ReactNode;
  accentColor: string;
};

function MetricCard({ label, value, icon, accentColor }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 flex items-center gap-3">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${accentColor}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className="text-xs text-slate-500 truncate">{label}</p>
        <p className="text-2xl font-bold tabular-nums text-slate-900 truncate">{value}</p>
      </div>
    </div>
  );
}

export function ResultsSnapshotSection() {
  const summary = usePeptideFilterStore((s) => s.summary);

  const hasSummary = summary !== null;

  const metrics = useMemo(() => {
    if (!hasSummary) {
      return {
        totalExtracted: 0,
        finalRetained: 0,
        dropRate: 0,
        top1Score: 0,
        avgTop3: 0,
        avgTop10: 0,
      };
    }
    return {
      totalExtracted: summary.totalExtracted,
      finalRetained: summary.finalRetained,
      dropRate: summary.dropRate,
      top1Score: summary.top1Score ?? 0,
      avgTop3: summary.averageTop3Score ?? 0,
      avgTop10: summary.averageTop10Score ?? 0,
    };
  }, [hasSummary, summary]);

  return (
    <section>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <MetricCard
          label="Total Extracted"
          value={formatNumber(metrics.totalExtracted)}
          icon={<BarChart3 className="h-5 w-5 text-slate-600" />}
          accentColor="bg-slate-100"
        />
        <MetricCard
          label="Final Retained"
          value={formatNumber(metrics.finalRetained)}
          icon={<Award className="h-5 w-5 text-emerald-600" />}
          accentColor="bg-emerald-100"
        />
        <MetricCard
          label="Drop Rate"
          value={formatPercent(metrics.dropRate)}
          icon={<TrendingDown className="h-5 w-5 text-blue-600" />}
          accentColor="bg-blue-100"
        />
        <MetricCard
          label="Top 1 Score"
          value={formatScore(metrics.top1Score)}
          icon={<Star className="h-5 w-5 text-blue-600" />}
          accentColor="bg-blue-100"
        />
        <MetricCard
          label="Avg Top 3 / Top 10"
          value={`${formatScore(metrics.avgTop3)} / ${formatScore(metrics.avgTop10)}`}
          icon={<BarChart3 className="h-5 w-5 text-slate-600" />}
          accentColor="bg-slate-100"
        />
      </div>
    </section>
  );
}
