<script lang="ts">
  import { Play, Radio } from '@lucide/svelte';
  import { api } from '../api';
  import { t } from '../i18n.svelte';
  import { waitForCapture } from '../polling';
  import { router } from '../router.svelte';
  import { sdr, settings, toasts } from '../stores.svelte';
  import type { Bookmark, CaptureResult } from '../types';
  import FrequencyField from './FrequencyField.svelte';
  import Presets from './Presets.svelte';
  import Progress from './Progress.svelte';
  import SessionCard from './SessionCard.svelte';

  let {
    mode,
    defaultFrequency,
    maxCapture,
    oncapture,
  }: {
    mode: 'aprs' | 'pocsag';
    defaultFrequency: number;
    maxCapture: number;
    oncapture: (r: CaptureResult) => void;
  } = $props();

  // svelte-ignore state_referenced_locally
  let frequency = $state(Number(router.params.get('f')) || defaultFrequency);
  let gain = $state(32);
  let streaming = $state(true);
  let streamHours = $state(1);
  // svelte-ignore state_referenced_locally
  let captureSeconds = $state(Math.min(120, maxCapture));
  let busy = $state(false);
  let captureStatus = $state('');
  let sessionId = $state<string | null>(null);

  // pick up a running session of this mode (e.g. after a page reload)
  $effect(() => {
    const active = sdr.status?.active_sessions.find((s) => s.mode === mode);
    if (active && !sessionId) sessionId = active.session_id;
  });

  async function start() {
    busy = true;
    try {
      if (streaming) {
        const r = await api.post<{ session_id: string }>('/stream-decode', {
          mode,
          frequency,
          gain,
          duration: Math.round(streamHours * 3600),
          ...settings.deviceParams(),
        });
        sessionId = r.session_id;
        toasts.push(t('{mode}-Streaming gestartet', { mode: mode.toUpperCase() }), 'success');
        void sdr.refresh();
      } else {
        const r = await api.post<{ capture_id: string }>('/capture-and-transcribe', {
          mode,
          frequency,
          gain,
          duration: captureSeconds,
          ...settings.deviceParams(),
        });
        const job = await waitForCapture(r.capture_id, (j) => (captureStatus = j.status));
        if (job.status === 'completed' && job.result) oncapture(job.result);
        else toasts.push(t('Aufnahme fehlgeschlagen: {error}', { error: job.error }), 'error');
      }
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
      captureStatus = '';
    }
  }
</script>

<Presets modes={[mode as Bookmark['mode']]} onpick={(b) => (frequency = b.frequency)} />

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  <div class="flex items-center gap-3 rounded-lg bg-slate-100 p-3 dark:bg-slate-800/60">
    <label class="flex cursor-pointer items-center gap-3 text-sm">
      <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={streaming} />
      <span>
        <span class="font-medium">{t('Dauerbetrieb (Streaming)')}</span>
        <span class="block text-xs text-slate-500"
          >{t('Pakete werden live gespeichert und angezeigt — bis 24 h')}</span
        >
      </span>
    </label>
  </div>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
    <FrequencyField bind:value={frequency} />
    <div>
      <label class="label" for="{mode}-gain">{t('Verstärkung (dB)')}</label>
      <input id="{mode}-gain" class="input" type="number" min="0" max="76" bind:value={gain} />
    </div>
    {#if streaming}
      <div>
        <label class="label" for="{mode}-hours">{t('Laufzeit (Stunden)')}</label>
        <input
          id="{mode}-hours"
          class="input"
          type="number"
          min="0.5"
          max="24"
          step="0.5"
          bind:value={streamHours}
        />
      </div>
    {:else}
      <div>
        <label class="label" for="{mode}-sec">{t('Dauer (s)')}</label>
        <input
          id="{mode}-sec"
          class="input"
          type="number"
          min="1"
          max={maxCapture}
          bind:value={captureSeconds}
        />
        <p class="hint">max. {maxCapture} s</p>
      </div>
    {/if}
  </div>
  {#if captureStatus}<Progress value={captureStatus === 'processing' ? 85 : 40} label={captureStatus} />{/if}
  <button class="btn-primary" type="submit" disabled={busy || sdr.busy}>
    {#if streaming}<Radio size={16} /> {t('Streaming starten')}{:else}<Play size={16} />
      {t('Aufnahme starten')}{/if}
  </button>
  {#if sdr.busy && !sessionId}<span class="ml-3 text-sm text-amber-600"
      >{t('SDR belegt ({kind})', { kind: sdr.status?.holder?.kind })}</span
    >{/if}
</form>

{#if sessionId}
  <div class="mt-4">
    <SessionCard
      {sessionId}
      countLabel={mode === 'aprs' ? t('Pakete') : t('Meldungen')}
      onended={() => void sdr.refresh()}
    />
  </div>
{/if}
