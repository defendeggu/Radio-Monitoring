<script lang="ts">
  let { text }: { text: string } = $props();
</script>

<p
  class="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500 dark:border-slate-700"
>
  {text}
</p>
