import { useMemo } from "react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";
import { TopCandidateSummary } from "./TopCandidateSummary";
import { TopThreeCards } from "./TopThreeCards";
import { CandidateResultsTable } from "./CandidateResultsTable";
import { ModeStatusBar } from "./ModeStatusBar";

export function ResultsPanel() {
  const candidates = usePeptideFilterStore((s) => s.candidates);
  const status = usePeptideFilterStore((s) => s.status);
  const selectedCandidateId = usePeptideFilterStore((s) => s.selectedCandidateId);

  const top1 = useMemo(() => {
    if (candidates.length === 0) return null;
    if (selectedCandidateId) {
      return candidates.find((c) => c.id === selectedCandidateId) ?? candidates[0];
    }
    return candidates[0];
  }, [candidates, selectedCandidateId]);

  const top3 = useMemo(() => candidates.slice(0, 3), [candidates]);

  return (
    <div className="space-y-6">
      <ModeStatusBar />
      <TopCandidateSummary candidate={top1} status={status} />
      <TopThreeCards candidates={top3} status={status} />
      <CandidateResultsTable candidates={candidates} status={status} />
    </div>
  );
}
