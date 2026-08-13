import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '@/i18n/LanguageContext';
import {
  getAmpStructureRecords,
  getStampCandidates,
  computeMeanPlddt,
  countVeryHighConfidence,
} from '@/lib/realAmpDataApi';
import type {
  AmpStructureRecord,
  StampHybridCandidate,
  CandidateBadgeInfo,
} from '@/types/stamp';
import { MolstarCifViewer } from '@/components/structure/MolstarCifViewer';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';

// ───────────────────────────────────────────────
// Sub-components
// ───────────────────────────────────────────────

function StatsCards({
  manifest,
  candidateCount,
}: {
  manifest: AmpStructureRecord[];
  candidateCount: number;
}) {
  const { t } = useLanguage();
  const meanPlddt = computeMeanPlddt(manifest);
  const highConf = countVeryHighConfidence(manifest);

  const cards = [
    {
      label: t.stampHybridDesign.stats.realAmpStructures,
      value: manifest.length,
      source: 'v0.6a ingestion',
    },
    {
      label: t.stampHybridDesign.stats.meanPlddt,
      value: meanPlddt.toFixed(2),
      source: 'calculated from manifest',
    },
    {
      label: t.stampHybridDesign.stats.veryHighConfidence,
      value: highConf,
      source: 'pLDDT ≥ 90',
    },
    {
      label: t.stampHybridDesign.stats.stampCandidates,
      value: candidateCount,
      source: 'Wang 2023 + P4/P15 hybrids',
    },
    {
      label: t.stampHybridDesign.stats.p4p15Mapping,
      value: t.common.pending,
      source: 'awaiting amp_structure_mapping.csv',
    },
  ];

  return (
    <div className="grid grid-cols-5 gap-4">
      {cards.map((card) => (
        <div
          key={card.label}
          className="rounded-lg border bg-white p-4 shadow-sm"
        >
          <div className="text-2xl font-bold text-slate-800">{card.value}</div>
          <div className="text-sm text-slate-500">{card.label}</div>
          <div className="mt-1 text-xs text-slate-400">{card.source}</div>
        </div>
      ))}
    </div>
  );
}

function getCandidateBadges(
  candidate: StampHybridCandidate,
  t: Record<string, unknown>
): CandidateBadgeInfo[] {
  const badges: CandidateBadgeInfo[] = [];
  const s = t.stampHybridDesign as Record<string, unknown>;
  const b = s.badges as Record<string, string>;

  if (candidate.candidate_id === 'R7_ref') {
    badges.push({ text: b.wang2023PositiveControl, variant: 'default' });
  }
  if (['A7_ref', 'G7_ref'].includes(candidate.candidate_id)) {
    badges.push({ text: b.nonCleavableControl, variant: 'secondary' });
  }
  if (candidate.candidate_id === 'R7_P4') {
    badges.push({ text: b.priorityExperimental, variant: 'destructive' });
  }
  if (candidate.candidate_id.includes('_P15')) {
    badges.push({ text: b.higherSafetyRisk, variant: 'warning' });
  }
  if (candidate.candidate_id.includes('_P4')) {
    badges.push({ text: b.p4CleanSequence, variant: 'outline' });
  }

  return badges;
}

function Badge({ info }: { info: CandidateBadgeInfo }) {
  const base = 'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium';
  const variants: Record<string, string> = {
    default: 'bg-slate-800 text-white',
    secondary: 'bg-slate-200 text-slate-800',
    destructive: 'bg-red-100 text-red-700',
    warning: 'bg-amber-100 text-amber-700',
    outline: 'border border-slate-300 text-slate-600',
  };
  return <span className={`${base} ${variants[info.variant]}`}>{info.text}</span>;
}

function TemplateBuilder() {
  const { t } = useLanguage();
  const s = t.stampHybridDesign as Record<string, unknown>;

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm h-full">
      <h3 className="mb-3 font-semibold text-slate-800">STAMP Template Builder</h3>
      <div className="space-y-3 text-sm">
        <div>
          <div className="text-slate-500">Target molecule</div>
          <div className="font-medium">Pseudomonas aeruginosa LPS</div>
        </div>
        <div>
          <div className="text-slate-500">Targeting domain</div>
          <div className="font-medium">LBP14 (RVQGRWKVRASFFK)</div>
          <div className="text-xs text-slate-400">[Wang 2023 Table 1]</div>
        </div>
        <div>
          <div className="text-slate-500">Linker options</div>
          <ul className="mt-1 space-y-1">
            <li className="rounded bg-slate-50 px-2 py-1">
              <span className="font-mono text-slate-700">RKRR</span>
              <span className="ml-2 text-xs text-slate-400">cleavable</span>
            </li>
            <li className="rounded bg-slate-50 px-2 py-1">
              <span className="font-mono text-slate-700">EAAAKEAAAK</span>
              <span className="ml-2 text-xs text-slate-400">rigid</span>
            </li>
            <li className="rounded bg-slate-50 px-2 py-1">
              <span className="font-mono text-slate-700">GGGGS</span>
              <span className="ml-2 text-xs text-slate-400">flexible</span>
            </li>
          </ul>
        </div>
        <div>
          <div className="text-slate-500">Killing domain</div>
          <div className="font-medium">L7 / P4(clean) / P15</div>
        </div>
        <div>
          <div className="text-slate-500">Orientation</div>
          <div className="font-medium">N-to-C</div>
        </div>
        <div>
          <div className="text-slate-500">Terminal modification</div>
          <div className="text-amber-600 text-xs">
            {s.title as string}: pending confirmation
          </div>
        </div>
      </div>
    </div>
  );
}

function CandidateTable({
  candidates,
  selectedId,
  onSelect,
}: {
  candidates: StampHybridCandidate[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { t } = useLanguage();
  const s = t.stampHybridDesign as Record<string, unknown>;
  const tbl = s.table as Record<string, string>;

  return (
    <div className="rounded-lg border bg-white shadow-sm h-full flex flex-col">
      <div className="border-b px-4 py-3">
        <h3 className="font-semibold text-slate-800">STAMP Hybrid Candidates</h3>
      </div>
      <div className="flex-1 overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50">
            <tr>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.candidateId}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.linker}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.killingDomain}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.length}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.netCharge}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.pi}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.mockFinalScore}</th>
              <th className="px-3 py-2 text-left font-medium text-slate-600">{tbl.structureStatus}</th>
            </tr>
          </thead>
          <tbody>
            {candidates.map((c) => {
              const badges = getCandidateBadges(c, t);
              const isSelected = selectedId === c.candidate_id;
              return (
                <tr
                  key={c.candidate_id}
                  className={`cursor-pointer border-b transition-colors hover:bg-slate-50 ${
                    isSelected ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => onSelect(c.candidate_id)}
                >
                  <td className="px-3 py-2">
                    <div className="font-medium text-slate-800">{c.candidate_id}</div>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {badges.map((b, i) => (
                        <Badge key={i} info={b} />
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-slate-600">{c.linker.sequence}</td>
                  <td className="px-3 py-2">{c.killing_domain.name}</td>
                  <td className="px-3 py-2">{c.biophysical.length}</td>
                  <td className="px-3 py-2">{c.biophysical.net_charge}</td>
                  <td className="px-3 py-2">{c.biophysical.pI}</td>
                  <td className="px-3 py-2">{c.mock_scores.final_score.toFixed(1)}</td>
                  <td className="px-3 py-2">
                    <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-700">
                      {tbl.awaitingPrediction}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function StructurePreview({
  selectedCandidate,
  manifest,
}: {
  selectedCandidate: StampHybridCandidate | null;
  manifest: AmpStructureRecord[];
}) {
  const { t } = useLanguage();
  const s = t.stampHybridDesign as Record<string, unknown>;
  const st = s.structure as Record<string, string>;

  const [currentCifUrl, setCurrentCifUrl] = useState<string>(
    '/structures/real_amp_monomers/AMP_001_model_0.cif'
  );
  const [viewerMessage, setViewerMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedCandidate) {
      setCurrentCifUrl('/structures/real_amp_monomers/AMP_001_model_0.cif');
      setViewerMessage(null);
      return;
    }

    // STAMP candidates do not have real hybrid structures
    if (
      selectedCandidate.structure_status.note?.includes('Awaiting') ??
      selectedCandidate.structure_status.monomer_predicted === false
    ) {
      setViewerMessage(st.noStampStructure);
      setCurrentCifUrl('');
      return;
    }

    // Check mapped structure for P4/P15
    const matched = manifest.find(
      (m) => m.priorityName === selectedCandidate.candidate_id
    );
    if (matched && matched.isPriorityCandidate) {
      setCurrentCifUrl(matched.publicPath);
      setViewerMessage(null);
    } else {
      setViewerMessage(st.p4p15Pending);
      setCurrentCifUrl('');
    }
  }, [selectedCandidate, manifest, st]);

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm h-full flex flex-col">
      <div className="mb-2 text-sm font-medium text-slate-800">{st.monomerPreview}</div>
      {viewerMessage ? (
        <div className="flex flex-1 items-center justify-center rounded-lg bg-slate-50">
          <div className="p-4 text-center">
            <div className="mb-2 text-2xl">⏳</div>
            <div className="text-sm text-slate-600">{viewerMessage}</div>
            <div className="mt-2 text-xs text-slate-400">{st.actionRequired}</div>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-[280px]">
          <MolstarCifViewer cifUrl={currentCifUrl} height={280} viewerId="stamp-molstar" />
        </div>
      )}
      <div className="mt-2 text-xs text-slate-400">{st.monomerDisclaimer}</div>
    </div>
  );
}

function ExplanationPanel() {
  const { t } = useLanguage();
  const s = t.stampHybridDesign as Record<string, unknown>;

  const items = [
    { key: 'r7a7g7Source', citation: '[Wang 2023 Table 1]' },
    { key: 'rkrrFunction' },
    { key: 'ea3kFunction' },
    { key: 'g4sFunction' },
    { key: 'monomerOnly', warning: true },
    { key: 'noDocking', warning: true },
    { key: 'nextStep', action: true },
  ];

  return (
    <div className="rounded-lg border bg-blue-50/50 p-4">
      <h3 className="mb-3 font-semibold text-slate-800">{s.title as string}</h3>
      <ol className="list-decimal list-inside space-y-2 text-sm text-slate-700">
        {items.map((item) => {
          const text = (s[item.key] as string) ?? '';
          return (
            <li key={item.key} className={item.warning ? 'text-amber-700' : ''}>
              {text}
              {item.citation && (
                <span className="ml-1 text-xs text-slate-400">{item.citation}</span>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function InfoBanner() {
  const { t } = useLanguage();
  const s = t.stampHybridDesign as Record<string, unknown>;
  const info = s.infoBanner as Record<string, string>;

  return (
    <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
      <div className="mt-0.5 text-amber-600">ℹ️</div>
      <div className="text-sm text-amber-800">
        <strong>{info.title}</strong>
        <p className="mt-1">{info.content}</p>
        <p className="mt-1 text-xs text-amber-600">
          {info.version}: v0.6b-stamp-hybrid-design-page | {info.dataStatus}: {info.monomerOnly}
        </p>
      </div>
    </div>
  );
}

// ───────────────────────────────────────────────
// Main page
// ───────────────────────────────────────────────

export default function StampHybridDesignPage() {
  const { t } = useLanguage();

  const [manifest, setManifest] = useState<AmpStructureRecord[]>([]);
  const [candidates, setCandidates] = useState<StampHybridCandidate[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [records, cands] = await Promise.all([
        getAmpStructureRecords(),
        getStampCandidates(),
      ]);
      setManifest(records);
      setCandidates(cands);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to load data';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const selectedCandidate = candidates.find((c) => c.candidate_id === selectedId) ?? null;

  return (
    <div className="min-h-screen bg-xh-bg p-6">
      <PipelineRunBanner />
      {/* Page header */}
      <header className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {t.pageTitle.stampHybridDesign}
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          {t.pageSubtitle.stampHybridDesign}
        </p>
        <div className="mt-3 bg-blue-50 border border-blue-200 rounded-lg p-3">
          <p className="text-xs text-blue-700 font-medium">当前已接入 One-click STAMP Demo 结果：</p>
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs text-blue-800">
            <div><span className="font-medium">Targeting Peptide:</span> DATAAAALAALG</div>
            <div><span className="font-medium">Linker:</span> EAAAK</div>
            <div><span className="font-medium">AMP:</span> P4</div>
            <div><span className="font-medium">Full Sequence:</span> DATAAAALAALG-EAAAK-FSRFLRRVRRYRPKISFNLEPFFKF-NH2</div>
          </div>
        </div>
      </header>

      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-xh-primary border-t-transparent" />
          <span className="ml-3 text-sm text-slate-500">Loading data...</span>
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Error: {error}
        </div>
      )}

      {!loading && !error && (
        <>
          {/* Stats cards */}
          <div className="mb-6">
            <StatsCards manifest={manifest} candidateCount={candidates.length} />
          </div>

          {/* Three-column layout */}
          <div className="mb-6 grid grid-cols-12 gap-4">
            <div className="col-span-3">
              <TemplateBuilder />
            </div>
            <div className="col-span-6">
              <CandidateTable
                candidates={candidates}
                selectedId={selectedId}
                onSelect={setSelectedId}
              />
            </div>
            <div className="col-span-3">
              <StructurePreview
                selectedCandidate={selectedCandidate}
                manifest={manifest}
              />
            </div>
          </div>

          {/* Explanation & Info */}
          <div className="space-y-4">
            <ExplanationPanel />
            <InfoBanner />
          </div>
        </>
      )}
    </div>
  );
}
