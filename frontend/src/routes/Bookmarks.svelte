<script lang="ts">
  import { Download, Pencil, Plus, Trash2, Upload } from '@lucide/svelte';
  import { api, download } from '../lib/api';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import FrequencyField from '../lib/components/FrequencyField.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { mhz } from '../lib/format';
  import { t } from '../lib/i18n.svelte';
  import { router } from '../lib/router.svelte';
  import { toasts } from '../lib/stores.svelte';
  import type { Bookmark } from '../lib/types';

  type Draft = Omit<Bookmark, 'id'> & { id?: string };
  const empty = (): Draft => ({
    name: '',
    frequency: 145_500_000,
    modulation: 'FM',
    mode: 'voice',
    notes: '',
    tags: [],
  });

  let items = $state<Bookmark[]>([]);
  let defaults = $state<Bookmark[]>([]);
  let draft = $state<Draft>(empty());
  let tagText = $state('');
  let fileInput: HTMLInputElement;

  const pages: Record<Bookmark['mode'], string> = {
    voice: 'voice',
    vox: 'vox',
    aprs: 'aprs',
    pocsag: 'pocsag',
    adsb: 'decoders',
    ais: 'decoders',
    ism: 'decoders',
  };

  async function load() {
    const r = await api.get<{ bookmarks: Bookmark[]; defaults: Bookmark[] }>('/bookmarks');
    items = r.bookmarks;
    defaults = r.defaults;
  }

  $effect(() => {
    load().catch(toasts.error.bind(toasts));
  });

  async function save() {
    const body = {
      ...draft,
      tags: tagText
        .split(',')
        .map((t) => t.trim())
        .filter(Boolean),
    };
    delete (body as { id?: string }).id;
    try {
      if (draft.id) await api.put(`/bookmarks/${draft.id}`, body);
      else await api.post('/bookmarks', body);
      draft = empty();
      tagText = '';
      await load();
      toasts.push(t('Gespeichert'), 'success');
    } catch (e) {
      toasts.error(e);
    }
  }

  async function remove(b: Bookmark) {
    try {
      await api.del(`/bookmarks/${b.id}`);
      await load();
    } catch (e) {
      toasts.error(e);
    }
  }

  async function importFile(event: Event) {
    const file = (event.currentTarget as HTMLInputElement).files?.[0];
    if (!file) return;
    try {
      const r = await api.post<{ imported: number }>('/bookmarks/import', JSON.parse(await file.text()));
      toasts.push(t('{n} Lesezeichen importiert', { n: r.imported }), 'success');
      await load();
    } catch (e) {
      toasts.error(e);
    }
  }

  async function adoptDefaults() {
    await api.post('/bookmarks/import', { bookmarks: defaults });
    await load();
  }
</script>

<PageHeader title={t('Lesezeichen')} description={t('Eigene Frequenzen und Presets für alle Betriebsarten')}>
  {#snippet actions()}
    <button
      class="btn-secondary"
      onclick={() =>
        download('/bookmarks/export', 'radiomoni-bookmarks.json').catch(toasts.error.bind(toasts))}
      ><Download size={14} /> Export</button
    >
    <button class="btn-secondary" onclick={() => fileInput.click()}><Upload size={14} /> Import</button>
    <input bind:this={fileInput} type="file" accept="application/json" class="hidden" onchange={importFile} />
  {/snippet}
</PageHeader>

<form
  class="card grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5"
  onsubmit={(e) => {
    e.preventDefault();
    void save();
  }}
>
  <div>
    <label class="label" for="bname">{t('Name')}</label>
    <input id="bname" class="input" bind:value={draft.name} maxlength="80" required />
  </div>
  <FrequencyField bind:value={draft.frequency} id="bfreq" checkDevice={false} />
  <div>
    <label class="label" for="bmode">{t('Betriebsart')}</label>
    <select id="bmode" class="input" bind:value={draft.mode}>
      {#each Object.keys(pages) as m (m)}<option value={m}>{m.toUpperCase()}</option>{/each}
    </select>
  </div>
  <div>
    <label class="label" for="bmod">Modulation</label>
    <select id="bmod" class="input" bind:value={draft.modulation}
      ><option>FM</option><option>AM</option><option>USB</option><option>LSB</option></select
    >
  </div>
  <div>
    <label class="label" for="btags">Tags</label>
    <input id="btags" class="input" bind:value={tagText} placeholder={t('ham, relais')} />
  </div>
  <div class="sm:col-span-2 lg:col-span-4">
    <label class="label" for="bnotes">{t('Notiz')}</label>
    <input id="bnotes" class="input" bind:value={draft.notes} maxlength="500" />
  </div>
  <div class="flex items-end gap-2">
    <button class="btn-primary" type="submit"
      ><Plus size={16} /> {draft.id ? t('Speichern') : t('Hinzufügen')}</button
    >
    {#if draft.id}<button
        type="button"
        class="btn-secondary"
        onclick={() => {
          draft = empty();
          tagText = '';
        }}>{t('Abbrechen')}</button
      >{/if}
  </div>
</form>

<section class="card mt-6 overflow-x-auto">
  {#if items.length}
    <table class="table">
      <thead
        ><tr
          ><th>{t('Name')}</th><th>{t('Frequenz')}</th><th>{t('Art')}</th><th>Mod.</th><th>Tags</th><th
          ></th></tr
        ></thead
      >
      <tbody>
        {#each items as b (b.id)}
          <tr>
            <td
              ><button
                class="text-left hover:text-accent-600"
                onclick={() => router.go(pages[b.mode], { f: b.frequency, m: b.modulation })}>{b.name}</button
              >
              {#if b.notes}<div class="text-xs text-slate-500">{b.notes}</div>{/if}</td
            >
            <td class="font-mono text-xs">{mhz(b.frequency)}</td>
            <td>{b.mode.toUpperCase()}</td>
            <td>{b.modulation}</td>
            <td class="text-xs">{b.tags.join(', ')}</td>
            <td class="whitespace-nowrap text-right">
              <button
                class="mr-2 text-slate-400 hover:text-accent-600"
                onclick={() => {
                  draft = { ...b };
                  tagText = b.tags.join(', ');
                }}
                aria-label={t('Bearbeiten')}><Pencil size={14} /></button
              >
              <button
                class="text-slate-400 hover:text-red-500"
                onclick={() => remove(b)}
                aria-label={t('Löschen')}><Trash2 size={14} /></button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  {:else}
    <EmptyState text={t('Noch keine eigenen Lesezeichen.')} />
    {#if defaults.length}
      <button class="btn-secondary mt-3" onclick={adoptDefaults}
        >{t('{n} Standard-Frequenzen übernehmen', { n: defaults.length })}</button
      >
    {/if}
  {/if}
</section>
