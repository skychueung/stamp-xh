import { useState } from 'react';
import { AlertTriangle, Download, FileBox, Loader2 } from 'lucide-react';
import { MolstarViewer } from './MolstarViewer';
import type { ModelArtifactItem } from '@/types/modelRegistry';

const ARTIFACT_TYPE_LABELS: Record<string, string> = {
  pdb: 'PDB structure',
  metrics: 'Metrics CSV',
  log: 'Log',
  manifest: 'Manifest',
  input: 'Input',
  other: 'File',
};

interface StructureViewerPanelProps {
  pdbUrl?: string | null;
  pdbArtifact?: ModelArtifactItem | null;
  title?: string;
}

export function StructureViewerPanel({
  pdbUrl,
  pdbArtifact,
  title = 'Structure Viewer',
}: StructureViewerPanelProps) {
  const [viewerError] = useState<string | null>(null);

  const handleDownload = () => {
    if (!pdbUrl) return;
    const a = document.createElement('a');
    a.href = pdbUrl;
    a.download = pdbArtifact?.name ?? 'structure.pdb';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-slate-900">{title}</h3>
          <p className="mt-1 text-sm text-slate-500">
            Computational prediction only — NOT_EXPERIMENTALLY_VALIDATED.
          </p>
        </div>
        {pdbUrl && (
          <button
            type="button"
            onClick={handleDownload}
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 px-3 py-2 text-sm font-medium text-slate-700 transition hover:border-slate-300 hover:bg-slate-50"
          >
            <Download className="w-4 h-4" />
            Download PDB
          </button>
        )}
      </div>

      {pdbArtifact && (
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2 py-1">
            <FileBox className="w-3 h-3" />
            {ARTIFACT_TYPE_LABELS[pdbArtifact.artifact_type] ?? 'File'}
          </span>
          <span>{pdbArtifact.path}</span>
          <span className="text-slate-400">{Math.max(0, pdbArtifact.size_bytes).toLocaleString()} bytes</span>
          <span
            className={`rounded-full px-2 py-0.5 font-medium ${
              pdbArtifact.exists
                ? 'bg-emerald-50 text-emerald-700'
                : 'bg-rose-50 text-rose-700'
            }`}
          >
            {pdbArtifact.exists ? 'Exists' : 'Missing'}
          </span>
        </div>
      )}

      <div className="rounded-2xl border border-slate-200 bg-slate-50 overflow-hidden">
        {pdbUrl ? (
          viewerError ? (
            <div className="flex h-[420px] flex-col items-center justify-center gap-3 p-8 text-center">
              <AlertTriangle className="w-8 h-8 text-amber-500" />
              <div className="space-y-1">
                <p className="font-medium text-slate-900">3D viewer unavailable</p>
                <p className="text-sm text-slate-500">{viewerError}</p>
              </div>
            </div>
          ) : (
            <MolstarViewer
              pdbUrl={pdbUrl}
              height={420}
              viewerId="structure-viewer-panel"
            />
          )
        ) : (
          <div className="flex h-[420px] flex-col items-center justify-center gap-3 p-8 text-center">
            <Loader2 className="w-8 h-8 text-slate-300" />
            <div className="space-y-1">
              <p className="font-medium text-slate-900">No structure loaded</p>
              <p className="text-sm text-slate-500">
                Select a model and run Probe / Dry Run, or choose a PDB artifact to view.
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <div className="flex items-start gap-2">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <div className="space-y-1">
            <p className="font-medium">Scientific boundary</p>
            <ul className="list-disc space-y-0.5 pl-4 text-xs">
              <li>This viewer displays predicted structural models only.</li>
              <li>No Kd, MIC, MM-GBSA, ipTM, pLDDT, RMSD, or RMSF is reported as experimental.</li>
              <li>All structures are NOT_EXPERIMENTALLY_VALIDATED computational artifacts.</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
