<script lang="ts">
  import { CalendarClock, Pencil, Play, Trash2 } from '@lucide/svelte';
  import { api } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { dateTime } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { toasts } from '../lib/stores.svelte';
  import type { Schedule } from '../lib/types';

  type Action = Schedule['action'];
  const TEMPLATES: Record<Action, Record<string, unknown>> = {
    stream: { mode: 'aprs', frequency: 144800000, gain: 32, duration: 7200 },
    capture: { mode: 'voice', frequency: 145500000, modulation: 'FM', duration: 60, gain: 20 },
    vox: { frequency: 446006250, modulation: 'FM', duration: 3600, squelch_db: 10, transcribe: true },
    decoder: { decoder: 'adsb', duration: 3600 },
  };
  const ACTION_LABELS: Record<Action, () => string> = {
    stream: () => 'Streaming (APRS/POCSAG)',
    capture: () => t('Einzelaufnahme'),
    vox: () => t('VOX-Aufnahme'),
    decoder: () => 'ADS-B/AIS/ISM',
  };

  let schedules = $state<Schedule[]>([]);
  let editId = $state<string | null>(null);
  let name = $state('');
  let cron = $state('0 7 * * *');
  let action = $state<Action>('stream');
  let enabled = $state(true);
  let paramsText = $state(JSON.stringify(TEMPLATES.stream, null, 2));
  let paramsError = $state('');

  async function load() {
    try {
      schedules = (await api.get<{ schedules: Schedule[] }>('/schedules')).schedules;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void load();
  });

  function setAction(a: Action) {
    action = a;
    paramsText = JSON.stringify(TEMPLATES[a], null, 2);
  }

  function reset() {
    editId = null;
    name = '';
    cron = '0 7 * * *';
    enabled = true;
    setAction('stream');
  }

  async function save() {
    let params: Record<string, unknown>;
    try {
      params = JSON.parse(paramsText);
      paramsError = '';
    } catch {
      paramsError = t('Parameter sind kein gültiges JSON');
      return;
    }
    try {
      const body = { name, cron, action, enabled, params };
      if (editId) await api.put(`/schedules/${editId}`, body);
      else await api.post('/schedules', body);
      reset();
      await load();
      toasts.push(t('Zeitplan gespeichert'), 'success');
    } catch (e) {
      toasts.error(e);
    }
  }

  function edit(s: Schedule) {
    editId = s.id;
    name = s.name;
    cron = s.cron;
    action = s.action;
    enabled = s.enabled;
    paramsText = JSON.stringify(s.params, null, 2);
  }

  async function runNow(s: Schedule) {
    try {
      const r = await api.post<{ status: string; reason?: string; error?: string }>(`/schedules/${s.id}/run`);
      toasts.push(
        `${s.name}: ${r.status}${r.reason ? ` (${r.reason})` : ''}${r.error ? ` — ${r.error}` : ''}`,
        r.status === 'started' ? 'success' : 'warning',
      );
      await load();
    } catch (e) {
      toasts.error(e);
    }
  }

  async function remove(s: Schedule) {
    try {
      await api.del(`/schedules/${s.id}`);
      await load();
    } catch (e) {
      toasts.error(e);
    }
  }
</script>

<PageHeader
  title={t('Zeitpläne')}
  description={t('Aufnahmen und Decoder automatisch zu festen Zeiten starten')}
/>

<form
  class="card grid grid-cols-1 gap-4 lg:grid-cols-2"
  onsubmit={(e) => {
    e.preventDefault();
    void save();
  }}
>
  <div class="space-y-4">
    <div>
      <label class="label" for="sname">{t('Name')}</label>
      <input
        id="sname"
        class="input"
        bind:value={name}
        required
        maxlength="80"
        placeholder={t('APRS am Morgen')}
      />
    </div>
    <div>
      <label class="label" for="scron">{t('Cron-Ausdruck')}</label>
      <input id="scron" class="input font-mono" bind:value={cron} required />
      <p class="hint">{t('Minute Stunde Tag Monat Wochentag — z. B. 0 7 * * 1-5 = werktags 07:00')}</p>
    </div>
    <div>
      <label class="label" for="saction">{t('Aktion')}</label>
      <select
        id="saction"
        class="input"
        value={action}
        onchange={(e) => setAction(e.currentTarget.value as Action)}
      >
        {#each Object.entries(ACTION_LABELS) as [value, label] (value)}<option {value}>{label()}</option
          >{/each}
      </select>
    </div>
    <label class="flex items-center gap-2 text-sm"
      ><input type="checkbox" class="accent-cyan-500" bind:checked={enabled} />
      {t('aktiv')}</label
    >
  </div>
  <div>
    <label class="label" for="sparams">{t('Parameter (JSON)')}</label>
    <textarea id="sparams" class="input h-48 font-mono text-xs" bind:value={paramsText} spellcheck="false"
    ></textarea>
    {#if paramsError}<p class="mt-1 text-xs text-red-500">{paramsError}</p>{/if}
    <p class="hint">
      {t(
        'Gleiche Felder wie die API (siehe API-Seite). Bei belegtem SDR wird bis zu 60 s gewartet, danach übersprungen.',
      )}
    </p>
  </div>
  <div class="flex gap-2 lg:col-span-2">
    <button class="btn-primary" type="submit"
      ><CalendarClock size={16} /> {editId ? t('Speichern') : t('Zeitplan anlegen')}</button
    >
    {#if editId}<button type="button" class="btn-secondary" onclick={reset}>{t('Abbrechen')}</button>{/if}
  </div>
</form>

<section class="card mt-6 overflow-x-auto">
  {#if schedules.length}
    <table class="table">
      <thead
        ><tr
          ><th>{t('Name')}</th><th>Cron</th><th>{t('Aktion')}</th><th>{t('Nächster Lauf')}</th><th
            >{t('Letzter Lauf')}</th
          ><th></th></tr
        ></thead
      >
      <tbody>
        {#each schedules as s (s.id)}
          <tr class={s.enabled ? '' : 'opacity-50'}>
            <td>{s.name}</td>
            <td class="font-mono text-xs">{s.cron}</td>
            <td>{ACTION_LABELS[s.action]()}</td>
            <td class="text-xs">{dateTime(s.next_run)}</td>
            <td class="text-xs">{s.last_run ? `${dateTime(s.last_run)} · ${s.last_status}` : '—'}</td>
            <td class="whitespace-nowrap text-right">
              <button
                class="mr-2 text-slate-400 hover:text-emerald-600"
                onclick={() => runNow(s)}
                aria-label={t('Jetzt ausführen')}><Play size={14} /></button
              >
              <button
                class="mr-2 text-slate-400 hover:text-accent-600"
                onclick={() => edit(s)}
                aria-label={t('Bearbeiten')}><Pencil size={14} /></button
              >
              <button
                class="text-slate-400 hover:text-red-500"
                onclick={() => remove(s)}
                aria-label={t('Löschen')}><Trash2 size={14} /></button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <EmptyState text={t('Noch keine Zeitpläne.')} />
  {/if}
</section>
