<script lang="ts">
  import { BellOff, Download, Search } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import DecoderControls from '../lib/components/DecoderControls.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { packetTime, time } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { live, toasts } from '../lib/stores.svelte';
  import type { PocsagMessage } from '../lib/types';

  let messages = $state<PocsagMessage[]>([]);
  let address = $state('');
  let hours = $state(24);

  // "Tone only" pages (no text) are most of the traffic; hiding them is remembered per browser
  const HIDE_KEY = 'radiomoni.pocsag.hideTone';
  let hideTone = $state(readHideTone());
  function readHideTone(): boolean {
    try {
      return localStorage.getItem(HIDE_KEY) === '1';
    } catch {
      return false;
    }
  }
  function toggleTone() {
    hideTone = !hideTone;
    try {
      localStorage.setItem(HIDE_KEY, hideTone ? '1' : '0');
    } catch {
      /* private mode: not remembered */
    }
    void load();
  }
  const isTone = (m: PocsagMessage) => !String(m.message_text ?? '').trim();
  const shown = $derived(hideTone ? messages.filter((m) => !isTone(m)) : messages);

  async function load() {
    try {
      const r = await api.get<{ results: PocsagMessage[] }>('/pocsag/search', {
        hours,
        limit: 300,
        address: address || undefined,
        text_only: hideTone || undefined,
      });
      messages = r.results;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void hours;
    void load();
    return live.on(['pocsag'], (e) => {
      const m = e.data as unknown as PocsagMessage;
      if (!address || String(m.address) === address) messages = [m, ...messages].slice(0, 500);
    });
  });
</script>

<PageHeader title="POCSAG" description={t('Pager-Meldungen (512 / 1200 / 2400 Baud)')}>
  {#snippet actions()}
    <button
      class="btn-secondary"
      onclick={() =>
        download(`/export/pocsag.csv?hours=${hours}`, 'pocsag.csv').catch(toasts.error.bind(toasts))}
    >
      <Download size={14} /> CSV
    </button>
  {/snippet}
</PageHeader>

<DecoderControls
  mode="pocsag"
  defaultFrequency={147_325_000}
  maxCapture={120}
  oncapture={(r) => {
    messages = [...(r.pocsag?.messages ?? []), ...messages];
  }}
/>

<section class="card mt-6">
  <form
    class="mb-3 flex flex-wrap items-end gap-3"
    onsubmit={(e) => {
      e.preventDefault();
      void load();
    }}
  >
    <div>
      <label class="label" for="ric">{t('Adresse (RIC)')}</label>
      <input
        id="ric"
        class="input font-mono"
        bind:value={address}
        inputmode="numeric"
        pattern="[0-9]*"
        placeholder="1234567"
      />
    </div>
    <div>
      <label class="label" for="ph">{t('Zeitraum')}</label>
      <select id="ph" class="input" bind:value={hours}>
        <option value={1}>1 h</option><option value={24}>24 h</option><option value={168}
          >{t('{n} Tage', { n: 7 })}</option
        >
      </select>
    </div>
    <button class="btn-secondary" type="submit"><Search size={14} /> {t('Suchen')}</button>
    <button
      class={hideTone ? 'btn-primary' : 'btn-secondary'}
      type="button"
      aria-pressed={hideTone}
      title={t('Meldungen ohne Text (nur Piepton) aus- oder einblenden')}
      onclick={toggleTone}
    >
      <BellOff size={14} />
      {hideTone ? t('„Nur Ton“ ausgeblendet') : t('„Nur Ton“ ausblenden')}
    </button>
  </form>
  {#if shown.length}
    <div class="overflow-x-auto">
      <table class="table">
        <thead
          ><tr
            ><th>{t('Zeit')}</th><th>{t('Adresse')}</th><th>{t('Typ')}</th><th>Baud</th><th
              >{t('Nachricht')}</th
            ></tr
          ></thead
        >
        <tbody>
          {#each shown as m, i (m.uuid ?? i)}
            <tr>
              <td class="text-xs whitespace-nowrap">{time(packetTime(m))}</td>
              <td class="font-mono">{m.address}</td>
              <td>{m.message_type}</td>
              <td>{m.baud_rate}</td>
              <td class="break-all">{m.message_text || t('Nur Ton')}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {:else}
    <EmptyState
      text={hideTone && messages.length
        ? t('Nur Meldungen ohne Text — „Nur Ton“ ist ausgeblendet.')
        : t('Noch keine POCSAG-Meldungen.')}
    />
  {/if}
</section>
