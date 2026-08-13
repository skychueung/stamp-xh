import { useState } from 'react';
import { Play, Trash2, ChevronRight, ArrowRight } from 'lucide-react';
import { TEXT } from '@/lib/platformText';
import { ScoreCard } from './ScoreCard';
import type { ScoreItem } from '@/types/peptide-ui';
import styles from './StampPanel.module.css';

const SCORE_DATA: ScoreItem[] = [
  {
    label: TEXT.scoreLabels.targetingPeptide,
    score: 0.9,
    maxScore: 1.0,
    criteria: TEXT.criteria.targetingPeptide,
  },
  {
    label: TEXT.scoreLabels.linker,
    score: 0.87,
    maxScore: 1.0,
    criteria: TEXT.criteria.linker,
  },
  {
    label: TEXT.scoreLabels.stamp,
    score: 0.88,
    maxScore: 1.0,
    criteria: TEXT.criteria.stamp,
  },
  {
    label: TEXT.scoreLabels.overall,
    score: 0.89,
    maxScore: 1.0,
    criteria: [],
  },
];

export function StampPanel() {
  const [sequence, setSequence] = useState('');
  const [advancedOpen, setAdvancedOpen] = useState(false);

  return (
    <div className={styles.panel}>
      <div className={styles.left}>
        <div className={styles.sectionTitle}>
          <span className={styles.icon}>🛡️</span>
          <span>{TEXT.stampTitle}</span>
        </div>

        <div className={styles.inputCard}>
          <label className={styles.inputLabel}>{TEXT.stampInputTitle}</label>
          <textarea
            className={styles.textarea}
            rows={4}
            placeholder={TEXT.stampPlaceholder}
            value={sequence}
            onChange={(e) => setSequence(e.target.value)}
          />
          <div className={styles.charCount}>{sequence.length} / 500</div>

          <div className={styles.actions}>
            <button type="button" className={styles.primaryBtn}>
              <Play className={styles.btnIcon} />
              {TEXT.inputBtn}
            </button>
            <button
              type="button"
              className={styles.secondaryBtn}
              onClick={() => setSequence('')}
            >
              <Trash2 className={styles.btnIcon} />
              {TEXT.clearBtn}
            </button>
          </div>
        </div>

        <button
          type="button"
          className={styles.advancedToggle}
          onClick={() => setAdvancedOpen(!advancedOpen)}
        >
          <span>{TEXT.advancedSettings}</span>
          <ChevronRight
            className={`${styles.toggleIcon} ${advancedOpen ? styles.toggleIconOpen : ''}`}
          />
          <span className={styles.toggleText}>{TEXT.showMoreParams}</span>
        </button>
      </div>

      <div className={styles.right}>
        <div className={styles.scoreHeader}>
          <span>{TEXT.stampScoreTitle}</span>
          <span className={styles.helpIcon}>?</span>
        </div>

        <div className={styles.scoreGrid}>
          {SCORE_DATA.slice(0, 3).map((item) => (
            <ScoreCard key={item.label} item={item} variant="default" />
          ))}
          <ScoreCard key={SCORE_DATA[3].label} item={SCORE_DATA[3]} variant="ring" />
        </div>

        <button type="button" className={styles.linkBtn}>
          {TEXT.viewDetailedReport}
          <ArrowRight className={styles.linkIcon} />
        </button>
      </div>
    </div>
  );
}
