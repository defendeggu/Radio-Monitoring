<script lang="ts">
  import { Download, Play } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import MapView, { type MapPoint } from '../lib/components/MapView.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import { packetTime, time } from '../lib/format';
  import { live, sdr, toasts } from '../lib/stores.svelte';
  import type { Aircraft } from '../lib/types';

  type Kind = 'adsb' | 'ais' | 'ism';
  interface DecoderInfo {
    decoder: Kind;
    tool: string;
    installed: boolean;
    default_frequency: number;
  }
  type Doc = Record<string, unknown> & { '@timestamp'?: string; timestamp?: string };

  const labels: Record<Kind, string> = {
    adsb: 'ADS-B (Flugzeuge)',
    ais: 'AIS (Schiffe)',
    ism: 'ISM-Sensoren',
  };
  let kind = $state<Kind>('adsb');
  let info = $state<DecoderInfo[]>([]);
  let gain = $state<number | null>(null);
  let ppm = $state(0);
  let hours = $state(1);
  let ismFrequency = $state(433_920_000);
  let sessionId = $state<string | null>(null);
  let aircraft = $state<Aircraft[]>([]);
  let docs = $state<Doc[]>([]);
  let busy = $state(false);

  const current = $derived(info.find((d) => d.decoder === kind));

  $effect(() => {
    api
      .get<{ decoders: DecoderInfo[] }>('/decoders')
      .then((r) => (info = r.decoders))
      .catch(() => {});
  });

  async function loadLatest() {
    try {
      const r = await api.get<{ results: Doc[] }>(`/decoders/${kind}/latest`, { hours: 24, limit: 200 });
      docs = r.results;
      if (kind === 'adsb') aircraft = r.results as unknown as Aircraft[];
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void kind;
    sessionId = sdr.status?.active_sessions.find((s) => s.mode === kind)?.session_id ?? null;
    void loadLatest();
    return live.on(['adsb_snapshot', 'ais', 'ism'], (e) => {
      if (e.type === 'adsb_snapshot' && kind === 'adsb')
        aircraft = (e.data as { aircraft: Aircraft[] }).aircraft;
      if (e.type === kind && kind !== 'adsb') {
        const d = e.data as Doc;
        const key = kind === 'ais' ? 'mmsi' : 'sensor_id';
        docs = [d, ...docs.filter((x) => x[key] !== d[key])];
      }
    });
  });

  async function start() {
    busy = true;
    try {
      const r = await api.post<{ session_id: string }>('/decoders/start', {
        decoder: kind,
        gain,
        ppm,
        duration: Math.round(hours * 3600),
        frequency: kind === 'ism' ? ismFrequency : null,
      });
      sessionId = r.session_id;
      toasts.push(`${labels[kind]} gestartet`, 'success');
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  const points = $derived<MapPoint[]>(
    kind === 'adsb'
      ? aircraft
          .filter((a) => a.latitude != null && a.longitude != null)
          .map((a) => ({
            id: a.icao,
            lat: a.latitude!,
            lon: a.longitude!,
            label: a.flight || a.icao,
            detail: `${a.altitude_ft ?? '?'} ft · ${a.ground_speed_kt ?? '?'} kt`,
            color: '#a855f7',
          }))
      : kind === 'ais'
        ? docs
            .filter((d) => d.latitude != null && d.longitude != null)
            .map((d) => ({
              id: String(d.mmsi),
              lat: Number(d.latitude),
              lon: Number(d.longitude),
              label: String(d.shipname || d.mmsi),
              detail: `${d.speed ?? '?'} kn`,
              color: '#3b82f6',
            }))
        : [],
  );

  const ismColumns = ['model', 'id', 'channel', 'temperature_C', 'humidity', 'battery_ok'];
</script>

<PageHeader
  title="ADS-B · AIS · ISM"
  description="Flugzeuge (RTL-SDR oder HackRF), Schiffe und Funksensoren (RTL-SDR)"
>
  {#snippet actions()}
    <button
      class="btn-secondary"
      onclick={() => download(`/export/${kind}.csv?hours=24`, `${kind}.csv`).catch(toasts.error.bind(toasts))}
    >
      <Download size={14} /> CSV
    </button>
  {/snippet}
</PageHeader>

<div class="mb-4 flex gap-2" role="tablist">
  {#each ['adsb', 'ais', 'ism'] as k (k)}
    <button
      role="tab"
      aria-selected={kind === k}
      class="chip {kind === k ? '!border-accent-500 text-accent-600 dark:text-accent-400' : ''}"
      onclick={() => (kind = k as Kind)}
    >
      {labels[k as Kind]}
    </button>
  {/each}
</div>

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  {#if current && !current.installed}
    <p class="text-sm text-red-500">{current.tool} ist im Container nicht installiert.</p>
  {/if}
  <p class="text-sm text-slate-500">
    Werkzeug: <code>{current?.tool ?? '…'}</code> ·
    {#if kind === 'adsb'}RTL-SDR oder HackRF · 1090 MHz{:else if kind === 'ais'}benötigt einen RTL-SDR ·
      161.975 / 162.025 MHz{:else}benötigt einen RTL-SDR{/if}
  </p>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-4">
    {#if kind === 'ism'}<FrequencyField bind:value={ismFrequency} />{/if}
    <div>
      <label class="label" for="dgain">Verstärkung (dB)</label>
      <input
        id="dgain"
        class="input"
        type="number"
        min="0"
        max="50"
        bind:value={gain}
        placeholder="automatisch"
      />
    </div>
    <div>
      <label class="label" for="ppm">Frequenzkorrektur (ppm)</label>
      <input id="ppm" class="input" type="number" min="-200" max="200" bind:value={ppm} />
    </div>
    <div>
      <label class="label" for="dh">Laufzeit (Stunden)</label>
      <input id="dh" class="input" type="number" min="0.5" max="24" step="0.5" bind:value={hours} />
    </div>
  </div>
  <button class="btn-primary" type="submit" disabled={busy || sdr.busy || current?.installed === false}
    ><Play size={16} /> Starten</button
  >
</form>

{#if sessionId}<div class="mt-4"><SessionCard {sessionId} countLabel="Meldungen" /></div>{/if}

{#if kind !== 'ism'}
  <section class="card mt-6"><MapView {points} /></section>
{/if}

<section class="card mt-6 overflow-x-auto">
  {#if kind === 'adsb'}
    {#if aircraft.length}
      <table class="table">
        <thead
          ><tr
            ><th>ICAO</th><th>Flug</th><th>Höhe (ft)</th><th>Speed (kt)</th><th>Kurs</th><th>Squawk</th><th
              >RSSI</th
            ></tr
          ></thead
        >
        <tbody>
          {#each aircraft as a (a.icao)}
            <tr
              ><td class="font-mono">{a.icao}</td><td class="font-mono">{a.flight ?? ''}</td><td
                >{a.altitude_ft ?? ''}</td
              ><td>{a.ground_speed_kt ?? ''}</td><td>{a.track ?? ''}</td><td>{a.squawk ?? ''}</td><td
                >{a.rssi ?? ''}</td
              ></tr
            >
          {/each}
        </tbody>
      </table>
    {:else}<EmptyState text="Keine Flugzeuge empfangen." />{/if}
  {:else if kind === 'ais'}
    {#if docs.length}
      <table class="table">
        <thead
          ><tr
            ><th>Zeit</th><th>MMSI</th><th>Name</th><th>Rufzeichen</th><th>Speed</th><th>Kurs</th><th>Ziel</th
            ></tr
          ></thead
        >
        <tbody>
          {#each docs as d (d.mmsi)}
            <tr
              ><td class="text-xs">{time(packetTime(d))}</td><td class="font-mono">{d.mmsi}</td><td
                >{d.shipname ?? ''}</td
              ><td>{d.callsign ?? ''}</td><td>{d.speed ?? ''}</td><td>{d.course ?? ''}</td><td
                >{d.destination ?? ''}</td
              ></tr
            >
          {/each}
        </tbody>
      </table>
    {:else}<EmptyState text="Keine Schiffe empfangen." />{/if}
  {:else if docs.length}
    <table class="table">
      <thead
        ><tr
          ><th>Zeit</th>{#each ismColumns as c (c)}<th>{c}</th>{/each}</tr
        ></thead
      >
      <tbody>
        {#each docs as d (d.sensor_id)}
          <tr
            ><td class="text-xs">{time(packetTime(d))}</td>{#each ismColumns as c (c)}<td>{d[c] ?? ''}</td
              >{/each}</tr
          >
        {/each}
      </tbody>
    </table>
  {:else}<EmptyState text="Keine Sensoren empfangen." />{/if}
</section>
