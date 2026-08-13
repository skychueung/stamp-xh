export type RiskLevel = "low" | "medium" | "high" | "unknown";

export type Candidate = {
  id: string;
  rank: number;
  sequence: string;
  length: number;

  priorityScore: number;
  disulfideScore: number;
  chargeScore: number;
  hydrophobicityScore: number;
  pIScore: number;

  netCharge: number | string;
  gravy: number | string;
  pI: number | string;
  cysCount: number;
  disulfideRisk: RiskLevel;

  rankingReason: string;
  topAdvantages: string[];

  passLength?: boolean;
  passCharge?: boolean;
  passGravy?: boolean;
  passPI?: boolean;
  passCys?: boolean;
};
