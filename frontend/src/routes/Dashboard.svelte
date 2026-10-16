<script lang="ts">
  import { RefreshCw } from '@lucide/svelte';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import TimelineChart from '../lib/components/TimelineChart.svelte';
  import { mhz, packetTime, relative, time } from '../lib/format';
  import { live, sdr, toasts } from '../lib/stores.svelte';
  import type { AlertEvent, DashboardStats } from '../lib/types';

  let hours = $state(24);
  let stats = $state<DashboardStats | null>(null);
  let alerts = $state<AlertEvent[]>([]);
  let loading = $state(false);

  const series = [
    { key: 'captures', label: 'Captures', color: '#06b6d4' },
    { key: 'aprs', label: 'APRS', color: '#22c55e' },
    { key: 'pocsag', label: 'POCSAG', color: '#f59e0b' },
    { key: 'adsb', label: 'ADS-B', color: '#a855f7' },
    { key: 'ais', label: 'AIS', color: '#3b82f6' },
    { key: 'ism', label: 'ISM', color: '#ec4899' },
  ];

  async function load() {
    loading = true;
    try {
      [stats, alerts] = await Promise.all([
        api.get<DashboardStats & { status: string }>('/dashboard/stats', { hours }),
        api.get<{ alerts: AlertEvent[] }>('/alerts/recent', { limit: 5 }).then((r) => r.alerts),
      ]);
    } catch (e) {
      toasts.error(e);
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void hours;
    void load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  });

  const feed = $derived(
    live.recent
      .filter((e) => ['aprs', 'pocsag', 'adsb', 'ais', 'ism', 'vox', 'alert'].includes(e.type))
      .slice(0, 12),
  );

  function describe(type: string, d: Record<string, unknown>): string {
    switch (type) {
      case 'aprs':
        return `${d.source_callsign ?? '?'} — ${String(d.message_text ?? '').slice(0, 80)}`;
      case 'pocsag':
        return `RIC ${d.address} — ${String(d.message_text ?? 'Tone only').slice(0, 80)}`;
      case 'adsb':
        return `${d.flight ?? d.icao} ${d.altitude_ft ? `${d.altitude_ft} ft` : ''}`;
      case 'ais':
        return `${d.shipname ?? d.mmsi}`;
      case 'ism':
        return `${d.model} ${d.temperature_C !== undefined ? `${d.temperature_C} °C` : ''}`;
      case 'vox':
        return `${d.state} ${d.text ?? d.audio_file ?? ''}`;
      case 'alert':
        return String(d.summary ?? '');
      default:
        return '';
    }
  }
</script>

<PageHeader title="Dashboard" description="Aktivität der letzten Stunden über alle Betriebsarten">
  {#snippet actions()}
    <select class="input !w-auto" bind:value={hours} aria-label="Zeitraum">
      <option value={6}>6 Stunden</option>
      <option value={24}>24 Stunden</option>
      <option value={72}>3 Tage</option>
      <option value={168}>7 Tage</option>
    </select>
    <button class="btn-secondary" onclick={load} disabled={loading} aria-label="Aktualisieren"
      ><RefreshCw size={16} /></button
    >
  {/snippet}
</PageHeader>

<div class="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
  <StatCard label="Captures" value={stats?.counts.captures ?? '–'} />
  <StatCard label="APRS" value={stats?.counts.aprs ?? '–'} />
  <StatCard label="POCSAG" value={stats?.counts.pocsag ?? '–'} />
  <StatCard label="ADS-B" value={stats?.counts.adsb ?? '–'} />
  <StatCard label="AIS" value={stats?.counts.ais ?? '–'} />
  <StatCard label="Alarme" value={stats?.counts.alerts ?? '–'} />
</div>

<div class="grid gap-6 lg:grid-cols-3">
  <section class="card lg:col-span-2">
    <h2 class="mb-3 text-sm font-semibold">Aktivität pro Stunde</h2>
    {#if stats?.timeline.length}
      <TimelineChart rows={stats.timeline} {series} />
    {:else}
      <EmptyState text="Noch keine Daten im gewählten Zeitraum" />
    {/if}
  </section>

  <section class="card">
    <h2 class="mb-3 text-sm font-semibold">SDR</h2>
    {#if sdr.status?.busy}
      <p class="text-sm">
        Belegt durch <strong>{sdr.status.holder?.kind}</strong>
        seit {relative(sdr.status.holder?.since)}
      </p>
      {#each sdr.status.active_sessions as s (s.session_id)}
        <p class="mt-2 text-sm text-slate-500">
          {s.mode.toUpperCase()} · {mhz(s.frequency)} · {s.packet_count} Pakete
        </p>
      {/each}
    {:else if sdr.detect?.detected}
      <p class="text-sm">{sdr.detect.type.toUpperCase()} ist frei.</p>
      <p class="mt-1 text-xs text-slate-500">
        {sdr.detect.frequency_range?.min_mhz}–{sdr.detect.frequency_range?.max_mhz} MHz
      </p>
    {:else}
      <p class="text-sm text-slate-500">{sdr.detect?.message ?? 'Kein SDR erkannt.'}</p>
    {/if}

    <h2 class="mt-6 mb-2 text-sm font-semibold">Letzte Alarme</h2>
    {#if alerts.length}
      <ul class="space-y-2 text-sm">
        {#each alerts as a (a.uuid)}
          <li><span class="text-xs text-slate-500">{time(a.timestamp)}</span> {a.summary}</li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm text-slate-500">Keine. <a class="underline" href="#/alerts">Regeln anlegen</a></p>
    {/if}
  </section>

  <section class="card lg:col-span-2">
    <h2 class="mb-3 text-sm font-semibold">Neueste APRS-Pakete</h2>
    {#if stats?.latest.aprs.length}
      <table class="table">
        <thead><tr><th>Zeit</th><th>Rufzeichen</th><th>Nachricht</th></tr></thead>
        <tbody>
          {#each stats.latest.aprs as p, i (p.uuid ?? i)}
            <tr
              ><td class="text-xs whitespace-nowrap">{time(packetTime(p))}</td><td class="font-mono"
                >{p.source_callsign}</td
              ><td class="break-all">{p.message_text}</td></tr
            >
          {/each}
        </tbody>
      </table>
    {:else}
      <EmptyState text="Keine APRS-Pakete" />
    {/if}
  </section>

  <section class="card">
    <h2 class="mb-3 flex items-center justify-between text-sm font-semibold">
      Live <span class="text-xs font-normal text-slate-500"
        >{live.state === 'open' ? 'verbunden' : live.state}</span
      >
    </h2>
    {#if feed.length}
      <ul class="space-y-2 text-sm">
        {#each feed as e, i (e.time + i)}
          <li class="break-words">
            <span
              class="mr-1 rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] uppercase dark:bg-slate-800"
              >{e.type}</span
            >
            {describe(e.type, e.data)}
          </li>
        {/each}
      </ul>
    {:else}
      <p class="text-sm text-slate-500">Wartet auf Ereignisse…</p>
    {/if}
  </section>
</div>
