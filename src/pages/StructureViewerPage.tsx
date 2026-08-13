import { structureMetadata } from '@/data/structureMetadata';
import { CandidateStructureCard } from '@/components/structure/CandidateStructureCard';
import styles from './StructureViewerPage.module.css';

const TEXT = {
  pageTitle: 'STRUCTURE VIEWER',
  pageSubtitle:
    'Interactive 3D visualization of ColabFold / AlphaFold2-predicted candidate peptide structures.',
  notice:
    'ColabFold / AlphaFold2 outputs are displayed as predicted structural models. Short peptides may be flexible and environment-dependent.',
  hint: '展示候选肽的预测三维结构、pLDDT 置信度及二级结构组成。预测结果仅供计算筛选参考，需结合实验验证。',
} as const;

export default function StructureViewerPage() {
  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <h1 className={styles.pageTitle}>{TEXT.pageTitle}</h1>
        <p className={styles.pageSubtitle}>{TEXT.pageSubtitle}</p>
      </header>

      <div className={styles.noticeBar}>
        <span className={styles.noticeIcon}>ⓘ</span>
        <div className={styles.noticeContent}>
          <p>{TEXT.notice}</p>
          <p className={styles.hint}>{TEXT.hint}</p>
        </div>
      </div>

      <div className={styles.cards}>
        {structureMetadata.map((candidate) => (
          <CandidateStructureCard key={candidate.id} candidate={candidate} />
        ))}
      </div>
    </div>
  );
}
