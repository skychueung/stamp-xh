/**
 * STAMP Platform - Language Configuration
 * Zero dependencies, localStorage persistence
 */

export type Language = 'zh' | 'en';

export const DEFAULT_LANGUAGE: Language = 'zh';

export const LANGUAGE_STORAGE_KEY = 'stamp-language-preference';

export function getInitialLanguage(): Language {
  try {
    const stored = localStorage.getItem(LANGUAGE_STORAGE_KEY);
    if (stored === 'zh' || stored === 'en') return stored;
  } catch { /* localStorage unavailable */ }
  return DEFAULT_LANGUAGE;
}

export function setStoredLanguage(language: Language): void {
  try {
    localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
  } catch { /* ignore */ }
}

export function getOppositeLanguage(language: Language): Language {
  return language === 'zh' ? 'en' : 'zh';
}
