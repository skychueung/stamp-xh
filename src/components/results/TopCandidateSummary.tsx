import { useState, useCallback } from "react";
import { Award, Zap, Beaker, ArrowRight, Copy, Check, GitCompare, Eye, FlaskConical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { RISK_COLORS } from "@/lib/constants";
import { formatScore, formatSequence } from "@/lib/format";
import type { Candidate } from "@/types";

type TopCandidateSummaryProps = {
  candidate: Candidate | null;
  status: "idle" | "loading" | "success" | "error" | "warming";
};

export function TopCandidateSummary({ candidate, status }: TopCandidateSummaryProps) {
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);
  const [copied, setCopied] = useState(false);

  const isCompared = candidate ? comparedCandidateIds.includes(candidate.id) : false;

  const handleCopy = useCallback(() => {
    if (candidate?.sequence) {
      void navigator.clipboard.writeText(candidate.sequence);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [candidate]);

  if (status === "loading") {
    return (
      <div className="rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white shadow-sm flex flex-col" style={{ minHeight: 260, maxHeight: 320 }}>
        <div className="flex items-center justify-between mb-4">
          <Skeleton className="h-3 w-32 bg-white/10" />
          <Skeleton className="h-6 w-12 bg-white/10 rounded-full" />
        </div>
        <div className="flex-1 flex flex-col items-center justify-center gap-4">
          <Skeleton className="h-10 w-56 bg-white/10 rounded-xl" />
          <Skeleton className="h-2 w-48 bg-white/10 rounded-full" />
          <div className="flex gap-2 mt-2">
            <Skeleton className="h-7 w-20 bg-white/10 rounded-lg" />
            <Skeleton className="h-7 w-20 bg-white/10 rounded-lg" />
            <Skeleton className="h-7 w-20 bg-white/10 rounded-lg" />
            <Skeleton className="h-7 w-20 bg-white/10 rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  if (status === "idle" || !candidate) {
    const isEmptyResult = status === "success";
    return (
      <div className="rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white shadow-sm flex flex-col items-center justify-center text-center" style={{ minHeight: 260, maxHeight: 320 }}>
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-white/5 mb-3">
          <FlaskConical className="h-6 w-6 text-slate-400" />
        </div>
        <h3 className="text-sm font-semibold text-slate-200">
          {isEmptyResult ? "未筛选到符合条件的候选" : "等待开始"}
        </h3>
        <p className="text-xs text-slate-400 mt-1 max-w-xs">
          {isEmptyResult
            ? "后端返回成功，但未找到符合条件的候选肽段，请放宽筛选条件重试。"
            : "配置参数并点击 \"Run Prediction\" 开始肽段筛选流程"}
        </p>
      </div>
    );
  }

  const riskStyle = RISK_COLORS[candidate.disulfideRisk] ?? RISK_COLORS.unknown;

  return (
    <div className="rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-5 text-white shadow-sm flex flex-col" style={{ minHeight: 260, maxHeight: 320 }}>
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            Top Candidate Summary
          </span>
          <h2 className="text-lg font-semibold mt-0.5">最佳候选肽段</h2>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1">
          <Award className="h-3.5 w-3.5 text-sky-400" />
          <span className="text-sm font-bold">#{candidate.rank}</span>
        </div>
      </div>

      <div className="flex-1 flex flex-col items-center justify-center text-center py-2 min-h-0">
        <div className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-4 py-2.5 border border-white/10">
          <span className="sequence-mono text-xl font-bold tracking-wider">
            {formatSequence(candidate.sequence, 24)}
          </span>
        </div>

        <div className="mt-4 w-full max-w-xs">
          <div className="flex items-center justify-between mb-1.5">
            <span className="text-[11px] text-slate-400">Priority Score</span>
            <span className="text-base font-bold tabular-nums">
              {formatScore(candidate.priorityScore)}
            </span>
          </div>
          <div className="h-1.5 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-400 to-emerald-400 transition-all duration-700 ease-out"
              style={{ width: `${(candidate.priorityScore ?? 0) * 100}%` }}
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-center gap-1.5">
          <MetricPill icon={<Zap className="h-3 w-3" />} label="Charge" value={formatScore(Number(candidate.netCharge))} />
          <MetricPill icon={<Beaker className="h-3 w-3" />} label="GRAVY" value={formatScore(Number(candidate.gravy))} />
          <MetricPill icon={<span className="text-[10px] font-bold">pI</span>} label="pI" value={formatScore(Number(candidate.pI))} />
          <MetricPill icon={<span className="text-[10px] font-bold">C</span>} label="Cys" value={String(candidate.cysCount)} />
          <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-[10px] font-medium`}>
            {candidate.disulfideRisk}
          </Badge>
        </div>

        <div className="mt-4 text-left w-full max-w-sm">
          <h4 className="text-[10px] font-medium text-slate-400 uppercase tracking-wider mb-1.5">
            Why it stands out
          </h4>
          <ul className="space-y-1">
            {(Array.isArray(candidate.topAdvantages) ? candidate.topAdvantages : [])
              .slice(0, 2)
              .map((adv, i) => (
                <li key={i} className="flex items-start gap-1.5 text-xs text-slate-300">
                  <ArrowRight className="h-3 w-3 text-teal-400 mt-0.5 shrink-0" />
                  <span className="line-clamp-1">{adv}</span>
                </li>
              ))}
          </ul>
        </div>
      </div>

      <div className="mt-3 flex items-center gap-2 shrink-0">
        <Button
          variant="ghost"
          className="flex-1 text-white/80 hover:text-white hover:bg-white/10 rounded-lg text-xs gap-1.5 h-8"
          onClick={() => selectCandidate(candidate.id)}
        >
          <Eye className="h-3.5 w-3.5" />
          View Detail
        </Button>
        <Button
          variant="ghost"
          className={`flex-1 rounded-lg text-xs gap-1.5 h-8 ${
            isCompared
              ? "text-teal-400 hover:text-teal-300 hover:bg-white/10"
              : "text-white/80 hover:text-white hover:bg-white/10"
          }`}
          onClick={() => toggleCompareCandidate(candidate.id)}
        >
          <GitCompare className="h-3.5 w-3.5" />
          {isCompared ? "Added" : "Compare"}
        </Button>
        <Button
          variant="ghost"
          className="flex-1 text-white/80 hover:text-white hover:bg-white/10 rounded-lg text-xs gap-1.5 h-8"
          onClick={handleCopy}
        >
          {copied ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
    </div>
  );
}

function MetricPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-1 rounded-md bg-white/5 px-2 py-1 border border-white/10">
      <span className="text-slate-400">{icon}</span>
      <span className="text-[10px] text-slate-500 uppercase">{label}</span>
      <span className="text-[11px] font-semibold tabular-nums">{value}</span>
    </div>
  );
}
