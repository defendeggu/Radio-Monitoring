import { startCapture, forceStopSdr, getSdrParams } from './api.js';
import { pollCaptureStatus } from './polling.js';
import { toast } from './toast.js';
import { validateFrequency } from './sdr.js';

export function init() {
  // Preset buttons
  document.querySelectorAll('#voiceTab .preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('voiceFrequency').value = btn.dataset.freq;
      document.getElementById('voiceModulation').value = btn.dataset.mod;
    });
  });

  document.getElementById('voiceReset')?.addEventListener('click', () => {
    document.getElementById('voiceForm').reset();
    hideStatus();
    hideResult();
    hideProgress();
  });

  document.getElementById('voiceStop')?.addEventListener('click', async () => {
    try {
      await forceStopSdr();
    } catch { /* ignore */ }
    document.getElementById('voiceStop').disabled = true;
  });

  document.getElementById('voiceForm').addEventListener('submit', handleSubmit, true);
  document.getElementById('voiceForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await startVoice();
  });
}

function handleSubmit(e) {
  const freq = parseInt(document.getElementById('voiceFrequency').value);
  if (!validateFrequency(freq)) {
    e.preventDefault();
    e.stopImmediatePropagation();
  }
}

async function startVoice() {
  const sdrParams = getSdrParams();
  if (!sdrParams) return;

  const frequency = parseInt(document.getElementById('voiceFrequency').value);
  const duration = parseInt(document.getElementById('voiceDuration').value);
  const body = {
    frequency,
    modulation: document.getElementById('voiceModulation').value,
    duration,
    gain: parseInt(document.getElementById('voiceGain').value),
    language: document.getElementById('voiceLanguage').value || null,
    mode: 'voice',
    ...sdrParams,
  };

  const startBtn = document.getElementById('voiceStart');
  const stopBtn = document.getElementById('voiceStop');

  startBtn.disabled = true;
  startBtn.innerHTML = `<svg class="animate-spin" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg> Recording...`;
  stopBtn.disabled = false;
  hideResult();
  showProgress(5, 'Starting...', duration);

  try {
    const data = await startCapture(body);

    pollCaptureStatus({
      captureId: data.capture_id,
      progressConfig: {
        barEl: document.getElementById('voiceProgressBar'),
        labelEl: document.getElementById('voiceProgressLabel'),
        containerEl: document.getElementById('voiceProgress'),
        duration,
      },
      onStatus(label) {
        document.getElementById('voiceProgressLabel').textContent = label;
      },
      onDone(result) {
        resetButtons();
        hideProgress();
        displayResult(result);
        toast('Transcription completed', 'success');
      },
      onError(msg) {
        resetButtons();
        hideProgress();
        toast('Capture failed: ' + msg, 'error');
      },
    });

  } catch (err) {
    resetButtons();
    hideProgress();
    toast('Error: ' + err.message, 'error');
  }
}

function resetButtons() {
  const startBtn = document.getElementById('voiceStart');
  startBtn.disabled = false;
  startBtn.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"/></svg> Start Recording`;
  document.getElementById('voiceStop').disabled = true;
}

function showProgress(pct, label, duration) {
  document.getElementById('voiceProgress').classList.remove('hidden');
  document.getElementById('voiceProgressBar').style.width = pct + '%';
  document.getElementById('voiceProgressLabel').textContent = label;
}

function hideProgress() {
  document.getElementById('voiceProgress').classList.add('hidden');
}

function hideStatus() {
  document.getElementById('voiceStatus').classList.add('hidden');
}

function hideResult() {
  document.getElementById('voiceResult').classList.add('hidden');
}

function displayResult(data) {
  const transcription = data.transcription || data;
  const text = (transcription.text || '').trim() || 'No speech detected (silence or noise only)';
  const capture = data.capture || {};

  const div = document.getElementById('voiceResult');
  div.innerHTML = `
    <h3 class="text-sm font-semibold text-slate-200 mb-3">Transcription Result</h3>
    <div class="text-slate-100 bg-slate-900/60 rounded-lg p-3 mb-3 leading-relaxed text-sm font-mono whitespace-pre-wrap">${escHtml(text)}</div>
    <div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
      ${stat('Language', transcription.language || 'N/A')}
      ${stat('Duration', capture.duration ? capture.duration + ' s' : 'N/A')}
      ${stat('Frequency', capture.frequency ? (capture.frequency / 1e6).toFixed(3) + ' MHz' : 'N/A')}
      ${stat('Modulation', capture.modulation || 'N/A')}
    </div>
  `;
  div.classList.remove('hidden');
}

function stat(label, value) {
  return `<div class="bg-slate-900/40 rounded-lg px-3 py-2">
    <div class="text-xs text-slate-500 mb-0.5">${label}</div>
    <div class="text-sm font-mono text-slate-200">${value}</div>
  </div>`;
}

function escHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
