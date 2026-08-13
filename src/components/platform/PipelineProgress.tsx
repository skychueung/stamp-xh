import { useNavigate } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import type { PipelineStep } from '@/types/platform';

interface PipelineProgressProps {
  currentStep: number;
}

export function PipelineProgress({ currentStep }: PipelineProgressProps) {
  const { t } = useLanguage();
  const navigate = useNavigate();

  const PIPELINE_STEPS: PipelineStep[] = [
    { step: 1, label: t.pipeline.targetProtein, description: 'Input target protein sequence or structure', status: 'pending', route: '/target-protein' },
    { step: 2, label: t.pipeline.epitopePrediction, description: 'Predict surface-exposed epitopes', status: 'pending', route: '/epitope-screening' },
    { step: 3, label: t.pipeline.epitopeScreening, description: 'Filter epitopes by physicochemical properties', status: 'pending', route: '/epitope-screening' },
    { step: 4, label: t.pipeline.recommendedEpitope, description: 'Select optimal target epitope', status: 'pending', route: '/epitope-screening' },
    { step: 5, label: t.pipeline.peptideGeneration, description: 'Generate complementary targeting peptides', status: 'pending', route: '/peptide-generation' },
    { step: 6, label: t.pipeline.peptideFiltering, description: 'Filter peptides by developability', status: 'pending', route: '/peptide-optimization' },
    { step: 7, label: t.pipeline.complementarity, description: 'Score epitope-peptide complementarity', status: 'pending', route: '/peptide-optimization' },
    { step: 8, label: t.pipeline.structureValidation, description: 'Validate complexes by 3D docking', status: 'pending', route: '/structure-validation' },
    { step: 9, label: t.pipeline.topCandidates, description: 'Rank and export top candidates', status: 'pending', route: '/final-ranking' },
  ];

  const steps = PIPELINE_STEPS.map((s) => ({
    ...s,
    status: s.step < currentStep ? 'completed' : s.step === currentStep ? 'current' : 'pending',
  }));

  return (
    <div className="w-full bg-white rounded-lg border border-xh-border p-4 mb-6">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-sm font-semibold text-xh-text">Pipeline Progress</h3>
        <span className="text-xs text-xh-muted">
          Step {currentStep} of {PIPELINE_STEPS.length}
        </span>
      </div>
      <div className="flex items-center gap-1 overflow-x-auto pb-2 scrollbar-thin">
        {steps.map((step, index) => (
          <div key={step.step} className="flex items-center shrink-0">
            <button
              type="button"
              onClick={() => navigate(step.route)}
              className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium transition-colors cursor-pointer whitespace-nowrap ${
                step.status === 'current'
                  ? 'bg-xh-primary text-white'
                  : step.status === 'completed'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-gray-50 text-gray-400 border border-gray-100'
              }`}
            >
              <span
                className={`flex items-center justify-center w-5 h-5 rounded-full text-[10px] font-bold ${
                  step.status === 'current'
                    ? 'bg-white text-xh-primary'
                    : step.status === 'completed'
                      ? 'bg-emerald-100 text-emerald-700'
                      : 'bg-gray-200 text-gray-400'
                }`}
              >
                {step.status === 'completed' ? '✓' : step.step}
              </span>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {index < steps.length - 1 && (
              <div
                className={`w-4 h-px mx-1 shrink-0 ${
                  step.status === 'completed' ? 'bg-emerald-300' : 'bg-gray-200'
                }`}
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
