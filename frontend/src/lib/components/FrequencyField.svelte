<script lang="ts">
  import { mhz, parseFrequency } from '../format';
  import { sdr } from '../stores.svelte';

  let {
    value = $bindable(),
    label = 'Frequenz',
    id = 'frequency',
    checkDevice = true,
  }: { value: number; label?: string; id?: string; checkDevice?: boolean } = $props();

  let text = $state('');
  let lastValue = 0;

  // keep the text in sync when the value changes from outside (presets)
  $effect(() => {
    if (value !== lastValue) {
      text = value ? String(+(value / 1e6).toFixed(6)) : '';
      lastValue = value;
    }
  });

  const parsed = $derived(parseFrequency(text));
  const outOfRange = $derived(checkDevice && parsed !== null && !sdr.supports(parsed));

  function update() {
    if (parsed !== null) {
      lastValue = parsed;
      value = parsed;
    }
  }
</script>

<div>
  <label class="label" for={id}>{label} (MHz)</label>
  <input
    {id}
    class="input font-mono"
    inputmode="decimal"
    bind:value={text}
    oninput={update}
    aria-invalid={parsed === null || outOfRange}
    placeholder="144.800"
  />
  {#if parsed === null && text}
    <p class="mt-1 text-xs text-red-500">Ungültige Frequenz — z. B. 144.8, 433.92M oder 1090 MHz</p>
  {:else if outOfRange}
    <p class="mt-1 text-xs text-amber-600">
      {mhz(parsed)} liegt ausserhalb von {sdr.detect?.type?.toUpperCase()} ({sdr.detect?.frequency_range
        ?.min_mhz}–{sdr.detect?.frequency_range?.max_mhz} MHz)
    </p>
  {:else}
    <p class="hint">{mhz(parsed)}</p>
  {/if}
</div>
