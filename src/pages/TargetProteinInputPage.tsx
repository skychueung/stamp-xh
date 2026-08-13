import { useState } from 'react';
import { useNavigate } from 'react-router';
import { useLanguage } from '@/i18n/LanguageContext';
import { useProject } from '@/contexts/ProjectContext';
import { PlatformLayout } from '@/layouts/PlatformLayout';
import { PipelineProgress } from '@/components/platform/PipelineProgress';
import { SectionCard } from '@/components/platform/SectionCard';
import { MetricCard } from '@/components/platform/MetricCard';
import { SequenceBadge } from '@/components/platform/SequenceBadge';
import { StatusPill } from '@/components/platform/StatusPill';
import { mockTargetProtein, mockTargetSummary, mockRecommendedChecks } from '@/data/platformMockData';
import { EPITOPE_SCAN_PARAMS_LS_KEY } from '@/types/realEpitope';
import { projectsApi } from '@/lib/api/projects';
import { targetProteinsApi } from '@/lib/api/targetProteins';
import { epitopeScansApi } from '@/lib/api/epitopeScans';
import type { TargetProteinCreate } from '@/types/targetProtein';
import type { EpitopeScanCreate } from '@/types/epitope';
import { Upload, Play, RotateCcw, FileText, Database, FolderOpen, Loader2, AlertCircle, SlidersHorizontal } from 'lucide-react';
import PipelineRunBanner from '@/components/platform/PipelineRunBanner';
import { sequenceHash } from '@/lib/sequenceHash';

const TABS = [
  { key: 'sequence', label: 'Protein Sequence', icon: FileText },
  { key: 'uniprot', label: 'UniProt ID', icon: Database },
  { key: 'structure', label: 'PDB / CIF File', icon: FolderOpen },
] as const;

const TARGET_TYPES = [
  { value: 'membrane', label: 'Membrane Protein' },
  { value: 'receptor', label: 'Receptor' },
  { value: 'enzyme', label: 'Enzyme' },
  { value: 'pathogen_surface', label: 'Pathogen Surface Protein' },
] as const;

export default function TargetProteinInputPage() {
  const { t } = useLanguage();
  const navigate = useNavigate();
  const { currentProject, setCurrentProject } = useProject();
  const [activeTab, setActiveTab] = useState<(typeof TABS)[number]['key']>('sequence');
  const [input, setInput] = useState(mockTargetProtein);
  const [isRunning, setIsRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);

  // 生成序列 Hash：安全上下文(HTTPS/localhost)用 Web Crypto SHA-256；
  // HTTP 非安全上下文(预览地址非 localhost)回退到同步哈希。
  // 修复 "Cannot read properties of undefined (reading 'digest')"。
  // 详见 src/lib/sequenceHash.ts。
  const generateSequenceHash = sequenceHash;

  // Scan parameters
  const [scanParams, setScanParams] = useState({
    window_size: 15,
    top_k: 20,
    min_charge: -4,
    max_charge: 6,
    max_gravy: 1.0,
    max_cys: 1,
  });

  const handleLoadExample = () => {
    setInput(mockTargetProtein);
    setRunError(null);
    setScanParams({
      window_size: 15,
      top_k: 20,
      min_charge: -4,
      max_charge: 6,
      max_gravy: 1.0,
      max_cys: 1,
    });
  };
  const handleReset = () => {
    setInput({
      name: '',
      species: '',
      targetType: 'membrane',
      sequence: '',
      regionOfInterest: '',
      notes: '',
    });
    setRunError(null);
    setScanParams({
      window_size: 15,
      top_k: 20,
      min_charge: -4,
      max_charge: 6,
      max_gravy: 1.0,
      max_cys: 1,
    });
  };

  const handleRunPrediction = async () => {
    const seq = input.sequence.trim();
    if (!seq) {
      setRunError('Please enter a target protein sequence.');
      return;
    }

    setIsRunning(true);
    setRunError(null);

    try {
      // Step 1: 确保当前 Project 存在
      let activeProjectId = currentProject?.id;
      if (!activeProjectId) {
        const newProject = await projectsApi.create({
          name: 'Target Analysis Workspace',
          project_type: 'epitope_scan',
        });
        setCurrentProject(newProject);
        activeProjectId = newProject.id;
      }

      // Step 2: 创建 Target Protein
      const seqHash = await generateSequenceHash(seq);
      const proteinData: TargetProteinCreate = {
        project_id: activeProjectId,
        name: input.name || 'Unknown Target',
        sequence: seq.toUpperCase(),
        sequence_hash: seqHash,
        source_type: 'manual',
      };
      const targetProtein = await targetProteinsApi.create(proteinData);

      // Step 3: 创建 Epitope Scan 任务
      const scanData: EpitopeScanCreate = {
        project_id: activeProjectId,
        target_protein_id: targetProtein.id,
        parameters: scanParams,
        algorithm: 'heuristic_v1',
      };
      const scanTask = await epitopeScansApi.create(scanData);

      // 保留扫描参数到 localStorage，供展示页使用
      localStorage.setItem(EPITOPE_SCAN_PARAMS_LS_KEY, JSON.stringify({
        window_size: scanParams.window_size,
        top_k: scanParams.top_k,
        min_charge: scanParams.min_charge,
        max_charge: scanParams.max_charge,
        max_gravy: scanParams.max_gravy,
        max_cys: scanParams.max_cys,
      }));

      // Step 4: 携带 scan_id 跳转到筛选页
      navigate(`/epitope-screening?scan_id=${scanTask.id}`);
    } catch (err: any) {
      console.error('Pipeline Error:', err);
      setRunError(err.message || 'Failed to initialize the pipeline. Please check the backend connection.');
    } finally {
      setIsRunning(false);
    }
  };

  return (
    <PlatformLayout>
      <PipelineRunBanner />
      <PipelineProgress currentStep={1} />

      <header className="mb-6">
        <h1 className="text-2xl font-bold text-xh-text tracking-tight">{t.pageTitle.targetProtein}</h1>
        <p className="text-sm text-xh-muted mt-1">
          {t.pageSubtitle.targetProtein}
        </p>
      </header>

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6">
        <div className="xl:col-span-8 space-y-6">
          <SectionCard>
            <div className="flex items-center gap-2 mb-4 border-b border-xh-border pb-3">
              {TABS.map((tab) => {
                const Icon = tab.icon;
                return (
                  <button
                    key={tab.key}
                    type="button"
                    onClick={() => setActiveTab(tab.key)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                      activeTab === tab.key
                        ? 'bg-xh-primary text-white'
                        : 'bg-gray-50 text-xh-muted hover:bg-gray-100'
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {activeTab === 'sequence' && (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-xh-text mb-1.5">Protein Name</label>
                    <input
                      type="text"
                      value={input.name}
                      onChange={(e) => setInput((s) => ({ ...s, name: e.target.value }))}
                      className="w-full px-3 py-2 rounded-md border border-xh-border text-sm focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-xh-text mb-1.5">Species / Strain</label>
                    <input
                      type="text"
                      value={input.species}
                      onChange={(e) => setInput((s) => ({ ...s, species: e.target.value }))}
                      className="w-full px-3 py-2 rounded-md border border-xh-border text-sm focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-xh-text mb-1.5">Target Type</label>
                  <div className="flex flex-wrap gap-2">
                    {TARGET_TYPES.map((t) => (
                      <button
                        key={t.value}
                        type="button"
                        onClick={() => setInput((s) => ({ ...s, targetType: t.value }))}
                        className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                          input.targetType === t.value
                            ? 'bg-xh-primary text-white border-xh-primary'
                            : 'bg-white text-xh-muted border-xh-border hover:bg-gray-50'
                        }`}
                      >
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-xh-text mb-1.5">Target Protein Sequence</label>
                  <textarea
                    value={input.sequence}
                    onChange={(e) => setInput((s) => ({ ...s, sequence: e.target.value }))}
                    rows={6}
                    className="w-full px-3 py-2 rounded-md border border-xh-border text-sm font-mono focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                  />
                </div>

                {/* ── Scan Parameters ── */}
                <div className="border border-xh-border rounded-md p-3 bg-gray-50/50">
                  <div className="flex items-center gap-2 mb-3">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-xh-muted" />
                    <span className="text-xs font-semibold text-xh-text uppercase tracking-wider">Scan Parameters</span>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Window Size</label>
                      <input
                        type="number"
                        value={scanParams.window_size}
                        onChange={(e) => setScanParams((s) => ({ ...s, window_size: Number(e.target.value) || 15 }))}
                        min={5} max={50}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Top K</label>
                      <input
                        type="number"
                        value={scanParams.top_k}
                        onChange={(e) => setScanParams((s) => ({ ...s, top_k: Number(e.target.value) || 20 }))}
                        min={1} max={200}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Min Charge</label>
                      <input
                        type="number"
                        value={scanParams.min_charge}
                        onChange={(e) => setScanParams((s) => ({ ...s, min_charge: Number(e.target.value) }))}
                        step={0.5}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Max Charge</label>
                      <input
                        type="number"
                        value={scanParams.max_charge}
                        onChange={(e) => setScanParams((s) => ({ ...s, max_charge: Number(e.target.value) }))}
                        step={0.5}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Max GRAVY</label>
                      <input
                        type="number"
                        value={scanParams.max_gravy}
                        onChange={(e) => setScanParams((s) => ({ ...s, max_gravy: Number(e.target.value) }))}
                        step={0.1}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] font-medium text-xh-muted mb-1">Max Cys</label>
                      <input
                        type="number"
                        value={scanParams.max_cys}
                        onChange={(e) => setScanParams((s) => ({ ...s, max_cys: Number(e.target.value) || 0 }))}
                        min={0} max={20}
                        className="w-full px-2 py-1.5 rounded border border-xh-border text-xs"
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-xh-text mb-1.5">Region of Interest</label>
                    <input
                      type="text"
                      value={input.regionOfInterest}
                      onChange={(e) => setInput((s) => ({ ...s, regionOfInterest: e.target.value }))}
                      className="w-full px-3 py-2 rounded-md border border-xh-border text-sm focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-xh-text mb-1.5">Notes</label>
                    <input
                      type="text"
                      value={input.notes}
                      onChange={(e) => setInput((s) => ({ ...s, notes: e.target.value }))}
                      className="w-full px-3 py-2 rounded-md border border-xh-border text-sm focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                    />
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'uniprot' && (
              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-xh-text mb-1.5">UniProt ID</label>
                  <input
                    type="text"
                    placeholder="e.g., P0DTC2"
                    className="w-full px-3 py-2 rounded-md border border-xh-border text-sm focus:outline-none focus:ring-2 focus:ring-xh-primary/20 focus:border-xh-primary"
                  />
                </div>
                <p className="text-xs text-xh-muted">Enter a UniProt accession to auto-fetch sequence and metadata.</p>
              </div>
            )}

            {activeTab === 'structure' && (
              <div className="space-y-4">
                <div className="border-2 border-dashed border-xh-border rounded-lg p-8 text-center">
                  <Upload className="w-8 h-8 text-xh-muted mx-auto mb-2" />
                  <p className="text-sm text-xh-text font-medium">Drag & drop structure file</p>
                  <p className="text-xs text-xh-muted mt-1">Supports FASTA, PDB, CIF formats</p>
                </div>
              </div>
            )}

            <div className="flex items-center gap-3 mt-6 pt-4 border-t border-xh-border">
              <button
                type="button"
                onClick={handleLoadExample}
                className="px-4 py-2 rounded-md text-sm font-medium border border-xh-border text-xh-text hover:bg-gray-50"
              >
                Load Example
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium border border-xh-border text-xh-text hover:bg-gray-50"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                Reset
              </button>
              <div className="flex-1" />
              <button
                type="button"
                onClick={handleRunPrediction}
                disabled={isRunning}
                className="flex items-center gap-2 px-5 py-2 rounded-md text-sm font-medium bg-xh-primary text-white hover:bg-xh-primary/90 disabled:opacity-60"
              >
                {isRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                {isRunning ? 'Running scan...' : 'Run Epitope Prediction'}
              </button>
            </div>

            {runError && (
              <div className="mt-3 p-3 rounded-md border border-red-200 bg-red-50 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />
                <p className="text-sm text-red-700">{runError}</p>
              </div>
            )}
          </SectionCard>
        </div>

        <div className="xl:col-span-4 space-y-6">
          <SectionCard title="Target Summary">
            <div className="grid grid-cols-2 gap-3">
              <MetricCard label="Length" value={mockTargetSummary.length} unit="aa" />
              <MetricCard label="TM Helices" value={mockTargetSummary.transmembraneHelices} />
              <MetricCard label="Domain Count" value={mockTargetSummary.domainCount} />
              <MetricCard label="Signal Peptide" value={mockTargetSummary.signalPeptide ? 'Yes' : 'No'} />
            </div>
            <div className="mt-3 text-xs text-xh-muted">
              <span className="font-medium text-xh-text">Localization:</span> {mockTargetSummary.predictedLocalization}
            </div>
            <div className="mt-1 text-xs text-xh-muted">
              <span className="font-medium text-xh-text">Structure:</span> {mockTargetSummary.structureAvailability}
            </div>
          </SectionCard>

          <SectionCard title="Recommended Checks">
            <div className="space-y-2.5">
              {mockRecommendedChecks.map((check) => (
                <div key={check.label} className="flex items-center justify-between">
                  <span className="text-sm text-xh-text">{check.label}</span>
                  <StatusPill status={check.passed ? 'pass' : 'warning'} />
                </div>
              ))}
            </div>
          </SectionCard>

          <SectionCard title="Sequence Preview">
            <SequenceBadge sequence={input.sequence.slice(0, 120)} />
            {input.sequence.length > 120 && (
              <p className="text-xs text-xh-muted mt-2">...and {input.sequence.length - 120} more residues</p>
            )}
          </SectionCard>
        </div>
      </div>
    </PlatformLayout>
  );
}
