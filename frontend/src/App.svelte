<script lang="ts">
  import { Menu } from '@lucide/svelte';
  import SettingsDialog from './lib/components/SettingsDialog.svelte';
  import Sidebar from './lib/components/Sidebar.svelte';
  import Toasts from './lib/components/Toasts.svelte';
  import { router } from './lib/router.svelte';
  import { t } from './lib/i18n.svelte';
  import { live, sdr, settings } from './lib/stores.svelte';
  import { routes } from './routes';

  let settingsOpen = $state(false);
  let mobileOpen = $state(false);

  const route = $derived(routes.find((r) => r.path === router.path) ?? routes[0]);

  $effect(() => {
    sdr.start();
    live.start();
    if (!settings.apiKey) settingsOpen = true;
  });

  $effect(() => {
    document.title = `${route.label()} · RadioMoni`;
  });
</script>

<div class="flex h-screen overflow-hidden">
  <Sidebar onsettings={() => (settingsOpen = true)} bind:mobileOpen />

  <main class="flex-1 overflow-y-auto">
    <div
      class="flex items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:hidden dark:border-slate-800 dark:bg-slate-900"
    >
      <button onclick={() => (mobileOpen = true)} aria-label={t('Menü öffnen')}><Menu size={20} /></button>
      <span class="text-sm font-semibold">RadioMoni · {route.label()}</span>
    </div>

    {#if sdr.authRequired}
      <div
        class="border-b border-amber-500/30 bg-amber-500/10 px-6 py-2 text-sm text-amber-700 dark:text-amber-300"
      >
        {t('Die API verlangt einen API-Key.')}
        <button class="underline" onclick={() => (settingsOpen = true)}>{t('Jetzt eingeben')}</button>
      </div>
    {:else if !sdr.apiReachable}
      <div class="border-b border-red-500/30 bg-red-500/10 px-6 py-2 text-sm text-red-700 dark:text-red-300">
        {t('Die API ist nicht erreichbar. Läuft der Container radio-transcription-api?')}
      </div>
    {/if}

    <div class="mx-auto max-w-6xl p-4 sm:p-6">
      {#key route.path}
        <route.component />
      {/key}
    </div>
  </main>
</div>

<SettingsDialog bind:open={settingsOpen} />
<Toasts />
