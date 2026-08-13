import { useCallback, useMemo, useState } from "react";
import { Award, Zap, Beaker, ArrowRight, Copy, Check, GitCompare, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { MOCK_CANDIDATES, RISK_COLORS } from "@/lib/constants";
import { formatScore, formatSequence } from "@/lib/format";

export function TopCandidateSpotlight() {
  const candidates = usePeptideFilterStore((s) => s.candidates);
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);
  const [copied, setCopied] = useState(false);

  const topCandidate = useMemo(() => {
    return candidates.length > 0 ? candidates[0] : MOCK_CANDIDATES[0];
  }, [candidates]);

  const isCompared = comparedCandidateIds.includes(topCandidate.id);

  const handleCopy = useCallback(() => {
    if (topCandidate?.sequence) {
      void navigator.clipboard.writeText(topCandidate.sequence);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [topCandidate]);

  const riskStyle = RISK_COLORS[topCandidate.disulfideRisk] ?? RISK_COLORS.unknown;

  return (
    <div className="rounded-2xl bg-gradient-to-br from-slate-900 to-slate-800 p-6 text-white shadow-sm h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <span className="text-[10px] font-semibold uppercase tracking-widest text-slate-400">
            Top Candidate Spotlight
          </span>
          <h2 className="text-xl font-semibold mt-1">最佳候选肽段</h2>
        </div>
        <div className="flex items-center gap-1.5 rounded-full bg-white/10 px-3 py-1.5">
          <Award className="h-4 w-4 text-sky-400" />
          <span className="text-sm font-bold">#{topCandidate.rank}</span>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col items-center justify-center text-center py-4">
        {/* Sequence */}
        <div className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-5 py-3 border border-white/10">
          <span className="sequence-mono text-2xl font-bold tracking-wider">
            {formatSequence(topCandidate.sequence, 20)}
          </span>
        </div>

        {/* Priority Score */}
        <div className="mt-6 w-full max-w-xs">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-slate-400">Priority Score</span>
            <span className="text-lg font-bold tabular-nums">
              {formatScore(topCandidate.priorityScore)}
            </span>
          </div>
          <div className="h-2 rounded-full bg-white/10 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-400 to-emerald-400 transition-all duration-700 ease-out"
              style={{ width: `${(topCandidate.priorityScore ?? 0) * 100}%` }}
            />
          </div>
        </div>

        {/* Metric Pills */}
        <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
          <MetricPill icon={<Zap className="h-3 w-3" />} label="Charge" value={formatScore(Number(topCandidate.netCharge))} />
          <MetricPill icon={<Beaker className="h-3 w-3" />} label="GRAVY" value={formatScore(Number(topCandidate.gravy))} />
          <MetricPill icon={<span className="text-[10px] font-bold">pI</span>} label="pI" value={formatScore(Number(topCandidate.pI))} />
          <MetricPill
            icon={<span className="text-[10px] font-bold">C</span>}
            label="Cys"
            value={String(topCandidate.cysCount)}
          />
          <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-xs font-medium`}>
            {topCandidate.disulfideRisk}
          </Badge>
        </div>

        {/* Why it stands out */}
        <div className="mt-6 text-left w-full max-w-sm">
          <h4 className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">
            Why it stands out
          </h4>
          <ul className="space-y-1.5">
            {topCandidate.topAdvantages.map((adv, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                <ArrowRight className="h-3.5 w-3.5 text-teal-400 mt-0.5 shrink-0" />
                {adv}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-6 flex items-center gap-2">
        <Button
          variant="ghost"
          className="flex-1 text-white/80 hover:text-white hover:bg-white/10 rounded-lg text-sm gap-2"
          onClick={() => selectCandidate(topCandidate.id)}
        >
          <Eye className="h-4 w-4" />
          View Detail
        </Button>
        <Button
          variant="ghost"
          className={`flex-1 rounded-lg text-sm gap-2 ${
            isCompared
              ? "text-teal-400 hover:text-teal-300 hover:bg-white/10"
              : "text-white/80 hover:text-white hover:bg-white/10"
          }`}
          onClick={() => toggleCompareCandidate(topCandidate.id)}
        >
          <GitCompare className="h-4 w-4" />
          {isCompared ? "Added" : "Compare"}
        </Button>
        <Button
          variant="ghost"
          className="flex-1 text-white/80 hover:text-white hover:bg-white/10 rounded-lg text-sm gap-2"
          onClick={handleCopy}
        >
          {copied ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
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
    <div className="flex items-center gap-1.5 rounded-lg bg-white/5 px-2.5 py-1.5 border border-white/10">
      <span className="text-slate-400">{icon}</span>
      <span className="text-[10px] text-slate-500 uppercase">{label}</span>
      <span className="text-xs font-semibold tabular-nums">{value}</span>
    </div>
  );
}
