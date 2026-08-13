import { useMemo, useState } from "react";
import { Copy, Check, GitCompare, ArrowRight, Shield, Zap, Beaker, FlaskConical, Dna } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { RISK_COLORS } from "@/lib/constants";
import { formatScore } from "@/lib/format";

export function CandidateDetailDrawer() {
  const selectedCandidateId = usePeptideFilterStore((s) => s.selectedCandidateId);
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const candidates = usePeptideFilterStore((s) => s.candidates);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);
  const [copied, setCopied] = useState(false);

  const open = selectedCandidateId !== null;
  const onOpenChange = (v: boolean) => {
    if (!v) selectCandidate(null);
  };

  const candidate = useMemo(() => {
    return candidates.find((c) => c.id === selectedCandidateId) ?? null;
  }, [candidates, selectedCandidateId]);

  const isCompared = candidate ? comparedCandidateIds.includes(candidate.id) : false;

  const handleCopy = () => {
    if (candidate?.sequence) {
      void navigator.clipboard.writeText(candidate.sequence);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (!candidate) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent className="w-[min(520px,90vw)] overflow-y-auto">
          <div className="flex items-center justify-center h-full text-slate-400">
            No candidate selected
          </div>
        </SheetContent>
      </Sheet>
    );
  }

  const riskStyle = RISK_COLORS[candidate.disulfideRisk] ?? RISK_COLORS.unknown;

  const scoreBars = [
    { label: "Disulfide", score: candidate.disulfideScore, icon: <Shield className="h-3.5 w-3.5" /> },
    { label: "Charge", score: candidate.chargeScore, icon: <Zap className="h-3.5 w-3.5" /> },
    { label: "Hydrophobicity", score: candidate.hydrophobicityScore, icon: <Beaker className="h-3.5 w-3.5" /> },
    { label: "pI", score: candidate.pIScore, icon: <FlaskConical className="h-3.5 w-3.5" /> },
  ];

  const filterChecks = [
    { label: "Length", pass: candidate.passLength },
    { label: "Charge", pass: candidate.passCharge },
    { label: "GRAVY", pass: candidate.passGravy },
    { label: "pI", pass: candidate.passPI },
    { label: "Cysteine", pass: candidate.passCys },
  ];

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(520px,90vw)] overflow-y-auto scrollbar-thin">
        <SheetHeader className="pb-4">
          <div className="flex items-center justify-between">
            <SheetTitle className="flex items-center gap-2 text-lg">
              <Dna className="h-5 w-5 text-slate-600" />
              Candidate Detail
            </SheetTitle>
          </div>
        </SheetHeader>

        {/* Overview */}
        <div className="rounded-xl bg-slate-50 border border-slate-200 p-4 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-200 text-sm font-bold">
              #{candidate.rank}
            </span>
            <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-xs font-medium`}>
              {candidate.disulfideRisk}
            </Badge>
          </div>
          <div className="rounded-lg bg-white px-3 py-2 border border-slate-100 mt-2">
            <span className="sequence-mono text-lg font-bold text-slate-900">{candidate.sequence}</span>
          </div>
          <div className="mt-3 flex items-center justify-between text-sm">
            <span className="text-slate-500">Length: <strong>{candidate.length}</strong> aa</span>
            <span className="text-slate-500">Priority: <strong>{formatScore(candidate.priorityScore)}</strong></span>
          </div>
        </div>

        {/* Score Breakdown */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-slate-900 mb-3">Score Breakdown</h4>
          <div className="space-y-3">
            {scoreBars.map((s) => (
              <div key={s.label}>
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-1.5 text-xs text-slate-600">
                    {s.icon}
                    {s.label}
                  </div>
                  <span className="text-xs font-mono font-medium tabular-nums">{formatScore(s.score)}</span>
                </div>
                <div className="h-2 rounded-full bg-slate-100 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-slate-500 transition-all duration-500"
                    style={{ width: `${(s.score ?? 0) * 100}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        <Separator className="my-4" />

        {/* Ranking Explanation */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-slate-900 mb-2">Ranking Explanation</h4>
          <p className="text-sm text-slate-600 leading-relaxed">{candidate.rankingReason}</p>
          <ul className="mt-3 space-y-1.5">
            {(Array.isArray(candidate.topAdvantages) ? candidate.topAdvantages : []).map((adv, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-600">
                <ArrowRight className="h-3.5 w-3.5 text-teal-500 mt-0.5 shrink-0" />
                {adv}
              </li>
            ))}
          </ul>
        </div>

        <Separator className="my-4" />

        {/* Filter Pass Status */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-slate-900 mb-3">Filter Pass Status</h4>
          <div className="grid grid-cols-5 gap-2">
            {filterChecks.map((f) => (
              <div
                key={f.label}
                className={`rounded-lg border px-2 py-2 text-center ${
                  f.pass
                    ? "bg-emerald-50 border-emerald-200"
                    : f.pass === false
                    ? "bg-rose-50 border-rose-200"
                    : "bg-slate-50 border-slate-200"
                }`}
              >
                <div
                  className={`text-lg font-bold ${
                    f.pass ? "text-emerald-600" : f.pass === false ? "text-rose-600" : "text-slate-400"
                  }`}
                >
                  {f.pass ? "✓" : f.pass === false ? "✗" : "—"}
                </div>
                <div className="text-[10px] text-slate-500 mt-1">{f.label}</div>
              </div>
            ))}
          </div>
        </div>

        <Separator className="my-4" />

        {/* Metrics grid */}
        <div className="mb-4">
          <h4 className="text-sm font-semibold text-slate-900 mb-3">Properties</h4>
          <div className="grid grid-cols-2 gap-2">
            <MetricRow label="Net Charge" value={formatScore(Number(candidate.netCharge))} />
            <MetricRow label="GRAVY" value={formatScore(Number(candidate.gravy))} />
            <MetricRow label="pI" value={formatScore(Number(candidate.pI))} />
            <MetricRow label="Cys Count" value={String(candidate.cysCount)} />
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2">
          <Button
            variant="outline"
            className="flex-1 rounded-lg border-slate-200 text-slate-700 hover:bg-slate-50 text-sm gap-2"
            onClick={() => toggleCompareCandidate(candidate.id)}
          >
            <GitCompare className="h-4 w-4" />
            {isCompared ? "Remove Compare" : "Add to Compare"}
          </Button>
          <Button
            variant="outline"
            className="flex-1 rounded-lg border-slate-200 text-slate-700 hover:bg-slate-50 text-sm gap-2"
            onClick={handleCopy}
          >
            {copied ? <Check className="h-4 w-4 text-emerald-500" /> : <Copy className="h-4 w-4" />}
            {copied ? "Copied" : "Copy"}
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className="text-sm font-semibold tabular-nums">{value}</span>
    </div>
  );
}
