// Small typed client for the RadioMoni API (served same-origin under /api by nginx).

import { t } from './i18n.svelte';

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api';
const KEY_STORAGE = 'radiomoni.apiKey';

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? '';
  } catch {
    return '';
  }
}

export function setApiKey(key: string): void {
  try {
    if (key) localStorage.setItem(KEY_STORAGE, key);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage unavailable (private mode) — key lives only for this page */
  }
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const key = getApiKey();
  return key ? { 'X-API-Key': key, ...extra } : extra;
}

type Query = Record<string, string | number | boolean | undefined | null>;

export function buildUrl(path: string, query?: Query): string {
  const url = API_BASE + path;
  if (!query) return url;
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(query)) {
    if (v !== undefined && v !== null && v !== '') params.set(k, String(v));
  }
  const qs = params.toString();
  return qs ? `${url}?${qs}` : url;
}

async function request<T>(method: string, path: string, body?: unknown, query?: Query): Promise<T> {
  const init: RequestInit = {
    method,
    headers: authHeaders(body !== undefined ? { 'Content-Type': 'application/json' } : {}),
  };
  if (body !== undefined) init.body = JSON.stringify(body);
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), init);
  } catch {
    throw new ApiError(t('API nicht erreichbar'), 0);
  }
  const text = await response.text();
  let data: Record<string, unknown> = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.slice(0, 200) };
    }
  }
  if (!response.ok) {
    const message =
      (data.error as string) ||
      (data.message as string) ||
      (response.status === 401 ? t('API-Key fehlt') : `HTTP ${response.status}`);
    throw new ApiError(message, response.status, data);
  }
  return data as T;
}

export const api = {
  get: <T>(path: string, query?: Query) => request<T>('GET', path, undefined, query),
  post: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
  put: <T>(path: string, body: unknown) => request<T>('PUT', path, body),
  del: <T>(path: string) => request<T>('DELETE', path),
};

/** Fetch a protected file (e.g. a recording) as an object URL for <audio>/<a download>. */
export async function fetchBlobUrl(path: string): Promise<string> {
  const response = await fetch(buildUrl(path), { headers: authHeaders() });
  if (!response.ok) throw new ApiError(`HTTP ${response.status}`, response.status);
  return URL.createObjectURL(await response.blob());
}

/** Download a protected file through the browser. */
export async function download(path: string, filename: string): Promise<void> {
  const url = await fetchBlobUrl(path);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
