export const API_BASE_URL = 'http://localhost:5000';
export const CAPTURE_URL = API_BASE_URL + '/capture-and-transcribe';

export function getApiKey() {
  return localStorage.getItem('api_key') || '';
}

function authHeaders(extra = {}) {
  const key = getApiKey();
  return { ...(key && { 'X-API-Key': key }), ...extra };
}

export async function apiGet(path) {
  const resp = await fetch(API_BASE_URL + path, { headers: authHeaders() });
  return { resp, data: await resp.json() };
}

export async function apiPost(path, body) {
  const resp = await fetch(API_BASE_URL + path, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(body),
  });
  return { resp, data: await resp.json() };
}

export async function apiDelete(path) {
  const resp = await fetch(API_BASE_URL + path, {
    method: 'DELETE',
    headers: authHeaders(),
  });
  return resp;
}

export async function startCapture(body) {
  const { resp, data } = await apiPost('/capture-and-transcribe', body);
  if (!resp.ok) throw new Error(data.error || 'Failed to start capture');
  return data;
}

export async function getCaptureStatus(captureId) {
  const { resp, data } = await apiGet('/capture-status/' + captureId);
  if (!resp.ok) throw new Error('Status poll failed');
  return data;
}

export async function detectSdr() {
  const { resp, data } = await apiGet('/sdr/detect');
  return { ok: resp.ok, data };
}

export async function forceStopSdr() {
  return apiPost('/sdr/force-stop', {});
}

export async function startStream(body) {
  const { resp, data } = await apiPost('/stream-decode', body);
  if (!resp.ok) throw new Error(data.error || data.message || `HTTP ${resp.status}`);
  return data;
}

export async function getStreamStatus(sessionId) {
  const { resp, data } = await apiGet('/stream-decode/' + sessionId);
  return { ok: resp.ok, status: resp.status, data };
}

export async function stopStream(sessionId) {
  return apiDelete('/stream-decode/' + sessionId);
}

export async function startRepeaterScan(body) {
  const { resp, data } = await apiPost('/scan-repeaters', body);
  return { ok: resp.ok, data };
}

export async function getRepeaterProgress(sessionId) {
  const { resp, data } = await apiGet(`/scan-repeaters/${sessionId}/progress`);
  return { ok: resp.ok, data };
}

export async function startMultiChannel(body) {
  const { resp, data } = await apiPost('/stream/multi/start', body);
  return { ok: resp.ok, data };
}

export function getSdrParams() {
  const deviceType = document.getElementById('globalSdrDevice').value;
  const params = { device_type: deviceType };
  if (deviceType === 'usrp') {
    const ip = document.getElementById('usrpIpAddress').value.trim();
    if (!ip) {
      alert('Bitte IP-Adresse des USRP N200 eingeben (z.B. 192.168.10.2)');
      return null;
    }
    params.device_address = ip;
  }
  return params;
}
