<script lang="ts">
  import { Search } from '@lucide/svelte';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Progress from '../lib/components/Progress.svelte';
  import { duration as fmt, mhz } from '../lib/format';
  import { sdr, toasts } from '../lib/stores.svelte';

  interface Result {
    callsign: string;
    frequency: number;
    error?: string;
    activity?: {
      carrier_detected: boolean;
      transmission_count: number;
      activity_percentage: number;
      average_signal_strength: number | null;
    };
  }
  interface ProgressResponse {
    status: string;
    progress: {
      current_repeater: number;
      total_repeaters: number;
      current_callsign: string | null;
      elapsed_seconds: number;
      estimated_remaining_seconds: number;
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

  let band = $state<'2m' | '70cm' | 'all'>('2m');
  let canton = $state('');
  let perRepeater = $state(60);
  let sessionId = $state<number | null>(null);
  let progress = $state<ProgressResponse | null>(null);
  let summary = $state<Summary[]>([]);
  let repeaterCount = $state<number | null>(null);

  async function loadSummary() {
    try {
      summary = (await api.get<{ summary: Summary[] }>('/repeater-activity/summary', { hours: 168 })).summary;
      repeaterCount = (await api.get<{ count: number }>('/repeaters', { limit: 1000 })).count;
    } catch {
      /* ignore */
    }
  }

  $effect(() => {
    void loadSummary();
  });

  $effect(() => {
    if (sessionId === null) return;
    const id = sessionId;
    const poll = async () => {
      try {
        progress = await api.get<ProgressResponse>(`/scan-repeaters/${id}/progress`);
        if (progress.status !== 'in_progress') {
          clearInterval(timer);
          void loadSummary();
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
    try {
      const body: Record<string, unknown> = { duration_per_repeater: perRepeater };
      if (band !== 'all') body.band = band;
      if (canton) body.canton = canton;
      const r = await api.post<{
        session_id: number;
        repeaters_count: number;
        estimated_duration_seconds: number;
      }>('/scan-repeaters', body);
      sessionId = r.session_id;
      toasts.push(
        `Scan von ${r.repeaters_count} Repeatern gestartet (~${fmt(r.estimated_duration_seconds)})`,
        'success',
      );
    } catch (e) {
      toasts.error(e);
    }
  }

  const pct = $derived(
    progress
      ? (Math.max(0, progress.progress.current_repeater - 1) /
          Math.max(1, progress.progress.total_repeaters)) *
          100
      : 0,
  );
</script>

<PageHeader
  title="Repeater-Scan"
  description="Schweizer FM-Relais nacheinander abhören und Aktivität messen"
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
      <label class="label" for="band">Band</label>
      <select id="band" class="input" bind:value={band}
        ><option value="2m">2 m</option><option value="70cm">70 cm</option><option value="all">alle</option
        ></select
      >
    </div>
    <div>
      <label class="label" for="canton">Kanton (optional)</label>
      <input id="canton" class="input uppercase" bind:value={canton} maxlength="2" placeholder="ZH" />
    </div>
    <div>
      <label class="label" for="per">Sekunden pro Repeater</label>
      <input id="per" class="input" type="number" min="5" max="600" bind:value={perRepeater} />
    </div>
  </div>
  {#if repeaterCount === 0}
    <p class="text-sm text-amber-600">
      Noch keine Repeater importiert — <code>./scripts/run_import.sh</code> ausführen.
    </p>
  {/if}
  <button class="btn-primary" type="submit" disabled={sdr.busy}><Search size={16} /> Scan starten</button>
</form>

{#if progress}
  <section class="card mt-6 space-y-3">
    <Progress
      value={progress.status === 'completed' ? 100 : pct}
      label="{progress.progress.current_callsign ?? ''} ({progress.progress.current_repeater}/{progress
        .progress.total_repeaters}) · noch ~{fmt(progress.progress.estimated_remaining_seconds)}"
    />
    {#if progress.error}<p class="text-sm text-red-500">{progress.error}</p>{/if}
    <table class="table">
      <thead
        ><tr
          ><th>Rufzeichen</th><th>Frequenz</th><th>Aktiv</th><th>Durchgänge</th><th>Aktivität</th><th
            >Signal</th
          ></tr
        ></thead
      >
      <tbody>
        {#each progress.results as r, i (r.callsign + i)}
          <tr class={r.activity?.carrier_detected ? 'bg-emerald-500/5' : ''}>
            <td class="font-mono">{r.callsign}</td><td class="font-mono text-xs">{mhz(r.frequency)}</td>
            <td>{r.error ? 'Fehler' : r.activity?.carrier_detected ? 'ja' : 'ruhig'}</td>
            <td>{r.activity?.transmission_count ?? 0}</td>
            <td>{r.activity?.activity_percentage?.toFixed(1) ?? 0} %</td>
            <td>{r.activity?.average_signal_strength?.toFixed(1) ?? '—'} dB</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </section>
{/if}

<section class="card mt-6">
  <h2 class="mb-3 text-sm font-semibold">Aktivste Repeater (7 Tage)</h2>
  {#if summary.length}
    <table class="table">
      <thead
        ><tr
          ><th>Rufzeichen</th><th>Frequenz</th><th>Band</th><th>Kanton</th><th>Ø Aktivität</th><th
            >Durchgänge</th
          ></tr
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
    <EmptyState text="Noch keine Scan-Ergebnisse." />
  {/if}
</section>
