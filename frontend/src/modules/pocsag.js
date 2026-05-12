import { startCapture, startStream, getStreamStatus, stopStream, getSdrParams } from './api.js';
import { pollCaptureStatus } from './polling.js';
import { toast } from './toast.js';
import { validateFrequency } from './sdr.js';

let streamSessionId = null;
let streamInterval = null;
let streamErrorCount = 0;

export function init() {
  // Presets
  document.querySelectorAll('#pocsagTab .preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.pocsagFreq) {
        document.getElementById('pocsagFrequency').value = btn.dataset.pocsagFreq;
      }
    });
  });

  document.getElementById('pocsagReset')?.addEventListener('click', () => {
    document.getElementById('pocsagForm').reset();
    document.getElementById('pocsagStatus').classList.add('hidden');
    document.getElementById('pocsagResult').classList.add('hidden');
    document.getElementById('pocsagProgress').classList.add('hidden');
  });

  // Streaming mode toggle
  document.getElementById('pocsagStreamingMode').addEventListener('change', (e) => {
    const streaming = e.target.checked;
    document.getElementById('pocsagNormalButtons').classList.toggle('hidden', streaming);
    document.getElementById('pocsagStreamButtons').classList.toggle('hidden', !streaming);
    const durationInput = document.getElementById('pocsagDuration');
    const hint = document.getElementById('pocsagDurationHint');
    if (streaming) {
      durationInput.value = 3600;
      durationInput.min = 60;
      durationInput.max = 86400;
      hint.textContent = 'Duration for streaming session (1–24 hours = 3600–86400 s)';
    } else {
      durationInput.value = 60;
      durationInput.min = 30;
      durationInput.max = 120;
      hint.textContent = 'Recommended: 60–120 s for POCSAG';
    }
  });

  // Normal capture
  document.getElementById('pocsagForm').addEventListener('submit', (e) => {
    const freq = parseInt(document.getElementById('pocsagFrequency').value);
    if (!validateFrequency(freq)) { e.preventDefault(); e.stopImmediatePropagation(); }
  }, true);

  document.getElementById('pocsagForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const duration = parseInt(document.getElementById('pocsagDuration').value);
    if (duration > 120) {
      toast('For durations > 120 s, enable Continuous Streaming Mode', 'warning');
      return;
    }
    await startNormalCapture();
  });

  // Streaming buttons
  document.getElementById('pocsagStreamStart').addEventListener('click', startStreaming);
  document.getElementById('pocsagStreamStop').addEventListener('click', stopStreaming);
}

async function startNormalCapture() {
  const sdrParams = getSdrParams();
  if (!sdrParams) return;
  const duration = parseInt(document.getElementById('pocsagDuration').value);

  const body = {
    frequency: parseInt(document.getElementById('pocsagFrequency').value),
    modulation: 'FM',
    duration,
    gain: parseInt(document.getElementById('pocsagGain').value),
    mode: 'pocsag',
    ...sdrParams,
  };

  const submitBtn = document.querySelector('#pocsagNormalButtons button[type="submit"]') ||
                    document.querySelector('#pocsagForm button[type="submit"]');
  submitBtn.disabled = true;
  submitBtn.textContent = 'Capturing POCSAG...';
  document.getElementById('pocsagResult').classList.add('hidden');

  const progressEl = document.getElementById('pocsagProgress');
  progressEl.classList.remove('hidden');

  try {
    const data = await startCapture(body);

    pollCaptureStatus({
      captureId: data.capture_id,
      progressConfig: {
        barEl: document.getElementById('pocsagProgressBar'),
        labelEl: document.getElementById('pocsagProgressLabel'),
        containerEl: progressEl,
        duration,
      },
      onDone(result) {
        resetSubmitBtn(submitBtn, 'Start POCSAG Capture');
        displayResult(result);
        toast('POCSAG capture completed', 'success');
      },
      onError(msg) {
        resetSubmitBtn(submitBtn, 'Start POCSAG Capture');
        progressEl.classList.add('hidden');
        toast('POCSAG capture failed: ' + msg, 'error');
      },
    });

  } catch (err) {
    resetSubmitBtn(submitBtn, 'Start POCSAG Capture');
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
    mode: 'pocsag',
    frequency: parseFloat(document.getElementById('pocsagFrequency').value),
    duration: parseInt(document.getElementById('pocsagDuration').value),
    gain: parseInt(document.getElementById('pocsagGain').value),
    ...sdrParams,
  };

  try {
    const data = await startStream(body);
    streamSessionId = data.session_id;
    streamErrorCount = 0;

    document.getElementById('pocsagStreamStart').disabled = true;
    document.getElementById('pocsagStreamStop').disabled = false;
    document.getElementById('pocsagStreamStats').classList.remove('hidden');
    document.getElementById('pocsagStreamStatus').textContent = 'Starting...';

    streamInterval = setInterval(updateStats, 2000);
    toast('POCSAG streaming started', 'success');
  } catch (err) {
    toast('Failed to start streaming: ' + err.message, 'error');
  }
}

async function stopStreaming() {
  if (!streamSessionId) return;
  try {
    const resp = await stopStream(streamSessionId);
    if (!resp.ok && resp.status !== 404) toast('Stop request failed', 'warning');
  } catch { /* ignore */ }

  clearInterval(streamInterval);
  streamInterval = null;
  streamErrorCount = 0;
  document.getElementById('pocsagStreamStatus').textContent = 'Stopped';

  setTimeout(() => {
    document.getElementById('pocsagStreamStart').disabled = false;
    document.getElementById('pocsagStreamStop').disabled = true;
    document.getElementById('pocsagStreamStats').classList.add('hidden');
    streamSessionId = null;
  }, 2000);

  toast('POCSAG streaming stopped', 'info');
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
        document.getElementById('pocsagStreamStatus').textContent = 'Session ended';
        document.getElementById('pocsagStreamStart').disabled = false;
        document.getElementById('pocsagStreamStop').disabled = true;
        toast('POCSAG streaming session ended', 'info');
      }
      return;
    }

    streamErrorCount = 0;
    document.getElementById('pocsagPacketCount').textContent = data.stats.packet_count;
    document.getElementById('pocsagElapsed').textContent = formatDuration(data.stats.elapsed_seconds);
    document.getElementById('pocsagLastPacket').textContent = data.stats.last_packet_time
      ? new Date(data.stats.last_packet_time).toLocaleTimeString() : '—';
    document.getElementById('pocsagStreamStatus').textContent = data.status;

    if (data.status === 'completed' || data.status === 'failed') {
      clearInterval(streamInterval);
      streamInterval = null;
      streamSessionId = null;
      document.getElementById('pocsagStreamStart').disabled = false;
      document.getElementById('pocsagStreamStop').disabled = true;
      if (data.status === 'failed') toast('POCSAG streaming failed: ' + (data.stats?.error || 'Unknown'), 'error');
      else toast('POCSAG streaming completed', 'success');
    }

  } catch {
    streamErrorCount++;
    if (streamErrorCount >= 3) {
      clearInterval(streamInterval);
      streamInterval = null;
      document.getElementById('pocsagStreamStatus').textContent = 'Polling error';
      document.getElementById('pocsagStreamStart').disabled = false;
      document.getElementById('pocsagStreamStop').disabled = true;
      toast('Lost contact with API during POCSAG streaming', 'error');
    }
  }
}

function displayResult(data) {
  const messages = data.pocsag?.messages || [];
  const count = data.pocsag?.message_count || 0;
  const capture = data.capture || {};

  const div = document.getElementById('pocsagResult');
  let html = `
    <h3 class="text-sm font-semibold text-slate-200 mb-3">POCSAG Messages Decoded</h3>
    <div class="grid grid-cols-3 gap-3 mb-4">
      <div class="bg-slate-900/40 rounded-lg px-3 py-2">
        <div class="text-xs text-slate-500">Messages</div>
        <div class="text-xl font-mono text-amber-400">${count}</div>
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

  if (messages.length === 0) {
    html += `<p class="text-sm text-slate-400">No POCSAG messages decoded. Ensure pager activity on this frequency.</p>`;
  } else {
    html += `<table>
      <thead><tr>
        <th>Time</th><th>Address</th><th>Type</th><th>Baud</th><th>Message</th>
      </tr></thead>
      <tbody>
        ${messages.map(m => `<tr>
          <td>${new Date(m.timestamp).toLocaleTimeString()}</td>
          <td class="font-semibold text-slate-100 font-sans">${escHtml(m.address)}</td>
          <td>${escHtml(m.message_type)}</td>
          <td>${m.baud_rate}</td>
          <td>${escHtml(m.message_text || 'Tone Only')}</td>
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
