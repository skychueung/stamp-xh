import { useRef, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { MetricCard } from '@/components/platform/MetricCard';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { StatusPill } from '@/components/platform/StatusPill';
import { DataTableShell } from '@/components/platform/DataTableShell';
import { ScoreBar } from '@/components/platform/ScoreBar';
import { ComplexMolstarViewer, type ComplexViewerRef } from '@/components/structure/ComplexMolstarViewer';
import { InterfaceContactMap } from '@/components/structure/InterfaceContactMap';
import {
  mockComplexInfo,
  mockStructureMetrics,
  mockDockingAnalysis,
  mockRankedPeptides,
  mockInterfaceContacts,
} from '@/data/platformMockData';
import { AlertTriangle, Box, Download, Camera, CheckCircle2, Info } from 'lucide-react';
import { MmgbsaReadinessCard } from '@/components/platform/MmgbsaReadinessCard';
import { batchComputationApi } from '@/lib/api/batchComputation';
import type { MmgbsaResultResponse } from '@/types/batchComputation';

export default function StructureValidationPage() {
  const { t } = useLanguage();
  const viewerRef = useRef<ComplexViewerRef>(null);
  const [searchParams] = useSearchParams();

  const [mmgbsaData, setMmgbsaData] = useState<MmgbsaResultResponse | null>(null);
  const [mmgbsaLoading, setMmgbsaLoading] = useState(false);
  const [mmgbsaError, setMmgbsaError] = useState<string | null>(null);

  const batchId = searchParams.get('batch_id');
  const itemId = searchParams.get('item_id');

  useEffect(() => {
    if (!batchId || !itemId) {
      setMmgbsaData(null);
      return;
    }

    let cancelled = false;
    const load = async () => {
      setMmgbsaLoading(true);
      setMmgbsaError(null);
      try {
        const resp = await batchComputationApi.getMmgbsaResults(batchId, itemId);
        if (!cancelled) {
          // ApiResponse wrapper: resp.data contains the actual payload
          const payload = (resp as any).data ?? resp;
          setMmgbsaData(payload as MmgbsaResultResponse);
        }
      } catch (err: any) {
        if (!cancelled) {
          setMmgbsaError(err?.message || 'Failed to load MM-GBSA results');
        }
      } finally {
        if (!cancelled) {
          setMmgbsaLoading(false);
        }
      }
    };

    load();
    return () => { cancelled = true; };
  }, [batchId, itemId]);

  const ratio = mockStructureMetrics.epitopeContactRatio;
  const ratioStatus = ratio >= 0.75 ? 'pass' : ratio >= 0.5 ? 'warning' : 'fail';
  const ratioColor = ratioStatus === 'pass' ? 'text-emerald-600' : ratioStatus === 'warning' ? 'text-amber-600' : 'text-red-600';
  const ratioBg = ratioStatus === 'pass' ? 'bg-emerald-50 border-emerald-200' : ratioStatus === 'warning' ? 'bg-amber-50 border-amber-200' : 'bg-red-50 border-red-200';

  // Build MmgbsaReadinessData from API response or null
  const readinessData = mmgbsaData && mmgbsaData.status !== 'NOT_AVAILABLE'
    ? {
        run_type: mmgbsaData.run_type ?? 'UNKNOWN',
        convergence_status: mmgbsaData.convergence_status ?? 'UNKNOWN',
        frames_used: mmgbsaData.frames_used,
        pilot_delta_total_kcal_mol: mmgbsaData.delta_g_total,
        official_mm_gbsa_delta_g: mmgbsaData.official_mm_gbsa_delta_g,
        warnings: mmgbsaData.warnings,
        components: mmgbsaData.components,
      }
    : null;

  return (
    <PlatformLayout>
      <PipelineProgress currentStep={8} />

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-xh-text tracking-tight">{t.pageTitle.structureValidation} (Mock)</h1>
        <p className="text-sm text-xh-muted mt-1">
          {t.pageSubtitle.structureValidation}
        </p>
        <div className="mt-3 bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
          <Info className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
          <p className="text-xs text-amber-700 leading-relaxed">
            <strong>NOT_EXPERIMENTALLY_VALIDATED</strong>
            {' — '}pDockQ is computed from ColabFold complex interface contacts and interface pLDDT using the Bryant et al. 2022 sigmoid formula. It is a <strong>computational interface-quality estimate</strong>, not experimental binding validation. FoldX energy_quality (interaction energy, VdW clashes, H-bonds, electrostatics, solvation) is a <strong>computational energy decomposition</strong> derived from AnalyseComplex. It is <strong>not a docking score</strong>, <strong>not MM-GBSA ΔG</strong>, and <strong>not experimentally validated binding affinity</strong>. ΔG and docking_score remain unavailable unless FoldX / FlexPepDock or equivalent validated workflows are integrated.
          </p>
        </div>
      </header>

      {/* Top 6 Metric Cards */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
        <MetricCard label="ipTM (mock)" value="—" highlight />
        <MetricCard label="pDockQ (mock)" value="—" highlight />
        <MetricCard label="Interface ΔG (mock)" value="—" unit="kcal/mol" />
        <MetricCard label={t.structureValidation.epitopeContactRatio} value={ratio.toFixed(2)} highlight />
        <MetricCard label={t.structureValidation.contactingResidues} value={mockStructureMetrics.contactResidues} />
        <MetricCard label={t.structureValidation.confidence} value={mockStructureMetrics.bindingConfidence.toFixed(2)} />
      </div>

      {/* MM-GBSA / MD Readiness */}
      {mmgbsaLoading ? (
        <div className="bg-slate-50 border border-slate-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-slate-600">Loading MM-GBSA results…</p>
        </div>
      ) : mmgbsaError ? (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
          <p className="text-sm text-red-700">{mmgbsaError}</p>
        </div>
      ) : (
        <div className="mb-6">
          <MmgbsaReadinessCard data={readinessData} />
        </div>
      )}

      {/* 20/60/20 Three-Column Layout */}
      <div className="flex flex-col xl:flex-row gap-6 mb-6">
        {/* Left: Selected Complex Info (20%) */}
        <div className="xl:w-[20%] shrink-0 space-y-4">
          <SectionCard title={t.structureValidation.selectedComplexInfo}>
            <div className="space-y-3 text-sm">
              <div>
                <span className="text-xh-muted block text-xs mb-1">{t.structureValidation.targetingPeptideSequence}</span>
                <SequenceBadge sequence={mockComplexInfo.peptideSequence} />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-xh-muted block text-[10px] uppercase">{t.structureValidation.epitopeRange}</span>
                  <span className="font-mono text-xs font-medium text-xh-text">{mockComplexInfo.epitopeRange}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-xh-muted block text-[10px] uppercase">Target Chain</span>
                  <span className="font-mono text-xs font-medium text-xh-text">{mockComplexInfo.targetChainId}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-xh-muted block text-[10px] uppercase">Peptide Chain</span>
                  <span className="font-mono text-xs font-medium text-xh-text">{mockComplexInfo.peptideChainId}</span>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <span className="text-xh-muted block text-[10px] uppercase">Method</span>
                  <span className="font-mono text-xs font-medium text-xh-text">{mockComplexInfo.predictionMethod}</span>
                </div>
              </div>
              <div>
                <span className="text-xh-muted block text-xs">Refinement</span>
                <span className="text-xs text-xh-text">{mockComplexInfo.refinementMethod}</span>
              </div>
              <div className="flex gap-2 pt-1">
                <button type="button" className="flex items-center gap-1.5 flex-1 px-3 py-2 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50">
                  <Download className="w-3.5 h-3.5" />
                  PDB
                </button>
                <button type="button" className="flex items-center gap-1.5 flex-1 px-3 py-2 rounded-md text-xs font-medium border border-xh-border text-xh-text hover:bg-gray-50">
                  <Camera className="w-3.5 h-3.5" />
                  Snapshot
                </button>
              </div>
            </div>
          </SectionCard>

          <SectionCard title={t.structureValidation.interfaceMetrics} className="hidden xl:block">
            <div className="space-y-2.5">
              <ScoreBar label="ipTM (mock)" value={mockStructureMetrics.ipTM} color="blue" />
              <ScoreBar label="pDockQ (mock)" value={mockStructureMetrics.pDockQ} color="blue" />
              <ScoreBar label={t.structureValidation.epitopeContactRatio} value={ratio} color={ratio >= 0.75 ? 'green' : ratio >= 0.5 ? 'amber' : 'red'} />
              <ScoreBar label={t.structureValidation.confidence} value={mockStructureMetrics.bindingConfidence} color="blue" />
            </div>
          </SectionCard>
        </div>

        {/* Center: 3D Viewer (60%, min-w-[600px]) */}
        <div className="xl:w-[60%] min-w-[600px] shrink-0">
          <ComplexMolstarViewer
            ref={viewerRef}
            complexPdbUrl="/structures/mock_complex.pdb"
            targetChainId={mockComplexInfo.targetChainId}
            peptideChainId={mockComplexInfo.peptideChainId}
            epitopeResidueRange={{ start: 455, end: 465 }}
            height={540}
            onLoad={() => console.log('Complex loaded')}
            onError={(err) => console.error('Complex load error:', err)}
          />
        </div>

        {/* Right: Docking & Interface Analysis (20%) */}
        <div className="xl:w-[20%] shrink-0 space-y-4">
          <SectionCard title={t.structureValidation.dockingInterfaceAnalysis}>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-xh-muted">{t.structureValidation.alphaFoldStatus}</span>
                <StatusPill status="pass" label={mockDockingAnalysis.alphaFoldMultimerStatus} />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-xh-muted">{t.structureValidation.flexPepDockStatus}</span>
                <StatusPill status="pass" label={mockDockingAnalysis.flexPepDockStatus} />
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-xh-muted">{t.structureValidation.foldXEnergy}</span>
                <span className="font-medium text-xh-text">{mockDockingAnalysis.foldXEnergy}</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-xh-muted">{t.structureValidation.hotspotContacts}</span>
                <span className="font-medium text-xh-text">{mockDockingAnalysis.hotspotContacts}</span>
              </div>
              <div className="border-t border-xh-border pt-2 mt-2 space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-xh-muted">ipTM (mock)</span>
                  <span className="font-medium text-xh-text">—</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-xh-muted">pDockQ (mock)</span>
                  <span className="font-medium text-xh-text">—</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-xh-muted">{t.structureValidation.epitopeContactRatio}</span>
                  <span className="font-bold text-xh-primary">{ratio.toFixed(2)}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-xh-muted">{t.structureValidation.offEpitopeBindingRisk}</span>
                  <span className={`font-medium capitalize ${
                    mockStructureMetrics.offEpitopeBindingRisk === 'low' ? 'text-emerald-600' : 'text-amber-600'
                  }`}>
                    {mockStructureMetrics.offEpitopeBindingRisk}
                  </span>
                </div>
              </div>
            </div>
          </SectionCard>

          <SectionCard title={t.structureValidation.interfaceContactMap} className="hidden xl:block">
            <InterfaceContactMap contacts={mockInterfaceContacts} />
          </SectionCard>
        </div>
      </div>

      {/* Epitope Binding Validation — Spans full width */}
      <div className={`rounded-lg border p-5 mb-6 ${ratioBg}`}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div className="flex items-center gap-3">
            {ratioStatus === 'pass' ? (
              <CheckCircle2 className="w-8 h-8 text-emerald-600 shrink-0" />
            ) : ratioStatus === 'warning' ? (
              <AlertTriangle className="w-8 h-8 text-amber-600 shrink-0" />
            ) : (
              <AlertTriangle className="w-8 h-8 text-red-600 shrink-0" />
            )}
            <div>
              <h3 className="text-sm font-semibold text-xh-text">{t.structureValidation.epitopeBindingValidation}</h3>
              <p className="text-xs text-xh-muted mt-0.5">
                Measures whether the targeting peptide truly contacts the selected epitope instead of binding to unrelated regions.
              </p>
            </div>
          </div>
          <div className="flex items-baseline gap-6">
            <div className="text-center">
              <span className={`text-3xl font-bold ${ratioColor}`}>{ratio.toFixed(2)}</span>
              <span className="text-[10px] text-xh-muted block uppercase tracking-wider mt-0.5">Contact Ratio</span>
            </div>
            <div className="text-center">
              <span className="text-lg font-semibold text-xh-text">{mockStructureMetrics.distanceToEpitope} Å</span>
              <span className="text-[10px] text-xh-muted block uppercase tracking-wider mt-0.5">Distance</span>
            </div>
            <div className="text-center">
              <span className={`text-lg font-semibold capitalize ${ratioColor}`}>
                {ratioStatus === 'pass' ? 'Passed' : ratioStatus === 'warning' ? 'Warning' : 'Failed'}
              </span>
              <span className="text-[10px] text-xh-muted block uppercase tracking-wider mt-0.5">{t.structureValidation.bindingSiteMatch}</span>
            </div>
          </div>
        </div>

        {ratio < 0.75 && (
          <div className="mt-4 bg-red-100 border border-red-300 rounded-md p-3 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-red-600 mt-0.5 shrink-0" />
            <div className="text-xs text-red-700">
              <p className="font-semibold">{t.structureValidation.offEpitopeWarning}</p>
              <p className="mt-0.5">
                Epitope contact ratio is {ratio.toFixed(2)} (&lt; 0.75). The targeting peptide may bind to non-target regions of the protein. Consider redesign.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Interface Contact Map — Full width */}
      <SectionCard title={t.structureValidation.interfaceContactMap} className="mb-6">
        <InterfaceContactMap contacts={mockInterfaceContacts} />
      </SectionCard>

      {/* Top Validated Complexes — Full width */}
      <SectionCard title={t.structureValidation.topValidatedComplexes}>
        <DataTableShell>
          <thead>
            <tr className="bg-gray-50 border-b border-xh-border">
              {['Peptide', 'ipTM (mock)', 'pDockQ (mock)', 'ΔG (mock)', 'Contact Ratio', 'Contacts', 'Off-epitope Risk', 'Status', 'Action'].map((h) => (
                <th key={h} className="px-3 py-2 text-[10px] font-semibold text-xh-muted whitespace-nowrap uppercase tracking-wider">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {mockRankedPeptides.slice(0, 3).map((pep) => (
              <tr key={pep.id} className="border-b border-gray-50 last:border-0 hover:bg-gray-50/50">
                <td className="px-3 py-2 text-xs font-mono text-xh-text">{pep.peptideSequence}</td>
                <td className="px-3 py-2 text-xs text-xh-muted">—</td>
                <td className="px-3 py-2 text-xs text-xh-muted">—</td>
                <td className="px-3 py-2 text-xs text-xh-muted">—</td>
                <td className="px-3 py-2 text-xs font-bold text-xh-primary">{pep.epitopeContactRatio.toFixed(2)}</td>
                <td className="px-3 py-2 text-xs text-xh-muted">{pep.contactResidues}</td>
                <td className="px-3 py-2 text-xs capitalize text-xh-muted">{pep.offEpitopeBindingRisk}</td>
                <td className="px-3 py-2"><StatusPill status={pep.structuralValidationStatus} /></td>
                <td className="px-3 py-2">
                  <div className="flex gap-2">
                    <button type="button" className="text-[10px] text-xh-primary hover:underline font-medium flex items-center gap-0.5">
                      <Box className="w-3 h-3" /> View
                    </button>
                    <button type="button" className="text-[10px] text-xh-primary hover:underline font-medium">Download</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </DataTableShell>
      </SectionCard>
    </PlatformLayout>
  );
}
