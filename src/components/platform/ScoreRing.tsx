import styles from './ScoreRing.module.css';

interface ScoreRingProps {
  score: number;
  label?: string;
  size?: number;
}

export function ScoreRing({ score, label, size = 100 }: ScoreRingProps) {
  const radius = 45;
  const circumference = 2 * Math.PI * radius;
  const progress = score * circumference;

  return (
    <div className={styles.container} style={{ width: size, height: size }}>
      <svg viewBox="0 0 100 100" className={styles.svg}>
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#E5E7EB"
          strokeWidth="8"
        />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke="#156B98"
          strokeWidth="8"
          strokeDasharray={`${progress} ${circumference}`}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          className={styles.progress}
        />
      </svg>
      <div className={styles.value}>{score.toFixed(2)}</div>
      {label && <div className={styles.label}>{label}</div>}
    </div>
  );
}
