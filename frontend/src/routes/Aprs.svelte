<script lang="ts">
  import { Download, Search } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import AprsSymbol from '../lib/components/AprsSymbol.svelte';
  import DecoderControls from '../lib/components/DecoderControls.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import MapView, { type MapPoint } from '../lib/components/MapView.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import ReceptionBadge from '../lib/components/ReceptionBadge.svelte';
  import { packetTime, time } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { live, toasts } from '../lib/stores.svelte';
  import type { AprsPacket } from '../lib/types';

  interface Feature {
    geometry: { coordinates: [number, number] };
    properties: {
      callsign: string;
      message?: string;
      timestamp?: string;
      type?: string;
      symbol_id?: string | null;
      symbol_name?: string | null;
      reception?: string;
    };
  }

  type Reception = '' | 'rf' | 'internet';
  const RECEPTION_KEY = 'radiomoni.aprs.reception';
  const RECEPTIONS: [Reception, () => string][] = [
    ['', () => t('Alle')],
    ['rf', () => t('Funk')],
    ['internet', () => t('Internet')],
  ];

  // packet types of radiomoni/aprs_parse.py
  const TYPES: Record<string, () => string> = {
    position: () => t('Position'),
    object: () => t('Objekt'),
    item: () => t('Item'),
    message: () => t('Nachricht'),
    bulletin: () => t('Bulletin'),
    ack: () => t('Bestätigung'),
    rej: () => t('Abgelehnt'),
    status: () => t('Status'),
    weather: () => t('Wetter'),
    telemetry: () => t('Telemetrie'),
    'telemetry-meta': () => t('Telemetrie-Setup'),
    capabilities: () => t('Fähigkeiten'),
    query: () => t('Abfrage'),
    nmea: () => t('NMEA'),
    unknown: () => t('unbekannt'),
  };
  const typeLabel = (p: AprsPacket) => {
    const type = p.packet_type ?? p.aprs_type ?? 'unknown';
    return TYPES[type]?.() ?? type;
  };
  const symbolUrl = (id?: string | null) =>
    id && /^[a-z0-9-]+$/.test(id) ? `/aprs-symbols/${id}.png` : undefined;

  let packets = $state<AprsPacket[]>([]);
  let features = $state<Feature[]>([]);
  let callsign = $state('');
  let hours = $state(24);
  let reception = $state<Reception>(readReception());

  function readReception(): Reception {
    try {
      const v = localStorage.getItem(RECEPTION_KEY);
      return v === 'rf' || v === 'internet' ? v : '';
    } catch {
      return '';
    }
  }

  function setReception(v: Reception) {
    reception = v;
    try {
      if (v) localStorage.setItem(RECEPTION_KEY, v);
      else localStorage.removeItem(RECEPTION_KEY);
    } catch {
      /* storage unavailable */
    }
  }

  const matchesReception = (r?: string | null) =>
    !reception || (r === 'internet' ? 'internet' : 'rf') === reception;

  async function load() {
    try {
      const [search, map] = await Promise.all([
        api.get<{ results: AprsPacket[] }>('/aprs/search', {
          hours,
          limit: 200,
          callsign: callsign || undefined,
          reception: reception || undefined,
        }),
        api.get<{ features: Feature[] }>('/aprs/map', { hours, reception: reception || undefined }),
      ]);
      packets = search.results;
      features = map.features;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void hours;
    void reception;
    void load();
    return live.on(['aprs'], (e) => {
      const p = e.data as unknown as AprsPacket;
      if (!matchesReception(p.reception)) return;
      if (!callsign || p.source_callsign?.toUpperCase() === callsign.toUpperCase())
        packets = [p, ...packets].slice(0, 500);
      const station = p.object_name || p.source_callsign;
      if (p.object_killed) {
        features = features.filter((f) => f.properties.callsign !== station);
      } else if (p.latitude != null && p.longitude != null) {
        features = [
          {
            geometry: { coordinates: [p.longitude, p.latitude] },
            properties: {
              callsign: station,
              message: p.message_text ?? '',
              timestamp: packetTime(p),
              symbol_id: p.symbol_id,
              symbol_name: p.symbol,
              reception: p.reception ?? 'rf',
            },
          },
          ...features.filter((f) => f.properties.callsign !== station),
        ];
      }
    });
  });

  const points = $derived<MapPoint[]>(
    features.map((f) => ({
      id: f.properties.callsign,
      lat: f.geometry.coordinates[1],
      lon: f.geometry.coordinates[0],
      label: f.properties.callsign,
      detail: `${f.properties.message ?? ''} (${time(f.properties.timestamp)})`,
      icon: symbolUrl(f.properties.symbol_id),
      internet: f.properties.reception === 'internet',
    })),
  );

  function exportAs(ext: 'csv' | 'geojson' | 'kml') {
    download(`/export/aprs.${ext}?hours=${hours}`, `aprs.${ext}`).catch(toasts.error.bind(toasts));
  }
</script>

<PageHeader
  title="APRS"
  description={t('Automatic Packet Reporting System — Positionen, Nachrichten, Wetter')}
>
  {#snippet actions()}
    <button class="btn-secondary" onclick={() => exportAs('csv')}><Download size={14} /> CSV</button>
    <button class="btn-secondary" onclick={() => exportAs('geojson')}>GeoJSON</button>
    <button class="btn-secondary" onclick={() => exportAs('kml')}>KML</button>
  {/snippet}
</PageHeader>

<DecoderControls
  mode="aprs"
  defaultFrequency={144_800_000}
  maxCapture={300}
  oncapture={(r) => {
    packets = [...(r.aprs?.packets ?? []), ...packets];
    void load();
  }}
/>

<section class="card mt-6">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-sm font-semibold">{t('Stationen ({n})', { n: points.length })}</h2>
    <div class="flex flex-wrap items-center gap-2">
      <div class="flex gap-1" role="group" aria-label={t('Empfang')}>
        {#each RECEPTIONS as [value, label] (value)}
          <button
            type="button"
            class="chip {reception === value
              ? '!border-accent-500 text-accent-600 dark:text-accent-400'
              : ''}"
            aria-pressed={reception === value}
            onclick={() => setReception(value)}>{label()}</button
          >
        {/each}
      </div>
      <select class="input !w-auto" bind:value={hours} aria-label={t('Zeitraum')}>
        <option value={1}>1 h</option><option value={24}>24 h</option><option value={168}
          >{t('{n} Tage', { n: 7 })}</option
        >
      </select>
    </div>
  </div>
  <MapView {points} />
  <p class="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
    <span class="flex items-center gap-1"><ReceptionBadge reception="rf" /> {t('eigener Empfänger')}</span>
    <span class="flex items-center gap-1"
      ><ReceptionBadge reception="internet" />
      {t('APRS-IS oder Import über aprs-stats; auf der Karte gestrichelt umrandet')}</span
    >
  </p>
</section>

<section class="card mt-6">
  <form
    class="mb-3 flex flex-wrap items-end gap-3"
    onsubmit={(e) => {
      e.preventDefault();
      void load();
    }}
  >
    <div>
      <label class="label" for="call">{t('Rufzeichen')}</label>
      <input
        id="call"
        class="input font-mono uppercase"
        bind:value={callsign}
        placeholder="HB9XYZ-7"
        maxlength="12"
      />
    </div>
    <button class="btn-secondary" type="submit"><Search size={14} /> {t('Suchen')}</button>
  </form>
  {#if packets.length}
    <div class="overflow-x-auto">
      <table class="table">
        <thead
          ><tr
            ><th>{t('Zeit')}</th><th><span class="sr-only">{t('Symbol')}</span></th><th>{t('Rufzeichen')}</th
            ><th>{t('Empfang')}</th><th>{t('Typ')}</th><th>{t('Position')}</th><th>Locator</th><th
              >{t('Nachricht')}</th
            ></tr
          ></thead
        >
        <tbody>
          {#each packets as p, i (p.uuid ?? i)}
            <tr>
              <td class="text-xs whitespace-nowrap">{time(packetTime(p))}</td>
              <td class="w-10 min-w-10"><AprsSymbol id={p.symbol_id} name={p.symbol} /></td>
              <td class="font-mono font-medium whitespace-nowrap">{p.source_callsign}</td>
              <td
                ><ReceptionBadge
                  reception={p.reception}
                  source={p.reception_source}
                  igate={p.igate}
                  alsoRf={p.also_rf}
                /></td
              >
              <td class="whitespace-nowrap">{typeLabel(p)}</td>
              <td class="font-mono text-xs"
                >{p.latitude != null && p.longitude != null
                  ? `${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}`
                  : '—'}{#if p.gemeinde}<div class="font-sans text-slate-500">
                    {p.gemeinde}{p.kanton && !p.gemeinde.endsWith(`(${p.kanton})`) ? ` (${p.kanton})` : ''}
                  </div>{/if}</td
              >
              <td class="font-mono text-xs">{p.maidenhead ?? '—'}</td>
              <td class="break-words">
                {p.message_text ?? ''}
                {#if p.raw_packet}
                  <details class="mt-1">
                    <summary class="cursor-pointer text-xs text-slate-500 select-none"
                      >{t('Rohdaten')}</summary
                    >
                    <code class="block font-mono text-xs break-all">{p.raw_packet}</code>
                  </details>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <EmptyState text={t('Noch keine APRS-Pakete — starte oben eine Aufnahme oder einen Stream.')} />
  {/if}
</section>
