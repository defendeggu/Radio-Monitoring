<script lang="ts">
  import { Square } from '@lucide/svelte';
  import { api } from '../api';
  import { t } from '../i18n.svelte';
  import { dateTime, duration, mhz } from '../format';
  import { live, toasts } from '../stores.svelte';
  import type { StreamSession } from '../types';

  let {
    sessionId,
    countLabel = t('Pakete'),
    onended,
  }: { sessionId: string; countLabel?: string; onended?: (s: StreamSession) => void } = $props();

  let session = $state<StreamSession | null>(null);
  let elapsed = $state(0);
  let stopping = $state(false);

  async function poll() {
    try {
      const r = await api.get<{ session: StreamSession; stats: { elapsed_seconds: number } }>(
        `/stream-decode/${sessionId}`,
      );
      session = r.session;
      elapsed = r.stats.elapsed_seconds;
      if (session.status === 'completed' || session.status === 'failed') onended?.(session);
    } catch (e) {
      if ((e as { status?: number }).status === 404) onended?.(session as StreamSession);
    }
  }

  $effect(() => {
    void poll();
    const timer = setInterval(poll, 3000);
    const off = live.on(['session'], (e) => {
      if ((e.data as { session_id?: string }).session_id === sessionId) void poll();
    });
    return () => {
      clearInterval(timer);
      off();
    };
  });

  async function stop() {
    stopping = true;
    try {
      await api.del(`/stream-decode/${sessionId}`);
      toasts.push(t('Session gestoppt'), 'success');
      await poll();
    } catch (e) {
      toasts.error(e);
    } finally {
      stopping = false;
    }
  }

  const running = $derived(session?.status === 'running' || session?.status === 'starting');
</script>

<div class="card flex flex-wrap items-center gap-6">
  <div class="flex items-center gap-2">
    <span
      class="h-2.5 w-2.5 rounded-full {running
        ? 'animate-pulse bg-emerald-500'
        : session?.status === 'failed'
          ? 'bg-red-500'
          : 'bg-slate-400'}"
    ></span>
    <span class="text-sm font-medium">{session?.status ?? t('lädt…')}</span>
  </div>
  <div class="text-sm">
    <span class="text-slate-500">{t('Frequenz')}</span>
    <span class="font-mono">{mhz(session?.frequency)}</span>
  </div>
  <div class="text-sm">
    <span class="text-slate-500">{countLabel}</span>
    <span class="font-mono text-accent-600 dark:text-accent-400">{session?.packet_count ?? 0}</span>
  </div>
  <div class="text-sm">
    <span class="text-slate-500">{t('Laufzeit')}</span> <span class="font-mono">{duration(elapsed)}</span>
  </div>
  {#if session?.last_packet_time}
    <div class="text-sm">
      <span class="text-slate-500">{t('Letztes')}</span>
      {dateTime(session.last_packet_time)}
    </div>
  {/if}
  {#if session?.error}<div class="w-full text-sm text-red-500">{session.error}</div>{/if}
  {#if running}
    <button class="btn-danger ml-auto" onclick={stop} disabled={stopping}
      ><Square size={14} /> {t('Stoppen')}</button
    >
  {/if}
</div>
