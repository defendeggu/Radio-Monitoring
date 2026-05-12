import { startMultiChannel, getStreamStatus, stopStream, getSdrParams } from './api.js';
import { toast } from './toast.js';

let multiChannelCount = 0;
let sessionId = null;
let pollInterval = null;
let startTime = null;

export function init() {
  document.getElementById('addChannelBtn')?.addEventListener('click', () => addChannel());
  document.getElementById('multiResetBtn')?.addEventListener('click', resetForm);
  document.getElementById('multiStopBtn')?.addEventListener('click', stopSession);
  document.getElementById('multiCenterFreq')?.addEventListener('input', updateSpanHint);
  document.getElementById('multiWidebandRate')?.addEventListener('change', updateSpanHint);
  document.getElementById('multiForm')?.addEventListener('submit', handleSubmit);

  // Pre-populate example channels
  addChannel('aprs', 144800000, 'APRS-EU');
  addChannel('pocsag', 147325000, 'POCSAG-1');
}

function addChannel(mode = 'aprs', frequency = '', label = '') {
  const list = document.getElementById('multiChannelList');
  if (list.children.length >= 8) {
    toast('Maximum 8 channels', 'warning');
    return;
  }
  const idx = multiChannelCount++;
  const row = document.createElement('div');
  row.id = `multiCh_${idx}`;
  row.className = 'flex gap-2 items-center flex-wrap';
  row.innerHTML = `
    <select id="multiChMode_${idx}" class="field-input w-auto text-xs py-1.5" onchange="window._updateMultiSpanHint()">
      <option value="aprs" ${mode==='aprs'?'selected':''}>APRS</option>
      <option value="pocsag" ${mode==='pocsag'?'selected':''}>POCSAG</option>
    </select>
    <input type="number" id="multiChFreq_${idx}" placeholder="Frequency (Hz)"
      value="${frequency}" class="field-input w-40 text-xs py-1.5 font-mono" onchange="window._updateMultiSpanHint()" />
    <input type="text" id="multiChLabel_${idx}" placeholder="Label" maxlength="20"
      value="${label}" class="field-input w-28 text-xs py-1.5" />
    <button type="button" onclick="window._removeMultiCh('multiCh_${idx}')"
      class="shrink-0 text-red-400 hover:text-red-300 transition-colors px-2 py-1.5 text-xs border border-red-500/30 rounded-lg">✕</button>
  `;
  list.appendChild(row);
  updateSpanHint();
}

// Expose helpers globally (used in inline onclick)
window._removeMultiCh = (id) => { document.getElementById(id)?.remove(); updateSpanHint(); };
window._updateMultiSpanHint = updateSpanHint;

function updateSpanHint() {
  const centerFreq = parseInt(document.getElementById('multiCenterFreq')?.value) || 0;
  const wbRate = parseInt(document.getElementById('multiWidebandRate')?.value) || 0;
  const hint = document.getElementById('multiSpanHint');
  if (!hint) return;
  if (!centerFreq || !wbRate) { hint.textContent = ''; return; }
  const halfBw = wbRate / 2;
  const lo = ((centerFreq - halfBw) / 1e6).toFixed(3);
  const hi = ((centerFreq + halfBw) / 1e6).toFixed(3);
  hint.textContent = `Capture span: ${lo}–${hi} MHz (±${(halfBw/1e6).toFixed(1)} MHz)`;
}

function getChannels() {
  const rows = document.getElementById('multiChannelList').children;
  const channels = [];
  for (const row of rows) {
    const id = row.id.replace('multiCh_', '');
    const mode = document.getElementById(`multiChMode_${id}`)?.value;
    const freq = parseInt(document.getElementById(`multiChFreq_${id}`)?.value);
    const label = (document.getElementById(`multiChLabel_${id}`)?.value || '').trim() || `ch${id}`;
    if (mode && freq) channels.push({ mode, frequency: freq, label });
  }
  return channels;
}

function resetForm() {
  document.getElementById('multiChannelList').innerHTML = '';
  multiChannelCount = 0;
  document.getElementById('multiStatus').classList.add('hidden');
  document.getElementById('multiStats').classList.add('hidden');
  updateSpanHint();
  addChannel('aprs', 144800000, 'APRS-EU');
  addChannel('pocsag', 147325000, 'POCSAG-1');
}

async function handleSubmit(e) {
  e.preventDefault();
  const sdrParams = getSdrParams();
  if (!sdrParams) return;

  const channels = getChannels();
  if (channels.length < 2) { toast('At least 2 channels required', 'warning'); return; }

  const body = {
    device_address: sdrParams.device_address,
    center_freq: parseInt(document.getElementById('multiCenterFreq').value),
    wideband_rate: parseInt(document.getElementById('multiWidebandRate').value),
    gain: parseInt(document.getElementById('multiGain').value),
    duration: parseInt(document.getElementById('multiDuration').value),
    channels,
  };

  const startBtn = document.getElementById('multiStartBtn');
  const stopBtn = document.getElementById('multiStopBtn');
  const statusDiv = document.getElementById('multiStatus');

  startBtn.disabled = true;
  statusDiv.classList.remove('hidden');
  statusDiv.textContent = 'Starting multi-channel session…';

  try {
    const { ok, data } = await startMultiChannel(body);

    if (!ok) {
      statusDiv.textContent = 'Error: ' + (data.error || 'Unknown');
      startBtn.disabled = false;
      toast('Multi-channel start failed', 'error');
      return;
    }

    sessionId = data.session_id;
    startTime = Date.now();
    statusDiv.textContent = `Running — session ${sessionId} | ×${data.decimation_factor} → ${(data.intermediate_rate/1e3).toFixed(0)} kS/s`;

    startBtn.classList.add('hidden');
    stopBtn.classList.remove('hidden');

    // Init stats table
    const tbody = document.getElementById('multiChannelStatsBody');
    document.getElementById('multiSessionId').textContent = sessionId;
    tbody.innerHTML = '';
    for (const ch of data.channels) {
      const tr = document.createElement('tr');
      tr.id = `multiStatRow_${ch.label}`;
      tr.className = 'divide-y divide-slate-700/50';
      tr.innerHTML = `
        <td class="px-3 py-2 text-slate-200">${escHtml(ch.label)}</td>
        <td class="px-3 py-2 text-slate-400 text-xs">${ch.mode.toUpperCase()}</td>
        <td class="px-3 py-2 text-right font-mono text-xs text-slate-300">${(ch.frequency/1e6).toFixed(4)} MHz</td>
        <td class="px-3 py-2 text-right font-mono text-cyan-400" id="multiPkt_${ch.label}">0</td>
      `;
      tbody.appendChild(tr);
    }
    document.getElementById('multiStats').classList.remove('hidden');

    pollInterval = setInterval(pollSession, 3000);
    toast('Multi-channel session started', 'success');

  } catch (err) {
    statusDiv.textContent = 'Request failed: ' + err.message;
    startBtn.disabled = false;
    toast('Error: ' + err.message, 'error');
  }
}

async function pollSession() {
  if (!sessionId) return;
  try {
    const { ok, data } = await getStreamStatus(sessionId);
    if (!ok) return;
    const session = data.session;

    document.getElementById('multiTotalPackets').textContent = session.packet_count ?? 0;
    document.getElementById('multiRuntime').textContent = Math.floor((Date.now() - startTime) / 1000) + 's';

    if (session.status === 'completed' || session.status === 'failed') {
      clearInterval(pollInterval); pollInterval = null;
      const statusDiv = document.getElementById('multiStatus');
      statusDiv.textContent = session.status === 'failed'
        ? `Session failed: ${session.error || 'unknown'}`
        : `Session completed — ${session.packet_count} packets decoded`;
      document.getElementById('multiStartBtn').classList.remove('hidden');
      document.getElementById('multiStartBtn').disabled = false;
      document.getElementById('multiStopBtn').classList.add('hidden');
      sessionId = null;
      toast(session.status === 'failed' ? 'Multi-channel session failed' : 'Multi-channel session completed',
        session.status === 'failed' ? 'error' : 'success');
    }
  } catch { /* ignore */ }
}

async function stopSession() {
  if (!sessionId) return;
  clearInterval(pollInterval); pollInterval = null;
  try {
    await stopStream(sessionId);
  } catch { /* ignore */ }
  document.getElementById('multiStatus').textContent = 'Session stopped.';
  document.getElementById('multiStartBtn').classList.remove('hidden');
  document.getElementById('multiStartBtn').disabled = false;
  document.getElementById('multiStopBtn').classList.add('hidden');
  sessionId = null;
  toast('Multi-channel session stopped', 'info');
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
