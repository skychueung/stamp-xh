import { Download } from 'lucide-react';
import type { CandidateStructureCardProps } from '@/types/structure-viewer';
import { PlddtBadge } from './PlddtBadge';
import { SecondaryStructureBar } from './SecondaryStructureBar';
import { MolstarViewer } from './MolstarViewer';
import styles from './CandidateStructureCard.module.css';

export function CandidateStructureCard({ candidate }: CandidateStructureCardProps) {
  const handleDownload = () => {
    const link = document.createElement('a');
    link.href = candidate.pdbUrl;
    link.download = `${candidate.id}.pdb`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className={styles.card}>
      <div className={styles.left}>
        <div className={styles.header}>
          <h3 className={styles.name}>{candidate.name}</h3>
          <PlddtBadge value={candidate.meanPlddt} />
        </div>

        <div className={styles.metaGrid}>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Sequence</span>
            <span className={styles.metaValueMono}>{candidate.sequence}</span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Length</span>
            <span className={styles.metaValue}>{candidate.length} aa</span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>Net charge</span>
            <span className={styles.metaValue}>{candidate.netCharge}</span>
          </div>
          <div className={styles.metaItem}>
            <span className={styles.metaLabel}>mean pLDDT</span>
            <span className={styles.metaValue}>{candidate.meanPlddt.toFixed(1)}</span>
          </div>
        </div>

        <div className={styles.ssSection}>
          <span className={styles.ssLabel}>Secondary structure</span>
          <SecondaryStructureBar composition={candidate.secondaryStructure} />
        </div>

        <button type="button" className={styles.downloadBtn} onClick={handleDownload}>
          <Download className={styles.btnIcon} />
          Download PDB
        </button>
      </div>

      <div className={styles.right}>
        <MolstarViewer
          pdbUrl={candidate.pdbUrl}
          height={380}
          viewerId={`molstar-${candidate.id}`}
        />
      </div>
    </div>
  );
}
