import { create } from "zustand";
import type { Candidate, PipelineStep, PredictionSummary, FilterParams } from "@/types";

type DataStatus = "idle" | "loading" | "success" | "error" | "warming";

type PeptideFilterState = {
  params: FilterParams;
  status: DataStatus;
  errorMessage: string | null;

  summary: PredictionSummary | null;
  pipelineSteps: PipelineStep[];
  candidates: Candidate[];

  selectedCandidateId: string | null;
  comparedCandidateIds: string[];
  activePipelineStepKey: string | null;

  setParams: (patch: Partial<FilterParams>) => void;
  setStatus: (status: DataStatus) => void;
  setErrorMessage: (message: string | null) => void;

  setPredictionResult: (payload: {
    summary: PredictionSummary;
    pipelineSteps: PipelineStep[];
    candidates: Candidate[];
  }) => void;

  selectCandidate: (id: string | null) => void;
  toggleCompareCandidate: (id: string) => void;
  setActivePipelineStep: (key: string | null) => void;
  resetAll: () => void;
};

export const usePeptideFilterStore = create<PeptideFilterState>((set) => ({
  params: {
    proteinName: "user_seq",
    proteinSequence: "",
    candidateCount: 120,
    lenMin: 5,
    lenMax: 15,
    chargeMin: -2,
    chargeMax: 2,
    gravyMin: -2,
    gravyMax: 2,
    piMin: 5,
    piMax: 9,
    cysMax: 2,
    disulfideWeight: 0.25,
    chargeWeight: 0.25,
    hydrophobicityWeight: 0.25,
    piWeight: 0.25,
  },
  status: "idle",
  errorMessage: null,
  summary: null,
  pipelineSteps: [],
  candidates: [],
  selectedCandidateId: null,
  comparedCandidateIds: [],
  activePipelineStepKey: null,

  setParams: (patch) => set((state) => ({ params: { ...state.params, ...patch } })),
  setStatus: (status) => set({ status }),
  setErrorMessage: (errorMessage) => set({ errorMessage }),

  setPredictionResult: ({ summary, pipelineSteps, candidates }) =>
    set({
      summary,
      pipelineSteps,
      candidates,
      status: "success",
      errorMessage: null,
      activePipelineStepKey: pipelineSteps[0]?.key ?? null,
    }),

  selectCandidate: (id) => set({ selectedCandidateId: id }),
  toggleCompareCandidate: (id) =>
    set((state) => {
      const exists = state.comparedCandidateIds.includes(id);
      return {
        comparedCandidateIds: exists
          ? state.comparedCandidateIds.filter((x) => x !== id)
          : [...state.comparedCandidateIds, id].slice(0, 4),
      };
    }),
  setActivePipelineStep: (key) => set({ activePipelineStepKey: key }),

  resetAll: () =>
    set({
      status: "idle",
      errorMessage: null,
      summary: null,
      pipelineSteps: [],
      candidates: [],
      selectedCandidateId: null,
      comparedCandidateIds: [],
      activePipelineStepKey: null,
    }),
}));
