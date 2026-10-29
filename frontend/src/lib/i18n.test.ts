import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, describe, expect, it } from 'vitest';
import { en } from './i18n/en';
import { i18n, t } from './i18n.svelte';

const SRC = join(__dirname, '..');

function sourceFiles(dir: string): string[] {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return sourceFiles(path);
    // the i18n module itself only has t('…') in its comments
    const skip = entry.name.endsWith('.test.ts') || entry.name.startsWith('i18n') || entry.name === 'en.ts';
    return /\.(svelte|ts)$/.test(entry.name) && !skip ? [path] : [];
  });
}

/** All t('…') keys used in the source, with the file they appear in */
function usedKeys(): Map<string, string> {
  const keys = new Map<string, string>();
  for (const file of sourceFiles(SRC)) {
    const text = readFileSync(file, 'utf8');
    for (const m of text.matchAll(/\bt\(\s*'((?:\\.|[^'\\])*)'/g)) keys.set(m[1].replace(/\\'/g, "'"), file);
  }
  return keys;
}

const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();

describe('translations', () => {
  const used = usedKeys();

  it('finds the t() calls', () => {
    expect(used.size).toBeGreaterThan(200);
  });

  it('only calls t() with a string literal', () => {
    for (const file of sourceFiles(SRC)) {
      const text = readFileSync(file, 'utf8');
      expect(text.match(/\bt\(\s*[^'\s)]/g) ?? [], file).toEqual([]);
    }
  });

  it('has an English text for every key', () => {
    const missing = [...used.keys()].filter((key) => !(key in en));
    expect(missing).toEqual([]);
  });

  it('has no unused English texts', () => {
    const unused = Object.keys(en).filter((key) => !used.has(key));
    expect(unused).toEqual([]);
  });

  it('keeps the same placeholders', () => {
    for (const [de, english] of Object.entries(en))
      expect(placeholders(english), de).toEqual(placeholders(de));
  });
});

describe('t()', () => {
  afterEach(() => i18n.set('de'));

  it('returns German by default and English when switched', () => {
    i18n.set('de');
    expect(t('Aufnahme starten')).toBe('Aufnahme starten');
    i18n.set('en');
    expect(t('Aufnahme starten')).toBe('Start recording');
  });

  it('fills placeholders and strips the context hint', () => {
    i18n.set('de');
    expect(t('{n} Stunden', { n: 6 })).toBe('6 Stunden');
    expect(t('Sprache||language')).toBe('Sprache');
    i18n.set('en');
    expect(t('{n} Stunden', { n: 6 })).toBe('6 hours');
    expect(t('Sprache||language')).toBe('Language');
  });

  it('remembers the choice and sets the document language', () => {
    i18n.set('en');
    expect(localStorage.getItem('radiomoni.locale')).toBe('en');
    expect(document.documentElement.lang).toBe('en');
  });
});
