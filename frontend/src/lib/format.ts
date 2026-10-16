// Formatting helpers (pure functions, unit tested)

export function mhz(hz: number | null | undefined, digits = 4): string {
  if (hz === null || hz === undefined || !Number.isFinite(hz)) return '—';
  return `${(hz / 1e6).toFixed(digits)} MHz`;
}

/** Parse "144.8", "144.800 MHz", "433920000" or "433.92M" into Hz. */
export function parseFrequency(input: string): number | null {
  const s = input.trim().toLowerCase().replace(',', '.').replace(/\s+/g, '');
  if (!s) return null;
  const match = s.match(/^(\d+(?:\.\d+)?)(hz|khz|k|mhz|m|ghz|g)?$/);
  if (!match) return null;
  const value = parseFloat(match[1]);
  const unit = match[2];
  let hz: number;
  if (unit === 'ghz' || unit === 'g') hz = value * 1e9;
  else if (unit === 'mhz' || unit === 'm') hz = value * 1e6;
  else if (unit === 'khz' || unit === 'k') hz = value * 1e3;
  else if (unit === 'hz') hz = value;
  else hz = value < 100_000 ? value * 1e6 : value; // bare small numbers are MHz
  return Math.round(hz);
}

export function duration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds)) return '—';
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  if (m) return `${m}m ${String(sec).padStart(2, '0')}s`;
  return `${sec}s`;
}

export function bytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(i ? 1 : 0)} ${units[i]}`;
}

export function time(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleTimeString('de-CH');
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('de-CH');
}

export function relative(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '—';
  const diff = (now - new Date(iso).getTime()) / 1000;
  if (!Number.isFinite(diff)) return '—';
  if (diff < 0) return `in ${duration(-diff)}`;
  if (diff < 60) return 'gerade eben';
  return `vor ${duration(diff)}`;
}

export function packetTime(p: { timestamp?: string; '@timestamp'?: string }): string | undefined {
  return p['@timestamp'] ?? p.timestamp;
}
