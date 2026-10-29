<script lang="ts">
  import { Play, Square } from '@lucide/svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Progress from '../lib/components/Progress.svelte';
  import { duration as fmt, mhz } from '../lib/format';
  import { i18n, t } from '../lib/i18n.svelte';
  import { sdr, toasts } from '../lib/stores.svelte';

  interface RepeaterInfo {
    uuid: string;
    callsign: string;
    output_frequency: number;
    band?: string;
    canton?: string;
    location_name?: string | null;
    ctcss_tone?: number | null;
  }
  interface Result {
    repeater_id?: string;
    callsign: string;
    frequency: number;
    rounds?: number;
    active_rounds?: number;
    errors?: number;
    transmission_count?: number;
    activity_percentage?: number;
    average_signal_strength?: number | null;
    error?: string | null;
  }
  interface ProgressResponse {
    status: 'in_progress' | 'completed' | 'stopped' | 'failed';
    progress: {
      current_repeater: number;
      total_repeaters: number;
      current_callsign: string | null;
      current_round?: number;
      rounds_completed?: number;
      duration_per_repeater?: number;
      total_duration?: number | null;
      until_stopped?: boolean;
      elapsed_seconds: number;
      estimated_remaining_seconds: number | null;
    };
    results: Result[];
    error?: string;
  }
  interface Summary {
    callsign: string;
    avg_activity_pct: number;
    total_transmissions: number;
    avg_signal_db: number | null;
    frequency_mhz: number;
    band: string;
    canton: string;
  }

  const CANTONS: Record<string, string> = {
    AG: 'Aargau',
    AI: 'Appenzell I.Rh.',
    AR: 'Appenzell A.Rh.',
    BE: 'Bern',
    BL: 'Basel-Landschaft',
    BS: 'Basel-Stadt',
    FL: 'Liechtenstein',
    FR: 'Freiburg',
    GE: 'Genf',
    GL: 'Glarus',
    GR: 'Graubünden',
    JU: 'Jura',
    LU: 'Luzern',
    NE: 'Neuenburg',
    NW: 'Nidwalden',
    OW: 'Obwalden',
    SG: 'St. Gallen',
    SH: 'Schaffhausen',
    SO: 'Solothurn',
    SZ: 'Schwyz',
    TG: 'Thurgau',
    TI: 'Tessin',
    UR: 'Uri',
    VD: 'Waadt',
    VS: 'Wallis',
    ZG: 'Zug',
    ZH: 'Zürich',
  };
  /** English names where they differ from the German ones */
  const CANTONS_EN: Record<string, string> = {
    AI: 'Appenzell Inner Rhodes',
    AR: 'Appenzell Outer Rhodes',
    FR: 'Fribourg',
    GE: 'Geneva',
    GR: 'Grisons',
    LU: 'Lucerne',
    NE: 'Neuchâtel',
    TI: 'Ticino',
    VD: 'Vaud',
    VS: 'Valais',
    ZH: 'Zurich',
  };
  const cantonName = (code: string) =>
    (i18n.locale === 'en' ? CANTONS_EN[code] : undefined) ?? CANTONS[code] ?? code;
  const DEFAULT_CANTON = 'LU';
  const ALL = '*';
  /** total scan time in seconds; 0 = one round, -1 = until stopped */
  const TOTALS: { value: number; label: () => string }[] = [
    { value: 0, label: () => t('Ein Durchgang') },
    { value: 1800, label: () => t('{n} Minuten', { n: 30 }) },
    { value: 3600, label: () => t('1 Stunde') },
    { value: 7200, label: () => t('{n} Stunden', { n: 2 }) },
    { value: 14400, label: () => t('{n} Stunden', { n: 4 }) },
    { value: 28800, label: () => t('{n} Stunden', { n: 8 }) },
    { value: 43200, label: () => t('{n} Stunden', { n: 12 }) },
    { value: 86400, label: () => t('{n} Stunden', { n: 24 }) },
    { value: -1, label: () => t('Bis Stopp') },
  ];
  const STATUS: Record<string, () => string> = {
    in_progress: () => t('läuft'),
    completed: () => t('abgeschlossen'),
    stopped: () => t('gestoppt'),
    failed: () => t('Fehler'),
  };

  let repeaters = $state<RepeaterInfo[]>([]);
  let loaded = $state(false);
  let canton = $state(DEFAULT_CANTON);
  const selected = new SvelteSet<string>();
  let total = $state(1800);
  let perRepeater = $state(60);
  let sessionId = $state<number | null>(null);
  let progress = $state<ProgressResponse | null>(null);
  let summary = $state<Summary[]>([]);
  let starting = $state(false);
  let stopping = $state(false);

  const cantons = $derived(
    [...new Set(repeaters.map((r) => r.canton).filter((c): c is string => !!c))]
      .sort((a, b) => cantonName(a).localeCompare(cantonName(b), i18n.locale))
      .map((c) => ({ code: c, count: repeaters.filter((r) => r.canton === c).length })),
  );
  const visible = $derived(
    repeaters
      .filter((r) => canton === ALL || r.canton === canton)
      .sort((a, b) => a.output_frequency - b.output_frequency || a.callsign.localeCompare(b.callsign)),
  );
  const chosen = $derived(visible.filter((r) => selected.has(r.uuid)));
  const roundSeconds = $derived(chosen.length * perRepeater);
  const running = $derived(progress?.status === 'in_progress');

  function selectAll(list: RepeaterInfo[]) {
    selected.clear();
    for (const r of list) selected.add(r.uuid);
  }

  function toggle(uuid: string) {
    if (selected.has(uuid)) selected.delete(uuid);
    else selected.add(uuid);
  }

  async function loadRepeaters() {
    try {
      repeaters = (await api.get<{ repeaters: RepeaterInfo[] }>('/repeaters', { limit: 1000 })).repeaters;
      if (!repeaters.some((r) => r.canton === canton)) canton = cantons[0]?.code ?? ALL;
      selectAll(repeaters.filter((r) => canton === ALL || r.canton === canton));
    } catch (e) {
      toasts.error(e);
    } finally {
      loaded = true;
    }
  }

  async function loadSummary() {
    try {
      summary = (await api.get<{ summary: Summary[] }>('/repeater-activity/summary', { hours: 168 })).summary;
    } catch {
      /* ignore */
    }
  }

  $effect(() => {
    void loadRepeaters();
    void loadSummary();
  });

  // pick up a scan that is already running (e.g. after reloading the page)
  $effect(() => {
    const holder = sdr.status?.holder;
    if (sessionId === null && holder?.kind === 'repeater_scan' && holder.owner.startsWith('scan:')) {
      const id = Number(holder.owner.slice(5));
      if (Number.isInteger(id)) sessionId = id;
    }
  });

  $effect(() => {
    if (sessionId === null) return;
    const id = sessionId;
    const poll = async () => {
      try {
        progress = await api.get<ProgressResponse>(`/scan-repeaters/${id}/progress`);
        if (progress.status !== 'in_progress') {
          clearInterval(timer);
          stopping = false;
          void loadSummary();
          void sdr.refresh();
        }
      } catch (e) {
        toasts.error(e);
        clearInterval(timer);
      }
    };
    const timer = setInterval(poll, 3000);
    void poll();
    return () => clearInterval(timer);
  });

  async function start() {
    if (!chosen.length) {
      toasts.push(t('Mindestens einen Repeater auswählen'), 'error');
      return;
    }
    starting = true;
    try {
      const body: Record<string, unknown> = {
        duration_per_repeater: perRepeater,
        repeater_ids: chosen.map((r) => r.uuid),
      };
      if (total === -1) body.until_stopped = true;
      else if (total > 0) body.total_duration = total;
      const r = await api.post<{ session_id: number; repeaters_count: number }>('/scan-repeaters', body);
      progress = null;
      sessionId = r.session_id;
      toasts.push(t('Scan von {n} Repeatern gestartet', { n: r.repeaters_count }), 'success');
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      starting = false;
    }
  }

  async function stop() {
    if (sessionId === null) return;
    stopping = true;
    try {
      await api.post(`/scan-repeaters/${sessionId}/stop`, {});
      toasts.push(t('Scan wird gestoppt'), 'success');
    } catch (e) {
      stopping = false;
      toasts.error(e);
    }
  }

  const pct = $derived.by(() => {
    const p = progress?.progress;
    if (!p) return 0;
    if (progress?.status !== 'in_progress') return 100;
    if (p.total_duration) return (p.elapsed_seconds / p.total_duration) * 100;
    return ((p.current_repeater - 1) / Math.max(1, p.total_repeaters)) * 100;
  });

  const progressLabel = $derived.by(() => {
    const p = progress?.progress;
    if (!p || !progress) return '';
    if (progress.status !== 'in_progress')
      return t('{status} nach {time}', { status: STATUS[progress.status](), time: fmt(p.elapsed_seconds) });
    const where = `${p.current_callsign ?? ''} (${p.current_repeater}/${p.total_repeaters})`;
    const round =
      p.until_stopped || p.total_duration ? `${t('Runde {n}', { n: p.current_round ?? 1 })} · ` : '';
    const rest =
      p.estimated_remaining_seconds === null
        ? t('bis Stopp')
        : t('noch ~{time}', { time: fmt(p.estimated_remaining_seconds) });
    return `${round}${where} · ${fmt(p.elapsed_seconds)} · ${rest}`;
  });
</script>

<PageHeader
  title={t('Repeater-Scan')}
  description={t('Schweizer FM-Relais nacheinander abhören und Aktivität messen')}
/>

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
    <div>
      <label class="label" for="canton">{t('Kanton')}</label>
      <select
        id="canton"
        class="input"
        bind:value={canton}
        onchange={() => selectAll(visible)}
        disabled={running}
      >
        {#each cantons as c (c.code)}
          <option value={c.code}>{c.code} – {cantonName(c.code)} ({c.count})</option>
        {/each}
        <option value={ALL}>{t('Alle Kantone ({n})', { n: repeaters.length })}</option>
      </select>
    </div>
    <div>
      <label class="label" for="total">{t('Dauer des Scans')}</label>
      <select id="total" class="input" bind:value={total} disabled={running}>
        {#each TOTALS as o (o.value)}<option value={o.value}>{o.label()}</option>{/each}
      </select>
    </div>
    <div>
      <label class="label" for="per">{t('Sekunden pro Repeater')}</label>
      <input
        id="per"
        class="input"
        type="number"
        min="5"
        max="600"
        bind:value={perRepeater}
        disabled={running}
      />
    </div>
  </div>

  {#if loaded && repeaters.length === 0}
    <p class="text-sm text-amber-600">
      {t('Noch keine Repeater importiert — ./scripts/run_import.sh ausführen.')}
    </p>
  {:else if visible.length}
    <div>
      <div class="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-sm">
        <span class="font-semibold"
          >{t('{n} von {total} Repeatern ausgewählt · eine Runde ≈ {time}', {
            n: chosen.length,
            total: visible.length,
            time: fmt(roundSeconds),
          })}</span
        >
        <span class="flex gap-3 text-xs">
          <button type="button" class="text-accent-600" onclick={() => selectAll(visible)} disabled={running}
            >{t('alle')}</button
          >
          <button type="button" class="text-accent-600" onclick={() => selected.clear()} disabled={running}
            >{t('keine')}</button
          >
        </span>
      </div>
      <div class="max-h-80 overflow-y-auto">
        <table class="table">
          <thead
            ><tr
              ><th></th><th>{t('Rufzeichen')}</th><th>{t('Standort')}</th><th>{t('Frequenz')}</th><th>Band</th
              ><th>CTCSS</th></tr
            ></thead
          >
          <tbody>
            {#each visible as r (r.uuid)}
              <tr
                class={running && progress?.progress.current_callsign === r.callsign
                  ? 'bg-accent-500/10'
                  : ''}
              >
                <td
                  ><input
                    type="checkbox"
                    class="h-4 w-4 accent-cyan-500"
                    aria-label={t('{call} scannen', { call: r.callsign })}
                    checked={selected.has(r.uuid)}
                    onchange={() => toggle(r.uuid)}
                    disabled={running}
                  /></td
                >
                <td class="font-mono">{r.callsign}</td>
                <td>{r.location_name ?? '—'}{canton === ALL && r.canton ? ` (${r.canton})` : ''}</td>
                <td class="font-mono text-xs">{mhz(r.output_frequency)}</td>
                <td>{r.band ?? '—'}</td>
                <td class="text-xs">{r.ctcss_tone ? `${r.ctcss_tone} Hz` : '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    </div>
  {/if}

  <div class="flex flex-wrap gap-3">
    <button class="btn-primary" type="submit" disabled={running || starting || sdr.busy || !chosen.length}
      ><Play size={16} /> {t('Scan starten')}</button
    >
    <button class="btn-danger" type="button" onclick={stop} disabled={!running || stopping}
      ><Square size={16} /> {stopping ? t('Stoppe…') : t('Stopp')}</button
    >
    {#if sdr.busy && !running}<span class="self-center text-sm text-amber-600"
        >{t('SDR ist belegt ({kind})', { kind: sdr.status?.holder?.kind })}</span
      >{/if}
  </div>
</form>

{#if progress}
  <section class="card mt-6 space-y-3">
    <Progress value={pct} label={progressLabel} />
    {#if progress.error}<p class="text-sm text-red-500">{progress.error}</p>{/if}
    {#if progress.results.length}
      <table class="table">
        <thead
          ><tr
            ><th>{t('Rufzeichen')}</th><th>{t('Frequenz')}</th><th>{t('Messungen')}</th><th
              >{t('Mit Träger')}</th
            ><th>{t('Durchgänge')}</th><th>{t('Ø Aktivität')}</th><th>Signal</th></tr
          ></thead
        >
        <tbody>
          {#each progress.results as r, i (r.callsign + i)}
            <tr class={r.active_rounds ? 'bg-emerald-500/5' : ''}>
              <td class="font-mono">{r.callsign}</td><td class="font-mono text-xs">{mhz(r.frequency)}</td>
              <td>{r.rounds ?? 0}{r.errors ? ` (${t('{n} Fehler', { n: r.errors })})` : ''}</td>
              <td>{r.active_rounds ?? 0}</td>
              <td>{r.transmission_count ?? 0}</td>
              <td>{r.activity_percentage?.toFixed(1) ?? 0} %</td>
              <td>{r.average_signal_strength?.toFixed(1) ?? '—'} dB</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  </section>
{/if}

<section class="card mt-6">
  <h2 class="mb-3 text-sm font-semibold">{t('Aktivste Repeater (7 Tage)')}</h2>
  {#if summary.length}
    <table class="table">
      <thead
        ><tr
          ><th>{t('Rufzeichen')}</th><th>{t('Frequenz')}</th><th>Band</th><th>{t('Kanton')}</th><th
            >{t('Ø Aktivität')}</th
          ><th>{t('Durchgänge')}</th></tr
        ></thead
      >
      <tbody>
        {#each summary as s (s.callsign)}
          <tr
            ><td class="font-mono">{s.callsign}</td><td class="font-mono text-xs"
              >{s.frequency_mhz?.toFixed(4)} MHz</td
            ><td>{s.band}</td><td>{s.canton}</td><td>{s.avg_activity_pct} %</td><td
              >{s.total_transmissions}</td
            ></tr
          >
        {/each}
      </tbody>
    </table>
  {:else}
    <EmptyState text={t('In den letzten 7 Tagen wurde noch keine Aktivität gemessen.')} />
  {/if}
</section>
