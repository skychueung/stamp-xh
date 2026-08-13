import { Eye, GitCompare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { RISK_COLORS } from "@/lib/constants";
import { formatScore } from "@/lib/format";
import type { Candidate } from "@/types";

type TopCandidateCardProps = {
  candidate: Candidate;
  isHighlighted?: boolean;
};

export function TopCandidateCard({ candidate, isHighlighted }: TopCandidateCardProps) {
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);

  const isCompared = comparedCandidateIds.includes(candidate.id);
  const riskStyle = RISK_COLORS[candidate.disulfideRisk] ?? RISK_COLORS.unknown;

  const rankColors: Record<number, string> = {
    1: "text-blue-500",
    2: "text-slate-400",
    3: "text-orange-400",
  };

  return (
    <div
      className={`rounded-xl border p-4 shadow-sm hover:shadow-md transition-all duration-200 cursor-pointer ${
        isHighlighted
          ? "border-teal-300 bg-teal-50/50 ring-1 ring-teal-200"
          : "border-slate-200 bg-white"
      }`}
      onClick={() => selectCandidate(candidate.id)}
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className={`text-2xl font-bold ${rankColors[candidate.rank] ?? "text-slate-600"}`}>
            #{candidate.rank}
          </span>
          <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-[10px] font-medium`}>
            {candidate.disulfideRisk}
          </Badge>
        </div>
        <span className="text-xs text-slate-400">{candidate.length} aa</span>
      </div>

      {/* Sequence */}
      <div className={`rounded-lg px-3 py-2 border mb-3 ${isHighlighted ? "bg-white border-teal-100" : "bg-slate-50 border-slate-100"}`}>
        <span className="sequence-mono text-sm font-semibold text-slate-800">
          {candidate.sequence}
        </span>
      </div>

      {/* Score */}
      <div className="mb-3">
        <div className="flex items-center justify-between text-xs mb-1">
          <span className="text-slate-500">Priority Score</span>
          <span className="font-semibold tabular-nums">{formatScore(candidate.priorityScore)}</span>
        </div>
        <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
          <div
            className="h-full rounded-full bg-slate-600 transition-all duration-500"
            style={{ width: `${(candidate.priorityScore ?? 0) * 100}%` }}
          />
        </div>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-3 gap-2 mb-4">
        <div className={`text-center rounded-md py-1 ${isHighlighted ? "bg-white" : "bg-slate-50"}`}>
          <p className="text-[10px] text-slate-400">Charge</p>
          <p className="text-xs font-semibold tabular-nums">{formatScore(Number(candidate.netCharge))}</p>
        </div>
        <div className={`text-center rounded-md py-1 ${isHighlighted ? "bg-white" : "bg-slate-50"}`}>
          <p className="text-[10px] text-slate-400">GRAVY</p>
          <p className="text-xs font-semibold tabular-nums">{formatScore(Number(candidate.gravy))}</p>
        </div>
        <div className={`text-center rounded-md py-1 ${isHighlighted ? "bg-white" : "bg-slate-50"}`}>
          <p className="text-[10px] text-slate-400">pI</p>
          <p className="text-xs font-semibold tabular-nums">{formatScore(Number(candidate.pI))}</p>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="flex-1 text-slate-600 hover:text-slate-900 hover:bg-slate-50 text-xs gap-1.5 h-8"
          onClick={(e) => {
            e.stopPropagation();
            selectCandidate(candidate.id);
          }}
        >
          <Eye className="h-3.5 w-3.5" />
          Detail
        </Button>
        <Button
          variant="ghost"
          size="sm"
          className={`flex-1 text-xs gap-1.5 h-8 ${
            isCompared
              ? "text-teal-600 hover:text-teal-700 hover:bg-teal-50"
              : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
          }`}
          onClick={(e) => {
            e.stopPropagation();
            toggleCompareCandidate(candidate.id);
          }}
        >
          <GitCompare className="h-3.5 w-3.5" />
          {isCompared ? "Added" : "Compare"}
        </Button>
      </div>
    </div>
  );
}

export function TopCandidateCardSkeleton() {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <Skeleton className="h-7 w-12" />
        <Skeleton className="h-5 w-14" />
      </div>
      <Skeleton className="h-8 w-full mb-3" />
      <Skeleton className="h-1.5 w-full mb-4" />
      <div className="grid grid-cols-3 gap-2 mb-4">
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
        <Skeleton className="h-9 w-full" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-8 flex-1" />
        <Skeleton className="h-8 flex-1" />
      </div>
    </div>
  );
}
