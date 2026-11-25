<script lang="ts">
  import { Download, ExternalLink, Image as ImageIcon, Play, Square } from '@lucide/svelte';
  import { api, download, fetchBlobUrl } from '../lib/api';
  import DeviceSelect from '../lib/components/DeviceSelect.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import MapView, { type MapPoint } from '../lib/components/MapView.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import { mhz, packetTime, time } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { live, sdr, toasts } from '../lib/stores.svelte';
  import type { OnAirMessage, OnAirMode, OnAirStatus } from '../lib/types';

  const GROUPS: Record<string, () => string> = {
    aviation: () => t('Luftfahrt'),
    sondes: () => t('Radiosonden'),
    digital_voice: () => t('Digitalfunk'),
    satellites: () => t('Satelliten'),
    maritime: () => t('Seefunk'),
    lora: () => t('LoRa / Mesh'),
    broadcast: () => t('Rundfunk'),
    sensors: () => t('Sensoren / Pager'),
    other: () => t('Weitere'),
  };
  const groupLabel = (g: string) => (GROUPS[g] ?? GROUPS.other)();

  let status = $state<OnAirStatus | null>(null);
  let modeList = $state<OnAirMode[]>([]);
  let modeId = $state('acars');
  let frequency = $state(131_725_000);
  let gain = $state<number | null>(null);
  let hours = $state(1);
  let deviceId = $state('');
  let busy = $state(false);
  let messages = $state<OnAirMessage[]>([]);
  let family = $state('');
  let points = $state<MapPoint[]>([]);
  let images = $state<{ id: string; url: string; text: string; time: string }[]>([]);
  let telemetry = $state<Record<string, unknown> | null>(null);

  const mode = $derived(modeList.find((m) => m.id === modeId));
  const grouped = $derived(
    Object.keys(GROUPS)
      .map((g) => ({ group: g, modes: modeList.filter((m) => m.group === g) }))
      .filter((g) => g.modes.length),
  );
  const session = $derived(status?.sessions?.[0] ?? null);
  const families = $derived([...new Set(messages.map((m) => m.family))].sort());
  const shown = $derived(family ? messages.filter((m) => m.family === family) : messages);

  async function loadStatus() {
    try {
      status = await api.get<OnAirStatus>('/onair/status');
    } catch (e) {
      toasts.error(e);
    }
  }

  async function loadModes() {
    try {
      modeList = (await api.get<{ modes: OnAirMode[] }>('/onair/modes')).modes;
    } catch {
      modeList = [];
    }
  }

  async function loadMessages() {
    try {
      const r = await api.get<{ results: OnAirMessage[] }>('/onair/search', { hours: 24, limit: 500 });
      messages = r.results;
      void loadImages(r.results);
    } catch (e) {
      toasts.error(e);
    }
  }

  async function loadMap() {
    try {
      const r = await api.get<{
        features: {
          geometry: { type: string; coordinates: number[] };
          properties: Record<string, unknown>;
        }[];
      }>('/onair/map', { hours: 24 });
      points = r.features
        .filter((f) => f.geometry.type === 'Point')
        .map((f) => ({
          id: `${f.properties.family}:${f.properties.ident ?? f.properties.text}`,
          lat: f.geometry.coordinates[1],
          lon: f.geometry.coordinates[0],
          label: String(f.properties.ident || f.properties.mode || ''),
          detail: String(f.properties.text ?? ''),
          color: f.properties.family === 'sonde' ? '#f97316' : '#14b8a6',
        }));
    } catch {
      points = [];
    }
  }

  async function loadImages(list: OnAirMessage[]) {
    const wanted = list.filter((m) => m.event_type === 'image.done').slice(0, 12);
    const known = new Set(images.map((i) => i.id));
    for (const m of wanted) {
      if (known.has(m.uuid)) continue;
      try {
        const url = await fetchBlobUrl(`/onair/images/${m.uuid}`);
        images = [...images, { id: m.uuid, url, text: m.text, time: time(packetTime(m)) }];
      } catch {
        /* picture gone (OnAir's gallery folder cleaned up) */
      }
    }
  }

  $effect(() => {
    void loadStatus();
    void loadModes();
    void loadMessages();
    void loadMap();
    const timer = setInterval(loadStatus, 15_000);
    const off = live.on(['onair', 'onair_status', 'session'], (e) => {
      if (e.type === 'onair') {
        const m = e.data as unknown as OnAirMessage;
        messages = [m, ...messages].slice(0, 1000);
        if (m.event_type === 'image.done') void loadImages([m]);
        if (m.latitude != null && m.longitude != null) void loadMap();
      } else if (e.type === 'onair_status') {
        telemetry = (e.data as { telemetry: Record<string, unknown> }).telemetry;
      } else {
        void loadStatus();
      }
    });
    return () => {
      clearInterval(timer);
      off();
      for (const i of images) URL.revokeObjectURL(i.url);
    };
  });

  function pickMode(id: string) {
    modeId = id;
    const m = modeList.find((x) => x.id === id);
    if (m?.default_frequency) frequency = m.default_frequency;
  }

  async function start() {
    busy = true;
    try {
      await api.post('/onair/start', {
        mode: modeId,
        frequency,
        gain,
        duration: Math.round(hours * 3600),
        ...(deviceId ? { device_id: deviceId } : {}),
      });
      toasts.push(t('OnAir {mode} gestartet', { mode: mode?.name ?? modeId }), 'success');
      void sdr.refresh();
      void loadStatus();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  async function stop() {
    busy = true;
    try {
      await api.post('/onair/stop');
      void sdr.refresh();
      void loadStatus();
    } catch (e) {
      toasts.error(e);
    } finally {
      busy = false;
    }
  }

  async function openOnAir() {
    try {
      const r = await api.get<{ url: string | null; port: number; token: string }>('/onair/link');
      const base = r.url || `${location.protocol}//${location.hostname}:${r.port}`;
      window.open(`${base}/?token=${encodeURIComponent(r.token)}`, '_blank', 'noopener,noreferrer');
    } catch (e) {
      toasts.error(e);
    }
  }
</script>

<PageHeader
  title="OnAir"
  description={t(
    'Zusätzlicher Empfänger mit eigenem Decoder (ACARS, VDL2, Radiosonden, Digitalfunk, Wettersatelliten …)',
  )}
>
  {#snippet actions()}
    <button class="btn-secondary" onclick={openOnAir} disabled={!status?.reachable}>
      <ExternalLink size={14} />
      {t('OnAir-Seite öffnen')}
    </button>
    <button
      class="btn-secondary"
      onclick={() => download('/export/onair.csv?hours=24', 'onair.csv').catch(toasts.error.bind(toasts))}
    >
      <Download size={14} /> CSV
    </button>
  {/snippet}
</PageHeader>

{#if status && !status.enabled}
  <div class="card mb-4 text-sm">
    {t(
      'OnAir ist nicht eingerichtet: Profil „onair“ in COMPOSE_PROFILES und ONAIR_URL setzen (docs/onair.md).',
    )}
  </div>
{:else if status && !status.reachable}
  <div class="card mb-4 text-sm text-red-500">
    {t('OnAir nicht erreichbar: {error}', { error: status.error ?? '?' })}
  </div>
{/if}

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-5">
    <div class="sm:col-span-2">
      <label class="label" for="omode">{t('Betriebsart')}</label>
      <select
        id="omode"
        class="input"
        value={modeId}
        onchange={(e) => pickMode((e.currentTarget as HTMLSelectElement).value)}
      >
        {#each grouped as g (g.group)}
          <optgroup label={groupLabel(g.group)}>
            {#each g.modes as m (m.id + (m.sub ?? ''))}<option value={m.id}>{m.name}</option>{/each}
          </optgroup>
        {/each}
      </select>
    </div>
    <FrequencyField bind:value={frequency} />
    <div>
      <label class="label" for="ogain">{t('Verstärkung (dB)')}</label>
      <input
        id="ogain"
        class="input"
        type="number"
        min="0"
        max="102"
        bind:value={gain}
        placeholder={t('automatisch')}
      />
    </div>
    <div>
      <label class="label" for="oh">{t('Laufzeit (Stunden)')}</label>
      <input id="oh" class="input" type="number" min="0.5" max="24" step="0.5" bind:value={hours} />
    </div>
    <DeviceSelect bind:value={deviceId} />
  </div>
  <div class="flex flex-wrap gap-2">
    <button
      class="btn-primary"
      type="submit"
      disabled={busy || !status?.reachable || !!session || sdr.busyFor(deviceId)}
      ><Play size={16} /> {t('Starten')}</button
    >
    {#if session}
      <button class="btn-secondary" type="button" onclick={stop} disabled={busy}
        ><Square size={16} /> {t('Stoppen')}</button
      >
    {/if}
  </div>
  <p class="text-xs text-slate-500">
    {t('OnAir hat das SDR nur während einer Sitzung offen; RadioMoni hält solange die SDR-Sperre.')}
  </p>
</form>

{#if session}
  <div class="mt-4 space-y-2">
    <SessionCard sessionId={session.session_id} countLabel={t('Meldungen')} />
    <p class="text-sm text-slate-500">
      {session.onair_mode_name ?? session.onair_mode} · {mhz(session.frequency)} MHz
      {#if telemetry}· {t('Signal')}: {telemetry.locked ? t('erkannt') : t('kein Signal')}{/if}
    </p>
  </div>
{/if}

{#if points.length}
  <section class="card mt-6"><MapView {points} /></section>
{/if}

{#if images.length}
  <section class="card mt-6">
    <h2 class="mb-3 flex items-center gap-2 font-semibold"><ImageIcon size={16} /> {t('Bilder')}</h2>
    <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
      {#each images as img (img.id)}
        <figure>
          <img src={img.url} alt={img.text} class="w-full rounded" />
          <figcaption class="mt-1 text-xs text-slate-500">{img.time} · {img.text}</figcaption>
        </figure>
      {/each}
    </div>
  </section>
{/if}

<section class="card mt-6 overflow-x-auto">
  {#if families.length > 1}
    <div class="mb-3 flex flex-wrap gap-2">
      <button class="chip {family === '' ? '!border-accent-500' : ''}" onclick={() => (family = '')}
        >{t('alle')}</button
      >
      {#each families as f (f)}
        <button class="chip {family === f ? '!border-accent-500' : ''}" onclick={() => (family = f)}
          >{f}</button
        >
      {/each}
    </div>
  {/if}
  {#if shown.length}
    <table class="table">
      <thead
        ><tr
          ><th>{t('Zeit')}</th><th>{t('Typ')}</th><th>{t('Kennung')}</th><th>MHz</th><th>{t('Meldung')}</th
          ></tr
        ></thead
      >
      <tbody>
        {#each shown.slice(0, 300) as m (m.uuid)}
          <tr>
            <td class="text-xs whitespace-nowrap">{time(packetTime(m))}</td>
            <td class="font-mono text-xs">{m.event_type}</td>
            <td class="font-mono">{m.ident ?? ''}</td>
            <td class="text-xs">{m.frequency ? mhz(m.frequency) : ''}</td>
            <td class="text-sm">
              <details>
                <summary class="cursor-pointer">{m.text}</summary>
                <pre class="mt-1 text-xs whitespace-pre-wrap">{JSON.stringify(m.fields, null, 2)}</pre>
              </details>
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}<EmptyState text={t('Noch keine OnAir-Meldungen.')} />{/if}
</section>

{#if status?.attribution}
  <p class="mt-6 text-xs text-slate-500">
    {status.attribution} ·
    <a class="underline" href={status.contributors} target="_blank" rel="noopener noreferrer"
      >{t('OnAir-Mitwirkende')}</a
    >
    · GPL-3.0
  </p>
{/if}
