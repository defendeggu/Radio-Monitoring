<script lang="ts">
  let { value, label }: { value: number; label?: string } = $props();
</script>

<div>
  {#if label}
    <div class="mb-1 flex justify-between text-xs text-slate-500">
      <span>{label}</span><span>{Math.round(value)}%</span>
    </div>
  {/if}
  <div
    class="h-1.5 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800"
    role="progressbar"
    aria-valuemin={0}
    aria-valuemax={100}
    aria-valuenow={Math.round(value)}
    aria-label={label}
  >
    <div
      class="h-full rounded-full bg-accent-500 transition-all duration-500"
      style="width: {Math.min(100, value)}%"
    ></div>
  </div>
</div>
