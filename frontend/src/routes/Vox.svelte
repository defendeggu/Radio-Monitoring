<script lang="ts">
  import { Radio } from '@lucide/svelte';
  import { api } from '../lib/api';
  import AudioPlayer from '../lib/components/AudioPlayer.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import LanguageField from '../lib/components/LanguageField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Presets from '../lib/components/Presets.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import { time } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { live, sdr, settings, toasts } from '../lib/stores.svelte';

  interface Segment {
    audio_file: string;
    duration?: number;
    text?: string;
    error?: string;
    at: string;
  }

  let frequency = $state(446_006_250);
  let modulation = $state<'FM' | 'AM'>('FM');
  let gain = $state(30);
  let squelch = $state(10);
  let hang = $state(1500);
  let hours = $state(1);
  let transcribe = $state(true);
  let language = $state('');
  let sessionId = $state<string | null>(null);
  let busy = $state(false);
  let open = $state(false);
  let segments = $state<Segment[]>([]);
  let selected = $state<string | null>(null);

  $effect(() => {
    const active = sdr.status?.active_sessions.find((s) => s.mode === 'vox');
    if (active && !sessionId) sessionId = active.session_id;
  });

  $effect(() =>
    live.on(['vox'], (e) => {
      const d = e.data as {
        session_id?: string;
        state: string;
        audio_file?: string;
        duration?: number;
        text?: string;
        error?: string;
      };
      if (sessionId && d.session_id && d.session_id !== sessionId) return;
      if (d.state === 'open') open = true;
      if (d.state === 'segment' && d.audio_file) {
        open = false;
        segments = [{ audio_file: d.audio_file, duration: d.duration, at: e.time }, ...segments].slice(
          0,
          100,
        );
      }
      if (d.state === 'transcribed' && d.audio_file) {
        segments = segments.map((s) => (s.audio_file === d.audio_file ? { ...s, text: d.text } : s));
      }
      if (d.state === 'transcription_failed' && d.audio_file) {
        segments = segments.map((s) =>
          s.audio_file === d.audio_file ? { ...s, error: d.error ?? t('unbekannter Fehler') } : s,
        );
      }
    }),
  );

  async function start() {
    busy = true;
    try {
      const r = await api.post<{ session_id: string }>('/vox/start', {
        frequency,
        modulation,
        gain,
        squelch_db: squelch,
        hang_time_ms: hang,
        duration: Math.round(hours * 3600),
        transcribe,
        language: language || null,
        ...settings.deviceParams(),
      });
      sessionId = r.session_id;
      segments = [];
      toasts.push(t('VOX-Aufnahme gestartet'), 'success');
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }
</script>

<PageHeader
  title={t('VOX-Aufnahme')}
  description={t('Kanal dauerhaft überwachen — aufgenommen und transkribiert wird nur, wenn jemand sendet')}
/>

<Presets
  modes={['vox', 'voice']}
  onpick={(b) => {
    frequency = b.frequency;
    modulation = b.modulation === 'AM' ? 'AM' : 'FM';
  }}
/>

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
    <FrequencyField bind:value={frequency} />
    <div>
      <label class="label" for="vmod">Modulation</label>
      <select id="vmod" class="input" bind:value={modulation}><option>FM</option><option>AM</option></select>
    </div>
    <div>
      <label class="label" for="vgain">{t('Verstärkung (dB)')}</label>
      <input id="vgain" class="input" type="number" min="0" max="76" bind:value={gain} />
    </div>
    <div>
      <label class="label" for="vh">{t('Laufzeit (Stunden)')}</label>
      <input id="vh" class="input" type="number" min="0.5" max="24" step="0.5" bind:value={hours} />
    </div>
    <div>
      <label class="label" for="sq">{t('Squelch: {n} dB über Rauschen', { n: squelch })}</label>
      <input id="sq" type="range" min="3" max="40" bind:value={squelch} class="w-full accent-cyan-500" />
      <p class="hint">{t('Niedriger = empfindlicher, mehr Fehlauslösungen')}</p>
    </div>
    <div>
      <label class="label" for="hang">{t('Nachlaufzeit (ms)')}</label>
      <input id="hang" class="input" type="number" min="100" max="10000" step="100" bind:value={hang} />
    </div>
    <LanguageField id="vlang" bind:value={language} />
    <label class="flex items-center gap-2 self-end pb-2 text-sm">
      <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={transcribe} />
      {t('Transkribieren')}
    </label>
  </div>
  <button class="btn-primary" type="submit" disabled={busy || sdr.busy}
    ><Radio size={16} /> {t('VOX starten')}</button
  >
</form>

{#if sessionId}
  <div class="mt-4 space-y-2">
    <SessionCard {sessionId} countLabel={t('Segmente')} />
    <p class="text-sm">
      Squelch:
      <span class="font-medium {open ? 'text-emerald-600' : 'text-slate-500'}"
        >{open ? t('offen — Signal') : t('geschlossen')}</span
      >
    </p>
  </div>
{/if}

<section class="card mt-6">
  <h2 class="mb-3 text-sm font-semibold">{t('Aufgenommene Durchgänge')}</h2>
  {#if segments.length}
    <ul class="divide-y divide-slate-100 dark:divide-slate-800">
      {#each segments as s (s.audio_file)}
        <li class="py-3">
          <button
            class="flex w-full flex-wrap items-baseline gap-3 text-left text-sm"
            onclick={() => (selected = selected === s.audio_file ? null : s.audio_file)}
          >
            <span class="font-mono text-xs text-slate-500">{time(s.at)}</span>
            <span class="font-mono text-xs">{s.duration?.toFixed(1)} s</span>
            {#if s.error}
              <span class="flex-1 text-red-500" title={s.error}>{t('Transkription fehlgeschlagen')}</span>
            {:else}
              <span class="flex-1">{s.text ?? (transcribe ? t('transkribiere…') : s.audio_file)}</span>
            {/if}
          </button>
          {#if selected === s.audio_file}<div class="mt-2"><AudioPlayer filename={s.audio_file} /></div>{/if}
        </li>
      {/each}
    </ul>
  {:else}
    <EmptyState text={t('Noch keine Durchgänge. Ältere VOX-Aufnahmen findest du unter Aufnahmen.')} />
  {/if}
</section>
