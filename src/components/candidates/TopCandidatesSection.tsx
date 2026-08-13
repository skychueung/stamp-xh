import { useMemo } from "react";
import { Award } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { MOCK_CANDIDATES } from "@/lib/constants";
import { CandidateSummaryCard } from "./CandidateSummaryCard";

export function TopCandidatesSection() {
  const candidates = usePeptideFilterStore((s) => s.candidates);

  const top3 = useMemo(() => {
    return candidates.length > 0 ? candidates.slice(0, 3) : MOCK_CANDIDATES;
  }, [candidates]);

  return (
    <section>
      <div className="flex items-center gap-2 mb-4">
        <Award className="h-5 w-5 text-slate-600" />
        <h2 className="text-lg font-semibold text-slate-900">Top Candidates</h2>
        <span className="text-sm text-slate-500 ml-1">前三名候选肽段</span>
      </div>
      <p className="text-sm text-slate-600 mb-4">
        Highest-scoring peptides after multi-dimensional filtering and ranking
      </p>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {top3.map((candidate) => (
          <CandidateSummaryCard key={candidate.id} candidate={candidate} />
        ))}
      </div>
    </section>
  );
}
