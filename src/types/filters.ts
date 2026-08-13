export type FilterParams = {
  proteinName: string;
  proteinSequence: string;
  candidateCount: number;

  lenMin: number;
  lenMax: number;
  chargeMin: number;
  chargeMax: number;
  gravyMin: number;
  gravyMax: number;
  piMin: number;
  piMax: number;
  cysMax: number;

  disulfideWeight: number;
  chargeWeight: number;
  hydrophobicityWeight: number;
  piWeight: number;
};
