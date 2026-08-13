import { useState } from 'react';
import { Play, RotateCcw, ArrowRight } from 'lucide-react';
import type { LinkerType, LinkerScore } from '@/types/peptide-ui';
import { TEXT } from '@/lib/platformText';
import styles from './LinkerPanel.module.css';

const LINKER_OPTIONS: { value: LinkerType; label: string; icon: string }[] = [
  { value: 'none', label: '无', icon: '○' },
  { value: 'flexible', label: '柔性', icon: '〜' },
  { value: 'rigid', label: '刚性', icon: '⬡' },
  { value: 'alternative', label: '备选', icon: '✦' },
];

const MOCK_SCORES: LinkerScore[] = [
  { id: 1, peptideSequence: 'GGGGS', linkerLength: 5, flexibility: '100%', score: 0.92 },
  { id: 2, peptideSequence: 'GGSGGS', linkerLength: 6, flexibility: '83%', score: 0.89 },
  { id: 3, peptideSequence: 'GGSGGSG', linkerLength: 7, flexibility: '86%', score: 0.87 },
  { id: 4, peptideSequence: 'EAAAK', linkerLength: 5, flexibility: '20%', score: 0.81 },
  { id: 5, peptideSequence: 'GGSEGGSE', linkerLength: 8, flexibility: '75%', score: 0.79 },
];

export function LinkerPanel() {
  const [selected, setSelected] = useState<LinkerType>('none');
  const [lenMin, setLenMin] = useState(5);
  const [lenMax, setLenMax] = useState(25);
  const [chargeMin, setChargeMin] = useState(-2);
  const [chargeMax, setChargeMax] = useState(2);
  const [flexibility, setFlexibility] = useState('Medium');
  const [excluded, setExcluded] = useState('');

  return (
    <div className={styles.panel}>
      <div className={styles.left}>
        <div className={styles.sectionTitle}>
          <span className={styles.icon}>🔗</span>
          <span>{TEXT.linkerTitle}</span>
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.fieldLabel}>{TEXT.linkerOptionsTitle}</label>
          <div className={styles.optionsGrid}>
            {LINKER_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                className={`${styles.optionBtn} ${selected === opt.value ? styles.optionActive : ''}`}
                onClick={() => setSelected(opt.value)}
              >
                <span className={styles.optionIcon}>{opt.icon}</span>
                <span>{opt.label}</span>
              </button>
            ))}
          </div>
        </div>

        <div className={styles.fieldGroup}>
          <label className={styles.fieldLabel}>{TEXT.linkerParamsTitle}</label>
          <div className={styles.paramsGrid}>
            <div className={styles.paramItem}>
              <span className={styles.paramLabel}>Length Range (aa)</span>
              <div className={styles.rangeRow}>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={lenMin}
                  onChange={(e) => setLenMin(Number(e.target.value))}
                />
                <span className={styles.rangeDash}>-</span>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={lenMax}
                  onChange={(e) => setLenMax(Number(e.target.value))}
                />
              </div>
            </div>
            <div className={styles.paramItem}>
              <span className={styles.paramLabel}>Net Charge Range</span>
              <div className={styles.rangeRow}>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={chargeMin}
                  onChange={(e) => setChargeMin(Number(e.target.value))}
                />
                <span className={styles.rangeDash}>-</span>
                <input
                  type="number"
                  className={styles.numberInput}
                  value={chargeMax}
                  onChange={(e) => setChargeMax(Number(e.target.value))}
                />
              </div>
            </div>
            <div className={styles.paramItem}>
              <span className={styles.paramLabel}>Flexibility Preference</span>
              <select
                className={styles.selectInput}
                value={flexibility}
                onChange={(e) => setFlexibility(e.target.value)}
              >
                <option>Low</option>
                <option>Medium</option>
                <option>High</option>
              </select>
            </div>
            <div className={styles.paramItem}>
              <span className={styles.paramLabel}>Excluded Residues</span>
              <input
                type="text"
                className={styles.textInput}
                placeholder="e.g., C, P, G"
                value={excluded}
                onChange={(e) => setExcluded(e.target.value)}
              />
            </div>
          </div>
        </div>

        <div className={styles.actions}>
          <button type="button" className={styles.primaryBtn}>
            <Play className={styles.btnIcon} />
            {TEXT.generateBtn}
          </button>
          <button
            type="button"
            className={styles.secondaryBtn}
            onClick={() => {
              setSelected('none');
              setLenMin(5);
              setLenMax(25);
              setChargeMin(-2);
              setChargeMax(2);
              setFlexibility('Medium');
              setExcluded('');
            }}
          >
            <RotateCcw className={styles.btnIcon} />
            {TEXT.resetBtn}
          </button>
        </div>
      </div>

      <div className={styles.right}>
        <div className={styles.scoreHeader}>
          <span>{TEXT.linkerScoreTitle}</span>
          <span className={styles.helpIcon}>?</span>
        </div>
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>序号</th>
                <th>靶向肽序列</th>
                <th>Linker 长度</th>
                <th>柔性</th>
                <th>评分</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_SCORES.map((row) => (
                <tr key={row.id}>
                  <td>{row.id}</td>
                  <td className={styles.sequenceCell}>{row.peptideSequence}</td>
                  <td>{row.linkerLength}</td>
                  <td>{row.flexibility}</td>
                  <td className={styles.scoreCell}>{row.score.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className={styles.linkBtn}>
          {TEXT.viewAllLinkers}
          <ArrowRight className={styles.linkIcon} />
        </button>
      </div>
    </div>
  );
}
