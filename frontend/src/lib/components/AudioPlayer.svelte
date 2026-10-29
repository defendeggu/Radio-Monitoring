<script lang="ts">
  import { Download, Pause, Play } from '@lucide/svelte';
  import WaveSurfer from 'wavesurfer.js';
  import { download, fetchBlobUrl } from '../api';
  import { t } from '../i18n.svelte';
  import { toasts } from '../stores.svelte';

  let { filename }: { filename: string } = $props();

  let container = $state<HTMLDivElement>();
  let ws: WaveSurfer | null = null;
  let playing = $state(false);
  let ready = $state(false);
  let error = $state('');

  $effect(() => {
    const name = filename;
    let url = '';
    let cancelled = false;
    ready = false;
    error = '';
    fetchBlobUrl(`/recordings/${encodeURIComponent(name)}`)
      .then((u) => {
        if (cancelled) return URL.revokeObjectURL(u);
        url = u;
        ws = WaveSurfer.create({
          container: container!,
          url,
          height: 56,
          waveColor: '#64748b',
          progressColor: '#06b6d4',
          cursorColor: '#22d3ee',
          barWidth: 2,
          barGap: 1,
        });
        ws.on('ready', () => (ready = true));
        ws.on('play', () => (playing = true));
        ws.on('pause', () => (playing = false));
        ws.on('finish', () => (playing = false));
      })
      .catch((e) => (error = t('Audio nicht verfügbar ({error})', { error: e.message })));
    return () => {
      cancelled = true;
      ws?.destroy();
      ws = null;
      if (url) URL.revokeObjectURL(url);
    };
  });
</script>

<div class="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
  {#if error}
    <p class="text-sm text-slate-500">{error}</p>
  {:else}
    <div class="flex items-center gap-3">
      <button
        class="btn-secondary !px-3"
        onclick={() => ws?.playPause()}
        disabled={!ready}
        aria-label={playing ? t('Pause') : t('Abspielen')}
      >
        {#if playing}<Pause size={16} />{:else}<Play size={16} />{/if}
      </button>
      <div bind:this={container} class="min-w-0 flex-1"></div>
      <button
        class="btn-secondary !px-3"
        onclick={() =>
          download(`/recordings/${encodeURIComponent(filename)}`, filename).catch(toasts.error.bind(toasts))}
        aria-label={t('Herunterladen')}
      >
        <Download size={16} />
      </button>
    </div>
  {/if}
</div>
