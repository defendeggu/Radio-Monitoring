<script lang="ts">
  import { onDestroy } from 'svelte';
  import { BookOpen, Play, RefreshCw, Trash2, Upload } from '@lucide/svelte';
  import { api } from '../lib/api';
  import { CW_BANDS, VHF_CW_BANDS } from '../lib/bands';
  import { SSB_BAND_IDS, TONES, markerKind, tags, type ContestRules, type SkimmerSpot } from '../lib/contest';
  import DeviceSelect from '../lib/components/DeviceSelect.svelte';
  import AudioPlayer from '../lib/components/AudioPlayer.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import Waterfall, { type Marker } from '../lib/components/Waterfall.svelte';
  import { dateTime } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { router } from '../lib/router.svelte';
  import {
    connectSpectrum,
    type Frame,
    type SpectrumConnection,
    type SpectrumState,
  } from '../lib/spectrum/frames';
  import { routes } from './index';
  import { live, sdr, settings, toasts } from '../lib/stores.svelte';

  interface Decoder {
    frequency: number;
    wpm: number | null;
    snr_db: number | null;
    callsign: string | null;
    text: string;
    sideband?: string;
  }

  interface SkimmerState extends SpectrumState {
    freq_low?: number;
    freq_high?: number;
    contest?: string;
    decoders?: Decoder[];
    blanked?: boolean;
    blanked_seconds?: number;
    spots?: number;
    recording?: { file: string; seconds: number; active: boolean; stopped: string | null } | null;
    skimmer_mode?: 'CW' | 'SSB';
    transcriber?: {
      pending: number;
      done: number;
      dropped: number;
      failed: number;
      busy: boolean;
      mean_seconds: number | null;
    } | null;
    transcripts?: { frequency: number; text: string; time: number }[] | null;
  }

  interface FileInfo {
    updated: string;
    bytes: number;
  }

  interface Status {
    contest: ContestRules;
    refdata: { entities: number; scp_calls: number; most_wanted: number; files: Record<string, FileInfo> };
    worked: { qsos: number; by_band: Record<string, number>; sources: string[] };
    n1mm: {
      enabled: boolean;
      listening: boolean;
      port: number;
      last_packet?: number;
      packets?: number;
      radios: { station: string; radio: string; freq_khz: number | null; transmitting: boolean }[];
    };
    cluster: {
      enabled: boolean;
      listening: boolean;
      port: number;
      clients: { call: string; address: string }[];
    };
  }

  let contests = $state<ContestRules[]>([]);
  let active = $state('general');
  let status = $state<Status | null>(null);
  let spots = $state<SkimmerSpot[]>([]);
  let priorityFilter = $state<'' | 'high' | 'normal' | 'dupe'>('');
  let bandFilter = $state('');

  let band = $state('20m');
  let mode = $state<'CW' | 'SSB'>('CW');
  let language = $state('en');
  let selected = $state<string | null>(null);
  let decoders = $state(24);
  let gain = $state(30);
  let deviceId = $state(''); // SDR for this start ('' = from the settings)
  let hours = $state(0);
  let recordIq = $state(false);
  let includeRbn = $state(false);
  let busy = $state(false);
  let updating = $state(false);
  let replaceLog = $state(true);

  let sessionId = $state<string | null>(null);
  let info = $state<SkimmerState | null>(null);
  let waterfall: Waterfall | undefined = $state();
  let stream: SpectrumConnection | null = null;

  const hasCw = routes.some((r) => r.path === 'cw');
  const rules = $derived(contests.find((c) => c.id === active) ?? status?.contest ?? null);
  const ALL_BANDS = [...CW_BANDS, ...VHF_CW_BANDS];
  // only the bands of the selected contest (all HF and VHF CW segments when it names none)
  const contestBands = $derived(
    (rules?.bands.length ? ALL_BANDS.filter((b) => rules!.bands.includes(b.id)) : ALL_BANDS).filter(
      (b) => mode === 'CW' || SSB_BAND_IDS.includes(b.id),
    ),
  );
  const modes = $derived((rules?.modes.length ? rules.modes : ['CW', 'SSB']) as ('CW' | 'SSB')[]);
  $effect(() => {
    if (modes.length && !modes.includes(mode)) mode = modes[0];
  });
  $effect(() => {
    if (contestBands.length && !contestBands.some((b) => b.id === band)) band = contestBands[0].id;
  });
  const shown = $derived(
    spots.filter(
      (s) => (!priorityFilter || s.priority === priorityFilter) && (!bandFilter || s.band === bandFilter),
    ),
  );
  const markers = $derived<Marker[]>(
    info?.freq_low
      ? spots
          .filter((s) => s.frequency >= info!.freq_low! && s.frequency <= info!.freq_high!)
          .map((s) => ({ frequency: s.frequency, label: s.callsign, kind: markerKind(s) }))
      : [],
  );

  async function loadStatus() {
    try {
      status = await api.get<Status>('/contest/status');
    } catch {
      status = null;
    }
  }

  async function loadSpots() {
    try {
      spots = (await api.get<{ spots: SkimmerSpot[] }>('/skimmer/spots', { max_age: 30 })).spots;
    } catch {
      spots = [];
    }
  }

  $effect(() => {
    api
      .get<{ active: string; contests: ContestRules[] }>('/contest/contests')
      .then((r) => {
        contests = r.contests;
        active = r.active;
      })
      .catch(() => {});
    void loadStatus();
    void loadSpots();
    const timers = [setInterval(loadStatus, 10_000), setInterval(loadSpots, 5_000)];
    return () => timers.forEach(clearInterval);
  });

  // new spots arrive as live events; reload the (merged, classified) list
  let pending: ReturnType<typeof setTimeout> | null = null;
  $effect(() =>
    live.on(['skimmer'], () => {
      if (!pending) pending = setTimeout(() => ((pending = null), void loadSpots()), 500);
    }),
  );

  // running skimmers (several can run on several SDRs); resume one after a reload
  let starting = $state(false); // form for another skimmer while one is shown
  const skimmers = $derived((sdr.status?.active_sessions ?? []).filter((s) => s.mode === 'skimmer'));
  $effect(() => {
    if (skimmers.length && !sessionId && !starting) attach(skimmers[0].session_id);
  });

  onDestroy(() => stream?.close());

  function onFrame(frame: Frame) {
    if (frame.kind === 'spectrum') waterfall?.addRow(frame.row);
    else if (frame.kind === 'json' && frame.data.state) info = frame.data.state as SkimmerState;
    else if (frame.kind === 'json' && frame.data.end) {
      info = null;
      sessionId = null;
      stream?.close();
      void sdr.refresh();
    }
  }

  function attach(id: string) {
    sessionId = id;
    waterfall?.clear();
    stream?.close();
    stream = connectSpectrum(id, false, onFrame);
  }

  async function selectContest() {
    try {
      await api.put('/contest/active', { contest: active });
      toasts.push(t('Contest gewählt: {name}', { name: rules?.name ?? active }), 'success');
      await Promise.all([loadStatus(), loadSpots()]);
    } catch (e) {
      toasts.error(e);
    }
  }

  async function start() {
    busy = true;
    try {
      const r = await api.post<{ session_id: string }>('/skimmer/start', {
        band,
        mode,
        ...(mode === 'SSB' ? { language: language || null } : {}),
        contest: active,
        max_decoders: mode === 'SSB' ? Math.min(decoders, 16) : decoders,
        gain,
        record_iq: recordIq,
        include_rbn: includeRbn,
        duration: Math.round(hours * 3600),
        ...settings.deviceParams(deviceId),
      });
      starting = false;
      attach(r.session_id);
      toasts.push(t('Skimmer gestartet'), 'success');
      void sdr.refresh();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  async function updateRefdata() {
    updating = true;
    try {
      const r = await api.post<{ files: Record<string, { ok: boolean; error?: string }> }>(
        '/contest/refdata/update',
      );
      const failed = Object.entries(r.files).filter(([, v]) => !v.ok);
      if (failed.length)
        toasts.push(t('Nicht aktualisiert: {files}', { files: failed.map(([k]) => k).join(', ') }), 'error');
      else toasts.push(t('Referenzdaten aktualisiert'), 'success');
      await loadStatus();
    } catch (e) {
      toasts.error(e);
    } finally {
      updating = false;
    }
  }

  async function importLog(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = '';
    if (!file) return;
    try {
      const r = await api.post<{ imported: number }>('/contest/worked/import', {
        text: await file.text(),
        replace: replaceLog,
      });
      toasts.push(t('{n} QSOs importiert', { n: r.imported }), 'success');
      await Promise.all([loadStatus(), loadSpots()]);
    } catch (e) {
      toasts.error(e);
    }
  }

  async function clearLog() {
    if (!confirm(t('Log der gearbeiteten Stationen löschen?'))) return;
    try {
      await api.del('/contest/worked');
      await Promise.all([loadStatus(), loadSpots()]);
    } catch (e) {
      toasts.error(e);
    }
  }

  function age(seconds: number): string {
    return seconds < 60 ? `${seconds}s` : `${Math.floor(seconds / 60)}m`;
  }

  const key = (s: SkimmerSpot) => s.callsign + s.khz;

  function toggle(spot: SkimmerSpot) {
    selected = selected === key(spot) ? null : key(spot);
  }

  function open(spot: SkimmerSpot) {
    if (hasCw) router.go('cw', { f: spot.frequency });
  }

  const fileLabels: Record<string, string> = {
    'cty.csv': 'cty.csv',
    'MASTER.SCP': 'MASTER.SCP',
    'mostwanted.json': 'Most Wanted',
  };
</script>

<PageHeader
  title={t('Contest-Skimmer')}
  description={t(
    'Alle CW-Signale eines Bandsegments gleichzeitig dekodieren, Multiplikatoren und seltene Stationen melden — auch in die N1MM+-Bandmap',
  )}
/>

<div class="grid grid-cols-1 gap-4 xl:grid-cols-3">
  <div class="space-y-4 xl:col-span-2">
    <section class="card space-y-3">
      <div class="flex flex-wrap items-end gap-3">
        <div class="min-w-64 flex-1">
          <label class="label" for="contest">{t('Contest')}</label>
          <select id="contest" class="input" bind:value={active} onchange={selectContest}>
            {#each contests as c (c.id)}<option value={c.id}>{c.name}</option>{/each}
          </select>
        </div>
        {#if rules?.url}
          <a
            class="pb-2 text-sm text-cyan-600 hover:underline"
            href={rules.url}
            target="_blank"
            rel="noopener noreferrer">{t('Reglement')}</a
          >
        {/if}
      </div>
      {#if rules}
        <p class="text-sm text-slate-600 dark:text-slate-300">
          {rules.modes.join(' / ')} · {rules.bands.join(' ')} ·
          {t('Multiplikatoren')}: {rules.multipliers.length
            ? rules.multipliers.map((m) => `${m.type} (${m.per})`).join(', ')
            : t('keine')} · {t('Doppelte')}: {rules.dupe}
        </p>
        {#if rules.when}<p class="text-sm">
            <span class="text-slate-500">{t('Termin')}:</span>
            {rules.when}
          </p>{/if}
        {#if rules.notes}<p class="hint">{rules.notes}</p>{/if}
        {#if rules.assistance}
          <p
            class="rounded-lg bg-amber-50 p-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
          >
            {rules.assistance}
          </p>
        {/if}
      {/if}
    </section>

    {#if skimmers.length > 1 || (sessionId && sdr.devices.length > 1)}
      <div class="flex flex-wrap items-center gap-2" role="tablist" aria-label={t('Laufende Skimmer')}>
        {#each skimmers as s (s.session_id)}
          <button
            class="chip {s.session_id === sessionId && !starting ? 'ring-2 ring-cyan-500' : ''}"
            type="button"
            role="tab"
            aria-selected={s.session_id === sessionId && !starting}
            onclick={() => ((starting = false), attach(s.session_id))}
            >{(s.frequency / 1e6).toFixed(3)} MHz{s.device_label ? ` · ${s.device_label}` : ''}</button
          >
        {/each}
        {#if sdr.devices.length > 1}
          <button class="chip" type="button" aria-pressed={starting} onclick={() => (starting = true)}
            >+ {t('Weiteren Skimmer starten')}</button
          >
        {/if}
      </div>
    {/if}
    {#if !sessionId || starting}
      <form
        class="card space-y-4"
        onsubmit={(e) => {
          e.preventDefault();
          void start();
        }}
      >
        <div>
          <span class="label">{t('Betriebsart')}</span>
          <div class="flex flex-wrap gap-2">
            {#each modes as m (m)}
              <button
                class="chip {mode === m ? 'ring-2 ring-cyan-500' : ''}"
                type="button"
                aria-pressed={mode === m}
                onclick={() => (mode = m)}>{m}</button
              >
            {/each}
          </div>
          {#if mode === 'SSB'}
            <p
              class="mt-2 rounded-lg bg-amber-50 p-2 text-sm text-amber-800 dark:bg-amber-950/40 dark:text-amber-200"
            >
              {t(
                'SSB ist experimentell: Whisper hört die Sprachkanäle ab, der Phonetik-Parser liest die Rufzeichen. Auf der CPU reicht das für wenige Kanäle; jeder Spot hat einen Ausschnitt zum Nachhören.',
              )}
            </p>
          {/if}
        </div>
        <div>
          <span class="label">{mode === 'SSB' ? t('Band (SSB-Segment)') : t('Band (CW-Segment)')}</span>
          <div class="flex flex-wrap gap-2">
            {#each contestBands as b (b.id)}
              <button
                class="chip {band === b.id ? 'ring-2 ring-cyan-500' : ''}"
                type="button"
                aria-pressed={band === b.id}
                onclick={() => (band = b.id)}>{b.label}</button
              >
            {/each}
          </div>
        </div>
        <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <label class="label" for="sdec">{t('Decoder gleichzeitig')}</label>
            <input id="sdec" class="input" type="number" min="1" max="64" bind:value={decoders} />
          </div>
          {#if mode === 'SSB'}
            <div>
              <label class="label" for="slang">{t('Sprache (Whisper)')}</label>
              <select id="slang" class="input" bind:value={language}>
                <option value="en">{t('Englisch')}</option>
                <option value="de">{t('Deutsch')}</option>
                <option value="fr">{t('Französisch')}</option>
                <option value="it">{t('Italienisch')}</option>
                <option value="">{t('automatisch')}</option>
              </select>
            </div>
          {/if}
          <DeviceSelect bind:value={deviceId} />
          <div>
            <label class="label" for="sgain">{t('Verstärkung (dB)')}</label>
            <input id="sgain" class="input" type="number" min="0" max="76" bind:value={gain} />
          </div>
          <div>
            <label class="label" for="shours">{t('Laufzeit (Stunden)')}</label>
            <input id="shours" class="input" type="number" min="0" max="72" step="1" bind:value={hours} />
            <p class="hint">{t('0 = bis zum Stoppen')}</p>
          </div>
        </div>
        <div class="flex flex-col gap-2 text-sm">
          <label class="flex items-center gap-2">
            <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={recordIq} />
            {t('IQ des Segments aufnehmen (für die Auswertung, ca. 1,4 GB pro Stunde)')}
          </label>
          <label class="flex items-center gap-2">
            <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={includeRbn} />
            {t('RBN-Spots der Contest-Bänder dazunehmen (nur wenn die Kategorie Hilfe erlaubt)')}
          </label>
        </div>
        <button class="btn-primary" type="submit" disabled={busy || sdr.busyFor(deviceId)}
          ><Play size={16} /> {t('Skimmer starten')}</button
        >
      </form>
    {:else}
      <SessionCard {sessionId} countLabel={t('Spots')} />
      <div class="card flex flex-wrap items-center gap-6 text-sm">
        <div>
          <span class="text-slate-500">{t('Segment')}</span>
          <span class="font-mono"
            >{info?.freq_low ? `${info.freq_low / 1000}–${info.freq_high! / 1000} kHz` : '–'}</span
          >
        </div>
        <div>
          <span class="text-slate-500">{t('Decoder')}</span>
          <span class="font-mono">{info?.decoders?.length ?? 0}</span>
        </div>
        <div>
          <span class="text-slate-500">{t('Ausgeblendet')}</span>
          <span class="font-mono {info?.blanked ? 'text-red-600' : ''}"
            >{info?.blanked ? t('jetzt') : `${info?.blanked_seconds ?? 0} s`}</span
          >
        </div>
        {#if info?.transcriber}
          <div>
            <span class="text-slate-500">Whisper</span>
            <span class="font-mono"
              >{t('{d} fertig, {p} wartend, {x} verworfen', {
                d: info.transcriber.done,
                p: info.transcriber.pending,
                x: info.transcriber.dropped,
              })}{info.transcriber.mean_seconds !== null
                ? ` · Ø ${info.transcriber.mean_seconds} s`
                : ''}</span
            >
          </div>
        {/if}
        {#if info?.recording}
          <div>
            <span class="text-slate-500">{t('IQ-Aufnahme')}</span>
            <span class="font-mono"
              >{info.recording.file} ({Math.round(info.recording.seconds / 60)} min)</span
            >
            {#if info.recording.stopped}<span class="text-red-600"> · {info.recording.stopped}</span>{/if}
          </div>
        {/if}
      </div>
      <Waterfall bind:this={waterfall} {markers} onpick={(f) => hasCw && router.go('cw', { f })} />
      {#if info?.decoders?.length}
        <section class="card">
          <h2 class="mb-2 text-sm font-semibold">{t('Aktive Decoder')}</h2>
          <ul class="grid grid-cols-1 gap-x-6 gap-y-1 font-mono text-xs sm:grid-cols-2">
            {#each info.decoders as d (d.frequency)}
              <li class="flex gap-2">
                <span class="w-20 text-right">{(d.frequency / 1000).toFixed(1)}</span>
                <span class="w-14 text-slate-500">{d.sideband ?? `${d.wpm} WPM`}</span>
                <span class="w-20 font-semibold">{d.callsign ?? ''}</span>
                <span class="truncate text-emerald-600 dark:text-emerald-400">{d.text}</span>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
      {#if info?.transcripts?.length}
        <section class="card">
          <h2 class="mb-2 text-sm font-semibold">{t('Zuletzt gehört (Whisper)')}</h2>
          <ul class="space-y-1 text-sm">
            {#each info.transcripts as tr (tr.time + tr.frequency)}
              <li class="flex gap-3">
                <span class="w-20 shrink-0 text-right font-mono text-xs"
                  >{(tr.frequency / 1000).toFixed(1)}</span
                >
                <span class="text-slate-700 dark:text-slate-300">{tr.text}</span>
              </li>
            {/each}
          </ul>
        </section>
      {/if}
    {/if}

    <section class="card">
      <div class="mb-3 flex flex-wrap items-end gap-3">
        <h2 class="mr-auto text-sm font-semibold">{t('Spots (30 min)')}</h2>
        <div>
          <label class="label" for="spri">{t('Priorität')}</label>
          <select id="spri" class="input" bind:value={priorityFilter}>
            <option value="">{t('alle')}</option>
            <option value="high">{t('Multi / selten')}</option>
            <option value="normal">{t('neu')}</option>
            <option value="dupe">{t('Doppelte')}</option>
          </select>
        </div>
        <div>
          <label class="label" for="sband">{t('Band')}</label>
          <select id="sband" class="input" bind:value={bandFilter}>
            <option value="">{t('alle')}</option>
            {#each ALL_BANDS as b (b.id)}<option value={b.id}>{b.label}</option>{/each}
          </select>
        </div>
      </div>
      {#if shown.length}
        <div class="max-h-[32rem] overflow-auto">
          <table class="w-full text-left text-sm">
            <thead class="sticky top-0 bg-white text-xs text-slate-500 dark:bg-slate-900">
              <tr>
                <th class="py-1 pr-2">{t('Alter')}</th>
                <th class="pr-2">kHz</th>
                <th class="pr-2">{t('Rufzeichen')}</th>
                <th class="pr-2">{t('Land')}</th>
                <th class="pr-2">WPM / Mode</th>
                <th class="pr-2">SNR</th>
                <th class="pr-2">{t('Hinweise')}</th>
                <th>{t('Quelle')}</th>
              </tr>
            </thead>
            <tbody>
              {#each shown as s (s.callsign + s.khz)}
                <tr
                  class="border-t border-slate-100 dark:border-slate-800 {s.priority === 'high'
                    ? 'font-semibold'
                    : s.priority === 'dupe'
                      ? 'text-slate-400'
                      : ''} {hasCw ? 'cursor-pointer hover:bg-cyan-50 dark:hover:bg-cyan-950/40' : ''}"
                  onclick={() => (s.mode === 'SSB' ? toggle(s) : open(s))}
                  title={s.mode === 'SSB'
                    ? t('Klick: gehörten Text und Ausschnitt zeigen')
                    : hasCw
                      ? t('Klick: auf der CW-Seite abhören')
                      : undefined}
                >
                  <td class="py-1 pr-2 font-mono text-xs text-slate-500">{age(s.age_seconds)}</td>
                  <td class="pr-2 font-mono">{s.khz.toFixed(1)}</td>
                  <td class="pr-2 font-mono">{s.callsign}</td>
                  <td class="pr-2 text-xs">{s.country ?? '–'}</td>
                  <td class="pr-2 font-mono">{s.wpm ?? s.mode}</td>
                  <td class="pr-2 font-mono">{s.snr_db}</td>
                  <td class="pr-2">
                    <span class="flex flex-wrap gap-1">
                      {#each tags(s, rules?.highlight ?? []) as tag (tag.label)}
                        <span class="rounded px-1.5 py-0.5 text-xs {TONES[tag.tone]}" title={tag.title}
                          >{tag.label}</span
                        >
                      {/each}
                    </span>
                  </td>
                  <td class="text-xs">{s.source === 'rbn' ? 'RBN' : t('eigener')}</td>
                </tr>
                {#if selected === key(s)}
                  <tr>
                    <td colspan="8" class="space-y-2 pb-3">
                      {#if s.text}<p class="text-sm italic">«{s.text}»</p>{/if}
                      {#if s.audio_file}<AudioPlayer filename={s.audio_file} />{/if}
                      <button
                        class="btn-secondary"
                        type="button"
                        onclick={() => router.go('spectrum', { f: s.frequency })}
                        >{t('Im Wasserfall mithören')}</button
                      >
                    </td>
                  </tr>
                {/if}
              {/each}
            </tbody>
          </table>
        </div>
      {:else}
        <EmptyState text={t('Noch keine Spots.')} />
      {/if}
    </section>
  </div>

  <div class="space-y-4">
    <section class="card space-y-2 text-sm">
      <div class="flex items-center">
        <h2 class="mr-auto font-semibold">{t('Referenzdaten')}</h2>
        <button class="btn-secondary" type="button" onclick={updateRefdata} disabled={updating}>
          <RefreshCw size={14} class={updating ? 'animate-spin' : ''} />
          {t('Aktualisieren')}
        </button>
      </div>
      {#if status}
        <ul class="space-y-1">
          {#each Object.entries(fileLabels) as [name, label] (name)}
            <li class="flex justify-between gap-2">
              <span>{label}</span>
              <span class="text-xs text-slate-500"
                >{status.refdata.files[name]
                  ? dateTime(status.refdata.files[name].updated)
                  : t('fehlt')}</span
              >
            </li>
          {/each}
        </ul>
        <p class="hint">
          {t('{e} Länder, {s} Rufzeichen in MASTER.SCP', {
            e: status.refdata.entities,
            s: status.refdata.scp_calls,
          })}
        </p>
        {#if !status.refdata.entities}
          <p class="text-xs text-amber-600">
            {t(
              'Ohne cty.csv werden Länder und Multiplikatoren nicht erkannt. Vor dem Contest einmal aktualisieren.',
            )}
          </p>
        {/if}
      {/if}
    </section>

    <section class="card space-y-2 text-sm">
      <div class="flex items-center">
        <h2 class="mr-auto font-semibold">{t('Gearbeitete Stationen')}</h2>
        <button class="btn-secondary" type="button" onclick={clearLog} aria-label={t('Log löschen')}
          ><Trash2 size={14} /></button
        >
      </div>
      {#if status}
        <p>
          {t('{n} QSOs', { n: status.worked.qsos })}
          {#if status.worked.qsos}
            <span class="text-xs text-slate-500"
              >· {Object.entries(status.worked.by_band)
                .map(([b, n]) => `${b} ${n}`)
                .join(' · ')}</span
            >
          {/if}
        </p>
      {/if}
      <label class="btn-secondary w-fit cursor-pointer">
        <Upload size={14} />
        {t('ADIF / Cabrillo importieren')}
        <input class="sr-only" type="file" accept=".adi,.adif,.log,.cbr,.txt" onchange={importLog} />
      </label>
      <label class="flex items-center gap-2 text-xs">
        <input type="checkbox" class="h-4 w-4 accent-cyan-500" bind:checked={replaceLog} />
        {t('Bisheriges Log ersetzen')}
      </label>
    </section>

    <section class="card space-y-2 text-sm">
      <h2 class="font-semibold">N1MM+</h2>
      {#if status?.n1mm.enabled}
        <p>
          {status.n1mm.listening
            ? t('empfängt auf UDP {port}', { port: status.n1mm.port })
            : t('nicht bereit')}
          {#if status.n1mm.last_packet}
            <span class="text-xs text-slate-500">· {t('{n} Pakete', { n: status.n1mm.packets ?? 0 })}</span>
          {/if}
        </p>
        {#each status.n1mm.radios as r (r.station + r.radio)}
          <p class="font-mono text-xs">
            {r.station} #{r.radio} · {r.freq_khz?.toFixed(1) ?? '–'} kHz
            {#if r.transmitting}<span class="text-red-600"> · TX</span>{/if}
          </p>
        {/each}
      {:else}
        <p class="hint">{t('Aus. N1MM_ENABLED=true in .env setzen (siehe docs/contest.md).')}</p>
      {/if}
    </section>

    <section class="card space-y-2 text-sm">
      <h2 class="font-semibold">{t('DX-Cluster für die Bandmap')}</h2>
      {#if status?.cluster.enabled}
        <p>
          {status.cluster.listening
            ? t('Telnet-Port {port}', { port: status.cluster.port })
            : t('nicht bereit')}
          · {t('{n} verbunden', { n: status.cluster.clients.length })}
        </p>
        {#each status.cluster.clients as c (c.address + c.call)}
          <p class="font-mono text-xs">{c.call} ({c.address})</p>
        {/each}
      {:else}
        <p class="hint">{t('Aus. CLUSTER_ENABLED=true in .env setzen (siehe docs/contest.md).')}</p>
      {/if}
      <a
        class="inline-flex items-center gap-1 text-xs text-cyan-600 hover:underline"
        href="https://github.com/defendeggu/Radio-Monitoring/blob/main/docs/contest.md"
        target="_blank"
        rel="noopener noreferrer"><BookOpen size={12} /> {t('Anleitung')}</a
      >
    </section>
  </div>
</div>
