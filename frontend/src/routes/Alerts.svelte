<script lang="ts">
  import { BellRing, Pencil, Send, Trash2 } from '@lucide/svelte';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { dateTime } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { live, toasts } from '../lib/stores.svelte';
  import type { AlertEvent, AlertRule } from '../lib/types';

  type Draft = Omit<AlertRule, 'id'> & { id?: string };
  const CHANNELS = ['ntfy', 'telegram', 'webhook', 'email'];
  const empty = (): Draft => ({
    name: '',
    enabled: true,
    source: 'any',
    field: 'any',
    match_type: 'contains',
    pattern: '',
    case_sensitive: false,
    channels: [],
    cooldown_seconds: 300,
  });

  let rules = $state<AlertRule[]>([]);
  let channels = $state<Record<string, boolean>>({});
  let recent = $state<AlertEvent[]>([]);
  let draft = $state<Draft>(empty());

  async function load() {
    try {
      const r = await api.get<{ rules: AlertRule[]; channels: Record<string, boolean> }>('/alerts/rules');
      rules = r.rules;
      channels = r.channels;
      recent = (await api.get<{ alerts: AlertEvent[] }>('/alerts/recent', { limit: 50 })).alerts;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void load();
    return live.on(['alert'], (e) => (recent = [e.data as unknown as AlertEvent, ...recent].slice(0, 50)));
  });

  async function save() {
    const { id, ...body } = draft;
    try {
      if (id) await api.put(`/alerts/rules/${id}`, body);
      else await api.post('/alerts/rules', body);
      draft = empty();
      await load();
      toasts.push(t('Regel gespeichert'), 'success');
    } catch (e) {
      toasts.error(e);
    }
  }

  async function remove(rule: AlertRule) {
    try {
      await api.del(`/alerts/rules/${rule.id}`);
      await load();
    } catch (e) {
      toasts.error(e);
    }
  }

  async function sendTest() {
    const active = CHANNELS.filter((c) => channels[c]);
    if (!active.length) return toasts.push(t('Kein Kanal konfiguriert (siehe .env)'), 'warning');
    const r = await api.post<{ results: Record<string, string> }>('/alerts/test', { channels: active });
    toasts.push(
      Object.entries(r.results)
        .map(([k, v]) => `${k}: ${v}`)
        .join(', '),
      'info',
    );
  }
</script>

<PageHeader
  title={t('Alarme')}
  description={t('Benachrichtigung bei bestimmten Rufzeichen, Pager-Adressen oder Stichworten')}
>
  {#snippet actions()}
    <button class="btn-secondary" onclick={sendTest}><Send size={14} /> {t('Test senden')}</button>
  {/snippet}
</PageHeader>

<p class="mb-4 text-sm text-slate-500">
  {t('Kanäle')}:
  {#each CHANNELS as c (c)}
    <span class="mr-3 {channels[c] ? 'text-emerald-600' : 'text-slate-400'}"
      >{channels[c] ? '●' : '○'} {c}</span
    >
  {/each}
  <span class="block text-xs"
    >{t('Ziele (ntfy-Topic, Telegram-Bot, Webhook, SMTP) werden in der .env konfiguriert.')}</span
  >
</p>

<form
  class="card grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4"
  onsubmit={(e) => {
    e.preventDefault();
    void save();
  }}
>
  <div>
    <label class="label" for="aname">{t('Name')}</label>
    <input id="aname" class="input" bind:value={draft.name} required maxlength="80" />
  </div>
  <div>
    <label class="label" for="asrc">{t('Quelle')}</label>
    <select id="asrc" class="input" bind:value={draft.source}>
      {#each ['any', 'aprs', 'pocsag', 'voice', 'adsb', 'ais', 'ism'] as s (s)}<option value={s}
          >{s === 'any' ? t('alle') : s.toUpperCase()}</option
        >{/each}
    </select>
  </div>
  <div>
    <label class="label" for="afield">{t('Feld')}</label>
    <select id="afield" class="input" bind:value={draft.field}>
      <option value="any">{t('beliebig')}</option>
      <option value="callsign">{t('Rufzeichen / Flug / Schiff')}</option>
      <option value="address">{t('POCSAG-Adresse')}</option>
      <option value="text">{t('Text / Transkript')}</option>
      <option value="icao">ICAO</option>
      <option value="mmsi">MMSI</option>
      <option value="model">{t('Sensor-Modell')}</option>
    </select>
  </div>
  <div>
    <label class="label" for="amatch">{t('Vergleich')}</label>
    <select id="amatch" class="input" bind:value={draft.match_type}>
      <option value="contains">{t('enthält')}</option>
      <option value="equals">{t('ist gleich')}</option>
      <option value="regex">{t('regulärer Ausdruck')}</option>
    </select>
  </div>
  <div class="sm:col-span-2">
    <label class="label" for="apat">{t('Muster')}</label>
    <input
      id="apat"
      class="input font-mono"
      bind:value={draft.pattern}
      required
      maxlength="200"
      placeholder={t('HB9XYZ oder FEUER|BRAND')}
    />
  </div>
  <div>
    <label class="label" for="acool">{t('Pause (s)')}</label>
    <input id="acool" class="input" type="number" min="0" max="86400" bind:value={draft.cooldown_seconds} />
    <p class="hint">{t('Minimaler Abstand zwischen zwei Alarmen dieser Regel')}</p>
  </div>
  <fieldset>
    <legend class="label">{t('Benachrichtigen per')}</legend>
    <div class="flex flex-wrap gap-3 text-sm">
      {#each CHANNELS as c (c)}
        <label class="flex items-center gap-1.5"
          ><input type="checkbox" class="accent-cyan-500" bind:group={draft.channels} value={c} />{c}</label
        >
      {/each}
    </div>
  </fieldset>
  <div class="flex items-center gap-4 sm:col-span-2 lg:col-span-4">
    <label class="flex items-center gap-1.5 text-sm"
      ><input type="checkbox" class="accent-cyan-500" bind:checked={draft.enabled} />
      {t('aktiv')}</label
    >
    <label class="flex items-center gap-1.5 text-sm"
      ><input type="checkbox" class="accent-cyan-500" bind:checked={draft.case_sensitive} />
      {t('Gross/klein beachten')}</label
    >
    <button class="btn-primary ml-auto" type="submit"
      ><BellRing size={16} /> {draft.id ? t('Speichern') : t('Regel anlegen')}</button
    >
    {#if draft.id}<button type="button" class="btn-secondary" onclick={() => (draft = empty())}
        >{t('Abbrechen')}</button
      >{/if}
  </div>
</form>

<section class="card mt-6 overflow-x-auto">
  <h2 class="mb-3 text-sm font-semibold">{t('Regeln')}</h2>
  {#if rules.length}
    <table class="table">
      <thead
        ><tr
          ><th>{t('Name')}</th><th>{t('Quelle')}</th><th>{t('Bedingung')}</th><th>{t('Kanäle')}</th><th
          ></th></tr
        ></thead
      >
      <tbody>
        {#each rules as r (r.id)}
          <tr class={r.enabled ? '' : 'opacity-50'}>
            <td>{r.name}</td><td>{r.source}</td>
            <td class="font-mono text-xs">{r.field} {r.match_type} “{r.pattern}”</td>
            <td class="text-xs">{r.channels.join(', ') || '—'}</td>
            <td class="whitespace-nowrap text-right">
              <button
                class="mr-2 text-slate-400 hover:text-accent-600"
                onclick={() => (draft = { ...r, channels: [...r.channels] })}
                aria-label={t('Bearbeiten')}><Pencil size={14} /></button
              >
              <button
                class="text-slate-400 hover:text-red-500"
                onclick={() => remove(r)}
                aria-label={t('Löschen')}><Trash2 size={14} /></button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <EmptyState text={t('Noch keine Regeln.')} />
  {/if}
</section>

<section class="card mt-6">
  <h2 class="mb-3 text-sm font-semibold">{t('Ausgelöste Alarme')}</h2>
  {#if recent.length}
    <ul class="space-y-2 text-sm">
      {#each recent as a (a.uuid)}
        <li>
          <span class="text-xs text-slate-500">{dateTime(a.timestamp)}</span> <strong>{a.rule_name}</strong> — {a.summary}
        </li>
      {/each}
    </ul>
  {:else}
    <EmptyState text={t('Noch keine Alarme ausgelöst.')} />
  {/if}
</section>
