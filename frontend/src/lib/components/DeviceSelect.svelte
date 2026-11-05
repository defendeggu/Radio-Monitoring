<script lang="ts">
  import { t } from '../i18n.svelte';
  import { sdr } from '../stores.svelte';

  // Pick the SDR for one start; only shown when more than one SDR is connected.
  let { value = $bindable(''), id = 'device-select' }: { value?: string; id?: string } = $props();

  const standard = $derived(sdr.deviceFor(''));
</script>

{#if sdr.devices.length > 1}
  <div>
    <label class="label" for={id}>{t('SDR')}</label>
    <select {id} class="input" bind:value>
      <option value="">{t('Standard ({label})', { label: standard?.label ?? '–' })}</option>
      {#each sdr.devices as d (d.id)}
        <option value={d.id}
          >{d.label}{d.busy ? (d.preemptible ? ` · ${t('Wasserfall')}` : ` · ${t('belegt')}`) : ''}</option
        >
      {/each}
    </select>
  </div>
{/if}
