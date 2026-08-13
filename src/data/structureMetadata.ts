import type { CandidateStructure } from '@/types/structure-viewer';
import metadata from './structure-metadata.json' with { type: 'json' };

export const structureMetadata: CandidateStructure[] = metadata.structures;
