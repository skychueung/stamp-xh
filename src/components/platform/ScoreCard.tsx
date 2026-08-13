import { CheckCircle2 } from 'lucide-react';
import type { ScoreItem } from '@/types/peptide-ui';
import { ScoreRing } from './ScoreRing';
import styles from './ScoreCard.module.css';

interface ScoreCardProps {
  item: ScoreItem;
  variant?: 'default' | 'ring';
}

export function ScoreCard({ item, variant = 'default' }: ScoreCardProps) {
  const percentage = (item.score / item.maxScore) * 100;

  if (variant === 'ring') {
    return (
      <div className={styles.card}>
        <div className={styles.ringHeader}>{item.label}</div>
        <div className={styles.ringBody}>
          <ScoreRing score={item.score / item.maxScore} size={120} />
        </div>
        <div className={styles.ringScoreText}>
          <span className={styles.scoreNumber}>{item.score.toFixed(2)}</span>
          <span className={styles.scoreMax}> / {item.maxScore.toFixed(2)}</span>
        </div>
        <ul className={styles.criteriaList}>
          {item.criteria.map((c) => (
            <li key={c} className={styles.criteriaItem}>
              <CheckCircle2 className={styles.criteriaIcon} />
              <span>{c}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className={styles.card}>
      <div className={styles.header}>{item.label}</div>
      <div className={styles.scoreRow}>
        <span className={styles.scoreNumber}>{item.score.toFixed(2)}</span>
        <span className={styles.scoreMax}> / {item.maxScore.toFixed(2)}</span>
      </div>
      <div className={styles.barTrack}>
        <div
          className={styles.barFill}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <ul className={styles.criteriaList}>
        {item.criteria.map((c) => (
          <li key={c} className={styles.criteriaItem}>
            <CheckCircle2 className={styles.criteriaIcon} />
            <span>{c}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
