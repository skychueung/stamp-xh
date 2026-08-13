import { useRef, useEffect, useCallback, forwardRef, useImperativeHandle, useState } from 'react';
import { Viewer } from 'molstar/lib/apps/viewer/app';
import { MolScriptBuilder as MS } from 'molstar/lib/mol-script/language/builder';
import { compileIdListSelection } from 'molstar/lib/mol-script/util/id-list';
import type { LoadOptions } from '@/types/platform';
import { Eye, EyeOff, RotateCcw, Download, Camera } from 'lucide-react';

const LAYER_COLORS = {
  target: 0xCCCCCC,
  epitope: 0xF59E0B,
  peptide: 0x06B6D4,
  contacts: 0xEF4444,
} as const;

type LayerKey = 'target' | 'epitope' | 'peptide' | 'contacts';

export interface ComplexViewerRef {
  loadPdbUrl: (url: string, options?: LoadOptions) => Promise<void>;
  loadPdbData: (pdbContent: string, options?: LoadOptions) => Promise<void>;
  showLayer: (layer: LayerKey) => void;
  hideLayer: (layer: LayerKey) => void;
  highlightEpitope: (range: { start: number; end: number }) => void;
  resetView: () => void;
  exportSnapshot: () => Promise<string>;
}

export interface ComplexViewerProps {
  complexPdbUrl?: string;
  targetChainId?: string;
  peptideChainId?: string;
  epitopeResidueRange?: { start: number; end: number };
  height?: number;
  onLoad?: () => void;
  onError?: (error: Error) => void;
}

function chainExpression(chainId: string) {
  return MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.struct.atomProperty.macromolecular.auth_asym_id(), chainId]),
  });
}

function epitopeExpression(chainId: string, start: number, end: number) {
  return MS.struct.generator.atomGroups({
    'chain-test': MS.core.rel.eq([MS.struct.atomProperty.macromolecular.auth_asym_id(), chainId]),
    'residue-test': MS.core.rel.inRange([MS.struct.atomProperty.macromolecular.label_seq_id(), start, end]),
  });
}

const ComplexMolstarViewer = forwardRef<ComplexViewerRef, ComplexViewerProps>(
  ({ complexPdbUrl, targetChainId = 'A', peptideChainId = 'B', epitopeResidueRange, height = 540, onLoad, onError }, ref) => {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const viewerRef = useRef<Viewer | null>(null);
    const layerRefs = useRef<Map<LayerKey, string>>(new Map());
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [layerVisible, setLayerVisible] = useState<Record<LayerKey, boolean>>({
      target: true,
      epitope: true,
      peptide: true,
      contacts: false,
    });

    useEffect(() => {
      let disposed = false;

      async function init() {
        if (!containerRef.current) return;
        try {
          setLoading(true);
          setError(null);

          const viewer = await Viewer.create(containerRef.current, {
            layoutIsExpanded: false,
            layoutShowControls: true,
            layoutShowRemoteState: false,
            layoutShowSequence: true,
            layoutShowLog: false,
            layoutShowLeftPanel: false,
            viewportShowExpand: true,
            viewportShowSelectionMode: true,
            viewportShowControls: true,
            viewportShowAnimation: true,
          });

          if (disposed) {
            viewer.dispose();
            return;
          }

          viewerRef.current = viewer;
          setLoading(false);

          if (complexPdbUrl) {
            await loadStructureUrl(complexPdbUrl, { targetChainId, peptideChainId, epitopeRange: epitopeResidueRange });
          }
        } catch (err) {
          if (disposed) return;
          const message = err instanceof Error ? err.message : 'Failed to initialize viewer';
          setError(message);
          setLoading(false);
          onError?.(new Error(message));
        }
      }

      void init();

      return () => {
        disposed = true;
        viewerRef.current?.dispose();
        viewerRef.current = null;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const buildStructure = useCallback(async (loadData: () => Promise<{ trajectory: unknown }>, options?: {
      targetChainId?: string;
      peptideChainId?: string;
      epitopeRange?: { start: number; end: number };
    }) => {
      const plugin = viewerRef.current?.plugin;
      if (!plugin) throw new Error('Viewer not initialized');

      setLoading(true);
      setError(null);
      layerRefs.current.clear();

      try {
        await plugin.clear();

        const { trajectory } = await loadData();
        const model = await plugin.builders.structure.createModel(trajectory as never);
        const structure = await plugin.builders.structure.createStructure(model);

        const tChain = options?.targetChainId ?? 'A';
        const pChain = options?.peptideChainId ?? 'B';
        const epiRange = options?.epitopeRange;

        // Target protein (full chain)
        const targetComp = await plugin.builders.structure.tryCreateComponentFromExpression(
          structure,
          chainExpression(tChain),
          'Target Protein'
        );
        if (targetComp) {
          const repr = await plugin.builders.structure.representation.addRepresentation(targetComp, {
            type: 'cartoon',
            color: 'uniform',
            colorParams: { value: LAYER_COLORS.target },
          });
          if (repr) layerRefs.current.set('target', repr.ref);
        }

        // Targeting peptide
        const peptideComp = await plugin.builders.structure.tryCreateComponentFromExpression(
          structure,
          chainExpression(pChain),
          'Targeting Peptide'
        );
        if (peptideComp) {
          const repr = await plugin.builders.structure.representation.addRepresentation(peptideComp, {
            type: 'ball-and-stick',
            color: 'uniform',
            colorParams: { value: LAYER_COLORS.peptide },
          });
          if (repr) layerRefs.current.set('peptide', repr.ref);
        }

        // Selected epitope (subset of target chain)
        if (epiRange) {
          const epitopeComp = await plugin.builders.structure.tryCreateComponentFromExpression(
            structure,
            epitopeExpression(tChain, epiRange.start, epiRange.end),
            'Selected Epitope'
          );
          if (epitopeComp) {
            const repr = await plugin.builders.structure.representation.addRepresentation(epitopeComp, {
              type: 'ball-and-stick',
              color: 'uniform',
              colorParams: { value: LAYER_COLORS.epitope },
            });
            if (repr) layerRefs.current.set('epitope', repr.ref);
          }
        }

        // Center camera
        plugin.managers.camera.reset();
        setLoading(false);
        onLoad?.();
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Failed to load structure';
        setError(message);
        setLoading(false);
        onError?.(new Error(message));
      }
    }, [onLoad, onError]);

    const loadStructureUrl = useCallback(async (url: string, options?: {
      targetChainId?: string;
      peptideChainId?: string;
      epitopeRange?: { start: number; end: number };
    }) => {
      const plugin = viewerRef.current?.plugin;
      if (!plugin) throw new Error('Viewer not initialized');

      await buildStructure(async () => {
        const data = await plugin.builders.data.download({ url: url as unknown as never, isBinary: false });
        const trajectory = await plugin.builders.structure.parseTrajectory(data, 'pdb');
        return { trajectory };
      }, options);
    }, [buildStructure]);

    const loadStructureData = useCallback(async (pdbContent: string, options?: {
      targetChainId?: string;
      peptideChainId?: string;
      epitopeRange?: { start: number; end: number };
    }) => {
      const plugin = viewerRef.current?.plugin;
      if (!plugin) throw new Error('Viewer not initialized');

      await buildStructure(async () => {
        const data = await plugin.builders.data.rawData({ data: pdbContent, label: 'complex.pdb' });
        const trajectory = await plugin.builders.structure.parseTrajectory(data, 'pdb');
        return { trajectory };
      }, options);
    }, [buildStructure]);

    useImperativeHandle(ref, () => ({
      loadPdbUrl: loadStructureUrl,
      loadPdbData: loadStructureData,
      showLayer: (layer) => {
        const plugin = viewerRef.current?.plugin;
        const ref = layerRefs.current.get(layer);
        if (plugin && ref) {
          plugin.state.data.updateCellState(ref, { isHidden: false });
          setLayerVisible((v) => ({ ...v, [layer]: true }));
        }
      },
      hideLayer: (layer) => {
        const plugin = viewerRef.current?.plugin;
        const ref = layerRefs.current.get(layer);
        if (plugin && ref) {
          plugin.state.data.updateCellState(ref, { isHidden: true });
          setLayerVisible((v) => ({ ...v, [layer]: false }));
        }
      },
      highlightEpitope: (range) => {
        const plugin = viewerRef.current?.plugin;
        if (!plugin) return;
        const query = compileIdListSelection(`${targetChainId} ${range.start}-${range.end}`, 'auth');
        void plugin.managers.structure.selection.fromCompiledQuery('set', query);
      },
      resetView: () => {
        viewerRef.current?.plugin?.managers.camera.reset();
      },
      exportSnapshot: async () => {
        const plugin = viewerRef.current?.plugin;
        if (!plugin) throw new Error('Viewer not initialized');
        const screenshot = plugin.helpers.viewportScreenshot;
        if (!screenshot) throw new Error('Screenshot helper not available');
        return await screenshot.getImageDataUri();
      },
    }));

    const handleDownload = () => {
      if (complexPdbUrl) {
        const link = document.createElement('a');
        link.href = complexPdbUrl;
        link.download = 'complex.pdb';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      }
    };

    const handleSnapshot = async () => {
      try {
        const plugin = viewerRef.current?.plugin;
        if (!plugin) return;
        const screenshot = plugin.helpers.viewportScreenshot;
        if (!screenshot) return;
        const dataUrl = await screenshot.getImageDataUri();
        const link = document.createElement('a');
        link.href = dataUrl;
        link.download = 'snapshot.png';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } catch {
        // ignore
      }
    };

    const toggleLayer = (layer: LayerKey) => {
      const next = !layerVisible[layer];
      setLayerVisible((v) => ({ ...v, [layer]: next }));
      if (next) {
        const plugin = viewerRef.current?.plugin;
        const ref = layerRefs.current.get(layer);
        if (plugin && ref) plugin.state.data.updateCellState(ref, { isHidden: false });
      } else {
        const plugin = viewerRef.current?.plugin;
        const ref = layerRefs.current.get(layer);
        if (plugin && ref) plugin.state.data.updateCellState(ref, { isHidden: true });
      }
    };

    return (
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <button
            type="button"
            onClick={() => toggleLayer('target')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
              layerVisible.target ? 'bg-gray-100 border-gray-300 text-gray-700' : 'bg-white border-gray-200 text-gray-400'
            }`}
          >
            {layerVisible.target ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            Target Protein
          </button>
          <button
            type="button"
            onClick={() => toggleLayer('epitope')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
              layerVisible.epitope ? 'bg-amber-50 border-amber-300 text-amber-700' : 'bg-white border-gray-200 text-gray-400'
            }`}
          >
            {layerVisible.epitope ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            Selected Epitope
          </button>
          <button
            type="button"
            onClick={() => toggleLayer('peptide')}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border transition-colors ${
              layerVisible.peptide ? 'bg-cyan-50 border-cyan-300 text-cyan-700' : 'bg-white border-gray-200 text-gray-400'
            }`}
          >
            {layerVisible.peptide ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            Targeting Peptide
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => {
              setLayerVisible({ target: true, epitope: true, peptide: true, contacts: false });
              viewerRef.current?.plugin?.managers.camera.reset();
            }}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border border-gray-200 text-xh-text hover:bg-gray-50"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            Reset View
          </button>
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border border-gray-200 text-xh-text hover:bg-gray-50"
          >
            <Download className="w-3.5 h-3.5" />
            PDB
          </button>
          <button
            type="button"
            onClick={handleSnapshot}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-medium border border-gray-200 text-xh-text hover:bg-gray-50"
          >
            <Camera className="w-3.5 h-3.5" />
            Snapshot
          </button>
        </div>

        <div className="relative rounded-lg border border-xh-border overflow-hidden bg-[#111318]" style={{ height }}>
          <div ref={containerRef} className="w-full h-full" />
          {loading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-[#111318]/90 z-10">
              <div className="w-8 h-8 border-2 border-xh-primary border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-gray-400">Loading structure...</span>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-[#111318]/90 z-10">
              <span className="text-sm font-semibold text-red-400">Structure load failed</span>
              <span className="text-xs text-gray-400 max-w-[80%] text-center">{error}</span>
            </div>
          )}

          <div className="absolute bottom-3 left-3 bg-black/70 backdrop-blur-sm rounded-md border border-gray-700 px-3 py-2 shadow-sm">
            <div className="text-xs font-semibold text-gray-200 mb-1.5">Legend</div>
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#CCCCCC' }} />
                <span className="text-[11px] text-gray-300">Target Protein</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#F59E0B' }} />
                <span className="text-[11px] text-gray-300">Selected Epitope</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-sm" style={{ backgroundColor: '#06B6D4' }} />
                <span className="text-[11px] text-gray-300">Targeting Peptide</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
);

ComplexMolstarViewer.displayName = 'ComplexMolstarViewer';

export { ComplexMolstarViewer };
