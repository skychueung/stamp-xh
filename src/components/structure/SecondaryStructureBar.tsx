import styles from './SecondaryStructureBar.module.css';
import type { SecondaryStructureBarProps } from '@/types/structure-viewer';

export function SecondaryStructureBar({ composition }: SecondaryStructureBarProps) {
  const helixPct = Math.round(composition.helix * 100);
  const sheetPct = Math.round(composition.sheet * 100);
  const coilPct = 100 - helixPct - sheetPct;

  return (
    <div className={styles.container}>
      <div className={styles.bar}>
        {helixPct > 0 && (
          <div
            className={styles.segmentHelix}
            style={{ width: `${helixPct}%` }}
            title={`α-helix ${helixPct}%`}
          />
        )}
        {sheetPct > 0 && (
          <div
            className={styles.segmentSheet}
            style={{ width: `${sheetPct}%` }}
            title={`β-sheet ${sheetPct}%`}
          />
        )}
        {coilPct > 0 && (
          <div
            className={styles.segmentCoil}
            style={{ width: `${coilPct}%` }}
            title={`coil ${coilPct}%`}
          />
        )}
      </div>
      <div className={styles.legend}>
        <div className={styles.legendItem}>
          <span className={`${styles.dot} ${styles.dotHelix}`} />
          <span>α-helix {helixPct}%</span>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.dot} ${styles.dotSheet}`} />
          <span>β-sheet {sheetPct}%</span>
        </div>
        <div className={styles.legendItem}>
          <span className={`${styles.dot} ${styles.dotCoil}`} />
          <span>coil {coilPct}%</span>
        </div>
      </div>
    </div>
  );
}
