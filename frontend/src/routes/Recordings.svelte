<script lang="ts">
  import { FileText, RefreshCw, Trash2 } from '@lucide/svelte';
  import { api, fetchBlobUrl } from '../lib/api';
  import AudioPlayer from '../lib/components/AudioPlayer.svelte';
  import EmptyState from '../lib/components/EmptyState.svelte';
  import PageHeader from '../lib/components/PageHeader.svelte';
  import { bytes, dateTime } from '../lib/format';
  import { toasts } from '../lib/stores.svelte';
  import type { Recording } from '../lib/types';

  interface Stats {
    count: number;
    total_bytes: number;
    retention_days: number;
    disk_free_bytes: number | null;
  }

  let recordings = $state<Recording[]>([]);
  let stats = $state<Stats | null>(null);
  let filter = $state('');
  let selected = $state<string | null>(null);
  let transcript = $state<string | null>(null);

  async function load() {
    try {
      const r = await api.get<{ recordings: Recording[]; stats: Stats }>('/recordings');
      recordings = r.recordings;
      stats = r.stats;
    } catch (e) {
      toasts.error(e);
    }
  }

  $effect(() => {
    void load();
  });

  async function select(rec: Recording) {
    selected = selected === rec.filename ? null : rec.filename;
    transcript = null;
    if (selected && rec.has_transcript) {
      try {
        const url = await fetchBlobUrl(
          `/recordings/${encodeURIComponent(rec.filename.replace(/\.wav$/, '.json'))}`,
        );
        const data = await (await fetch(url)).json();
        URL.revokeObjectURL(url);
        transcript = data.text ?? null;
      } catch {
        transcript = null;
      }
    }
  }

  async function remove(rec: Recording) {
    if (!confirm(`${rec.filename} löschen?`)) return;
    try {
      await api.del(`/recordings/${encodeURIComponent(rec.filename)}`);
      recordings = recordings.filter((r) => r.filename !== rec.filename);
      toasts.push('Gelöscht', 'success');
    } catch (e) {
      toasts.error(e);
    }
  }

  const shown = $derived(recordings.filter((r) => r.filename.toLowerCase().includes(filter.toLowerCase())));
</script>

<PageHeader title="Aufnahmen" description="Gespeicherte Audiodateien abspielen, herunterladen und löschen">
  {#snippet actions()}
    <button class="btn-secondary" onclick={load} aria-label="Aktualisieren"><RefreshCw size={16} /></button>
  {/snippet}
</PageHeader>

{#if stats}
  <p class="mb-4 text-sm text-slate-500">
    {stats.count} Dateien · {bytes(stats.total_bytes)} · frei {bytes(stats.disk_free_bytes)} ·
    {stats.retention_days > 0
      ? `automatisch gelöscht nach ${stats.retention_days} Tagen`
      : 'keine automatische Löschung'}
  </p>
{/if}

<section class="card">
  <input
    class="input mb-4"
    bind:value={filter}
    placeholder="Filtern (z. B. vox_, capture_2026…)"
    aria-label="Filter"
  />
  {#if shown.length}
    <ul class="divide-y divide-slate-100 dark:divide-slate-800">
      {#each shown as rec (rec.filename)}
        <li class="py-3">
          <div class="flex flex-wrap items-center gap-3">
            <button
              class="flex-1 text-left font-mono text-sm break-all hover:text-accent-600"
              onclick={() => select(rec)}
              aria-expanded={selected === rec.filename}
            >
              {rec.filename}
            </button>
            {#if rec.has_transcript}<FileText
                size={14}
                class="text-slate-400"
                aria-label="mit Transkript"
              />{/if}
            <span class="text-xs text-slate-500">{bytes(rec.size)}</span>
            <span class="text-xs text-slate-500">{dateTime(rec.created)}</span>
            <button class="text-slate-400 hover:text-red-500" onclick={() => remove(rec)} aria-label="Löschen"
              ><Trash2 size={16} /></button
            >
          </div>
          {#if selected === rec.filename}
            <div class="mt-3 space-y-2">
              <AudioPlayer filename={rec.filename} />
              {#if transcript}<p class="rounded bg-slate-100 p-3 text-sm dark:bg-slate-800">
                  {transcript}
                </p>{/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>
  {:else}
    <EmptyState text="Keine Aufnahmen." />
  {/if}
</section>
