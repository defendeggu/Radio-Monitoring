<script lang="ts">
  import { onDestroy } from 'svelte';
  import { AudioWaveform, Headphones, Mic, Play, Radio, VolumeX } from '@lucide/svelte';
  import { api } from '../lib/api';
  import { CW_BANDS, VHF_BANDS, centreOf, type Band } from '../lib/bands';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import Waterfall, { type Marker } from '../lib/components/Waterfall.svelte';
  import { mhz } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { router } from '../lib/router.svelte';
  import { routes } from './index';
  import type { ColormapName } from '../lib/spectrum/colormap';
  import {
    connectSpectrum,
    type Frame,
    type SpectrumConnection,
    type SpectrumState,
  } from '../lib/spectrum/frames';
  import { LivePlayer } from '../lib/spectrum/player';
  import { sdr, settings, toasts } from '../lib/stores.svelte';
  import type { Bookmark } from '../lib/types';

  type Listen = 'FM' | 'AM' | 'USB' | 'LSB' | 'CW';

  const SPANS: Record<string, number[]> = {
    hackrf: [2_000_000, 4_000_000, 8_000_000, 10_000_000],
    rtlsdr: [250_000, 1_024_000, 2_048_000, 2_400_000],
    airspyhf: [768_000],
    usrp: [1_000_000, 2_000_000, 5_000_000, 10_000_000],
  };
  const WIDTHS: Record<Listen, number> = { FM: 12_500, AM: 8_000, USB: 2_700, LSB: 2_700, CW: 500 };

  let centre = $state(Number(router.params.get('f')) || 145_500_000);
  let span = $state(2_000_000);
  let gain = $state(30);
  let fftSize = $state(2048);
  let colours = $state<ColormapName>('classic');
  let auto = $state(true);
  let lo = $state(-110);
  let hi = $state(-40);

  let sessionId = $state<string | null>(null);
  let info = $state<SpectrumState | null>(null);
  let ended = $state<string | null>(null);
  let connection = $state<'connecting' | 'open' | 'closed'>('closed');
  let busy = $state(false);
  let listen = $state(false);
  let volume = $state(0.7);
  let modulation = $state<Listen>('FM');
  let cwBandwidth = $state(500);
  let squelchOn = $state(false);
  let squelch = $state(10);
  let bookmarks = $state<Bookmark[]>([]);

  let waterfall: Waterfall | undefined = $state();
  let stream: SpectrumConnection | null = null;
  const player = new LivePlayer();

  const hasCw = routes.some((r) => r.path === 'cw');
  const spans = $derived(SPANS[sdr.detect?.type ?? ''] ?? [2_000_000]);
  const tunable = $derived(!!info?.tunable);
  const others = $derived(
    (sdr.status?.active_sessions ?? []).filter(
      (s) => (s.mode === 'vox' || s.mode === 'cw') && s.session_id !== sessionId,
    ),
  );
  const markers = $derived<Marker[]>(
    info
      ? bookmarks
          .filter((b) => Math.abs(b.frequency - info!.centre) < info!.span / 2)
          .map((b) => ({ frequency: b.frequency, label: b.name, kind: 'bookmark' }))
      : [],
  );

  $effect(() => {
    if (!spans.includes(span)) span = spans[0];
  });

  // resume a waterfall that is already running (e.g. after a reload)
  $effect(() => {
    const active = sdr.status?.active_sessions.find((s) => s.mode === 'spectrum');
    if (active && !sessionId) attach(active.session_id);
  });

  $effect(() => {
    api
      .get<{ bookmarks: Bookmark[]; defaults: Bookmark[] }>('/bookmarks')
      .then((r) => (bookmarks = r.bookmarks.length ? r.bookmarks : r.defaults))
      .catch(() => (bookmarks = []));
  });

  onDestroy(() => {
    stream?.close();
    void player.stop();
  });

  function onFrame(frame: Frame) {
    if (frame.kind === 'spectrum') waterfall?.addRow(frame.row);
    else if (frame.kind === 'audio') player.push(frame.audio.pcm, frame.audio.rate);
    else if (frame.data.state) {
      info = frame.data.state;
      modulation = (info.modulation as Listen) || modulation;
    } else if (frame.data.end) {
      ended = frame.data.reason ?? frame.data.end;
      void sdr.refresh();
    }
  }

  function connect() {
    stream?.close();
    if (sessionId) stream = connectSpectrum(sessionId, listen, onFrame, (s) => (connection = s));
  }

  function attach(id: string) {
    sessionId = id;
    ended = null;
    info = null;
    waterfall?.clear();
    connect();
  }

  async function start() {
    busy = true;
    try {
      const r = await api.post<{ session_id: string }>('/spectrum', {
        frequency: centre,
        sample_rate: span,
        gain,
        fft_size: fftSize,
        ...settings.deviceParams(),
      });
      attach(r.session_id);
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  async function tune(changes: Record<string, unknown>) {
    if (!sessionId || !tunable) return;
    try {
      const r = await api.post<{ state: SpectrumState }>(`/spectrum/${sessionId}/tune`, changes);
      info = r.state;
      if ('channel' in changes || 'centre' in changes) player.reset();
    } catch (e) {
      toasts.error(e);
    }
  }

  function pick(frequency: number, shift: boolean) {
    if (shift && hasCw) return router.go('cw', { f: frequency });
    if (!info) return;
    if (Math.abs(frequency - info.centre) > info.span * 0.45)
      void tune({ centre: frequency, channel: frequency });
    else void tune({ channel: frequency });
  }

  function band(b: Band) {
    centre = centreOf(b);
    if (sessionId && tunable && !ended) void tune({ centre, channel: centre });
  }

  async function toggleListen() {
    if (listen) {
      listen = false;
      await player.stop();
    } else {
      try {
        await player.start(volume);
        listen = true;
      } catch (e) {
        toasts.error(e);
        return;
      }
    }
    connect();
  }

  function openWith(path: string) {
    if (!info) return;
    const f = info.channel;
    if (path === 'voice') router.go('voice', { f, m: modulation === 'CW' ? 'USB' : modulation });
    else router.go(path, { f });
  }

  $effect(() => player.setVolume(volume));
</script>

<PageHeader
  title={t('Spektrum')}
  description={t('Wasserfall mit Mithören — weicht automatisch, sobald ein anderer Job das SDR braucht')}
/>

<div class="mb-4 flex flex-wrap gap-2" aria-label={t('Bänder')}>
  {#each [...VHF_BANDS, ...CW_BANDS] as b (b.id)}
    <button class="chip" type="button" onclick={() => band(b)}
      >{b.id === 'air' ? t('Flugfunk') : b.label}</button
    >
  {/each}
</div>

{#if !sessionId || ended}
  <form
    class="card space-y-4"
    onsubmit={(e) => {
      e.preventDefault();
      void start();
    }}
  >
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <FrequencyField bind:value={centre} label={t('Mittenfrequenz')} />
      <div>
        <label class="label" for="span">{t('Bandbreite')}</label>
        <select id="span" class="input" bind:value={span}>
          {#each spans as s (s)}<option value={s}>{(s / 1e6).toFixed(3)} MHz</option>{/each}
        </select>
      </div>
      <div>
        <label class="label" for="sgain">{t('Verstärkung (dB)')}</label>
        <input id="sgain" class="input" type="number" min="0" max="76" bind:value={gain} />
      </div>
      <div>
        <label class="label" for="fft">{t('FFT-Grösse')}</label>
        <select id="fft" class="input" bind:value={fftSize}>
          <option value={1024}>1024</option><option value={2048}>2048</option><option value={4096}
            >4096</option
          >
        </select>
      </div>
    </div>
    <button class="btn-primary" type="submit" disabled={busy || sdr.busy}>
      <Play size={16} />
      {t('Wasserfall starten')}
    </button>
    {#if others.length}
      <div class="flex flex-wrap items-center gap-2 text-sm">
        <span class="text-slate-500">{t('Laufende Session ansehen:')}</span>
        {#each others as s (s.session_id)}
          <button class="chip" type="button" onclick={() => attach(s.session_id)}>
            {s.mode.toUpperCase()} · {mhz(s.frequency)}
          </button>
        {/each}
      </div>
    {/if}
  </form>
  {#if ended}
    <p
      class="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
    >
      {t('Wasserfall beendet: {reason}', { reason: ended })}
    </p>
  {/if}
{/if}

{#if sessionId}
  <div class="mt-4 space-y-3">
    {#if !ended}<SessionCard {sessionId} showCount={false} />{/if}

    <Waterfall
      bind:this={waterfall}
      channel={tunable ? (info?.channel ?? null) : null}
      channelWidth={modulation === 'CW' ? cwBandwidth : WIDTHS[modulation]}
      {markers}
      colormapName={colours}
      {auto}
      bind:lo
      bind:hi
      onpick={pick}
      onretune={(c) => void tune({ centre: c })}
    />

    <div class="card grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div>
        <span class="label">{t('Anzeige')}</span>
        <div class="flex items-center gap-3 text-sm">
          <select class="input" bind:value={colours} aria-label={t('Farben')}>
            <option value="classic">{t('Farbig')}</option>
            <option value="grey">{t('Graustufen')}</option>
          </select>
          <label class="flex items-center gap-1 whitespace-nowrap">
            <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={auto} />
            {t('Auto-Pegel')}
          </label>
        </div>
      </div>
      <div>
        <label class="label" for="lo">{t('Pegel {lo} … {hi} dB', { lo, hi })}</label>
        <div class="flex gap-2">
          <input id="lo" type="range" min="-140" max="-20" bind:value={lo} disabled={auto} class="w-full" />
          <input type="range" min="-120" max="0" bind:value={hi} disabled={auto} class="w-full" />
        </div>
      </div>
      <div class="text-sm">
        <span class="label">{t('Status')}</span>
        {#if info}
          <span class="font-mono">{mhz(info.centre)} ± {(info.span / 2e6).toFixed(3)} MHz</span>
          <span class="ml-2 text-xs text-slate-500">{connection === 'open' ? '● live' : connection}</span>
        {:else}
          {t('verbinde…')}
        {/if}
      </div>
      {#if !tunable && info}
        <p class="text-sm text-slate-500">
          {t('Spektrum einer laufenden {mode}-Session — nur ansehen, Abstimmen auf deren Seite.', {
            mode: info.mode.toUpperCase(),
          })}
        </p>
      {/if}
    </div>

    {#if tunable && !ended}
      <section class="card space-y-4">
        <div class="flex flex-wrap items-center gap-4">
          <h2 class="text-sm font-semibold">{t('Mithören')}</h2>
          <span class="font-mono text-sm">{mhz(info?.channel)}</span>
          <button class={listen ? 'btn-secondary' : 'btn-primary'} type="button" onclick={toggleListen}>
            {#if listen}<VolumeX size={16} /> {t('Stumm')}{:else}<Headphones size={16} /> {t('Hören')}{/if}
          </button>
          <button class="btn-secondary" type="button" onclick={() => openWith('voice')}
            ><Mic size={16} /> {t('Aufnehmen')}</button
          >
          <button class="btn-secondary" type="button" onclick={() => openWith('vox')}
            ><Radio size={16} /> {t('VOX starten')}</button
          >
          {#if hasCw}
            <button class="btn-secondary" type="button" onclick={() => openWith('cw')}
              ><AudioWaveform size={16} /> {t('CW dekodieren')}</button
            >
          {/if}
        </div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label class="label" for="lmod">Modulation</label>
            <select
              id="lmod"
              class="input"
              bind:value={modulation}
              onchange={() => void tune({ modulation })}
            >
              <option>FM</option><option>AM</option><option>USB</option><option>LSB</option><option>CW</option
              >
            </select>
          </div>
          {#if modulation === 'CW'}
            <div>
              <label class="label" for="cwbw">{t('CW-Filter')}</label>
              <select
                id="cwbw"
                class="input"
                bind:value={cwBandwidth}
                onchange={() => void tune({ cw_bandwidth: cwBandwidth })}
              >
                <option value={250}>250 Hz</option><option value={500}>500 Hz</option><option value={1000}
                  >1000 Hz</option
                >
              </select>
            </div>
          {/if}
          <div>
            <label class="label" for="vol">{t('Lautstärke')}</label>
            <input id="vol" type="range" min="0" max="1.5" step="0.05" bind:value={volume} class="w-full" />
          </div>
          <div>
            <label class="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                class="h-4 w-4 accent-cyan-500"
                bind:checked={squelchOn}
                onchange={() => void tune(squelchOn ? { squelch_db: squelch } : { squelch_off: true })}
              />
              {t('Squelch: {n} dB über Rauschen', { n: squelch })}
            </label>
            <input
              type="range"
              min="3"
              max="40"
              bind:value={squelch}
              disabled={!squelchOn}
              onchange={() => void tune({ squelch_db: squelch })}
              class="w-full accent-cyan-500"
            />
          </div>
        </div>
        <p class="hint">
          {t(
            'Klick in den Wasserfall stimmt den Kanal ab, Ziehen verschiebt die Mitte, Umschalt-Klick öffnet den CW-Decoder.',
          )}
        </p>
      </section>
    {/if}
  </div>
{/if}
