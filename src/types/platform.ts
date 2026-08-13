export type StatusType = 'pass' | 'warning' | 'fail' | 'pending' | 'processing';

export type PipelineStep = {
  step: number;
  label: string;
  description: string;
  status: 'completed' | 'current' | 'pending';
  route: string;
};

export type TargetType = 'membrane' | 'receptor' | 'enzyme' | 'pathogen_surface';

export type TargetProteinInput = {
  name: string;
  species: string;
  targetType: TargetType;
  sequence: string;
  regionOfInterest: string;
  notes: string;
  uniprotId?: string;
  pdbFile?: string;
};

export type TargetProteinSummary = {
  length: number;
  predictedLocalization: string;
  transmembraneHelices: number;
  signalPeptide: boolean;
  domainCount: number;
  structureAvailability: string;
};

export type RecommendedCheck = {
  label: string;
  passed: boolean;
  detail?: string;
};

export type EpitopeMetrics = {
  surfaceAccessibility: number;
  functionalRelevance: number;
  specificityRisk: number;
  disorderScore: number;
  flexibilityScore: number;
  secondaryStructure: string;
};

export type EpitopeCandidate = {
  id: string;
  rank: number;
  start: number;
  end: number;
  sequence: string;
  length: number;
  charge: number;
  hydrophobicity: number;
  pI: number;
  cysteineCount: number;
  bepiPredScore: number;
  surfaceExposure: number;
  functionalRelevance: number;
  specificityRisk: number;
  disorder: number;
  flexibility: number;
  secondaryStructure: string;
  overallScore: number;
  metrics: EpitopeMetrics;
  regionType: 'extracellular_loop' | 'surface_exposed' | 'transmembrane';
  recommendationReason?: string;
};

export type PeptideMetrics = {
  solubility: number;
  aggregationPropensity: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  toxicityRisk: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  hemolysisRisk: number;
  proteaseStability: number;
  synthesisDifficulty: number;
  repeatedResidues: boolean;
  extremeHydrophobicity: boolean;
  offTargetSimilarity: number;
};

export type GeneratedPeptide = {
  id: string;
  rank: number;
  sequence: string;
  length: number;
  netCharge: number;
  pI: number;
  hydrophobicity: number;
  solubility: number;
  complementarityPreScore: number;
  offTargetRisk: number;
  novelty: number;
  diversityCluster: string;
  status: StatusType;
  metrics: PeptideMetrics;
};

export type OptimizedPeptide = {
  id: string;
  candidate: string;
  sequence: string;
  solubility: number;
  aggregationRisk: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  toxicity: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  hemolysis: number;
  proteaseStability: number;
  synthesisDifficulty: number;
  overallScore: number;
  isOptimized: boolean;
};

export type OptimizationSettings = {
  strategy: 'masked_mutation' | 'topk_sampling' | 'multi_round';
  rounds: number;
  mutationRate: number;
  keepCoreResidues: boolean;
  solubilityWeight: number;
  aggregationPenalty: number;
  toxicityPenalty: number;
  hemolysisPenalty: number;
  proteaseStabilityWeight: number;
  synthesisDifficultyWeight: number;
};

export type StructureMetrics = {
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  ipTM: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  pDockQ: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  interfaceDeltaG: number;
  epitopeContactRatio: number;
  contactResidues: number;
  distanceToEpitope: number;
  offEpitopeBindingRisk: 'low' | 'medium' | 'high';
  interfaceResidueMap: InterfaceContact[];
  bindingConfidence: number;
  structuralValidationStatus: StatusType;
};

export type InterfaceContact = {
  epitopeResidue: string;
  peptideResidue: string;
  distance: number;
  contactType: 'hydrophobic' | 'electrostatic' | 'hydrogen-bond' | 'van-der-waals';
  energy?: number;
};

// 3D 复合物验证核心数据结构
export interface StructureValidationData {
  // 复合物来源
  complexPdbUrl: string;
  targetPdbUrl?: string;

  // 链标识
  targetChainId: string;
  peptideChainId: string;

  // 表位定位（用于高亮）
  epitopeResidueRange: {
    start: number;
    end: number;
  };

  // 接触残基对（用于 Interface Contact Map）
  contactResidues: Array<{
    targetResidue: string;
    peptideResidue: string;
    distance: number;
    type: 'hydrophobic' | 'electrostatic' | 'hydrogen-bond' | 'van-der-waals';
    energy?: number;
  }>;

  // 界面指标（顶部卡片）
  interfaceMetrics: {
    ipTM: number;
    pDockQ: number;
    interfaceDeltaG: number;
    epitopeContactRatio: number;
    contactingResidues: number;
    distanceToEpitope: number;
  };

  // 风险评估（判断卡）
  offEpitopeBindingRisk: 'low' | 'medium' | 'high';
  bindingSiteMatch: 'passed' | 'warning' | 'failed';

  // 计算状态
  alphaFoldStatus: 'completed' | 'running' | 'pending';
  flexPepDockStatus: 'completed' | 'running' | 'pending';
  foldXEnergy: number;

  // 元数据
  modelSource: 'AlphaFold-Multimer' | 'ColabFold' | 'Custom';
  confidence: 'high' | 'medium' | 'low';
}

// 3D Viewer 加载选项
export interface LoadOptions {
  targetChainId?: string;
  peptideChainId?: string;
  epitopeRange?: { start: number; end: number };
  targetColor?: string;
}

export type ComplexInfo = {
  id: string;
  peptideSequence: string;
  epitopeSequence: string;
  epitopeRange: string;
  targetChainId: string;
  peptideChainId: string;
  predictionMethod: string;
  refinementMethod: string;
  pdbUrl: string;
};

export type DockingAnalysis = {
  alphaFoldMultimerStatus: string;
  flexPepDockStatus: string;
  foldXEnergy: number;
  hotspotContacts: number;
};

export type RankedPeptide = {
  id: string;
  rank: number;
  peptideSequence: string;
  targetEpitopeId: string;
  length: number;
  netCharge: number;
  pI: number;
  hydrophobicity: number;
  solubility: number;
  aggregationRisk: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  hemolysisRisk: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  toxicityRisk: number;
  proteaseStability: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  ipTM: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  pDockQ: number;
  /** MOCK_ONLY_NOT_RETURNED_BY_P5_LITE_BACKEND */
  interfaceDeltaG: number;
  epitopeContactRatio: number;
  contactResidues: number;
  offEpitopeBindingRisk: 'low' | 'medium' | 'high';
  structuralValidationStatus: StatusType;
  overallScore: number;
  recommendationReason: string;
  pdbUrl?: string;
};

export type RankingWeight = {
  label: string;
  key: string;
  value: number;
};

export type TableColumn<T> = {
  key: string;
  header: string;
  accessor: (row: T) => unknown;
  width?: string;
};

export type GenerationSettings = {
  model: 'pepmlm' | 'esm' | 'custom';
  candidateCount: number;
  lengthMin: number;
  lengthMax: number;
  netChargePreference: number;
  hydrophobicityTarget: number;
  diversityLevel: number;
  temperature: number;
  topK: number;
  seed: number;
  includeLinker: boolean;
};

export type ComplementarityScore = {
  electrostatic: number;
  hydrophobicMatching: number;
  shapeContact: number;
  sequenceCompatibility: number;
  bindingPreference: number;
  preScore: number;
};

export type FilterLayer = {
  label: string;
  passed: boolean;
  value?: string | number;
};

export type DevelopabilityFilter = {
  label: string;
  passed: boolean;
  riskLevel?: RiskLevel;
};

type RiskLevel = 'low' | 'medium' | 'high';
