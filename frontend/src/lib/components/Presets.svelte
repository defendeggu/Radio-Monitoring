<script lang="ts">
  import { api } from '../api';
  import { mhz } from '../format';
  import type { Bookmark } from '../types';

  let {
    modes,
    onpick,
  }: { modes: Bookmark['mode'][]; onpick: (b: Pick<Bookmark, 'frequency' | 'modulation' | 'name'>) => void } =
    $props();

  let items = $state<Pick<Bookmark, 'frequency' | 'modulation' | 'name' | 'mode'>[]>([]);

  $effect(() => {
    api
      .get<{ bookmarks: Bookmark[]; defaults: Bookmark[] }>('/bookmarks')
      .then((r) => {
        const all = r.bookmarks.length ? r.bookmarks : r.defaults;
        items = all.filter((b) => modes.includes(b.mode));
      })
      .catch(() => (items = []));
  });
</script>

{#if items.length}
  <div class="mb-5 flex flex-wrap gap-2" aria-label="Frequenz-Lesezeichen">
    {#each items as item (item.name + item.frequency)}
      <button class="chip" type="button" onclick={() => onpick(item)}>
        {item.name}
        <span class="ml-1 font-mono text-accent-600 dark:text-accent-400">{mhz(item.frequency, 3)}</span>
      </button>
    {/each}
    <a class="chip" href="#/bookmarks">+ Lesezeichen</a>
  </div>
{/if}
