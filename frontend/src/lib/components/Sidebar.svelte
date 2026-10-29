<script lang="ts">
  import { ChevronsLeft, ChevronsRight, Settings } from '@lucide/svelte';
  import { router } from '../router.svelte';
  import { i18n, t } from '../i18n.svelte';
  import { live, sdr, settings } from '../stores.svelte';
  import { routes, groups } from '../../routes';

  let { onsettings, mobileOpen = $bindable(false) }: { onsettings: () => void; mobileOpen?: boolean } =
    $props();

  const collapsed = $derived(settings.sidebarCollapsed && !mobileOpen);
  const visible = $derived(routes.filter((r) => !r.usrpOnly || settings.deviceType === 'usrp'));

  const sdrText = $derived.by(() => {
    if (!sdr.apiReachable) return t('API nicht erreichbar');
    if (sdr.authRequired) return t('API-Key erforderlich');
    if (sdr.status?.busy) return t('Belegt: {kind}', { kind: sdr.status.holder?.kind });
    if (sdr.detect && !sdr.detect.detected) return t('Kein SDR erkannt');
    return sdr.detect?.detected ? t('{type} frei', { type: sdr.detect.type.toUpperCase() }) : t('Prüfe SDR…');
  });
  const sdrColor = $derived(
    !sdr.apiReachable || sdr.authRequired
      ? 'bg-red-500'
      : sdr.status?.busy
        ? 'bg-amber-500 animate-pulse'
        : sdr.detect?.detected
          ? 'bg-emerald-500'
          : 'bg-slate-400',
  );
</script>

<aside
  class="fixed inset-y-0 left-0 z-[1000] flex flex-col border-r border-slate-200 bg-white transition-all duration-200 md:static dark:border-slate-800 dark:bg-slate-900
    {collapsed ? 'w-16' : 'w-64'} {mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}"
  aria-label="Navigation"
>
  <div class="flex items-center gap-3 border-b border-slate-200 px-4 py-4 dark:border-slate-800">
    <img src="/favicon.svg" alt="" class="h-6 w-6 shrink-0" />
    {#if !collapsed}
      <div>
        <div class="text-sm leading-tight font-semibold">RadioMoni</div>
        <div class="text-xs text-slate-500">v4.0</div>
      </div>
    {/if}
  </div>

  <nav class="flex-1 overflow-y-auto px-2 py-3">
    {#each groups as group (group.id)}
      {#if !collapsed}<div
          class="px-3 pt-3 pb-1 text-[10px] font-semibold tracking-widest text-slate-400 uppercase"
        >
          {group.label()}
        </div>{/if}
      {#each visible.filter((r) => r.group === group.id) as route (route.path)}
        {@const Icon = route.icon}
        <a
          href="#/{route.path}"
          onclick={() => (mobileOpen = false)}
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors {router.path ===
          route.path
            ? 'bg-accent-500/10 font-medium text-accent-600 dark:text-accent-400'
            : 'text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800'} {collapsed
            ? 'justify-center'
            : ''}"
          aria-current={router.path === route.path ? 'page' : undefined}
          title={collapsed ? route.label() : undefined}
        >
          <Icon size={18} class="shrink-0" />
          {#if !collapsed}<span>{route.label()}</span>{/if}
        </a>
      {/each}
    {/each}
  </nav>

  <div class="space-y-2 border-t border-slate-200 p-3 dark:border-slate-800">
    <button
      class="flex w-full items-center gap-2 rounded-lg bg-slate-100 px-2 py-1.5 text-left text-xs dark:bg-slate-800 {collapsed
        ? 'justify-center'
        : ''}"
      onclick={onsettings}
      title={sdrText}
    >
      <span class="h-2 w-2 shrink-0 rounded-full {sdrColor}"></span>
      {#if !collapsed}
        <span class="flex-1 truncate">{sdrText}</span>
        <span class="text-slate-400" title={t('Live-Verbindung')}
          >{live.state === 'open' ? '● live' : '○'}</span
        >
      {/if}
    </button>
    <div class="flex gap-2 {collapsed ? 'flex-col' : ''}">
      <button
        class="btn-secondary flex-1 !px-2 !py-1.5 text-xs"
        onclick={onsettings}
        aria-label={t('Einstellungen')}
      >
        <Settings size={14} />{#if !collapsed}{t('Einstellungen')}{/if}
      </button>
      <button
        class="btn-secondary !px-2 !py-1.5 text-xs font-semibold"
        onclick={() => i18n.set(i18n.locale === 'de' ? 'en' : 'de')}
        aria-label={t('Sprache wechseln')}
        title={i18n.locale === 'de' ? 'English' : 'Deutsch'}
      >
        {i18n.locale === 'de' ? 'EN' : 'DE'}
      </button>
      <button
        class="btn-secondary hidden !px-2 !py-1.5 md:inline-flex"
        onclick={() => settings.toggleSidebar()}
        aria-label={t('Seitenleiste ein-/ausklappen')}
      >
        {#if settings.sidebarCollapsed}<ChevronsRight size={14} />{:else}<ChevronsLeft size={14} />{/if}
      </button>
    </div>
  </div>
</aside>

{#if mobileOpen}
  <button
    class="fixed inset-0 z-[999] bg-slate-950/60 md:hidden"
    aria-label={t('Menü schliessen')}
    onclick={() => (mobileOpen = false)}
  ></button>
{/if}
