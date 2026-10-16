<script lang="ts">
  import type { Snippet } from 'svelte';

  let { title, description, actions }: { title: string; description?: string; actions?: Snippet } = $props();
</script>

<header class="mb-6 flex flex-wrap items-start justify-between gap-4">
  <div>
    <h1 class="text-xl font-semibold">{title}</h1>
    {#if description}<p class="mt-1 text-sm text-slate-500 dark:text-slate-400">{description}</p>{/if}
  </div>
  {#if actions}<div class="flex flex-wrap gap-2">{@render actions()}</div>{/if}
</header>
