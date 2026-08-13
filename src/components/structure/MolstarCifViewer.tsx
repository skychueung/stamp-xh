import { useRef, useEffect, useState } from 'react';
import { Viewer } from 'molstar/lib/apps/viewer/app';
import 'molstar/lib/mol-plugin-ui/skin/light.scss';
import styles from './MolstarViewer.module.css';

interface MolstarCifViewerProps {
  cifUrl: string;
  height?: number;
  viewerId?: string;
}

export function MolstarCifViewer({ cifUrl, height = 420, viewerId }: MolstarCifViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const viewerRef = useRef<Viewer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let disposed = false;

    async function init() {
      if (!containerRef.current || !cifUrl) return;

      try {
        setLoading(true);
        setError(null);

        // Dispose previous viewer if URL changed
        if (viewerRef.current) {
          viewerRef.current.dispose();
          viewerRef.current = null;
        }

        const viewer = await Viewer.create(containerRef.current, {
          layoutIsExpanded: false,
          layoutShowControls: true,
          layoutShowRemoteState: false,
          layoutShowSequence: true,
          layoutShowLog: false,
          layoutShowLeftPanel: false,
        });

        if (disposed) {
          viewer.dispose();
          return;
        }

        viewerRef.current = viewer;

        // Load CIF format (mmcif)
        await viewer.loadStructureFromUrl(cifUrl, 'mmcif', false);
        setLoading(false);
      } catch (err) {
        if (disposed) return;
        const message = err instanceof Error ? err.message : 'Failed to load structure';
        setError(message);
        setLoading(false);
      }
    }

    void init();

    return () => {
      disposed = true;
      viewerRef.current?.dispose();
      viewerRef.current = null;
    };
  }, [cifUrl]);

  return (
    <div className={styles.wrapper} style={{ height }}>
      <div id={viewerId} ref={containerRef} className={styles.viewer} />
      {loading && (
        <div className={styles.overlay}>
          <div className={styles.spinner} />
          <span className={styles.overlayText}>Loading structure...</span>
        </div>
      )}
      {error && (
        <div className={styles.overlay}>
          <span className={styles.errorText}>Structure load failed</span>
          <span className={styles.errorDetail}>{error}</span>
        </div>
      )}
    </div>
  );
}
