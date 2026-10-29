<script lang="ts">
  import { FileArchive, Play, Square } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import AudioPlayer from '../lib/components/AudioPlayer.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import Presets from '../lib/components/Presets.svelte';
  import Progress from '../lib/components/Progress.svelte';
  import { duration as fmtDuration, mhz } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { waitForCapture } from '../lib/polling';
  import { router } from '../lib/router.svelte';
  import { sdr, settings, toasts } from '../lib/stores.svelte';
  import type { CaptureJob, CaptureResult, Modulation } from '../lib/types';

  let frequency = $state(Number(router.params.get('f')) || 145_500_000);
  let modulation = $state<Modulation>((router.params.get('m') as Modulation) || 'FM');
  let duration = $state(30);
  let gain = $state(20);
  let language = $state('');
  let beamSize = $state(5);
  let prompt = $state('');
  let showAdvanced = $state(false);

  let job = $state<CaptureJob | null>(null);
  let result = $state<CaptureResult | null>(null);
  let started = $state(0);
  let now = $state(Date.now());
  let abort: AbortController | null = null;

  const running = $derived(!!job && job.status !== 'completed' && job.status !== 'failed');
  const progress = $derived.by(() => {
    if (!job) return 0;
    if (job.status === 'queued') return 3;
    if (job.status === 'capturing') return Math.min(70, 5 + ((now - started) / 1000 / duration) * 65);
    if (job.status === 'processing') return 85;
    return 100;
  });

  $effect(() => {
    if (!running) return;
    const timer = setInterval(() => (now = Date.now()), 500);
    return () => clearInterval(timer);
  });

  async function start() {
    result = null;
    abort = new AbortController();
    try {
      const body = {
        frequency,
        modulation,
        duration,
        gain,
        mode: 'voice',
        language: language || null,
        beam_size: beamSize,
        initial_prompt: prompt || null,
        ...settings.deviceParams(),
      };
      const { capture_id } = await api.post<{ capture_id: string }>('/capture-and-transcribe', body);
      job = { capture_id, status: 'queued', mode: 'voice', created_at: '', result: null, error: null };
      started = Date.now();
      const final = await waitForCapture(
        capture_id,
        (j) => {
          if (j.status === 'capturing' && job?.status !== 'capturing') started = Date.now();
          job = j;
        },
        abort.signal,
      );
      if (final.status === 'completed') {
        result = final.result;
        toasts.push(t('Transkription fertig'), 'success');
      } else {
        toasts.push(t('Aufnahme fehlgeschlagen: {error}', { error: final.error }), 'error', 10_000);
      }
    } catch (e) {
      if ((e as Error).name !== 'AbortError') toasts.error(e);
      job = null;
    }
  }

  async function stop() {
    abort?.abort();
    try {
      await api.post('/sdr/force-stop');
      toasts.push(t('SDR gestoppt'), 'info');
    } catch (e) {
      toasts.error(e);
    }
    job = null;
  }
</script>

<PageHeader title={t('Sprache')} description={t('Aufnehmen und mit Whisper transkribieren (FM/AM/SSB)')} />

<Presets
  modes={['voice', 'vox']}
  onpick={(b) => {
    frequency = b.frequency;
    modulation = b.modulation;
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
      <label class="label" for="mod">Modulation</label>
      <select id="mod" class="input" bind:value={modulation}>
        <option>FM</option><option>AM</option><option>USB</option><option>LSB</option>
      </select>
    </div>
    <div>
      <label class="label" for="dur">{t('Dauer (s)')}</label>
      <input id="dur" class="input" type="number" min="1" max="600" bind:value={duration} />
      <p class="hint">1–600 s</p>
    </div>
    <div>
      <label class="label" for="gain">{t('Verstärkung (dB)')}</label>
      <input id="gain" class="input" type="number" min="0" max="76" bind:value={gain} />
    </div>
  </div>

  <button
    type="button"
    class="text-xs text-accent-600 underline dark:text-accent-400"
    onclick={() => (showAdvanced = !showAdvanced)}
    aria-expanded={showAdvanced}
  >
    {showAdvanced ? t('Whisper-Optionen ausblenden') : t('Whisper-Optionen anzeigen')}
  </button>
  {#if showAdvanced}
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <div>
        <label class="label" for="lang">{t('Sprache||language')}</label>
        <input
          id="lang"
          class="input"
          bind:value={language}
          placeholder={t('automatisch (de, en, fr…)')}
          maxlength="3"
        />
      </div>
      <div>
        <label class="label" for="beam">Beam size</label>
        <input id="beam" class="input" type="number" min="1" max="10" bind:value={beamSize} />
        <p class="hint">{t('Höher = genauer, langsamer')}</p>
      </div>
      <div>
        <label class="label" for="prompt">{t('Vokabular-Hinweis')}</label>
        <input
          id="prompt"
          class="input"
          bind:value={prompt}
          maxlength="500"
          placeholder={t('z. B. HB9 Rufzeichen, Ortsnamen')}
        />
      </div>
    </div>
  {/if}

  {#if running}<Progress
      value={progress}
      label={job?.status === 'processing'
        ? t('Transkribiere…')
        : job?.status === 'queued'
          ? t('Warte auf SDR…')
          : t('Nehme auf…')}
    />{/if}

  <div class="flex flex-wrap gap-3">
    <button class="btn-primary" type="submit" disabled={running || sdr.busy}
      ><Play size={16} /> {t('Aufnahme starten')}</button
    >
    <button class="btn-danger" type="button" onclick={stop} disabled={!running && !sdr.busy}
      ><Square size={16} /> {t('Stopp')}</button
    >
    {#if sdr.busy && !running}<span class="self-center text-sm text-amber-600"
        >{t('SDR ist belegt ({kind})', { kind: sdr.status?.holder?.kind })}</span
      >{/if}
  </div>
</form>

{#if result?.transcription}
  {@const tr = result.transcription}
  <section class="card mt-6 space-y-4">
    {#if result.simulation_mode}
      <p class="rounded bg-amber-500/10 p-2 text-sm text-amber-700 dark:text-amber-300">
        {t('Simulationsmodus: Diese Transkription ist nicht echt.')}
      </p>
    {/if}
    <div class="flex flex-wrap gap-6 text-sm">
      <span
        ><span class="text-slate-500">{t('Frequenz')}</span>
        <span class="font-mono">{mhz(result.capture.frequency)}</span></span
      >
      <span
        ><span class="text-slate-500">{t('Sprache||language')}</span>
        {tr.language} ({Math.round(tr.language_probability * 100)} %)</span
      >
      <span><span class="text-slate-500">{t('Dauer')}</span> {fmtDuration(tr.duration)}</span>
    </div>
    <p
      class="rounded-lg bg-slate-100 p-4 font-mono text-sm leading-relaxed whitespace-pre-wrap dark:bg-slate-800"
    >
      {tr.text || t('Keine Sprache erkannt (Rauschen oder Stille).')}
    </p>
    {#if tr.segments.length > 1}
      <details>
        <summary class="cursor-pointer text-sm text-slate-500"
          >{t('{n} Segmente', { n: tr.segments.length })}</summary
        >
        <ol class="mt-2 space-y-1 text-sm">
          {#each tr.segments as s, i (i)}
            <li>
              <span class="font-mono text-xs text-slate-500">{s.start.toFixed(1)}–{s.end.toFixed(1)} s</span>
              {s.text}
            </li>
          {/each}
        </ol>
      </details>
    {/if}
    <AudioPlayer filename={result.capture.audio_file} />
    {#if result.capture.id}
      <button
        class="btn-secondary"
        onclick={() =>
          download(
            `/export/capture/${result?.capture.id}.zip`,
            `capture-${result?.capture.id?.slice(0, 8)}.zip`,
          ).catch(toasts.error.bind(toasts))}
      >
        <FileArchive size={16} />
        {t('Als ZIP exportieren')}
      </button>
    {/if}
  </section>
{/if}
