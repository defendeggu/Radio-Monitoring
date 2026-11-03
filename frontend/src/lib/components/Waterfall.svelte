<script lang="ts">
  import { onMount } from 'svelte';
  import { mhz } from '../format';
  import { t } from '../i18n.svelte';
  import { colormap, colourIndex, type ColormapName } from '../spectrum/colormap';
  import type { SpectrumRow } from '../spectrum/frames';

  export interface Marker {
    frequency: number;
    label: string;
    kind?: 'bookmark' | 'spot';
  }

  let {
    channel = null,
    channelWidth = 0,
    markers = [],
    colormapName = 'classic',
    auto = true,
    lo = $bindable(-110),
    hi = $bindable(-40),
    onpick,
    onretune,
  }: {
    channel?: number | null;
    channelWidth?: number;
    markers?: Marker[];
    colormapName?: ColormapName;
    auto?: boolean;
    lo?: number;
    hi?: number;
    onpick?: (frequency: number, shift: boolean) => void;
    onretune?: (centre: number) => void;
  } = $props();

  const HISTORY = 300;
  let rows: SpectrumRow[] = [];
  let latest = $state<SpectrumRow | null>(null);
  let avg: Float32Array | null = null;
  let peak: Float32Array | null = null;
  let zoom = $state({ start: 0, end: 1 });
  let hover = $state<{ x: number; frequency: number; db: number } | null>(null);
  let drag: { x: number; centre: number } | null = null;

  let line: HTMLCanvasElement;
  let fall: HTMLCanvasElement;
  let box: HTMLDivElement;
  let width = $state(800);

  const lut = $derived(colormap(colormapName));

  /** dB of bin i of a row */
  function db(row: SpectrumRow, i: number): number {
    return row.dbMin + (row.bins[i] * (row.dbMax - row.dbMin)) / 255;
  }

  function visible(row: SpectrumRow): [number, number] {
    const n = row.bins.length;
    return [Math.floor(zoom.start * n), Math.max(Math.floor(zoom.start * n) + 2, Math.ceil(zoom.end * n))];
  }

  /** Frequency at horizontal position x (CSS pixels) */
  function freqAt(x: number, row: SpectrumRow | null = latest): number {
    if (!row) return 0;
    const f = zoom.start + (x / width) * (zoom.end - zoom.start);
    return Math.round(row.centre - row.span / 2 + f * row.span);
  }

  function xOf(frequency: number, row: SpectrumRow): number {
    const f = (frequency - (row.centre - row.span / 2)) / row.span;
    return ((f - zoom.start) / (zoom.end - zoom.start)) * width;
  }

  export function addRow(row: SpectrumRow) {
    const last = rows[0];
    if (
      last &&
      (last.centre !== row.centre || last.span !== row.span || last.bins.length !== row.bins.length)
    ) {
      rows = [];
      avg = peak = null;
    }
    rows.unshift(row);
    if (rows.length > HISTORY) rows.length = HISTORY;
    const n = row.bins.length;
    if (!avg || !peak || avg.length !== n) {
      avg = new Float32Array(n);
      peak = new Float32Array(n);
      for (let i = 0; i < n; i++) avg[i] = peak[i] = db(row, i);
    }
    for (let i = 0; i < n; i++) {
      const v = db(row, i);
      avg[i] = 0.7 * avg[i] + 0.3 * v;
      peak[i] = Math.max(v, peak[i] - 0.3);
    }
    if (auto) autoRange(row);
    latest = row;
    drawRow(row);
    drawLine();
  }

  export function clear() {
    rows = [];
    avg = peak = null;
    latest = null;
    fall?.getContext('2d')?.clearRect(0, 0, fall.width, fall.height);
    drawLine();
  }

  function autoRange(row: SpectrumRow) {
    const values = Array.from(row.bins).sort((a, b) => a - b);
    const floor = row.dbMin + (values[Math.floor(values.length * 0.1)] * (row.dbMax - row.dbMin)) / 255;
    const top = row.dbMin + (values[values.length - 1] * (row.dbMax - row.dbMin)) / 255;
    lo = Math.round(0.9 * lo + 0.1 * (floor - 5));
    hi = Math.round(0.9 * hi + 0.1 * Math.max(floor + 30, top + 5));
  }

  function paint(ctx: CanvasRenderingContext2D, row: SpectrumRow, y: number, cols: number) {
    const [i0, i1] = visible(row);
    const image = ctx.createImageData(cols, 1);
    for (let x = 0; x < cols; x++) {
      const i = i0 + Math.floor((x / cols) * (i1 - i0));
      const c = colourIndex(db(row, i), lo, hi) * 3;
      image.data[x * 4] = lut[c];
      image.data[x * 4 + 1] = lut[c + 1];
      image.data[x * 4 + 2] = lut[c + 2];
      image.data[x * 4 + 3] = 255;
    }
    ctx.putImageData(image, 0, y);
  }

  function columns(): number {
    return Math.max(64, Math.min(2048, Math.round(width)));
  }

  function drawRow(row: SpectrumRow) {
    const ctx = fall?.getContext('2d');
    if (!ctx) return;
    const cols = columns();
    if (fall.width !== cols || fall.height !== HISTORY) return redraw();
    ctx.drawImage(fall, 0, 0, cols, HISTORY - 1, 0, 1, cols, HISTORY - 1);
    paint(ctx, row, 0, cols);
  }

  function redraw() {
    const ctx = fall?.getContext('2d');
    if (!ctx) return;
    fall.width = columns();
    fall.height = HISTORY;
    ctx.fillStyle = 'rgb(0,0,20)';
    ctx.fillRect(0, 0, fall.width, fall.height);
    rows.forEach((row, y) => paint(ctx, row, y, fall.width));
  }

  function drawLine() {
    const ctx = line?.getContext('2d');
    if (!ctx) return;
    const ratio = window.devicePixelRatio || 1;
    const h = 140;
    line.width = Math.round(width * ratio);
    line.height = h * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const dark = document.documentElement.classList.contains('dark');
    ctx.fillStyle = dark ? '#020617' : '#f8fafc';
    ctx.fillRect(0, 0, width, h);
    const row = latest;
    ctx.font = '10px ui-monospace, monospace';
    // dB grid
    ctx.strokeStyle = dark ? '#1e293b' : '#e2e8f0';
    ctx.fillStyle = dark ? '#64748b' : '#94a3b8';
    for (let d = Math.ceil(lo / 10) * 10; d <= hi; d += 10) {
      const y = h - ((d - lo) / (hi - lo)) * h;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
      ctx.fillText(`${d}`, 2, y - 2);
    }
    if (!row || !avg || !peak) return;
    const [i0, i1] = visible(row);
    const yOf = (v: number) => h - ((v - lo) / (hi - lo)) * h;
    for (const [series, colour] of [
      [peak, dark ? 'rgba(148,163,184,0.5)' : 'rgba(100,116,139,0.5)'],
      [avg, '#06b6d4'],
    ] as [Float32Array, string][]) {
      ctx.strokeStyle = colour;
      ctx.beginPath();
      for (let i = i0; i < i1; i++) {
        const x = ((i - i0) / (i1 - i0 - 1)) * width;
        if (i === i0) ctx.moveTo(x, yOf(series[i]));
        else ctx.lineTo(x, yOf(series[i]));
      }
      ctx.stroke();
    }
    // listening channel
    if (channel !== null) {
      const x = xOf(channel, row);
      const w = Math.max(2, (channelWidth / row.span / (zoom.end - zoom.start)) * width);
      ctx.fillStyle = 'rgba(16,185,129,0.18)';
      ctx.fillRect(x - w / 2, 0, w, h);
      ctx.strokeStyle = '#10b981';
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, h);
      ctx.stroke();
    }
    // markers (bookmarks, spots)
    for (const m of markers) {
      const x = xOf(m.frequency, row);
      if (x < 0 || x > width) continue;
      ctx.strokeStyle = m.kind === 'spot' ? '#f59e0b' : '#a855f7';
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(x, h - 14);
      ctx.lineTo(x, h);
      ctx.stroke();
      ctx.save();
      ctx.translate(x + 2, h - 16);
      ctx.rotate(-Math.PI / 2);
      ctx.fillText(m.label, 0, 0);
      ctx.restore();
    }
  }

  // repaint when the display settings change
  $effect(() => {
    void [lo, hi, lut, zoom.start, zoom.end, width];
    redraw();
    drawLine();
  });
  $effect(() => {
    void [channel, channelWidth, markers];
    drawLine();
  });

  onMount(() => {
    const observer = new ResizeObserver(() => (width = box.clientWidth || 800));
    observer.observe(box);
    width = box.clientWidth || 800;
    return () => observer.disconnect();
  });

  function pos(e: MouseEvent): number {
    return e.clientX - box.getBoundingClientRect().left;
  }

  function move(e: MouseEvent) {
    if (!latest) return;
    const x = pos(e);
    const frequency = freqAt(x);
    const [i0, i1] = visible(latest);
    const i = Math.min(i1 - 1, i0 + Math.floor((x / width) * (i1 - i0)));
    hover = { x, frequency, db: Math.round(db(latest, Math.max(0, i))) };
  }

  function down(e: MouseEvent) {
    if (latest) drag = { x: pos(e), centre: latest.centre };
  }

  function up(e: MouseEvent) {
    if (!drag || !latest) return;
    const dx = pos(e) - drag.x;
    if (Math.abs(dx) > 6 && onretune) {
      const hzPerPx = (latest.span * (zoom.end - zoom.start)) / width;
      onretune(Math.round(drag.centre - dx * hzPerPx));
    } else {
      onpick?.(freqAt(pos(e)), e.shiftKey);
    }
    drag = null;
  }

  /** Zoom by `factor` around the view fraction `f` (0 = left edge, 1 = right edge) */
  function zoomAt(f: number, factor: number) {
    const span = Math.min(1, Math.max(0.02, (zoom.end - zoom.start) * factor));
    let start = f - (f - zoom.start) * (span / (zoom.end - zoom.start));
    start = Math.min(Math.max(0, start), 1 - span);
    zoom = { start, end: start + span };
  }

  function wheel(e: WheelEvent) {
    e.preventDefault();
    zoomAt(zoom.start + (pos(e) / width) * (zoom.end - zoom.start), e.deltaY > 0 ? 1.25 : 0.8);
  }

  /** Keyboard: arrows move the channel (Shift = 10×), +/- zoom around the channel */
  function key(e: KeyboardEvent) {
    if (!latest) return;
    const here = channel ?? latest.centre;
    const step =
      Math.max(10, Math.round((latest.span * (zoom.end - zoom.start)) / 200)) * (e.shiftKey ? 10 : 1);
    const f = (here - (latest.centre - latest.span / 2)) / latest.span;
    if (e.key === 'ArrowLeft' || e.key === 'ArrowDown') onpick?.(here - step, false);
    else if (e.key === 'ArrowRight' || e.key === 'ArrowUp') onpick?.(here + step, false);
    else if (e.key === '+' || e.key === '=') zoomAt(f, 0.8);
    else if (e.key === '-') zoomAt(f, 1.25);
    else return;
    e.preventDefault();
  }
</script>

<div class="space-y-1">
  <div
    bind:this={box}
    class="relative cursor-crosshair overflow-hidden rounded-lg border border-slate-200 select-none dark:border-slate-800"
    role="slider"
    tabindex="0"
    aria-label={t(
      'Spektrum und Wasserfall: klicken zum Abstimmen, ziehen zum Verschieben, Mausrad zum Zoomen',
    )}
    aria-valuemin={latest ? latest.centre - latest.span / 2 : 0}
    aria-valuemax={latest ? latest.centre + latest.span / 2 : 0}
    aria-valuenow={channel ?? latest?.centre ?? 0}
    aria-valuetext={mhz(channel ?? latest?.centre)}
    onkeydown={key}
    onmousemove={move}
    onmouseleave={() => (hover = null)}
    onmousedown={down}
    onmouseup={up}
    onwheel={wheel}
  >
    <canvas bind:this={line} style="width: 100%; height: 140px; display: block"></canvas>
    <canvas bind:this={fall} style="width: 100%; height: 300px; display: block; image-rendering: pixelated"
    ></canvas>
    {#if hover}
      <div class="pointer-events-none absolute top-0 h-full w-px bg-white/60" style="left: {hover.x}px"></div>
      <div
        class="pointer-events-none absolute top-1 rounded bg-slate-900/80 px-1.5 py-0.5 font-mono text-xs text-white"
        style="left: {Math.min(hover.x + 8, width - 150)}px"
      >
        {mhz(hover.frequency, 4)} · {hover.db} dB
      </div>
    {/if}
    {#if !latest}
      <div class="absolute inset-0 flex items-center justify-center text-sm text-slate-400">
        {t('Warte auf Daten…')}
      </div>
    {/if}
  </div>
  {#if latest}
    <div class="flex justify-between font-mono text-xs text-slate-500">
      <span>{(freqAt(0) / 1e6).toFixed(4)}</span>
      <span>{mhz(freqAt(width / 2), 4)}</span>
      <span>{(freqAt(width) / 1e6).toFixed(4)}</span>
    </div>
    {#if zoom.end - zoom.start < 1}
      <button class="text-xs text-cyan-600 hover:underline" onclick={() => (zoom = { start: 0, end: 1 })}
        >{t('Zoom zurücksetzen')}</button
      >
    {/if}
  {/if}
</div>
