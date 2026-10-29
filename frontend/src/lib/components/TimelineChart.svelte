<script lang="ts">
  // Stacked bar chart of events per hour (plain SVG, no chart library)
  import { t } from '../i18n.svelte';
  let {
    rows,
    series,
  }: {
    rows: ({ time: string } & Record<string, number | string>)[];
    series: { key: string; label: string; color: string }[];
  } = $props();

  const width = 720;
  const height = 160;
  const max = $derived(
    Math.max(1, ...rows.map((r) => series.reduce((sum, s) => sum + (Number(r[s.key]) || 0), 0))),
  );
  const barWidth = $derived(rows.length ? width / rows.length : width);
</script>

<figure>
  <svg
    viewBox="0 0 {width} {height + 20}"
    class="h-44 w-full"
    role="img"
    aria-label={t('Aktivität pro Stunde')}
  >
    {#each rows as row, i (row.time)}
      {@const hour = new Date(row.time).getHours()}
      {#each series as s, j (s.key)}
        {@const below = series.slice(0, j).reduce((sum, x) => sum + (Number(row[x.key]) || 0), 0)}
        {@const value = Number(row[s.key]) || 0}
        {#if value}
          <rect
            x={i * barWidth + 1}
            width={Math.max(1, barWidth - 2)}
            y={height - ((below + value) / max) * height}
            height={(value / max) * height}
            fill={s.color}
            rx="1"
          >
            <title>{hour}:00 — {s.label}: {value}</title>
          </rect>
        {/if}
      {/each}
      {#if i % Math.max(1, Math.ceil(rows.length / 12)) === 0}
        <text
          x={i * barWidth + barWidth / 2}
          y={height + 15}
          text-anchor="middle"
          class="fill-slate-500 text-[10px]">{hour}h</text
        >
      {/if}
    {/each}
    <line x1="0" x2={width} y1={height} y2={height} class="stroke-slate-300 dark:stroke-slate-700" />
  </svg>
  <figcaption class="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
    {#each series as s (s.key)}
      <span class="flex items-center gap-1.5"
        ><span class="h-2.5 w-2.5 rounded-sm" style="background: {s.color}"></span>{s.label}</span
      >
    {/each}
  </figcaption>
</figure>
