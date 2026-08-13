export interface SecondaryStructureComposition {
  helix: number;
  sheet: number;
  coil: number;
}

export interface CandidateStructure {
  id: string;
  name: string;
  sequence: string;
  length: number;
  netCharge: number;
  meanPlddt: number;
  pdbUrl: string;
  secondaryStructure: SecondaryStructureComposition;
}

export type StructureRenderMode = 'cartoon' | 'surface' | 'ball-and-stick';

export interface MolstarViewerProps {
  pdbUrl: string;
  height?: number;
  viewerId: string;
}

export interface SecondaryStructureBarProps {
  composition: SecondaryStructureComposition;
}

export interface PlddtBadgeProps {
  value: number;
}

export interface CandidateStructureCardProps {
  candidate: CandidateStructure;
}
