import { Award } from "lucide-react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { TopCandidateCard, TopCandidateCardSkeleton } from "./TopCandidateCard";
import type { Candidate } from "@/types";

type TopThreeCardsProps = {
  candidates: Candidate[];
  status: "idle" | "loading" | "success" | "error" | "warming";
};

export function TopThreeCards({ candidates, status }: TopThreeCardsProps) {
  const selectedCandidateId = usePeptideFilterStore((s) => s.selectedCandidateId);

  const isEmpty = status === "idle" || (status === "success" && candidates.length === 0);

  if (status === "loading") {
    return (
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Award className="h-4 w-4 text-slate-600" />
          <h2 className="text-base font-semibold text-slate-900">Top 3 Candidates</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <TopCandidateCardSkeleton />
          <TopCandidateCardSkeleton />
          <TopCandidateCardSkeleton />
        </div>
      </section>
    );
  }

  if (isEmpty) {
    return (
      <section>
        <div className="flex items-center gap-2 mb-3">
          <Award className="h-4 w-4 text-slate-600" />
          <h2 className="text-base font-semibold text-slate-900">Top 3 Candidates</h2>
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="rounded-xl border border-slate-200 bg-slate-50/50 p-4 flex flex-col items-center justify-center text-center min-h-[200px]"
            >
              <span className="text-3xl font-bold text-slate-200">#{i}</span>
              <p className="text-xs text-slate-400 mt-2">No data</p>
            </div>
          ))}
        </div>
      </section>
    );
  }

  const top3 = candidates.slice(0, 3);

  return (
    <section>
      <div className="flex items-center gap-2 mb-3">
        <Award className="h-4 w-4 text-slate-600" />
        <h2 className="text-base font-semibold text-slate-900">Top 3 Candidates</h2>
        <span className="text-xs text-slate-500 ml-1">前三名候选肽段</span>
      </div>
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {top3.map((candidate) => (
          <TopCandidateCard
            key={candidate.id}
            candidate={candidate}
            isHighlighted={selectedCandidateId === candidate.id}
          />
        ))}
      </div>
    </section>
  );
}
