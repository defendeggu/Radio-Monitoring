import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import svelte from 'eslint-plugin-svelte';
import globals from 'globals';
import ts from 'typescript-eslint';

export default ts.config(
  js.configs.recommended,
  ...ts.configs.recommended,
  ...svelte.configs.recommended,
  prettier,
  ...svelte.configs.prettier,
  {
    languageOptions: { globals: { ...globals.browser, ...globals.node } },
  },
  {
    files: ['**/*.svelte', '**/*.svelte.ts'],
    languageOptions: { parserOptions: { parser: ts.parser } },
  },
  {
    rules: {
      // {@html} is never used — all radio data is untrusted
      'svelte/no-at-html-tags': 'error',
      '@typescript-eslint/no-explicit-any': 'off',
    },
  },
  { ignores: ['dist/', 'node_modules/', 'playwright-report/', 'test-results/'] },
);
