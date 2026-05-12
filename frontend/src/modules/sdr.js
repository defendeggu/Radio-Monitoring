import { detectSdr } from './api.js';

// Global SDR capabilities
window.sdrType = null;
window.sdrFrequencyRange = null;
window.sdrMaxSampleRate = null;

export async function init() {
  initSelector();
  await runDetect();
}

function initSelector() {
  const deviceSelect = document.getElementById('globalSdrDevice');
  const ipInput = document.getElementById('usrpIpAddress');
  const ipHint = document.getElementById('usrpIpHint');

  function applyUsrpVisibility() {
    const isUsrp = deviceSelect.value === 'usrp';
    ipInput.classList.toggle('hidden', !isUsrp);
    ipHint.classList.toggle('hidden', !isUsrp);
  }

  deviceSelect.addEventListener('change', function () {
    localStorage.setItem('sdrDeviceType', this.value);
    applyUsrpVisibility();

    // Show/hide Multi-Channel tab
    const multiBtn = document.getElementById('multiTabBtn');
    if (multiBtn) multiBtn.classList.toggle('hidden', this.value !== 'usrp');
  });

  ipInput.addEventListener('input', function () {
    localStorage.setItem('usrpIpAddress', this.value);
  });

  // Restore saved settings
  const savedDevice = localStorage.getItem('sdrDeviceType');
  if (savedDevice) deviceSelect.value = savedDevice;
  const savedIp = localStorage.getItem('usrpIpAddress');
  if (savedIp) ipInput.value = savedIp;

  applyUsrpVisibility();

  // Initial multi-tab visibility
  const multiBtn = document.getElementById('multiTabBtn');
  if (multiBtn) multiBtn.classList.toggle('hidden', deviceSelect.value !== 'usrp');
}

async function runDetect() {
  const dot = document.getElementById('sdr-dot');
  const label = document.getElementById('sdr-label');

  try {
    const { ok, data } = await detectSdr();
    if (ok) {
      window.sdrType = data.type;
      window.sdrFrequencyRange = data.frequency_range;
      window.sdrMaxSampleRate = data.max_sample_rate_hz;

      const freqRange = `${data.frequency_range.min_mhz.toFixed(1)}–${data.frequency_range.max_mhz.toFixed(0)} MHz`;
      dot.className = 'w-2 h-2 rounded-full bg-emerald-400 shrink-0';
      label.textContent = `${data.type.toUpperCase()} (${freqRange})`;
      label.className = 'text-emerald-400 truncate text-xs';
    } else {
      dot.className = 'w-2 h-2 rounded-full bg-amber-400 shrink-0';
      label.textContent = 'No SDR detected';
      label.className = 'text-amber-400 truncate text-xs';
    }
  } catch {
    dot.className = 'w-2 h-2 rounded-full bg-red-400 shrink-0';
    label.textContent = 'API unreachable';
    label.className = 'text-red-400 truncate text-xs';
  }
}

export function validateFrequency(frequency) {
  if (!window.sdrFrequencyRange) return true;
  const { min_hz, max_hz } = window.sdrFrequencyRange;
  if (frequency < min_hz || frequency > max_hz) {
    const freqMHz = (frequency / 1e6).toFixed(3);
    const minMHz = (min_hz / 1e6).toFixed(1);
    const maxMHz = (max_hz / 1e6).toFixed(0);
    alert(
      `Frequency ${freqMHz} MHz is out of range for ${(window.sdrType || '').toUpperCase()}.\n\n` +
      `Valid range: ${minMHz}–${maxMHz} MHz`
    );
    return false;
  }
  return true;
}
