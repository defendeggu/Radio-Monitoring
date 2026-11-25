<script lang="ts">
  import { ExternalLink, RefreshCw } from '@lucide/svelte';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import StatCard from '../lib/components/StatCard.svelte';
  import { dateTime, duration, relative } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { toasts } from '../lib/stores.svelte';
  import type { AprsStatsStatus, AprsStatsSummary, AprsTrip } from '../lib/types';

  type Period = 'today' | 'week' | 'all';
  const PERIODS: [Period, () => string][] = [
    ['today', () => t('Heute')],
    ['week', () => t('7 Tage')],
    ['all', () => t('Alles')],
  ];

  let status = $state<AprsStatsStatus | null>(null);
  let summary = $state<Record<Period, AprsStatsSummary> | null>(null);
  let trips = $state<AprsTrip[]>([]);
  let period = $state<Period>('week');
  let syncing = $state(false);

  const nf = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 });
  const num = (v: number | null | undefined) => (v == null ? '–' : nf.format(v));
  const current = $derived(summary?.[period] ?? null);
  const rf = $derived(current?.by_source?.rf ?? 0);
  const internet = $derived(current ? (current.points ?? 0) - rf : 0);

  async function load() {
    try {
      status = await api.get<AprsStatsStatus>('/aprsstats/status');
    } catch (e) {
      toasts.error(e);
      return;
    }
    if (!status.enabled || !status.reachable) return;
    try {
      const [s, tr] = await Promise.all([
        api.get<Record<Period, AprsStatsSummary>>('/aprsstats/summary'),
        api.get<{ trips: AprsTrip[] }>('/aprsstats/trips', { days: 7, limit: 50 }),
      ]);
      summary = s;
      trips = tr.trips;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void load();
    const timer = setInterval(load, 60_000);
    return () => clearInterval(timer);
  });

  async function syncNow() {
    syncing = true;
    try {
      await api.post('/aprsstats/sync');
      toasts.push(t('Abgleich mit aprs-stats fertig'), 'success');
      void load();
    } catch (e) {
      toasts.error(e);
    } finally {
      syncing = false;
    }
  }

  async function openAprsStats() {
    try {
      const r = await api.get<{ url: string | null; port: number }>('/aprsstats/link');
      window.open(
        r.url || `${location.protocol}//${location.hostname}:${r.port}`,
        '_blank',
        'noopener,noreferrer',
      );
    } catch (e) {
      toasts.error(e);
    }
  }
</script>

<PageHeader
  title={t('APRS-Statistik')}
  description={t(
    'Fahrten, Orte und besuchte Gemeinden aus aprs-stats — über Funk und über Internet empfangen',
  )}
>
  {#snippet actions()}
    <button class="btn-secondary" onclick={syncNow} disabled={syncing || !status?.reachable}>
      <RefreshCw size={14} />
      {t('Jetzt abgleichen')}
    </button>
    <button class="btn-secondary" onclick={openAprsStats} disabled={!status?.reachable}>
      <ExternalLink size={14} />
      {t('aprs-stats öffnen')}
    </button>
  {/snippet}
</PageHeader>

{#if status && !status.enabled}
  <div class="card text-sm">
    {t(
      'aprs-stats ist nicht eingerichtet: Profil „aprsstats“ in COMPOSE_PROFILES und APRSSTATS_URL setzen (docs/aprs-stats.md).',
    )}
  </div>
{:else if status && !status.reachable}
  <div class="card text-sm text-red-500">
    {t('aprs-stats nicht erreichbar: {error}', { error: status.error ?? '?' })}
  </div>
{:else if status}
  <div class="mb-4 flex flex-wrap gap-2" role="tablist">
    {#each PERIODS as [value, label] (value)}
      <button
        role="tab"
        aria-selected={period === value}
        class="chip {period === value ? '!border-accent-500 text-accent-600 dark:text-accent-400' : ''}"
        onclick={() => (period = value)}>{label()}</button
      >
    {/each}
  </div>

  {#if current}
    <div class="grid grid-cols-2 gap-4 lg:grid-cols-5">
      <StatCard label={t('Kilometer')} value={num(current.km)} />
      <StatCard
        label={t('Positionen')}
        value={num(current.points)}
        hint={t('{n} Geräte', { n: current.devices ?? 0 })}
      />
      <StatCard label={t('über Funk · Internet')} value={`${num(rf)} · ${num(internet)}`} />
      <StatCard
        label={t('Gemeinden')}
        value={num(current.gemeinden)}
        hint={current.gemeinden_total ? t('von {n}', { n: current.gemeinden_total }) : undefined}
      />
      <StatCard
        label={t('Kantone')}
        value={num(current.kantone)}
        hint={current.kantone_total ? t('von {n}', { n: current.kantone_total }) : undefined}
      />
    </div>
  {/if}

  <section class="card mt-6 overflow-x-auto">
    <h2 class="mb-3 text-sm font-semibold">{t('Fahrten der letzten 7 Tage')}</h2>
    {#if trips.length}
      <table class="table">
        <thead
          ><tr
            ><th>{t('Start')}</th><th>{t('Gerät')}</th><th>{t('Von → Nach')}</th><th class="text-right">km</th
            ><th class="text-right">{t('Dauer')}</th><th class="text-right">{t('Ø km/h')}</th></tr
          ></thead
        >
        <tbody>
          {#each trips as trip (trip.uuid)}
            <tr>
              <td class="text-xs whitespace-nowrap">{dateTime(trip.start)}</td>
              <td class="font-mono whitespace-nowrap">{trip.callsign}</td>
              <td>
                {#if trip.round_trip}{trip.from} · {t('Rundfahrt')}{:else}{trip.from ?? '?'} → {trip.to ??
                    '?'}{/if}
              </td>
              <td class="text-right font-mono">{num(trip.km)}</td>
              <td class="text-right font-mono whitespace-nowrap">{duration(trip.seconds)}</td>
              <td class="text-right font-mono">{num(trip.avg_speed)}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {:else}<EmptyState text={t('Keine Fahrten in den letzten 7 Tagen.')} />{/if}
  </section>

  <section class="card mt-6 text-sm">
    <h2 class="mb-2 font-semibold">aprs-stats {status.version ?? ''}</h2>
    <dl class="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-[max-content_1fr]">
      <dt class="text-slate-500">{t('APRS-IS-Verbindung')}</dt>
      <dd>{status.collector?.state ?? '–'} {status.collector?.login ? `· ${status.collector.login}` : ''}</dd>
      <dt class="text-slate-500">{t('Letzter Abgleich')}</dt>
      <dd>
        {status.sync?.time ? relative(status.sync.time) : '–'}
        {#if status.sync?.error}<span class="text-red-500"> · {status.sync.error}</span>{/if}
      </dd>
      <dt class="text-slate-500">{t('Funk-Pakete an aprs-stats')}</dt>
      <dd>
        {status.feed_rf
          ? t('{sent} gesendet, {kept} übernommen', {
              sent: status.feed?.sent ?? 0,
              kept: status.feed?.kept ?? 0,
            })
          : t('aus')}
      </dd>
    </dl>
    <p class="mt-3 text-xs text-slate-500">
      {t(
        'Karte, Heatmap, Gemeinden, Orte benennen, Import von aprs.fi und Baken gibt es auf der Seite von aprs-stats.',
      )}
    </p>
  </section>
{/if}
