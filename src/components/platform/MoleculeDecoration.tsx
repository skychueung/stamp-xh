import styles from './MoleculeDecoration.module.css';

export function MoleculeDecoration() {
  return (
    <div className={styles.container} aria-hidden="true">
      <svg viewBox="0 0 200 100" className={styles.svg}>
        {/* Horizontal backbone */}
        <line x1="10" y1="50" x2="190" y2="50" className={styles.line} />
        
        {/* Nodes */}
        <circle cx="20" cy="50" r="5" className={styles.node} />
        <circle cx="50" cy="35" r="4" className={styles.node} />
        <circle cx="50" cy="65" r="4" className={styles.node} />
        <circle cx="80" cy="50" r="5" className={styles.node} />
        <circle cx="110" cy="30" r="4" className={styles.node} />
        <circle cx="110" cy="70" r="4" className={styles.node} />
        <circle cx="140" cy="50" r="5" className={styles.node} />
        <circle cx="170" cy="40" r="4" className={styles.node} />
        <circle cx="170" cy="60" r="4" className={styles.node} />
        
        {/* Side connections */}
        <line x1="20" y1="50" x2="50" y2="35" className={styles.lineThin} />
        <line x1="20" y1="50" x2="50" y2="65" className={styles.lineThin} />
        <line x1="50" y1="35" x2="50" y2="65" className={styles.lineThin} />
        <line x1="80" y1="50" x2="110" y2="30" className={styles.lineThin} />
        <line x1="80" y1="50" x2="110" y2="70" className={styles.lineThin} />
        <line x1="110" y1="30" x2="110" y2="70" className={styles.lineThin} />
        <line x1="140" y1="50" x2="170" y2="40" className={styles.lineThin} />
        <line x1="140" y1="50" x2="170" y2="60" className={styles.lineThin} />
        <line x1="170" y1="40" x2="170" y2="60" className={styles.lineThin} />
      </svg>
    </div>
  );
}
