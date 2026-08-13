/**
 * STAMP Platform — Computational Structure Validation Types (v0.10-P6o)
 *
 * Lightweight re-export of structure prediction, interface quality,
 * and energy quality types originally defined in projectResults.ts.
 *
 * Use this file when you only need validation-related types without
 * pulling in the full project-results schema.
 */

export type {
  StructurePredictionMetrics,
  InterfaceQualityMetrics,
  InterfaceQualityInputFeatures,
  InterfaceQualityProvenance,
  InterfaceQualityForbiddenMetrics,
  EnergyQualityMetrics,
  EnergyQualityTerms,
  EnergyQualityFlags,
  EnergyQualityForbiddenMetrics,
  ForbiddenMetrics,
} from './projectResults';
