import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, api, authHeaders, buildUrl, setApiKey } from './api';

afterEach(() => {
  setApiKey('');
  vi.unstubAllGlobals();
});

describe('api client', () => {
  it('builds URLs and drops empty params', () => {
    expect(buildUrl('/aprs/search', { hours: 24, callsign: '', limit: undefined })).toBe(
      '/api/aprs/search?hours=24',
    );
  });

  it('sends the API key header', () => {
    setApiKey('secret');
    expect(authHeaders()).toEqual({ 'X-API-Key': 'secret' });
  });

  it('raises ApiError with the server message', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ error: 'SDR device is busy' }), { status: 409 })),
    );
    await expect(api.post('/stream-decode', {})).rejects.toMatchObject({
      status: 409,
      message: 'SDR device is busy',
    });
  });

  it('reports unreachable API as status 0', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('network');
      }),
    );
    const err = (await api.get('/health').catch((e: unknown) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(0);
  });
});
