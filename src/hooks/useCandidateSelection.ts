import { useCallback } from "react";
import { usePeptideFilterStore } from "@/store/peptideFilterStore";

export function useCandidateSelection() {
  const selectCandidate = usePeptideFilterStore((s) => s.selectCandidate);
  const toggleCompareCandidate = usePeptideFilterStore((s) => s.toggleCompareCandidate);
  const selectedCandidateId = usePeptideFilterStore((s) => s.selectedCandidateId);
  const comparedCandidateIds = usePeptideFilterStore((s) => s.comparedCandidateIds);

  const openDetail = useCallback(
    (id: string) => selectCandidate(id),
    [selectCandidate]
  );

  const closeDetail = useCallback(
    () => selectCandidate(null),
    [selectCandidate]
  );

  const toggleCompare = useCallback(
    (id: string) => toggleCompareCandidate(id),
    [toggleCompareCandidate]
  );

  const isSelected = useCallback(
    (id: string) => selectedCandidateId === id,
    [selectedCandidateId]
  );

  const isCompared = useCallback(
    (id: string) => comparedCandidateIds.includes(id),
    [comparedCandidateIds]
  );

  const compareCount = comparedCandidateIds.length;
  const canAddMore = compareCount < 4;

  return {
    openDetail,
    closeDetail,
    toggleCompare,
    isSelected,
    isCompared,
    compareCount,
    canAddMore,
    selectedCandidateId,
    comparedCandidateIds,
  };
}
