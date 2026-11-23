<script lang="ts">
  // APRS symbol image (aprs.fi set, built into the web image under /aprs-symbols/)
  let { id, name = '', size = 24 }: { id?: string | null; name?: string | null; size?: number } = $props();

  let failed = $state(false);
  const valid = $derived(!!id && /^[a-z0-9-]+$/.test(id));
</script>

{#if valid && !failed}
  <img
    src={`/aprs-symbols/${id}.png`}
    alt={name ?? ''}
    title={name ?? ''}
    width={size}
    height={size}
    class="inline-block max-w-none shrink-0"
    style="width: {size}px; height: {size}px"
    loading="lazy"
    onerror={() => (failed = true)}
  />
{:else}
  <span class="inline-block shrink-0" style="width: {size}px; height: {size}px" aria-hidden="true"></span>
{/if}
