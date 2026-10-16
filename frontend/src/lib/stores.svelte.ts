// Global UI state (Svelte 5 runes). Imported by components as singletons.

import { api, getApiKey, setApiKey } from './api';
import { connectEvents, type LiveConnection } from './sse';
import type { DeviceType, LiveEvent, SdrDetect, SdrStatus } from './types';

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(`radiomoni.${key}`);
    return raw === null ? fallback : (JSON.parse(raw) as T);
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown): void {
  try {
    localStorage.setItem(`radiomoni.${key}`, JSON.stringify(value));
  } catch {
    /* ignore */
  }
}

// ------------------------------------------------------------------ settings
export type Theme = 'system' | 'dark' | 'light';

class Settings {
  theme = $state<Theme>(loadTheme());
  apiKey = $state(getApiKey());
  deviceType = $state<DeviceType>(load('deviceType', 'auto'));
  usrpAddress = $state<string>(load('usrpAddress', ''));
  sidebarCollapsed = $state<boolean>(load('sidebarCollapsed', false));

  setTheme(theme: Theme) {
    this.theme = theme;
    try {
      localStorage.setItem('radiomoni.theme', theme);
    } catch {
      /* ignore */
    }
    applyTheme(theme);
  }

  setApiKey(key: string) {
    this.apiKey = key.trim();
    setApiKey(this.apiKey);
    live.restart();
    sdr.refresh();
  }

  setDevice(type: DeviceType, address = this.usrpAddress) {
    this.deviceType = type;
    this.usrpAddress = address;
    save('deviceType', type);
    save('usrpAddress', address);
  }

  toggleSidebar() {
    this.sidebarCollapsed = !this.sidebarCollapsed;
    save('sidebarCollapsed', this.sidebarCollapsed);
  }

  /** Device parameters for request bodies */
  deviceParams(): { device_type: DeviceType; device_address?: string } {
    return this.deviceType === 'usrp'
      ? { device_type: 'usrp', device_address: this.usrpAddress }
      : { device_type: this.deviceType };
  }
}

function loadTheme(): Theme {
  try {
    return (localStorage.getItem('radiomoni.theme') as Theme) || 'system';
  } catch {
    return 'system';
  }
}

export function applyTheme(theme: Theme): void {
  const dark =
    theme === 'dark' || (theme === 'system' && window.matchMedia?.('(prefers-color-scheme: dark)').matches);
  document.documentElement.classList.toggle('dark', !!dark);
}

export const settings = new Settings();

// ------------------------------------------------------------------ toasts
export interface Toast {
  id: number;
  kind: 'info' | 'success' | 'error' | 'warning';
  message: string;
}

class Toasts {
  items = $state<Toast[]>([]);
  private next = 1;

  push(message: string, kind: Toast['kind'] = 'info', timeout = 5000) {
    const id = this.next++;
    this.items = [...this.items.slice(-4), { id, kind, message }];
    if (timeout) setTimeout(() => this.dismiss(id), timeout);
  }

  dismiss(id: number) {
    this.items = this.items.filter((t) => t.id !== id);
  }

  error(e: unknown) {
    this.push(e instanceof Error ? e.message : String(e), 'error', 8000);
  }
}

export const toasts = new Toasts();

// ------------------------------------------------------------------ SDR
class Sdr {
  detect = $state<SdrDetect | null>(null);
  status = $state<SdrStatus | null>(null);
  apiReachable = $state(true);
  authRequired = $state(false);
  private timer: ReturnType<typeof setInterval> | null = null;

  get busy(): boolean {
    return !!this.status?.busy;
  }

  async refresh() {
    try {
      this.status = await api.get<SdrStatus>('/sdr/status');
      this.apiReachable = true;
      this.authRequired = false;
    } catch (e) {
      const status = (e as { status?: number }).status;
      this.apiReachable = status !== 0;
      this.authRequired = status === 401 || status === 403;
    }
  }

  async runDetect() {
    try {
      this.detect = await api.get<SdrDetect>('/sdr/detect');
    } catch {
      this.detect = null;
    }
  }

  start() {
    void this.refresh();
    void this.runDetect();
    this.timer ??= setInterval(() => void this.refresh(), 10_000);
  }

  /** Is `hz` inside the range of the detected device? (true when unknown) */
  supports(hz: number): boolean {
    const range = this.detect?.frequency_range;
    return !range || (hz >= range.min_hz && hz <= range.max_hz);
  }
}

export const sdr = new Sdr();

// ------------------------------------------------------------------ live events
type Listener = (event: LiveEvent) => void;

class Live {
  state = $state<'connecting' | 'open' | 'closed'>('closed');
  recent = $state<LiveEvent[]>([]);
  private connection: LiveConnection | null = null;
  private listeners = new Set<Listener>();

  start() {
    if (this.connection) return;
    this.connection = connectEvents(
      (event) => this.dispatch(event),
      (state) => (this.state = state),
    );
  }

  restart() {
    this.connection?.close();
    this.connection = null;
    this.start();
  }

  /** Subscribe to events; returns an unsubscribe function (use in $effect). */
  on(types: string[], fn: Listener): () => void {
    const listener: Listener = (e) => {
      if (types.includes(e.type)) fn(e);
    };
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private dispatch(event: LiveEvent) {
    if (event.type !== 'adsb_snapshot') {
      this.recent = [event, ...this.recent].slice(0, 100);
    }
    if (['session', 'capture', 'sdr', 'scan'].includes(event.type)) void sdr.refresh();
    if (event.type === 'alert') {
      toasts.push(`Alarm: ${(event.data as { summary?: string }).summary ?? ''}`, 'warning', 10_000);
    }
    for (const listener of this.listeners) listener(event);
  }
}

export const live = new Live();
