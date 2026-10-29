<script lang="ts">
  import { KeyRound, X } from '@lucide/svelte';
  import { api } from '../api';
  import { i18n, LOCALES, t } from '../i18n.svelte';
  import { live, sdr, settings, toasts, type Theme } from '../stores.svelte';
  import type { DeviceType } from '../types';

  let { open = $bindable(false) }: { open?: boolean } = $props();

  let dialog: HTMLDialogElement;
  let key = $state(settings.apiKey);
  let device = $state<DeviceType>(settings.deviceType);
  let address = $state(settings.usrpAddress);
  let testing = $state(false);

  $effect(() => {
    if (open && !dialog.open) {
      key = settings.apiKey;
      device = settings.deviceType;
      address = settings.usrpAddress;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });

  const addressValid = $derived(
    device !== 'usrp' || /^(\d{1,3}\.){3}\d{1,3}$|^[0-9a-fA-F:]+$/.test(address.trim()),
  );

  async function saveAndTest() {
    settings.setApiKey(key);
    settings.setDevice(device, address.trim());
    testing = true;
    try {
      await api.get('/stats');
      toasts.push(t('Verbindung zur API funktioniert'), 'success');
      open = false;
    } catch (e) {
      toasts.error(e);
    } finally {
      testing = false;
      void sdr.runDetect();
    }
  }
</script>

<dialog
  bind:this={dialog}
  onclose={() => (open = false)}
  class="m-auto w-full max-w-lg rounded-xl border border-slate-200 bg-white p-0 text-slate-900 shadow-2xl backdrop:bg-slate-950/60 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-100"
  aria-labelledby="settings-title"
>
  <form
    method="dialog"
    class="space-y-5 p-6"
    onsubmit={(e) => {
      e.preventDefault();
      void saveAndTest();
    }}
  >
    <div class="flex items-center justify-between">
      <h2 id="settings-title" class="text-lg font-semibold">{t('Einstellungen')}</h2>
      <button
        type="button"
        class="text-slate-400 hover:text-slate-600"
        onclick={() => (open = false)}
        aria-label={t('Schliessen')}><X size={18} /></button
      >
    </div>

    <div>
      <label class="label" for="api-key">{t('API-Key')}</label>
      <div class="relative">
        <KeyRound size={16} class="absolute top-2.5 left-3 text-slate-400" />
        <input
          id="api-key"
          class="input pl-9 font-mono"
          type="password"
          autocomplete="off"
          bind:value={key}
          placeholder={t('aus .env (API_KEYS)')}
        />
      </div>
      <p class="hint">
        {t('Wird nur in diesem Browser gespeichert. Den Key zeigt ./scripts/setup-env.sh an.')}
      </p>
    </div>

    <div class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div>
        <label class="label" for="device">{t('SDR-Gerät')}</label>
        <select id="device" class="input" bind:value={device}>
          <option value="auto">{t('Automatisch erkennen')}</option>
          <option value="hackrf">HackRF One</option>
          <option value="rtlsdr">RTL-SDR</option>
          <option value="airspyhf">Airspy HF+</option>
          <option value="usrp">{t('USRP N200 (Netzwerk)')}</option>
        </select>
      </div>
      {#if device === 'usrp'}
        <div>
          <label class="label" for="usrp">{t('USRP IP-Adresse')}</label>
          <input
            id="usrp"
            class="input font-mono"
            bind:value={address}
            placeholder="192.168.10.2"
            aria-invalid={!addressValid}
          />
          {#if !addressValid}<p class="mt-1 text-xs text-red-500">
              {t('Bitte eine IP-Adresse eingeben')}
            </p>{/if}
        </div>
      {/if}
    </div>

    <fieldset>
      <legend class="label">Sprache / Language</legend>
      <div class="flex gap-2">
        {#each LOCALES as l (l.value)}
          <button
            type="button"
            class="chip {i18n.locale === l.value
              ? '!border-accent-500 text-accent-600 dark:text-accent-400'
              : ''}"
            onclick={() => i18n.set(l.value)}
            aria-pressed={i18n.locale === l.value}>{l.label}</button
          >
        {/each}
      </div>
    </fieldset>

    <fieldset>
      <legend class="label">{t('Darstellung')}</legend>
      <div class="flex gap-2">
        {#each [['system', t('System')], ['dark', t('Dunkel')], ['light', t('Hell')]] as [value, text] (value)}
          <button
            type="button"
            class="chip {settings.theme === value
              ? '!border-accent-500 text-accent-600 dark:text-accent-400'
              : ''}"
            onclick={() => settings.setTheme(value as Theme)}
            aria-pressed={settings.theme === value}>{text}</button
          >
        {/each}
      </div>
    </fieldset>

    <div class="rounded-lg bg-slate-100 p-3 text-xs text-slate-600 dark:bg-slate-800 dark:text-slate-400">
      SDR: {sdr.detect?.detected ? sdr.detect.type.toUpperCase() : t('nicht erkannt')} · {t(
        'Live-Verbindung',
      )}: {live.state}
    </div>

    <div class="flex justify-end gap-2">
      <button type="button" class="btn-secondary" onclick={() => (open = false)}>{t('Abbrechen')}</button>
      <button type="submit" class="btn-primary" disabled={testing || !addressValid}
        >{t('Speichern & testen')}</button
      >
    </div>
  </form>
</dialog>
