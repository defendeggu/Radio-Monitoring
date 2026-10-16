import { expect, test, type Page } from '@playwright/test';

// Minimal mocked API so the UI can be exercised without backend or SDR.
async function mockApi(page: Page) {
  const json = (body: unknown, status = 200) => ({
    status,
    contentType: 'application/json',
    body: JSON.stringify(body),
  });
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname.replace(/^\/api/, '');
    if (path === '/events')
      return route.fulfill({ status: 200, contentType: 'text/event-stream', body: 'retry: 3000\n\n' });
    if (path === '/sdr/status')
      return route.fulfill(json({ busy: false, holder: null, active_sessions: [] }));
    if (path === '/sdr/detect')
      return route.fulfill(
        json({
          detected: true,
          type: 'rtlsdr',
          frequency_range: { min_hz: 24e6, max_hz: 1766e6, min_mhz: 24, max_mhz: 1766 },
        }),
      );
    if (path === '/dashboard/stats')
      return route.fulfill(
        json({
          hours: 24,
          counts: { captures: 3, aprs: 7, pocsag: 0, adsb: 0, ais: 0, alerts: 1 },
          timeline: [],
          latest: {
            aprs: [{ source_callsign: '<img src=x onerror=alert(1)>', message_text: 'hi' }],
            pocsag: [],
            captures: [],
          },
        }),
      );
    if (path === '/alerts/recent') return route.fulfill(json({ alerts: [] }));
    if (path === '/bookmarks')
      return route.fulfill(
        json({
          bookmarks: [],
          defaults: [{ name: 'APRS Europe', frequency: 144800000, modulation: 'FM', mode: 'aprs' }],
        }),
      );
    if (path === '/aprs/search') return route.fulfill(json({ results: [], count: 0 }));
    if (path === '/aprs/map') return route.fulfill(json({ type: 'FeatureCollection', features: [] }));
    if (path === '/stream-decode')
      return route.fulfill(json({ error: 'SDR device is busy — in use by capture' }, 409));
    if (path === '/stats') return route.fulfill(json({ statistics: {} }));
    return route.fulfill(json({}));
  });
  await page.route('https://tile.openstreetmap.org/**', (route) => route.fulfill({ status: 204 }));
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('radiomoni.apiKey', 'test-key'));
  await mockApi(page);
});

test('dashboard renders and escapes radio data', async ({ page }) => {
  let dialog = false;
  page.on('dialog', () => (dialog = true));
  await page.goto('/');
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('<img src=x onerror=alert(1)>')).toBeVisible();
  expect(dialog).toBe(false);
  await expect(page.getByText('RTLSDR frei')).toBeVisible();
});

test('navigation and APRS start shows server error', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'APRS' }).click();
  await expect(page).toHaveURL(/#\/aprs/);
  await page.getByRole('button', { name: /APRS Europe/ }).click();
  await expect(page.getByLabel('Frequenz (MHz)')).toHaveValue('144.8');
  await page.getByRole('button', { name: 'Streaming starten' }).click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
});

test('settings dialog stores the API key', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Einstellungen' }).click();
  await page.getByLabel('API-Key').fill('new-key');
  await page.getByRole('button', { name: 'Speichern & testen' }).click();
  expect(await page.evaluate(() => localStorage.getItem('radiomoni.apiKey'))).toBe('new-key');
});
