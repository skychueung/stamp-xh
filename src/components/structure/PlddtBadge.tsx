import styles from './PlddtBadge.module.css';
import type { PlddtBadgeProps } from '@/types/structure-viewer';

function getPlddtLabel(value: number): string {
  if (value >= 90) return 'Very high';
  if (value >= 70) return 'Confident';
  if (value >= 50) return 'Low';
  return 'Very low';
}

function getPlddtClass(value: number): string {
  if (value >= 90) return styles.veryHigh;
  if (value >= 70) return styles.confident;
  if (value >= 50) return styles.low;
  return styles.veryLow;
}

export function PlddtBadge({ value }: PlddtBadgeProps) {
  return (
    <span className={`${styles.badge} ${getPlddtClass(value)}`}>
      <span className={styles.value}>{value.toFixed(1)}</span>
      <span className={styles.label}>{getPlddtLabel(value)}</span>
    </span>
  );
}
