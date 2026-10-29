// UI language (German / English). German texts are the keys; en.ts maps them to English.
//
//   t('Aufnahme starten')                 → "Start recording" when English is active
//   t('{n} Pakete', { n: 3 })              → placeholders in {braces}
//   t('Sprache||language')                  → text after "||" only tells apart words with two meanings
//
// Missing translations fall back to German. i18n.test.ts checks that every t('…') literal has one.

import { en } from './i18n/en';

export type Locale = 'de' | 'en';
export const LOCALES: { value: Locale; label: string }[] = [
  { value: 'de', label: 'Deutsch' },
  { value: 'en', label: 'English' },
];

const STORAGE_KEY = 'radiomoni.locale';

function initialLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'de' || stored === 'en') return stored;
  } catch {
    /* ignore */
  }
  const browser =
    typeof navigator === 'undefined' ? 'de' : (navigator.languages?.[0] ?? navigator.language ?? 'de');
  return browser.toLowerCase().startsWith('de') ? 'de' : 'en';
}

class I18n {
  locale = $state<Locale>(initialLocale());

  constructor() {
    this.apply();
  }

  set(locale: Locale) {
    this.locale = locale;
    try {
      localStorage.setItem(STORAGE_KEY, locale);
    } catch {
      /* ignore */
    }
    this.apply();
  }

  /** Locale for dates and numbers (toLocaleString) */
  get dateLocale(): string {
    return this.locale === 'en' ? 'en-GB' : 'de-CH';
  }

  private apply() {
    if (typeof document !== 'undefined') document.documentElement.lang = this.locale;
  }
}

export const i18n = new I18n();

export function t(de: string, params?: Record<string, string | number | null | undefined>): string {
  const text = (i18n.locale === 'en' ? en[de] : undefined) ?? de.split('||')[0];
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, key: string) =>
    key in params ? String(params[key] ?? '') : match,
  );
}
