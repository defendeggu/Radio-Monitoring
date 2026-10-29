import { defineConfig, devices } from '@playwright/test';

// Smoke tests against the production build with a mocked API (see e2e/).
export default defineConfig({
  testDir: 'e2e',
  timeout: 30_000,
  // German browser locale: the UI picks its language from it (English tests switch explicitly)
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure', locale: 'de-CH' },
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1',
    port: 4173,
    reuseExistingServer: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
