<script lang="ts">
  import { t } from '../i18n.svelte';

  // value: ISO code for Whisper ('' = automatic detection)
  let { value = $bindable(), id = 'language' }: { value: string; id?: string } = $props();

  const LANGUAGES = [
    { code: 'en', label: () => t('Englisch') },
    { code: 'de', label: () => t('Deutsch') },
    { code: 'it', label: () => t('Italienisch') },
    { code: 'fr', label: () => t('Französisch') },
  ];
  const OTHER = 'other';

  let choice = $state('');
  let custom = $state('');
  let lastValue: string | undefined;

  function selection(code: string): string {
    return !code || LANGUAGES.some((l) => l.code === code) ? code : OTHER;
  }

  // follow changes from outside (e.g. a reset) without touching a half-typed code
  $effect(() => {
    if (value !== lastValue) {
      choice = selection(value);
      if (choice === OTHER) custom = value;
      lastValue = value;
    }
  });

  const invalid = $derived(choice === OTHER && custom.trim() !== '' && !/^[a-z]{2,3}$/i.test(custom.trim()));

  function update() {
    lastValue = choice === OTHER ? (invalid ? '' : custom.trim().toLowerCase()) : choice;
    value = lastValue;
  }
</script>

<div>
  <label class="label" for={id}>{t('Sprache||language')}</label>
  <select {id} class="input" bind:value={choice} onchange={update}>
    <option value="">{t('automatisch')}</option>
    {#each LANGUAGES as l (l.code)}<option value={l.code}>{l.label()}</option>{/each}
    <option value={OTHER}>{t('Andere…')}</option>
  </select>
  {#if choice === OTHER}
    <input
      class="input mt-2 font-mono"
      bind:value={custom}
      oninput={update}
      maxlength="3"
      placeholder="es, nl, rm…"
      aria-label={t('ISO-Sprachcode')}
      aria-invalid={invalid}
    />
    {#if invalid}
      <p class="mt-1 text-xs text-red-500">{t('2–3 Buchstaben, z. B. es, nl, rm')}</p>
    {:else}
      <p class="hint">{t('ISO-Sprachcode, leer = automatisch')}</p>
    {/if}
  {/if}
</div>
