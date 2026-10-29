<script lang="ts">
  import { CircleAlert, CircleCheck, Info, TriangleAlert, X } from '@lucide/svelte';
  import { toasts } from '../stores.svelte';
  import { t } from '../i18n.svelte';

  const icons = { info: Info, success: CircleCheck, error: CircleAlert, warning: TriangleAlert };
  const colors = {
    info: 'border-sky-500/40 text-sky-700 dark:text-sky-300',
    success: 'border-emerald-500/40 text-emerald-700 dark:text-emerald-300',
    error: 'border-red-500/40 text-red-700 dark:text-red-300',
    warning: 'border-amber-500/40 text-amber-700 dark:text-amber-300',
  };
</script>

<div class="pointer-events-none fixed top-4 right-4 z-[2000] flex w-80 flex-col gap-2" aria-live="polite">
  {#each toasts.items as toast (toast.id)}
    {@const Icon = icons[toast.kind]}
    <div
      class="pointer-events-auto flex items-start gap-3 rounded-lg border bg-white p-3 text-sm shadow-lg dark:bg-slate-900 {colors[
        toast.kind
      ]}"
      role={toast.kind === 'error' ? 'alert' : 'status'}
    >
      <Icon size={18} class="mt-0.5 shrink-0" />
      <span class="flex-1 break-words text-slate-800 dark:text-slate-200">{toast.message}</span>
      <button
        class="text-slate-400 hover:text-slate-600"
        onclick={() => toasts.dismiss(toast.id)}
        aria-label={t('Schliessen')}
      >
        <X size={14} />
      </button>
    </div>
  {/each}
</div>
