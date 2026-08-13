import { useState, useEffect, useCallback } from 'react';
import { TEXT } from '@/lib/platformText';
import { MoleculeDecoration } from '@/components/platform/MoleculeDecoration';
import { LinkerPanel } from '@/components/platform/LinkerPanel';
import { StampPanel } from '@/components/platform/StampPanel';
import styles from './TargetingPeptidePage.module.css';

export default function TargetingPeptidePage() {
  const [activeSection, setActiveSection] = useState<'linker' | 'stamp'>('linker');

  const scrollToSection = useCallback((sectionId: 'linker' | 'stamp') => {
    const element = document.getElementById(sectionId);
    element?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    setActiveSection(sectionId);
  }, []);

  useEffect(() => {
    const handleScroll = () => {
      const linker = document.getElementById('linker');
      const stamp = document.getElementById('stamp');
      if (!linker || !stamp) return;

      const linkerRect = linker.getBoundingClientRect();
      const stampRect = stamp.getBoundingClientRect();
      const offset = 120;

      if (stampRect.top <= offset) {
        setActiveSection('stamp');
      } else if (linkerRect.top <= offset) {
        setActiveSection('linker');
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <div className={styles.page}>
      <header className={styles.pageHeader}>
        <div className={styles.headerText}>
          <h1 className={styles.pageTitle}>{TEXT.pageTitle}</h1>
          <p className={styles.pageSubtitle}>{TEXT.pageSubtitle}</p>
        </div>
        <MoleculeDecoration />
      </header>

      <div className={styles.sectionTabs}>
        <button
          type="button"
          className={`${styles.tab} ${activeSection === 'linker' ? styles.tabActive : ''}`}
          onClick={() => scrollToSection('linker')}
        >
          {TEXT.linkerTab}
        </button>
        <button
          type="button"
          className={`${styles.tab} ${activeSection === 'stamp' ? styles.tabActive : ''}`}
          onClick={() => scrollToSection('stamp')}
        >
          {TEXT.stampTab}
        </button>
      </div>

      <section id="linker" className={styles.section}>
        <LinkerPanel />
      </section>

      <section id="stamp" className={styles.section}>
        <StampPanel />
      </section>

      <div className={styles.noticeBar}>
        <span className={styles.noticeIcon}>ⓘ</span>
        <span>{TEXT.noticeText}</span>
      </div>
    </div>
  );
}
