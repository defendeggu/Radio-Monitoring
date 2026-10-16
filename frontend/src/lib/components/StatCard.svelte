<script lang="ts">
  let { label, value, hint }: { label: string; value: string | number; hint?: string } = $props();
</script>

<div class="card !p-4">
  <div class="text-xs font-medium tracking-wide text-slate-500 uppercase">{label}</div>
  <div class="mt-1 font-mono text-2xl text-accent-600 dark:text-accent-400">{value}</div>
  {#if hint}<div class="mt-0.5 text-xs text-slate-500">{hint}</div>{/if}
</div>
