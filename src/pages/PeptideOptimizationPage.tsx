import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { ScoreBar } from '@/components/platform/ScoreBar';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { StatusPill } from '@/components/platform/StatusPill';
import { DataTableShell } from '@/components/platform/DataTableShell';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';
import { pipelineRunsApi } from '@/lib/api/pipelineRuns';
import { mockSelectedEpitope, mockOptimizedPeptides } from '@/data/platformMockData';
import { Box, ArrowRight, Play, Filter } from 'lucide-react';

const BASIC_FILTERS = [
  { label: 'Length (8–20 aa)', passed: true },
  { label: 'Net Charge (-3 to +6)', passed: true },
  { label: 'Hydrophobicity (-1.0 to +0.5)', passed: true },
  { label: 'pI (4.0–10.0)', passed: true },
  { label: 'Cysteine / Disulfide (≤2)', passed: true },
];

const DEV_FILTERS = [
  { label: 'Solubility', passed: true, risk: 'low' as const },
  { label: 'Aggregation Propensity', passed: true, risk: 'low' as const },
  { label: 'Toxicity Risk', passed: true, risk: 'low' as const },
  { label: 'Hemolysis Risk', passed: true, risk: 'low' as const },
  { label: 'Protease Stability', passed: true, risk: 'low' as const },
  { label: 'Synthesis Difficulty', passed: true, risk: 'low' as const },
  { label: 'Repeated Residues', passed: true, risk: 'low' as const },
  { label: 'Extreme Hydrophobicity', passed: true, risk: 'low' as const },
  { label: 'Off-target Similarity', passed: true, risk: 'low' as const },
];

interface PipelineOptimizedPeptide {
  sequence: string;
  length: number;
  net_charge: number;
  hydrophobic_ratio: number;
  aggregation_risk_proxy: string;
  synthesis_risk_proxy: string;
  hemolysis_risk_proxy: string;
  rank_score: number;
}

export default function PeptideOptimizationPage() {
  const { t } = useLanguage();
  const [searchParams] = useSearchParams();
  const runId = searchParams.get('pipeline_run_id');
  const [pipelinePeptides, setPipelinePeptides] = useState<PipelineOptimizedPeptide[] | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  useEffect(() => {
    if (!runId) return;
    setPipelineLoading(true);
    pipelineRunsApi.get(runId)
      .then((run) => {
        const step = run.steps.find((s) => s.step_name === 'PEPTIDE_OPTIMIZATION');
        const peptides = step?.output_summary?.optimized_peptides as PipelineOptimizedPeptide[] | undefined;
        if (peptides) setPipelinePeptides(peptides);
      })
      .catch(() => setPipelinePeptides(null))
      .finally(() => setPipelineLoading(false));
  }, [runId]);

  const topOptimized = mockOptimizedPeptides.filter((p) => p.isOptimized);

  return (
    <PlatformLayout>
      <PipelineProgress currentStep={6} />
      <PipelineRunBanner />

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-xh-text tracking-tight">{t.pageTitle.peptideOptimization}</h1>
        <p className="text-sm text-xh-muted mt-1">
          {t.pageSubtitle.peptideOptimization}
        </p>
      </header>

      {/* Pipeline real data section */}
      {runId && (
        <SectionCard title={pipelineLoading ? '加载 Pipeline 数据...' : 'Pipeline 优化肽 (真实数据)'}>
          {pipelineLoading && <p className="text-sm text-xh-muted">加载中...</p>}
          {!pipelineLoading && pipelinePeptides && pipelinePeptides.length > 0 && (
            <DataTableShell>
              <thead>
                <tr className="bg-gray-50 border-b border-xh-border">
                  {['Sequence', 'Length', 'Net Charge', 'Hydrophobic', 'Agg Risk', 'Synth Risk', 'Hemo Risk', 'Rank Score'].map((h) => (
                    <th key={h} className="px-2 py-2 text-[10px] font-semibold text-xh-muted whitespace-nowrap uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {pipelinePeptides.map((p, i) => (
                  <tr key={i} className="border-b border-gray-50 last:border-0">
                    <td className="px-2 py-2 text-xs font-mono text-xh-text">{p.sequence}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.length}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.net_charge}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.hydrophobic_ratio.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.aggregation_risk_proxy}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.synthesis_risk_proxy}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.hemolysis_risk_proxy}</td>
                    <td className="px-2 py-2 text-xs font-bold text-xh-primary">{p.rank_score.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTableShell>
          )}
          {!pipelineLoading && (!pipelinePeptides || pipelinePeptides.length === 0) && (
            <p className="text-sm text-xh-muted">该 Pipeline Run 暂无优化肽数据。</p>
          )}
        </SectionCard>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <SectionCard title="Selected Epitope">
          <SequenceBadge sequence={mockSelectedEpitope.sequence} />
          <p className="text-xs text-xh-muted mt-2">{mockSelectedEpitope.start}-{mockSelectedEpitope.end} · {mockSelectedEpitope.regionType.replace('_', ' ')}</p>
        </SectionCard>
        <SectionCard title="Lead Targeting Peptide">
          <SequenceBadge sequence="RWYKYKWRYKYK" />
          <p className="text-xs text-xh-muted mt-2">Lead-1 · Initial complementarity score: 0.91</p>
        </SectionCard>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 space-y-6">
          <SectionCard title="Optimization Controls">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-xh-text mb-1.5">Strategy</label>
                <select className="w-full px-3 py-2 rounded-md border border-xh-border text-sm bg-white">
                  <option>Masked Mutation</option>
                  <option>Top-k Sampling</option>
                  <option>Multi-round Optimization</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-xh-text mb-1.5">Rounds</label>
                <input type="number" defaultValue={3} min={1} max={10} className="w-full px-3 py-2 rounded-md border border-xh-border text-sm" />
              </div>
              <div>
                <label className="block text-xs font-medium text-xh-text mb-1.5">Mutation Rate</label>
                <input type="number" defaultValue={0.15} step={0.05} min={0} max={1} className="w-full px-3 py-2 rounded-md border border-xh-border text-sm" />
              </div>
              <div className="flex items-center gap-2">
                <input type="checkbox" id="keepCore" defaultChecked className="rounded border-xh-border" />
                <label htmlFor="keepCore" className="text-xs text-xh-text">Keep Core Residues</label>
              </div>
            </div>

            <div className="mt-4 pt-4 border-t border-xh-border space-y-3">
              <p className="text-xs font-medium text-xh-text">Optimization Weights</p>
              <ScoreBar label="Solubility Weight" value={0.9} color="blue" />
              <ScoreBar label="Aggregation Penalty" value={0.85} color="blue" />
              <ScoreBar label="Toxicity Penalty" value={0.95} color="blue" />
              <ScoreBar label="Hemolysis Penalty" value={0.8} color="blue" />
              <ScoreBar label="Protease Stability Weight" value={0.75} color="blue" />
              <ScoreBar label="Synthesis Difficulty Weight" value={0.7} color="blue" />
            </div>

            <button type="button" className="flex items-center gap-2 mt-4 px-5 py-2 rounded-md text-sm font-medium bg-xh-primary text-white hover:bg-xh-primary/90">
              <Play className="w-4 h-4" />
              Run Optimization
            </button>
          </SectionCard>

          <SectionCard title="Targeting Peptide Screening / Developability Filtering">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <p className="text-xs font-semibold text-xh-text mb-3 flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5" />
                  Basic 5-Layer Filtering
                </p>
                <div className="space-y-2">
                  {BASIC_FILTERS.map((f) => (
                    <div key={f.label} className="flex items-center justify-between">
                      <span className="text-xs text-xh-text">{f.label}</span>
                      <StatusPill status={f.passed ? 'pass' : 'fail'} />
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="text-xs font-semibold text-xh-text mb-3 flex items-center gap-1.5">
                  <Filter className="w-3.5 h-3.5" />
                  Developability Filtering
                </p>
                <div className="space-y-2">
                  {DEV_FILTERS.map((f) => (
                    <div key={f.label} className="flex items-center justify-between">
                      <span className="text-xs text-xh-text">{f.label}</span>
                      <StatusPill status={f.passed ? 'pass' : 'warning'} label={f.risk} />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title="Before vs After Optimization">
            <DataTableShell>
              <thead>
                <tr className="bg-gray-50 border-b border-xh-border">
                  {['Candidate', 'Sequence', 'Solubility', 'Aggregation', 'Toxicity', 'Hemolysis', 'Protease', 'Synth.Diff', 'Overall'].map((h) => (
                    <th key={h} className="px-2 py-2 text-[10px] font-semibold text-xh-muted whitespace-nowrap uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {mockOptimizedPeptides.map((p) => (
                  <tr key={p.id} className={`border-b border-gray-50 last:border-0 ${p.isOptimized ? 'bg-emerald-50/30' : ''}`}>
                    <td className="px-2 py-2 text-xs font-medium text-xh-text">{p.candidate}</td>
                    <td className="px-2 py-2 text-xs font-mono text-xh-text">{p.sequence}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.solubility.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.aggregationRisk.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.toxicity.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.hemolysis.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.proteaseStability.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs text-xh-muted">{p.synthesisDifficulty.toFixed(2)}</td>
                    <td className="px-2 py-2 text-xs font-bold text-xh-primary">{p.overallScore.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </DataTableShell>
          </SectionCard>
        </div>

        <div className="xl:col-span-4 space-y-6">
          <SectionCard title="Top Optimized Peptides">
            <div className="space-y-4">
              {topOptimized.map((p, idx) => (
                <div key={p.id} className="rounded-lg border border-xh-border p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-semibold text-xh-text">Top {idx + 1}</span>
                    <span className="text-lg font-bold text-xh-primary">{p.overallScore.toFixed(2)}</span>
                  </div>
                  <SequenceBadge sequence={p.sequence} />
                  <p className="text-xs text-xh-muted mt-2">Improved solubility and reduced aggregation risk.</p>
                  <div className="flex gap-2 mt-3">
                    <button type="button" className="flex items-center gap-1.5 flex-1 px-3 py-1.5 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50">
                      <Box className="w-3.5 h-3.5" />
                      Validate in 3D
                    </button>
                    <button type="button" className="flex items-center gap-1.5 flex-1 px-3 py-1.5 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50">
                      <ArrowRight className="w-3.5 h-3.5" />
                      Predict Complex
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </SectionCard>
        </div>
      </div>
    </PlatformLayout>
  );
}
