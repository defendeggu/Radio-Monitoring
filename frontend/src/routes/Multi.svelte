<script lang="ts">
  import { Plus, Radio, Trash2 } from '@lucide/svelte';
  import { api } from '../lib/api';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import SessionCard from '../lib/components/SessionCard.svelte';
  import { mhz } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { sdr, settings, toasts } from '../lib/stores.svelte';

  interface Channel {
    mode: 'aprs' | 'pocsag';
    frequency: number;
    label: string;
  }

  let center = $state(146_000_000);
  let rate = $state(5_000_000);
  let gain = $state(30);
  let hours = $state(1);
  let channels = $state<Channel[]>([
    { mode: 'aprs', frequency: 144_800_000, label: 'APRS' },
    { mode: 'pocsag', frequency: 147_325_000, label: 'POCSAG' },
  ]);
  let sessionId = $state<string | null>(null);

  const span = $derived({ min: center - rate / 2, max: center + rate / 2 });

  async function start() {
    try {
      const r = await api.post<{ session_id: string }>('/stream/multi/start', {
        device_address: settings.usrpAddress,
        center_freq: center,
        wideband_rate: rate,
        gain,
        duration: Math.round(hours * 3600),
        channels,
      });
      sessionId = r.session_id;
      toasts.push(t('Multi-Channel gestartet'), 'success');
    } catch (e) {
      toasts.error(e);
    }
  }
</script>

<PageHeader
  title="Multi-Channel (USRP N200)"
  description={t('Ein Breitband-IQ-Strom, bis zu 8 Kanäle gleichzeitig dekodiert (DDC)')}
/>

{#if !settings.usrpAddress}
  <p class="card mb-4 text-sm text-amber-600">
    {t('Bitte zuerst in den Einstellungen die IP-Adresse des USRP eintragen.')}
  </p>
{/if}

<form
  class="card space-y-4"
  onsubmit={(e) => {
    e.preventDefault();
    void start();
  }}
>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-4">
    <FrequencyField bind:value={center} label={t('Mittenfrequenz')} checkDevice={false} />
    <div>
      <label class="label" for="rate">{t('Bandbreite (MS/s)')}</label>
      <input
        id="rate"
        class="input"
        type="number"
        min="1"
        max="25"
        step="0.5"
        value={rate / 1e6}
        oninput={(e) => (rate = Math.round(Number(e.currentTarget.value) * 1e6))}
      />
      <p class="hint">{mhz(span.min, 3)} – {mhz(span.max, 3)}</p>
    </div>
    <div>
      <label class="label" for="mgain">{t('Verstärkung (dB)')}</label>
      <input id="mgain" class="input" type="number" min="0" max="76" bind:value={gain} />
    </div>
    <div>
      <label class="label" for="mh">{t('Laufzeit (Stunden)')}</label>
      <input id="mh" class="input" type="number" min="0.5" max="24" step="0.5" bind:value={hours} />
    </div>
  </div>

  <fieldset class="space-y-2">
    <legend class="label">{t('Kanäle ({n}/8)', { n: channels.length })}</legend>
    {#each channels as ch, i (i)}
      <div class="grid grid-cols-[6rem_1fr_1fr_auto] items-end gap-2">
        <select class="input" bind:value={ch.mode} aria-label={t('Betriebsart')}
          ><option value="aprs">APRS</option><option value="pocsag">POCSAG</option></select
        >
        <FrequencyField
          bind:value={ch.frequency}
          id="ch{i}"
          label={t('Kanal {n}', { n: i + 1 })}
          checkDevice={false}
        />
        <input class="input" bind:value={ch.label} maxlength="32" aria-label={t('Bezeichnung')} />
        <button
          type="button"
          class="btn-secondary !px-3"
          onclick={() => (channels = channels.filter((_, j) => j !== i))}
          disabled={channels.length <= 2}
          aria-label={t('Kanal entfernen')}><Trash2 size={14} /></button
        >
      </div>
      {#if ch.frequency < span.min || ch.frequency > span.max}<p class="text-xs text-red-500">
          {t('Kanal {n} liegt ausserhalb der Bandbreite', { n: i + 1 })}
        </p>{/if}
    {/each}
    <button
      type="button"
      class="btn-secondary"
      disabled={channels.length >= 8}
      onclick={() =>
        (channels = [...channels, { mode: 'aprs', frequency: center, label: `ch${channels.length}` }])}
    >
      <Plus size={14} />
      {t('Kanal')}
    </button>
  </fieldset>
  <button class="btn-primary" type="submit" disabled={sdr.busy || !settings.usrpAddress}
    ><Radio size={16} /> {t('Starten')}</button
  >
</form>

{#if sessionId}<div class="mt-4"><SessionCard {sessionId} /></div>{/if}
