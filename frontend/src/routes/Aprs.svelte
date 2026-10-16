<script lang="ts">
  import { Download, Search } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import DecoderControls from '../lib/components/DecoderControls.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import MapView, { type MapPoint } from '../lib/components/MapView.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { packetTime, time } from '../lib/format';
  import { live, toasts } from '../lib/stores.svelte';
  import type { AprsPacket } from '../lib/types';

  interface Feature {
    geometry: { coordinates: [number, number] };
    properties: { callsign: string; message?: string; timestamp?: string; type?: string };
  }

  let packets = $state<AprsPacket[]>([]);
  let features = $state<Feature[]>([]);
  let callsign = $state('');
  let hours = $state(24);

  async function load() {
    try {
      const [search, map] = await Promise.all([
        api.get<{ results: AprsPacket[] }>('/aprs/search', {
          hours,
          limit: 200,
          callsign: callsign || undefined,
        }),
        api.get<{ features: Feature[] }>('/aprs/map', { hours }),
      ]);
      packets = search.results;
      features = map.features;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void hours;
    void load();
    return live.on(['aprs'], (e) => {
      const p = e.data as unknown as AprsPacket;
      if (!callsign || p.source_callsign?.toUpperCase() === callsign.toUpperCase())
        packets = [p, ...packets].slice(0, 500);
      if (p.latitude != null && p.longitude != null) {
        features = [
          {
            geometry: { coordinates: [p.longitude, p.latitude] },
            properties: {
              callsign: p.source_callsign,
              message: p.message_text ?? '',
              timestamp: packetTime(p),
            },
          },
          ...features.filter((f) => f.properties.callsign !== p.source_callsign),
        ];
      }
    });
  });

  const points = $derived<MapPoint[]>(
    features.map((f) => ({
      id: f.properties.callsign,
      lat: f.geometry.coordinates[1],
      lon: f.geometry.coordinates[0],
      label: f.properties.callsign,
      detail: `${f.properties.message ?? ''} (${time(f.properties.timestamp)})`,
    })),
  );

  function exportAs(ext: 'csv' | 'geojson' | 'kml') {
    download(`/export/aprs.${ext}?hours=${hours}`, `aprs.${ext}`).catch(toasts.error.bind(toasts));
  }
</script>

<PageHeader title="APRS" description="Automatic Packet Reporting System — Positionen, Nachrichten, Wetter">
  {#snippet actions()}
    <button class="btn-secondary" onclick={() => exportAs('csv')}><Download size={14} /> CSV</button>
    <button class="btn-secondary" onclick={() => exportAs('geojson')}>GeoJSON</button>
    <button class="btn-secondary" onclick={() => exportAs('kml')}>KML</button>
  {/snippet}
</PageHeader>

<DecoderControls
  mode="aprs"
  defaultFrequency={144_800_000}
  maxCapture={300}
  oncapture={(r) => {
    packets = [...(r.aprs?.packets ?? []), ...packets];
    void load();
  }}
/>

<section class="card mt-6">
  <div class="mb-3 flex items-center justify-between">
    <h2 class="text-sm font-semibold">Stationen ({points.length})</h2>
    <select class="input !w-auto" bind:value={hours} aria-label="Zeitraum">
      <option value={1}>1 h</option><option value={24}>24 h</option><option value={168}>7 Tage</option>
    </select>
  </div>
  <MapView {points} />
</section>

<section class="card mt-6">
  <form
    class="mb-3 flex flex-wrap items-end gap-3"
    onsubmit={(e) => {
      e.preventDefault();
      void load();
    }}
  >
    <div>
      <label class="label" for="call">Rufzeichen</label>
      <input
        id="call"
        class="input font-mono uppercase"
        bind:value={callsign}
        placeholder="HB9XYZ-7"
        maxlength="12"
      />
    </div>
    <button class="btn-secondary" type="submit"><Search size={14} /> Suchen</button>
  </form>
  {#if packets.length}
    <div class="overflow-x-auto">
      <table class="table">
        <thead
          ><tr
            ><th>Zeit</th><th>Rufzeichen</th><th>Typ</th><th>Position</th><th>Locator</th><th>Nachricht</th
            ></tr
          ></thead
        >
        <tbody>
          {#each packets as p, i (p.uuid ?? i)}
            <tr>
              <td class="text-xs whitespace-nowrap">{time(packetTime(p))}</td>
              <td class="font-mono font-medium">{p.source_callsign}</td>
              <td>{p.aprs_type ?? p.packet_type}</td>
              <td class="font-mono text-xs"
                >{p.latitude != null && p.longitude != null
                  ? `${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}`
                  : '—'}</td
              >
              <td class="font-mono text-xs">{p.maidenhead ?? '—'}</td>
              <td class="break-all">{p.message_text ?? ''}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <EmptyState text="Noch keine APRS-Pakete — starte oben eine Aufnahme oder einen Stream." />
  {/if}
</section>
