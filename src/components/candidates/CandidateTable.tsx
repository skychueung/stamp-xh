import { GitCompare, Eye } from "lucide-react";
import { Checkbox } from "@/components/ui/checkbox";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { RISK_COLORS } from "@/lib/constants";
import { formatScore } from "@/lib/format";
import type { Candidate } from "@/types";

type CandidateTableProps = {
  candidates: Candidate[];
};

export function CandidateTable({ candidates }: CandidateTableProps) {
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const selectedCandidateId = usePeptideFilterStore((s) => s.selectedCandidateId);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-xs font-medium text-slate-500 uppercase">
            <th className="py-3 px-3 text-left w-10">Cmp</th>
            <th className="py-3 px-3 text-left">Rank</th>
            <th className="py-3 px-3 text-left">Sequence</th>
            <th className="py-3 px-3 text-right">Len</th>
            <th className="py-3 px-3 text-right">Score</th>
            <th className="py-3 px-3 text-right">Disulfide</th>
            <th className="py-3 px-3 text-right">Charge</th>
            <th className="py-3 px-3 text-right">Hydro</th>
            <th className="py-3 px-3 text-right">pI</th>
            <th className="py-3 px-3 text-right">Net Chg</th>
            <th className="py-3 px-3 text-right">GRAVY</th>
            <th className="py-3 px-3 text-right">pI</th>
            <th className="py-3 px-3 text-right">Cys</th>
            <th className="py-3 px-3 text-left">Risk</th>
            <th className="py-3 px-3 text-left w-20">Action</th>
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => {
            const riskStyle = RISK_COLORS[c.disulfideRisk] ?? RISK_COLORS.unknown;
            const isCompared = comparedCandidateIds.includes(c.id);
            const isHighlighted = selectedCandidateId === c.id;

            return (
              <tr
                key={c.id}
                className={`border-b border-slate-100 hover:bg-slate-50/80 cursor-pointer transition-colors ${
                  isHighlighted ? "bg-teal-50/60 ring-1 ring-inset ring-teal-100" : ""
                }`}
                onClick={() => selectCandidate(c.id)}
              >
                <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                  <Checkbox
                    checked={isCompared}
                    onCheckedChange={() => toggleCompareCandidate(c.id)}
                  />
                </td>
                <td className="py-3 px-3 font-semibold tabular-nums">#{c.rank}</td>
                <td className="py-3 px-3">
                  <span className="sequence-mono font-semibold text-slate-800">{c.sequence}</span>
                </td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{c.length}</td>
                <td className="py-3 px-3 text-right tabular-nums font-semibold">{formatScore(c.priorityScore)}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(c.disulfideScore)}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(c.chargeScore)}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(c.hydrophobicityScore)}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(c.pIScore)}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(Number(c.netCharge))}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(Number(c.gravy))}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{formatScore(Number(c.pI))}</td>
                <td className="py-3 px-3 text-right tabular-nums text-slate-600">{c.cysCount}</td>
                <td className="py-3 px-3">
                  <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-[10px] font-medium`}>
                    {c.disulfideRisk}
                  </Badge>
                </td>
                <td className="py-3 px-3" onClick={(e) => e.stopPropagation()}>
                  <div className="flex items-center gap-1">
                    <button
                      className="p-1 rounded hover:bg-slate-100 text-slate-500 hover:text-slate-700"
                      onClick={() => selectCandidate(c.id)}
                      title="View detail"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    <button
                      className={`p-1 rounded hover:bg-slate-100 ${
                        isCompared ? "text-teal-600" : "text-slate-500 hover:text-slate-700"
                      }`}
                      onClick={() => toggleCompareCandidate(c.id)}
                      title="Compare"
                    >
                      <GitCompare className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function CandidateTableSkeleton() {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="bg-slate-50 text-xs font-medium text-slate-500 uppercase">
            {Array.from({ length: 15 }).map((_, i) => (
              <th key={i} className="py-3 px-3 text-left">
                <Skeleton className="h-3 w-12" />
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {Array.from({ length: 6 }).map((_, rowIdx) => (
            <tr key={rowIdx} className="border-b border-slate-100">
              {Array.from({ length: 15 }).map((__, colIdx) => (
                <td key={colIdx} className="py-3 px-3">
                  <Skeleton className="h-3 w-full" />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
