<script lang="ts">
  import { onDestroy } from 'svelte';
  import { Headphones, Play, VolumeX } from '@lucide/svelte';
  import { api } from '../lib/api';
  import { CW_BANDS, NCDXF_BEACONS, cwBandOf, type Band } from '../lib/bands';
  import AudioPlayer from '../lib/components/AudioPlayer.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import RbnSpots from '../lib/components/RbnSpots.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import Waterfall, { type Marker } from '../lib/components/Waterfall.svelte';
  import { mhz, time } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { router } from '../lib/router.svelte';
  import {
    connectSpectrum,
    type Frame,
    type SpectrumConnection,
    type SpectrumState,
  } from '../lib/spectrum/frames';
  import { LivePlayer } from '../lib/spectrum/player';
  import { live, sdr, settings, toasts } from '../lib/stores.svelte';
  import type { RbnSpot } from '../lib/types';

  interface Transmission {
    uuid: string;
    timestamp: string;
    frequency: number;
    text: string;
    callsigns: string[];
    wpm: number;
    snr_db: number;
    audio_file?: string;
  }

  interface CwState extends SpectrumState {
    wpm?: number;
    snr_db?: number;
    afc_hz?: number;
    tone_hz?: number;
  }

  let frequency = $state(Number(router.params.get('f')) || 14_025_000);
  let gain = $state(30);
  let wpm = $state(20);
  let bandwidth = $state(200);
  let tone = $state(700);
  let record = $state(false);
  let hours = $state(1);

  let sessionId = $state<string | null>(null);
  let info = $state<CwState | null>(null);
  let busy = $state(false);
  let listen = $state(false);
  let volume = $state(0.7);
  let text = $state('');
  let transmissions = $state<Transmission[]>([]);
  let selected = $state<string | null>(null);
  let picked = $state<number | null>(null);
  let rbnBand = $state('20m'); // follows the receiver frequency (effect below)

  let waterfall: Waterfall | undefined = $state();
  let stream: SpectrumConnection | null = null;
  const player = new LivePlayer();

  const receiving = $derived(info?.channel ?? frequency);
  const markers = $derived<Marker[]>(
    NCDXF_BEACONS.map((f) => ({ frequency: f, label: 'NCDXF', kind: 'bookmark' as const })),
  );

  // resume a running CW session (reload, or started from the waterfall page)
  $effect(() => {
    const active = sdr.status?.active_sessions.find((s) => s.mode === 'cw');
    if (active && !sessionId) attach(active.session_id);
  });

  // keep the RBN window on the band of the receiver
  $effect(() => {
    const b = cwBandOf(receiving);
    if (b) rbnBand = b.id;
  });

  $effect(() =>
    live.on(['cw'], (e) => {
      const d = e.data as { session_id?: string; state: string; text?: string } & Partial<Transmission>;
      if (sessionId && d.session_id && d.session_id !== sessionId) return;
      if (d.state === 'text' && d.text) text = (text + d.text).slice(-3000);
      if (d.state === 'transmission' && d.uuid) {
        transmissions = [d as Transmission, ...transmissions].slice(0, 100);
        text += '\n';
      }
    }),
  );

  $effect(() => {
    api
      .get<{ transmissions: Transmission[] }>('/cw/transmissions', { hours: 24, limit: 50 })
      .then((r) => (transmissions = r.transmissions))
      .catch(() => {});
  });

  onDestroy(() => {
    stream?.close();
    void player.stop();
  });

  $effect(() => player.setVolume(volume));

  function onFrame(frame: Frame) {
    if (frame.kind === 'spectrum') waterfall?.addRow(frame.row);
    else if (frame.kind === 'audio') player.push(frame.audio.pcm, frame.audio.rate);
    else if (frame.data.state) info = frame.data.state as CwState;
    else if (frame.data.end) {
      info = null;
      sessionId = null;
      stream?.close();
      void sdr.refresh();
    }
  }

  function connect() {
    stream?.close();
    if (sessionId) stream = connectSpectrum(sessionId, listen, onFrame);
  }

  function attach(id: string) {
    sessionId = id;
    text = '';
    waterfall?.clear();
    connect();
  }

  async function start(at = frequency) {
    busy = true;
    try {
      const r = await api.post<{ session_id: string }>('/cw/start', {
        frequency: at,
        gain,
        wpm,
        cw_bandwidth: bandwidth,
        tone_hz: tone,
        record,
        duration: Math.round(hours * 3600),
        ...settings.deviceParams(),
      });
      frequency = at;
      attach(r.session_id);
      toasts.push(t('CW-Decoder gestartet'), 'success');
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  async function tune(channel: number) {
    if (!sessionId) return;
    try {
      const r = await api.post<{ state: CwState }>(`/cw/${sessionId}/tune`, { channel });
      info = { ...info, ...r.state };
      frequency = channel;
      player.reset();
      text += `\n— ${mhz(channel, 4)} —\n`;
    } catch (e) {
      toasts.error(e);
    }
  }

  /** Stop the job holding the SDR (after asking) so the CW decoder can start. */
  async function freeSdr(): Promise<boolean> {
    await sdr.refresh();
    if (!sdr.busy) return true;
    const kind = sdr.status?.holder?.kind ?? '?';
    const blocking = sdr.status?.active_sessions.filter((s) => s.mode !== 'spectrum') ?? [];
    if (!blocking.length) {
      toasts.push(
        t('SDR belegt durch {kind} — dieser Job lässt sich hier nicht stoppen.', { kind }),
        'error',
      );
      return false;
    }
    if (!confirm(t('Das SDR wird gerade von {kind} benutzt. Stoppen und auf CW umschalten?', { kind })))
      return false;
    for (const s of blocking) await api.del(`/stream-decode/${s.session_id}`).catch(() => {});
    for (let i = 0; i < 40; i++) {
      await new Promise((r) => setTimeout(r, 500));
      await sdr.refresh();
      if (!sdr.busy) return true;
    }
    toasts.push(t('Das SDR wurde nicht rechtzeitig frei.'), 'error');
    return false;
  }

  /** Click on an RBN spot: put the receiver on its frequency right away. */
  async function pickSpot(spot: RbnSpot) {
    picked = spot.frequency;
    if (sessionId) return tune(spot.frequency);
    frequency = spot.frequency;
    if (await freeSdr()) await start(spot.frequency);
  }

  function pickBand(b: Band) {
    const f = Math.round(b.start + 25_000);
    rbnBand = b.id;
    if (sessionId) void tune(f);
    else frequency = f;
  }

  function pick(f: number) {
    if (sessionId) void tune(f);
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
</script>

<PageHeader
  title="CW"
  description={t(
    'Morse live dekodieren — Kurzwelle mit RBN-Spots, ein Klick auf einen Spot stimmt den Empfänger ab',
  )}
/>

<div class="mb-4 flex flex-wrap gap-2" aria-label={t('Bänder')}>
  {#each CW_BANDS as b (b.id)}
    <button class="chip" type="button" onclick={() => pickBand(b)}>{b.label}</button>
  {/each}
</div>

<div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
  <div class="space-y-4 xl:col-span-2">
    {#if !sessionId}
      <form
        class="card space-y-4"
        onsubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <FrequencyField bind:value={frequency} />
          <div>
            <label class="label" for="cgain">{t('Verstärkung (dB)')}</label>
            <input id="cgain" class="input" type="number" min="0" max="76" bind:value={gain} />
          </div>
          <div>
            <label class="label" for="cwpm">{t('Erwartetes Tempo (WPM)')}</label>
            <input id="cwpm" class="input" type="number" min="5" max="60" bind:value={wpm} />
            <p class="hint">{t('Der Decoder passt sich an')}</p>
          </div>
          <div>
            <label class="label" for="cbw">{t('Decoder-Filter')}</label>
            <select id="cbw" class="input" bind:value={bandwidth}>
              <option value={100}>100 Hz</option><option value={200}>200 Hz</option><option value={300}
                >300 Hz</option
              ><option value={500}>500 Hz</option>
            </select>
          </div>
          <div>
            <label class="label" for="ctone">{t('Tonhöhe beim Mithören (Hz)')}</label>
            <input id="ctone" class="input" type="number" min="300" max="1200" step="10" bind:value={tone} />
          </div>
          <div>
            <label class="label" for="chours">{t('Laufzeit (Stunden)')}</label>
            <input id="chours" class="input" type="number" min="0.5" max="24" step="0.5" bind:value={hours} />
          </div>
          <label class="flex items-center gap-2 self-end pb-2 text-sm">
            <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={record} />
            {t('Durchgänge als WAV speichern')}
          </label>
        </div>
        <button class="btn-primary" type="submit" disabled={busy || sdr.busy}
          ><Play size={16} /> {t('CW-Decoder starten')}</button
        >
      </form>
    {:else}
      <SessionCard {sessionId} countLabel={t('Durchgänge')} />
      <div class="card flex flex-wrap items-center gap-6 text-sm">
        <div>
          <span class="text-slate-500">{t('Empfänger')}</span>
          <span class="font-mono">{mhz(info?.channel)}</span>
        </div>
        <div><span class="text-slate-500">WPM</span> <span class="font-mono">{info?.wpm ?? '–'}</span></div>
        <div>
          <span class="text-slate-500">SNR</span> <span class="font-mono">{info?.snr_db ?? '–'} dB</span>
        </div>
        <div>
          <span class="text-slate-500">AFC</span> <span class="font-mono">{info?.afc_hz ?? 0} Hz</span>
        </div>
        <button class={listen ? 'btn-secondary' : 'btn-primary'} type="button" onclick={toggleListen}>
          {#if listen}<VolumeX size={16} /> {t('Stumm')}{:else}<Headphones size={16} /> {t('Mithören')}{/if}
        </button>
        <input
          type="range"
          min="0"
          max="1.5"
          step="0.05"
          bind:value={volume}
          aria-label={t('Lautstärke')}
          class="w-28"
        />
      </div>
    {/if}

    <section class="card">
      <h2 class="mb-2 text-sm font-semibold">{t('Dekodierter Text')}</h2>
      <pre
        class="h-48 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-sm whitespace-pre-wrap text-emerald-300"
        aria-live="polite">{text || t('Noch kein Text.')}</pre>
    </section>

    {#if sessionId}
      <Waterfall
        bind:this={waterfall}
        channel={info?.channel ?? null}
        channelWidth={bandwidth}
        {markers}
        onpick={pick}
        onretune={(c) => void tune(c)}
      />
    {/if}

    <section class="card">
      <h2 class="mb-3 text-sm font-semibold">{t('Durchgänge (24 h)')}</h2>
      {#if transmissions.length}
        <ul class="divide-y divide-slate-100 dark:divide-slate-800">
          {#each transmissions as tx (tx.uuid)}
            <li class="py-2">
              <button
                class="flex w-full flex-wrap items-baseline gap-3 text-left text-sm"
                onclick={() => (selected = selected === tx.uuid ? null : tx.uuid)}
              >
                <span class="font-mono text-xs text-slate-500">{time(tx.timestamp)}</span>
                <span class="font-mono text-xs">{mhz(tx.frequency, 4)}</span>
                <span class="font-mono text-xs">{tx.wpm} WPM</span>
                {#each tx.callsigns as c (c)}<span class="chip">{c}</span>{/each}
                <span class="flex-1 font-mono">{tx.text}</span>
              </button>
              {#if selected === tx.uuid && tx.audio_file}
                <div class="mt-2"><AudioPlayer filename={tx.audio_file} /></div>
              {/if}
            </li>
          {/each}
        </ul>
      {:else}
        <EmptyState text={t('Noch keine Durchgänge.')} />
      {/if}
    </section>
  </div>

  <div class="space-y-4">
    <RbnSpots bind:band={rbnBand} frequency={receiving} selected={picked} onpick={pickSpot} />
    <p class="hint">
      {t(
        'Kurzwelle braucht ein KW-taugliches SDR und eine KW-Antenne (siehe Hardware-Doku). NCDXF-Baken (violett) eignen sich als Testsignal.',
      )}
    </p>
  </div>
</div>
