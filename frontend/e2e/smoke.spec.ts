import { expect, test, type Page } from '@playwright/test';

// Minimal mocked API so the UI can be exercised without backend or SDR.
const cwStarts: Record<string, unknown>[] = [];
const skimmerStarts: Record<string, unknown>[] = [];
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
    if (path === '/rbn/status')
      return route.fulfill(
        json({ enabled: true, configured: true, connected: true, host: 'x', spots_per_minute: 12 }),
      );
    if (path === '/rbn/spots')
      return route.fulfill(
        json({
          spots: [
            {
              callsign: 'OH6BG',
              frequency: 14025500,
              khz: 14025.5,
              band: '20m',
              mode: 'CW',
              snr_db: 22,
              wpm: 27,
              type: 'CQ',
              skimmers: ['DK9IP'],
              skimmer_count: 3,
              best_skimmer: 'DK9IP',
              first_seen: 0,
              last_seen: 0,
              age_seconds: 42,
            },
          ],
        }),
      );
    if (path === '/cw/transmissions') return route.fulfill(json({ transmissions: [] }));
    if (path === '/contest/contests')
      return route.fulfill(
        json({
          active: 'cq-ww-cw',
          contests: [
            {
              id: 'cq-ww-cw',
              name: 'CQ WW DX CW',
              modes: ['CW', 'SSB'],
              bands: ['40m', '20m'],
              dupe: 'band',
              multipliers: [{ type: 'cq_zone', per: 'band' }],
              highlight: [],
              url: '',
              notes: '',
              assistance: 'A local skimmer counts as assistance.',
            },
          ],
        }),
      );
    if (path === '/contest/status')
      return route.fulfill(
        json({
          contest: {
            id: 'cq-ww-cw',
            name: 'CQ WW DX CW',
            modes: ['CW'],
            bands: [],
            dupe: 'band',
            multipliers: [],
            highlight: [],
            url: '',
            notes: '',
            assistance: '',
          },
          refdata: { entities: 346, scp_calls: 40000, most_wanted: 340, files: {} },
          worked: { qsos: 2, by_band: { '20m': 2 }, sources: ['import'] },
          n1mm: { enabled: false, listening: false, port: 12060, radios: [] },
          cluster: {
            enabled: true,
            listening: true,
            port: 7300,
            clients: [{ call: 'HB9XX', address: '192.168.1.5' }],
          },
        }),
      );
    if (path === '/skimmer/spots')
      return route.fulfill(
        json({
          spots: [
            {
              callsign: 'P5ABC',
              frequency: 14012300,
              khz: 14012.3,
              band: '20m',
              mode: 'CW',
              snr_db: 21,
              wpm: 28,
              type: 'CQ',
              skimmers: ['HB9XYZ-#'],
              skimmer_count: 1,
              first_seen: 0,
              last_seen: 0,
              age_seconds: 12,
              source: 'skimmer',
              country: 'DPR of Korea',
              continent: 'AS',
              cq_zone: 25,
              itu_zone: 44,
              wpx: 'P5',
              in_scp: true,
              portable: false,
              swiss: false,
              dupe: false,
              new_mults: [{ type: 'cq_zone', value: '25', label: 'CQ zone 25' }],
              rank: 1,
              rare: true,
              priority: 'high',
              in_contest: true,
            },
          ],
        }),
      );
    if (path === '/skimmer/start') {
      skimmerStarts.push(route.request().postDataJSON());
      return route.fulfill(json({ error: 'SDR device is busy — in use by cw' }, 409));
    }
    if (path === '/cw/start') {
      cwStarts.push(route.request().postDataJSON());
      return route.fulfill(json({ error: 'SDR device is busy — in use by capture' }, 409));
    }
    if (path === '/spectrum')
      return route.fulfill(json({ error: 'SDR device is busy — in use by vox' }, 409));
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
  await page.getByRole('link', { name: 'APRS', exact: true }).click();
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

test('switches the interface to English and remembers it', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Sprache wechseln' }).click();
  await expect(page.getByRole('heading', { name: 'Dashboard' })).toBeVisible();
  await expect(page.getByText('RTLSDR free')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Recordings' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');

  await page.reload();
  await page.getByRole('link', { name: 'Voice' }).click();
  await expect(page.getByRole('button', { name: 'Start recording' })).toBeVisible();
  await expect(page.getByLabel('Frequency (MHz)')).toBeVisible();
});

test('uses English for an English browser', async ({ browser }) => {
  const context = await browser.newContext({ locale: 'en-US' });
  const page = await context.newPage();
  await page.addInitScript(() => localStorage.setItem('radiomoni.apiKey', 'test-key'));
  await mockApi(page);
  await page.goto('/');
  await expect(page.getByRole('button', { name: 'Settings' })).toBeVisible();
  await context.close();
});

test('spectrum page: band shortcut and start error', async ({ page }) => {
  await page.goto('/#/spectrum');
  await expect(page.getByRole('heading', { name: 'Spektrum' })).toBeVisible();
  await page.getByRole('button', { name: '2 m', exact: true }).click();
  await expect(page.getByLabel('Mittenfrequenz (MHz)')).toHaveValue('145');
  await page.getByRole('button', { name: 'Wasserfall starten' }).click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
});

test('CW page: a click on an RBN spot starts the decoder on its frequency', async ({ page }) => {
  cwStarts.length = 0;
  await page.goto('/#/cw');
  await expect(page.getByRole('heading', { name: 'CW', exact: true })).toBeVisible();
  await expect(page.getByText('OH6BG')).toBeVisible();
  await page.getByText('OH6BG').click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
  expect(cwStarts.at(-1)?.frequency).toBe(14025500);
  await expect(page.getByLabel('Frequenz (MHz)')).toHaveValue('14.0255');
});

test('contest page: classified spots and skimmer start', async ({ page }) => {
  skimmerStarts.length = 0;
  await page.goto('/#/contest');
  await expect(page.getByRole('heading', { name: 'Contest-Skimmer' })).toBeVisible();
  await expect(page.getByText('P5ABC')).toBeVisible();
  await expect(page.getByText('MULT', { exact: true })).toBeVisible();
  await expect(page.getByText('RARE #1')).toBeVisible();
  await expect(page.getByText('A local skimmer counts as assistance.')).toBeVisible();
  await expect(page.getByText('HB9XX (192.168.1.5)')).toBeVisible();
  await page.getByRole('button', { name: '40 m', exact: true }).click();
  await page.getByRole('button', { name: 'Skimmer starten' }).click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
  expect(skimmerStarts.at(-1)).toMatchObject({
    band: '40m',
    mode: 'CW',
    contest: 'cq-ww-cw',
    max_decoders: 24,
  });
});

test('contest page: SSB start sends mode and language', async ({ page }) => {
  skimmerStarts.length = 0;
  await page.goto('/#/contest');
  await page.getByRole('button', { name: 'SSB', exact: true }).click();
  await expect(page.getByText('SSB ist experimentell')).toBeVisible();
  await page.getByLabel('Sprache (Whisper)').selectOption('de');
  await page.getByRole('button', { name: 'Skimmer starten' }).click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
  expect(skimmerStarts.at(-1)).toMatchObject({ mode: 'SSB', language: 'de', band: '20m', max_decoders: 16 });
});

test('two SDRs: the CW start runs on the chosen device', async ({ page }) => {
  cwStarts.length = 0;
  const device = (id: string, label: string, busy = false) => ({
    id,
    type: id.split(':')[0],
    label,
    busy,
    preemptible: false,
    holder: busy ? { owner: 'stream:x', kind: 'aprs', since: '', details: {} } : null,
    sessions: [],
  });
  await page.route('**/api/sdr/status', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        busy: true,
        preemptible: false,
        holder: { owner: 'stream:x', kind: 'aprs', since: '', details: {} },
        active_sessions: [],
        default_device: 'hackrf:abc',
        devices: [device('hackrf:abc', 'HackRF One', true), device('rtlsdr:0', 'RTL-SDR')],
      }),
    }),
  );
  await page.goto('/#/cw');
  await expect(page.getByText('2 SDRs, 1 belegt')).toBeVisible();
  const start = page.getByRole('button', { name: 'CW-Decoder starten' });
  await expect(start).toBeDisabled(); // the default SDR (HackRF) is busy
  await page.getByLabel('SDR', { exact: true }).selectOption('rtlsdr:0');
  await expect(start).toBeEnabled();
  await start.click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
  expect(cwStarts.at(-1)).toMatchObject({ device_id: 'rtlsdr:0', device_type: 'auto' });
});

test('OnAir page: mode sets the frequency, start sends the mode, messages are escaped', async ({ page }) => {
  const starts: Record<string, unknown>[] = [];
  await page.route('**/api/onair/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, '');
    const json = (body: unknown, status = 200) => ({
      status,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
    if (path === '/onair/status')
      return route.fulfill(
        json({
          enabled: true,
          reachable: true,
          version: '4.6.0',
          sessions: [],
          attribution: 'Based on OnAir by Kristijonas Adomaitis - https://on-air.dev',
          contributors: 'https://github.com/adswill/OnAir/blob/main/CONTRIBUTORS.md',
        }),
      );
    if (path === '/onair/modes')
      return route.fulfill(
        json({
          modes: [
            {
              id: 'acars',
              family: 18,
              sub: null,
              name: 'ACARS',
              default_frequency: 131500000,
              group: 'aviation',
            },
            {
              id: 'sonde',
              family: 15,
              sub: null,
              name: 'Radiosonde',
              default_frequency: 403000000,
              group: 'sondes',
            },
          ],
        }),
      );
    if (path === '/onair/search')
      return route.fulfill(
        json({
          count: 1,
          results: [
            {
              uuid: 'u1',
              '@timestamp': '2026-11-25T10:27:35Z',
              event_type: 'acars.message',
              family: 'acars',
              mode: 'ACARS',
              ident: 'MU0218',
              text: '<img src=x onerror=alert(1)> POS',
              fields: { flight: 'MU0218' },
              frequency: 131725000,
            },
          ],
        }),
      );
    if (path === '/onair/map') return route.fulfill(json({ type: 'FeatureCollection', features: [] }));
    if (path === '/onair/start') {
      starts.push(route.request().postDataJSON());
      return route.fulfill(json({ error: 'SDR device is busy — in use by aprs' }, 409));
    }
    return route.fulfill(json({}));
  });
  let dialog = false;
  page.on('dialog', () => (dialog = true));
  await page.goto('/#/onair');
  await expect(page.getByRole('heading', { name: 'OnAir' })).toBeVisible();
  await expect(page.getByText('<img src=x onerror=alert(1)> POS')).toBeVisible();
  expect(dialog).toBe(false);
  await page.getByLabel('Betriebsart').selectOption('sonde');
  await expect(page.getByLabel('Frequenz (MHz)')).toHaveValue('403');
  await page.getByRole('button', { name: 'Starten' }).click();
  await expect(page.getByText('SDR device is busy')).toBeVisible();
  expect(starts.at(-1)).toMatchObject({ mode: 'sonde', frequency: 403000000, gain: null, duration: 3600 });
  await expect(page.getByText('Based on OnAir by Kristijonas Adomaitis')).toBeVisible();
});

test('APRS: reception column and filter (over the air / internet)', async ({ page }) => {
  const searches: string[] = [];
  await page.route('**/api/aprs/**', async (route) => {
    const url = new URL(route.request().url());
    const json = (body: unknown) => ({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
    if (url.pathname.endsWith('/aprs/map'))
      return route.fulfill(json({ type: 'FeatureCollection', features: [] }));
    searches.push(url.searchParams.get('reception') ?? '');
    const all = [
      {
        uuid: 'a',
        source_callsign: 'N0RF-9',
        packet_type: 'position',
        message_text: 'funk',
        reception: 'rf',
      },
      {
        uuid: 'b',
        source_callsign: 'N0NET-9',
        packet_type: 'position',
        message_text: 'netz',
        reception: 'internet',
        reception_source: 'aprs_is',
        igate: 'N0GATE-10',
        gemeinde: 'Luzern',
        kanton: 'LU',
      },
      { uuid: 'c', source_callsign: 'N0OLD', packet_type: 'status', message_text: 'alt' },
    ];
    const r = url.searchParams.get('reception');
    const results = all.filter((p) => !r || (p.reception === 'internet' ? 'internet' : 'rf') === r);
    return route.fulfill(json({ results, count: results.length }));
  });
  await page.goto('/#/aprs');
  const rows = page.locator('table tbody tr');
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(1)).toContainText('Internet');
  await expect(rows.nth(1)).toContainText('APRS-IS');
  await expect(rows.nth(1)).toContainText('Luzern (LU)');
  await expect(rows.nth(2)).toContainText('Funk'); // stored before 5.8.0: over the air
  await page.getByRole('button', { name: 'Internet', exact: true }).click();
  await expect(rows).toHaveCount(1);
  expect(searches.at(-1)).toBe('internet');
  await page.getByRole('button', { name: 'Funk', exact: true }).click();
  await expect(rows).toHaveCount(2);
});

test('APRS statistics page: tiles, trips, link', async ({ page }) => {
  await page.route('**/api/aprsstats/**', async (route) => {
    const path = new URL(route.request().url()).pathname.replace(/^\/api/, '');
    const json = (body: unknown) => ({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(body),
    });
    const s = (km: number) => ({
      km,
      points: 30,
      devices: 2,
      days: 1,
      by_source: { rf: 12, aprs_is: 18 },
      gemeinden: 7,
      gemeinden_total: 2110,
      kantone: 2,
      kantone_total: 26,
      last: null,
    });
    if (path === '/aprsstats/status')
      return route.fulfill(
        json({
          enabled: true,
          reachable: true,
          version: '0.6.0',
          feed_rf: true,
          collector: { state: 'connected' },
        }),
      );
    if (path === '/aprsstats/summary')
      return route.fulfill(json({ today: s(5), week: s(123.4), all: s(999) }));
    if (path === '/aprsstats/trips')
      return route.fulfill(
        json({
          trips: [
            {
              uuid: 't1',
              callsign: 'N0CALL-9',
              start: '2026-11-25T08:00:00Z',
              end: '2026-11-25T08:30:00Z',
              km: 21.5,
              seconds: 1800,
              avg_speed: 43,
              from: 'Zuhause',
              to: 'Luzern (LU)',
              round_trip: false,
            },
          ],
        }),
      );
    return route.fulfill(json({}));
  });
  await page.goto('/#/aprs-stats');
  await expect(page.getByRole('heading', { name: 'APRS-Statistik' })).toBeVisible();
  await expect(page.getByText('123.4').or(page.getByText('123,4'))).toBeVisible();
  await expect(page.getByText('12 · 18')).toBeVisible();
  await expect(page.getByText('Zuhause → Luzern (LU)')).toBeVisible();
  await page.getByRole('tab', { name: 'Heute' }).click();
  await expect(page.getByText('5', { exact: true })).toBeVisible();
});
