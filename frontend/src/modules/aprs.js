import { startCapture, startStream, getStreamStatus, stopStream, getSdrParams } from './api.js';
import { pollCaptureStatus } from './polling.js';
import { toast } from './toast.js';
import { validateFrequency } from './sdr.js';

let streamSessionId = null;
let streamInterval = null;
let streamErrorCount = 0;

export function init() {
  // Presets
  document.querySelectorAll('#aprsTab .preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.aprsFreq) {
        document.getElementById('aprsFrequency').value = btn.dataset.aprsFreq;
      }
    });
  });

  document.getElementById('aprsReset')?.addEventListener('click', () => {
    document.getElementById('aprsForm').reset();
    document.getElementById('aprsStatus').classList.add('hidden');
    document.getElementById('aprsResult').classList.add('hidden');
    document.getElementById('aprsProgress').classList.add('hidden');
  });

  // Streaming mode toggle
  document.getElementById('aprsStreamingMode').addEventListener('change', (e) => {
    const streaming = e.target.checked;
    document.getElementById('aprsNormalButtons').classList.toggle('hidden', streaming);
    document.getElementById('aprsStreamButtons').classList.toggle('hidden', !streaming);
    const durationInput = document.getElementById('aprsDuration');
    const hint = document.getElementById('aprsDurationHint');
    if (streaming) {
      durationInput.value = 3600;
      durationInput.max = 86400;
      hint.textContent = 'Duration for streaming session (1–24 hours = 3600–86400 s)';
    } else {
      durationInput.value = 300;
      durationInput.max = 300;
      hint.textContent = 'Recommended: 300 s for APRS capture';
    }
  });

  // Normal capture form
  document.getElementById('aprsForm').addEventListener('submit', (e) => {
    const freq = parseInt(document.getElementById('aprsFrequency').value);
    if (!validateFrequency(freq)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);

  document.getElementById('aprsForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const duration = parseInt(document.getElementById('aprsDuration').value);
    if (duration > 300) {
      toast('For durations > 300 s, enable Continuous Streaming Mode', 'warning');
      return;
    }
    await startNormalCapture();
  });

  // Streaming buttons
  document.getElementById('aprsStreamStart').addEventListener('click', startStreaming);
  document.getElementById('aprsStreamStop').addEventListener('click', stopStreaming);
}

async function startNormalCapture() {
  const sdrParams = getSdrParams();
  if (!sdrParams) return;
  const duration = parseInt(document.getElementById('aprsDuration').value);

  const body = {
    frequency: parseInt(document.getElementById('aprsFrequency').value),
    modulation: 'FM',
    duration,
    gain: parseInt(document.getElementById('aprsGain').value),
    mode: 'aprs',
    ...sdrParams,
  };

  const submitBtn = document.querySelector('#aprsNormalButtons button[type="submit"]') ||
                    document.querySelector('#aprsForm button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Capturing APRS...';
  document.getElementById('aprsResult').classList.add('hidden');

  const progressEl = document.getElementById('aprsProgress');
  progressEl.classList.remove('hidden');

  try {
    const data = await startCapture(body);

    pollCaptureStatus({
      captureId: data.capture_id,
      progressConfig: {
        barEl: document.getElementById('aprsProgressBar'),
        labelEl: document.getElementById('aprsProgressLabel'),
        containerEl: progressEl,
        duration,
      },
      onDone(result) {
        resetSubmitBtn(submitBtn, 'Start APRS Capture');
        displayResult(result);
        toast('APRS capture completed', 'success');
      },
      onError(msg) {
        resetSubmitBtn(submitBtn, 'Start APRS Capture');
        progressEl.classList.add('hidden');
        toast('APRS capture failed: ' + msg, 'error');
      },
    });

  } catch (err) {
    resetSubmitBtn(submitBtn, 'Start APRS Capture');
    progressEl.classList.add('hidden');
    toast('Error: ' + err.message, 'error');
  }
}

function resetSubmitBtn(btn, label) {
  btn.disabled = false;
  btn.textContent = label;
}

async function startStreaming() {
  const sdrParams = getSdrParams();
  if (!sdrParams) return;

  const body = {
    mode: 'aprs',
    frequency: parseFloat(document.getElementById('aprsFrequency').value),
    duration: parseInt(document.getElementById('aprsDuration').value),
    gain: parseInt(document.getElementById('aprsGain').value),
    ...sdrParams,
  };

  try {
    const data = await startStream(body);
    streamSessionId = data.session_id;
    streamErrorCount = 0;

    document.getElementById('aprsStreamStart').disabled = true;
    document.getElementById('aprsStreamStop').disabled = false;
    document.getElementById('aprsStreamStats').classList.remove('hidden');
    document.getElementById('aprsStreamStatus').textContent = 'Starting...';

    streamInterval = setInterval(updateStats, 2000);
    toast('APRS streaming started', 'success');
  } catch (err) {
    toast('Failed to start streaming: ' + err.message, 'error');
  }
}

async function stopStreaming() {
  if (!streamSessionId) return;
  try {
    const resp = await stopStream(streamSessionId);
    if (!resp.ok && resp.status !== 404) {
      toast('Stop request failed', 'warning');
    }
  } catch { /* ignore */ }

  clearInterval(streamInterval);
  streamInterval = null;
  streamErrorCount = 0;
  document.getElementById('aprsStreamStatus').textContent = 'Stopped';

  setTimeout(() => {
    document.getElementById('aprsStreamStart').disabled = false;
    document.getElementById('aprsStreamStop').disabled = true;
    document.getElementById('aprsStreamStats').classList.add('hidden');
    streamSessionId = null;
  }, 2000);

  toast('APRS streaming stopped', 'info');
}

async function updateStats() {
  if (!streamSessionId) return;
  try {
    const { ok, status, data } = await getStreamStatus(streamSessionId);

    if (!ok) {
      if (status === 404) {
        clearInterval(streamInterval);
        streamInterval = null;
        streamSessionId = null;
        document.getElementById('aprsStreamStatus').textContent = 'Session ended';
        document.getElementById('aprsStreamStart').disabled = false;
        document.getElementById('aprsStreamStop').disabled = true;
        toast('APRS streaming session ended', 'info');
      }
      return;
    }

    streamErrorCount = 0;
    document.getElementById('aprsPacketCount').textContent = data.stats.packet_count;
    document.getElementById('aprsElapsed').textContent = formatDuration(data.stats.elapsed_seconds);
    document.getElementById('aprsLastPacket').textContent = data.stats.last_packet_time
      ? new Date(data.stats.last_packet_time).toLocaleTimeString() : '—';
    document.getElementById('aprsStreamStatus').textContent = data.status;

    if (data.status === 'completed' || data.status === 'failed') {
      clearInterval(streamInterval);
      streamInterval = null;
      streamSessionId = null;
      document.getElementById('aprsStreamStart').disabled = false;
      document.getElementById('aprsStreamStop').disabled = true;
      if (data.status === 'failed') toast('APRS streaming failed: ' + (data.stats?.error || 'Unknown'), 'error');
      else toast('APRS streaming completed', 'success');
    }

  } catch {
    streamErrorCount++;
    if (streamErrorCount >= 3) {
      clearInterval(streamInterval);
      streamInterval = null;
      document.getElementById('aprsStreamStatus').textContent = 'Polling error';
      document.getElementById('aprsStreamStart').disabled = false;
      document.getElementById('aprsStreamStop').disabled = true;
      toast('Lost contact with API during APRS streaming', 'error');
    }
  }
}

function displayResult(data) {
  const packets = data.aprs?.packets || [];
  const count = data.aprs?.packet_count || 0;
  const capture = data.capture || {};

  const div = document.getElementById('aprsResult');
  let html = `
    <h3 class="text-sm font-semibold text-slate-200 mb-3">APRS Packets Decoded</h3>
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="bg-slate-900/40 rounded-lg px-3 py-2">
        <div class="text-xs text-slate-500">Packets</div>
        <div class="text-xl font-mono text-cyan-400">${count}</div>
      </div>
      <div class="bg-slate-900/40 rounded-lg px-3 py-2">
        <div class="text-xs text-slate-500">Frequency</div>
        <div class="text-sm font-mono text-slate-200">${capture.frequency ? (capture.frequency/1e6).toFixed(3)+' MHz' : 'N/A'}</div>
      </div>
      <div class="bg-slate-900/40 rounded-lg px-3 py-2">
        <div class="text-xs text-slate-500">Duration</div>
        <div class="text-sm font-mono text-slate-200">${capture.duration ? capture.duration+'s' : 'N/A'}</div>
      </div>
    </div>
  `;

  if (packets.length === 0) {
    html += `<p class="text-sm text-slate-400">No APRS packets decoded. Ensure APRS activity on this frequency.</p>`;
  } else {
    html += `<table>
      <thead><tr>
        <th>Time</th><th>Callsign</th><th>Type</th><th>Position</th><th>Message</th>
      </tr></thead>
      <tbody>
        ${packets.map(p => `<tr>
          <td>${new Date(p.timestamp).toLocaleTimeString()}</td>
          <td class="font-semibold text-slate-100 font-sans">${escHtml(p.source_callsign)}</td>
          <td>${escHtml(p.aprs_type)}</td>
          <td>${p.latitude && p.longitude ? `${p.latitude.toFixed(4)}, ${p.longitude.toFixed(4)}` : 'N/A'}</td>
          <td>${escHtml(p.message_text || '—')}</td>
        </tr>`).join('')}
      </tbody>
    </table>`;
  }

  div.innerHTML = html;
  div.classList.remove('hidden');
}

function formatDuration(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = Math.floor(s % 60);
  return h > 0
    ? `${h}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`
    : `${m}:${String(sec).padStart(2,'0')}`;
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
