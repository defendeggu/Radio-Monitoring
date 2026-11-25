<script lang="ts">
  // How an APRS packet came in: over the air (own receiver) or from the internet (aprs-stats:
  // APRS-IS, aprs.fi import, own beacon). Packets stored before 5.8.0 have no field: over the air.
  import { Globe, RadioTower } from '@lucide/svelte';
  import { t } from '../i18n.svelte';

  let {
    reception,
    source,
    igate,
    alsoRf = false,
  }: {
    reception?: string | null;
    source?: string | null;
    igate?: string | null;
    alsoRf?: boolean;
  } = $props();

  const internet = $derived(reception === 'internet');
  const detail = $derived(
    source === 'import'
      ? t('Import aprs.fi')
      : source === 'beacon'
        ? t('eigene Bake')
        : source === 'aprs_is'
          ? 'APRS-IS'
          : '',
  );
  const title = $derived(
    [
      internet ? t('Über Internet empfangen') : t('Über Funk empfangen'),
      igate ? `iGate ${igate}` : '',
      alsoRf ? t('auch über Funk gehört') : '',
    ]
      .filter(Boolean)
      .join(' · '),
  );
</script>

<span
  class="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs font-medium whitespace-nowrap {internet
    ? 'bg-amber-500/15 text-amber-700 dark:text-amber-400'
    : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400'}"
  {title}
>
  {#if internet}<Globe size={12} aria-hidden="true" />{t('Internet')}{:else}<RadioTower
      size={12}
      aria-hidden="true"
    />{t('Funk')}{/if}
  {#if detail}<span class="font-normal opacity-75">· {detail}</span>{/if}
  {#if alsoRf}<RadioTower size={12} aria-label={t('auch über Funk gehört')} />{/if}
</span>
