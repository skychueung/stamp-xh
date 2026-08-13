import { useMemo } from "react";
import { GitCompare, Check } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { RISK_COLORS } from "@/lib/constants";
import { formatScore } from "@/lib/format";

export function CandidateCompareDrawer() {
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);
  const candidates = usePeptideFilterStore((s) => s.candidates);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);

  const open = comparedCandidateIds.length > 0;

  const compared = useMemo(() => {
    return comparedCandidateIds
      .map((id) => candidates.find((c) => c.id === id))
      .filter(Boolean) as typeof candidates;
  }, [comparedCandidateIds, candidates]);

  const onOpenChange = (v: boolean) => {
    if (!v) {
      // Clear all compared candidates when closing
      comparedCandidateIds.forEach((id) => toggleCompareCandidate(id));
    }
  };

  if (compared.length === 0) return null;

  const comparisonRows = [
    { label: "Sequence", key: "sequence", format: (v: unknown) => String(v) },
    { label: "Length", key: "length", format: (v: unknown) => `${v} aa` },
    { label: "Priority Score", key: "priorityScore", format: (v: unknown) => formatScore(Number(v)) },
    { label: "Disulfide Score", key: "disulfideScore", format: (v: unknown) => formatScore(Number(v)) },
    { label: "Charge Score", key: "chargeScore", format: (v: unknown) => formatScore(Number(v)) },
    { label: "Hydrophobicity", key: "hydrophobicityScore", format: (v: unknown) => formatScore(Number(v)) },
    { label: "pI Score", key: "pIScore", format: (v: unknown) => formatScore(Number(v)) },
    { label: "Net Charge", key: "netCharge", format: (v: unknown) => formatScore(Number(v)) },
    { label: "GRAVY", key: "gravy", format: (v: unknown) => formatScore(Number(v)) },
    { label: "pI", key: "pI", format: (v: unknown) => formatScore(Number(v)) },
    { label: "Cys Count", key: "cysCount", format: (v: unknown) => String(v) },
  ];

  function getValue(candidate: (typeof candidates)[0], key: string): unknown {
    return (candidate as Record<string, unknown>)[key];
  }

  function isBestValue(row: typeof comparisonRows[0], value: unknown, allValues: unknown[]): boolean {
    if (row.key === "sequence" || row.key === "length") return false;
    const nums = allValues.map((v) => Number(v));
    if (nums.some(isNaN)) return false;
    const max = Math.max(...nums);
    return Number(value) === max;
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-[min(720px,95vw)] overflow-y-auto scrollbar-thin">
        <SheetHeader className="pb-4">
          <SheetTitle className="flex items-center gap-2 text-lg">
            <GitCompare className="h-5 w-5 text-slate-600" />
            Compare Candidates
          </SheetTitle>
        </SheetHeader>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr>
                <th className="py-2 px-3 text-left text-xs font-medium text-slate-500 sticky left-0 bg-white min-w-[120px]">
                  Property
                </th>
                {compared.map((c) => (
                  <th key={c.id} className="py-2 px-3 text-center min-w-[120px]">
                    <div className="flex flex-col items-center gap-1">
                      <span className="sequence-mono text-xs font-bold text-slate-800">{c.sequence}</span>
                      <Badge variant="secondary" className="text-[10px]">
                        #{c.rank}
                      </Badge>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {comparisonRows.map((row, rowIdx) => {
                const allValues = compared.map((c) => getValue(c, row.key));
                return (
                  <tr
                    key={row.key}
                    className={rowIdx % 2 === 0 ? "bg-slate-50/50" : ""}
                  >
                    <td className="py-2.5 px-3 text-xs font-medium text-slate-600 sticky left-0 bg-inherit">
                      {row.label}
                    </td>
                    {compared.map((c) => {
                      const val = getValue(c, row.key);
                      const best = isBestValue(row, val, allValues);
                      return (
                        <td key={c.id} className="py-2.5 px-3 text-center">
                          {best ? (
                            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                              <Check className="h-3 w-3" />
                              {row.format(val)}
                            </span>
                          ) : (
                            <span className="text-xs text-slate-700">{row.format(val)}</span>
                          )}
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
              {/* Risk row */}
              <tr className="bg-slate-50/50">
                <td className="py-2.5 px-3 text-xs font-medium text-slate-600 sticky left-0 bg-inherit">
                  Risk
                </td>
                {compared.map((c) => {
                  const riskStyle = RISK_COLORS[c.disulfideRisk] ?? RISK_COLORS.unknown;
                  return (
                    <td key={c.id} className="py-2.5 px-3 text-center">
                      <Badge className={`${riskStyle.bg} ${riskStyle.text} border-0 text-[10px] font-medium`}>
                        {c.disulfideRisk}
                      </Badge>
                    </td>
                  );
                })}
              </tr>
              {/* Pass status row */}
              <tr>
                <td className="py-2.5 px-3 text-xs font-medium text-slate-600 sticky left-0 bg-white">
                  Pass Status
                </td>
                {compared.map((c) => (
                  <td key={c.id} className="py-2.5 px-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      {c.passLength !== undefined && (
                        <PassDot pass={c.passLength} />
                      )}
                      {c.passCharge !== undefined && (
                        <PassDot pass={c.passCharge} />
                      )}
                      {c.passGravy !== undefined && (
                        <PassDot pass={c.passGravy} />
                      )}
                      {c.passPI !== undefined && (
                        <PassDot pass={c.passPI} />
                      )}
                      {c.passCys !== undefined && (
                        <PassDot pass={c.passCys} />
                      )}
                    </div>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      </SheetContent>
    </Sheet>
  );
}

function PassDot({ pass }: { pass: boolean | undefined }) {
  if (pass === undefined) return null;
  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${
        pass ? "bg-emerald-500" : "bg-rose-500"
      }`}
      title={pass ? "Pass" : "Fail"}
    />
  );
}
