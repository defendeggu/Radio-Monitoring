<script lang="ts">
  import { ChevronDown, ChevronRight } from '@lucide/svelte';
  import { api } from '../api';
  import { t } from '../i18n.svelte';
  import type { RbnSpot } from '../types';

  let {
    band = $bindable('20m'),
    frequency = null,
    selected = null,
    onpick,
  }: {
    band?: string;
    frequency?: number | null;
    selected?: number | null;
    onpick: (spot: RbnSpot) => void;
  } = $props();

  interface RbnStatus {
    enabled: boolean;
    configured: boolean;
    connected: boolean;
    host: string;
    error?: string | null;
    spots_per_minute?: number;
  }

  const BANDS = ['160m', '80m', '60m', '40m', '30m', '20m', '17m', '15m', '12m', '10m'];
  const OPEN_KEY = 'radiomoni.rbn.open';

  function loadOpen(): boolean {
    try {
      return localStorage.getItem(OPEN_KEY) !== '0';
    } catch {
      return true;
    }
  }

  let open = $state(loadOpen());
  let spots = $state<RbnSpot[]>([]);
  let status = $state<RbnStatus | null>(null);
  let call = $state('');
  let cqOnly = $state(false);
  let sortBy = $state<'frequency' | 'time'>('frequency');
  let loading = $state(false);

  const sorted = $derived(
    [...spots].sort((a, b) =>
      sortBy === 'frequency' ? a.frequency - b.frequency : a.age_seconds - b.age_seconds,
    ),
  );

  function toggle() {
    open = !open;
    try {
      localStorage.setItem(OPEN_KEY, open ? '1' : '0');
    } catch {
      /* ignore */
    }
  }

  async function load() {
    loading = true;
    try {
      const r = await api.get<{ spots: RbnSpot[] }>('/rbn/spots', {
        band,
        call: call.trim() || undefined,
        cq_only: cqOnly || undefined,
        max_age: 15,
        limit: 300,
      });
      spots = r.spots;
    } catch {
      spots = [];
    } finally {
      loading = false;
    }
  }

  async function loadStatus() {
    try {
      status = await api.get<RbnStatus>('/rbn/status');
    } catch {
      status = null;
    }
  }

  $effect(() => {
    void [band, call, cqOnly];
    if (!open) return;
    void load();
    const timer = setInterval(load, 5000);
    return () => clearInterval(timer);
  });

  $effect(() => {
    void loadStatus();
    const timer = setInterval(loadStatus, 30_000);
    return () => clearInterval(timer);
  });

  /** On the receiver frequency (±500 Hz)? */
  function tuned(s: RbnSpot): boolean {
    return frequency !== null && Math.abs(s.frequency - frequency) <= 500;
  }

  function age(seconds: number): string {
    return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`;
  }
</script>

<section class="card">
  <button
    class="flex w-full items-center gap-2 text-left"
    type="button"
    onclick={toggle}
    aria-expanded={open}
  >
    {#if open}<ChevronDown size={16} />{:else}<ChevronRight size={16} />{/if}
    <h2 class="text-sm font-semibold">{t('RBN-Spots (Reverse Beacon Network)')}</h2>
    {#if status?.connected}
      <span class="ml-auto text-xs text-emerald-600"
        >● {t('{n} Spots/min', { n: status.spots_per_minute ?? 0 })}</span
      >
    {:else if status?.enabled}
      <span class="ml-auto text-xs text-amber-600">{t('nicht verbunden')}</span>
    {/if}
  </button>

  {#if open}
    {#if status && (!status.enabled || !status.configured)}
      <p class="mt-3 text-sm text-slate-500">
        {t(
          'RBN ist aus. In .env RBN_ENABLED=true und RBN_CALLSIGN (dein Rufzeichen) setzen, dann den API-Container neu starten.',
        )}
      </p>
    {:else}
      {#if status?.error && !status.connected}
        <p class="mt-2 text-xs text-red-500">{status.error}</p>
      {/if}
      <div class="mt-3 flex flex-wrap items-end gap-3 text-sm">
        <div>
          <label class="label" for="rbnband">{t('Band')}</label>
          <select id="rbnband" class="input" bind:value={band}>
            {#each BANDS as b (b)}<option value={b}>{b}</option>{/each}
          </select>
        </div>
        <div>
          <label class="label" for="rbncall">{t('Rufzeichen')}</label>
          <input id="rbncall" class="input w-32 font-mono uppercase" bind:value={call} maxlength="12" />
        </div>
        <label class="flex items-center gap-2 pb-2">
          <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={cqOnly} />
          {t('Nur CQ')}
        </label>
        <div>
          <label class="label" for="rbnsort">{t('Sortierung')}</label>
          <select id="rbnsort" class="input" bind:value={sortBy}>
            <option value="frequency">{t('Frequenz')}</option>
            <option value="time">{t('Zeit')}</option>
          </select>
        </div>
      </div>
      <div class="mt-3 max-h-80 overflow-auto">
        <table class="w-full text-left text-sm">
          <thead class="sticky top-0 bg-white text-xs text-slate-500 dark:bg-slate-900">
            <tr>
              <th class="py-1 pr-2">{t('Alter')}</th>
              <th class="pr-2">kHz</th>
              <th class="pr-2">{t('Rufzeichen')}</th>
              <th class="pr-2">SNR</th>
              <th class="pr-2">WPM</th>
              <th class="pr-2" title={t('Anzahl Skimmer')}>Sk.</th>
              <th>{t('Typ')}</th>
            </tr>
          </thead>
          <tbody>
            {#each sorted as s (s.callsign + s.khz)}
              <tr
                class="cursor-pointer border-t border-slate-100 hover:bg-cyan-50 dark:border-slate-800 dark:hover:bg-cyan-950/40
                  {tuned(s) ? 'bg-emerald-50 font-semibold dark:bg-emerald-950/40' : ''}
                  {selected === s.frequency ? 'ring-1 ring-cyan-500 ring-inset' : ''}"
                onclick={() => onpick(s)}
                title={t('Klick: Empfänger auf {khz} kHz stellen', { khz: s.khz.toFixed(1) })}
              >
                <td class="py-1 pr-2 font-mono text-xs text-slate-500">{age(s.age_seconds)}</td>
                <td class="pr-2 font-mono">{s.khz.toFixed(1)}</td>
                <td class="pr-2 font-mono">{s.callsign}</td>
                <td class="pr-2 font-mono">{s.snr_db}</td>
                <td class="pr-2 font-mono">{s.wpm ?? '–'}</td>
                <td class="pr-2 font-mono">{s.skimmer_count}</td>
                <td class="text-xs">{s.type}</td>
              </tr>
            {:else}
              <tr>
                <td colspan="7" class="py-3 text-center text-slate-500">
                  {loading ? t('lädt…') : t('Keine Spots in diesem Band (letzte 15 Minuten).')}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
    <p class="mt-2 text-xs text-slate-500">
      {t('Daten:')}
      <a
        class="text-cyan-600 hover:underline"
        href="https://www.reversebeacon.net/"
        target="_blank"
        rel="noopener noreferrer">Reverse Beacon Network</a
      >
    </p>
  {/if}
</section>
