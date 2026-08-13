import type { FilterParams, PredictionSummary, PipelineStep, Candidate } from "@/types";

export type PredictResponse = {
  summary: PredictionSummary;
  pipelineSteps: PipelineStep[];
  candidates: Candidate[];
};

export async function checkApiHealth(): Promise<boolean> {
  try {
    const res = await fetch("/api/health", { method: "GET", cache: "no-store" });
    return res.ok;
  } catch {
    return false;
  }
}

export async function runPrediction(params: FilterParams): Promise<PredictResponse> {
  const payload = {
    name: params.proteinName,
    sequence: params.proteinSequence,
    min_len: params.lenMin,
    max_len: params.lenMax,
    min_charge: params.chargeMin,
    max_gravy: params.gravyMax,
    min_pi: params.piMin,
    max_pi: params.piMax,
    max_cys: params.cysMax,
    disulfide_weight: params.disulfideWeight,
    charge_weight: params.chargeWeight,
    hydrophobicity_weight: params.hydrophobicityWeight,
    pi_weight: params.piWeight,
  };

  const res = await fetch("/api/predict", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    throw new Error(`Prediction failed: HTTP ${res.status}`);
  }

  const data = await res.json();

  return {
    summary: {
      totalExtracted: data.total_extracted ?? 0,
      finalRetained: data.retained_count ?? 0,
      dropRate:
        data.total_extracted && data.retained_count !== undefined
          ? (data.total_extracted - data.retained_count) / data.total_extracted
          : 0,
      top1Sequence: data.ranked_peptides?.[0]?.sequence ?? null,
      top1Score: data.ranked_peptides?.[0]?.priority_score ?? null,
      proteinName: data.protein_name ?? null,
      sequenceLength: data.sequence_length ?? null,
      mode: data.mode ?? null,
      source: data.source ?? null,
      validationStatus: data.validation_status ?? null,
      note: data.note ?? null,
    },
    pipelineSteps: [],
    candidates: (data.ranked_peptides ?? []).map((item: Record<string, unknown>, idx: number) => ({
      id: `${idx + 1}-${item.sequence ?? "candidate"}`,
      rank: item.rank ?? idx + 1,
      sequence: item.sequence ?? "",
      length: item.length ?? 0,
      priorityScore: item.priority_score ?? 0,
      disulfideScore: item.disulfide_score ?? 0,
      chargeScore: item.charge_score ?? 0,
      hydrophobicityScore: item.hydrophobicity_score ?? 0,
      pIScore: item.pI_score ?? item.pi_score ?? 0,
      netCharge: item.Net_Charge_pH7_4 ?? "-",
      gravy: item.GRAVY ?? "-",
      pI: item.pI ?? "-",
      cysCount: item.Cys_Count ?? 0,
      disulfideRisk: item.Disulfide_Risk ?? "unknown",
      rankingReason: item.ranking_reason ?? "",
      topAdvantages: Array.isArray(item.top_advantages)
        ? item.top_advantages
        : typeof item.top_advantages === "string" && item.top_advantages
          ? item.top_advantages.split(";").filter(Boolean)
          : [],
      passLength: item.Pass_Length,
      passCharge: item.Pass_Charge,
      passGravy: item.Pass_GRAVY,
      passPI: item.Pass_pI,
      passCys: item.Pass_Cys,
    })),
  };
}
