import { startRepeaterScan, getRepeaterProgress } from './api.js';
import { toast } from './toast.js';

let currentSessionId = null;
let pollInterval = null;

export function init() {
  // Presets
  document.querySelectorAll('#repeaterTab .preset-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.dataset.band !== undefined) document.getElementById('repeaterBand').value = btn.dataset.band;
      if (btn.dataset.canton !== undefined) document.getElementById('repeaterCanton').value = btn.dataset.canton;
    });
  });

  document.getElementById('repeaterReset')?.addEventListener('click', () => {
    document.getElementById('repeaterForm').reset();
    document.getElementById('repeaterBand').value = '2m';
    document.getElementById('repeaterStatus').classList.add('hidden');
    document.getElementById('repeaterProgress').classList.add('hidden');
    document.getElementById('repeaterResults').classList.add('hidden');
  });

  document.getElementById('repeaterForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await startScan();
  });

  window.addEventListener('beforeunload', () => {
    if (pollInterval) clearInterval(pollInterval);
  });
}

async function startScan() {
  const body = {
    duration_per_repeater: parseInt(document.getElementById('repeaterDuration').value),
    gain: parseInt(document.getElementById('repeaterGain').value),
  };
  const band = document.getElementById('repeaterBand').value;
  const canton = document.getElementById('repeaterCanton').value;
  if (band) body.band = band;
  if (canton) body.canton = canton;

  const startBtn = document.getElementById('repeaterStartBtn');
  const statusDiv = document.getElementById('repeaterStatus');
  const progressDiv = document.getElementById('repeaterProgress');
  const resultsDiv = document.getElementById('repeaterResults');

  startBtn.disabled = true;
  statusDiv.textContent = 'Initializing scan...';
  statusDiv.classList.remove('hidden');
  progressDiv.classList.add('hidden');
  resultsDiv.classList.add('hidden');

  try {
    const { ok, data } = await startRepeaterScan(body);

    if (ok && data.status === 'success') {
      currentSessionId = data.session_id;
      statusDiv.textContent = `Scan started — ${data.repeaters_count} repeaters, ~${Math.floor(data.estimated_duration_seconds / 60)} min`;
      progressDiv.classList.remove('hidden');
      resultsDiv.classList.remove('hidden');
      startPolling(data.session_id);
      toast(`Repeater scan started (${data.repeaters_count} repeaters)`, 'info');
    } else {
      statusDiv.textContent = 'Error: ' + (data.message || 'Failed to start scan');
      startBtn.disabled = false;
      toast('Failed to start scan: ' + (data.message || 'Unknown error'), 'error');
    }
  } catch (err) {
    statusDiv.textContent = 'Error: ' + err.message;
    startBtn.disabled = false;
    toast('Scan error: ' + err.message, 'error');
  }
}

function startPolling(sessionId) {
  if (pollInterval) clearInterval(pollInterval);

  pollInterval = setInterval(async () => {
    try {
      const { ok, data } = await getRepeaterProgress(sessionId);
      if (!ok) return;

      if (data.status === 'in_progress') {
        updateProgress(data.progress);
        updateResults(data.results);
      } else if (data.status === 'completed') {
        updateProgress(data.progress);
        updateResults(data.results);
        stopPolling('completed');
      } else if (data.status === 'failed') {
        stopPolling('failed', data.error);
      }
    } catch { /* ignore transient errors */ }
  }, 2000);
}

function stopPolling(status, error) {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
  currentSessionId = null;

  const statusDiv = document.getElementById('repeaterStatus');
  const startBtn = document.getElementById('repeaterStartBtn');

  if (status === 'completed') {
    statusDiv.textContent = 'Scan completed!';
    toast('Repeater scan completed', 'success');
  } else {
    statusDiv.textContent = 'Scan failed: ' + (error || 'Unknown error');
    toast('Repeater scan failed: ' + (error || 'Unknown'), 'error');
  }

  startBtn.disabled = false;
}

function updateProgress(p) {
  if (!p) return;
  const pct = p.total_repeaters > 0 ? (p.current_repeater / p.total_repeaters) * 100 : 0;
  document.getElementById('progressBar').style.width = `${pct}%`;
  document.getElementById('progressRepeater').textContent = `Repeater ${p.current_repeater}/${p.total_repeaters}`;
  document.getElementById('progressCallsign').textContent = p.current_callsign || '—';
  document.getElementById('progressElapsed').textContent = p.elapsed_seconds + 's';
  document.getElementById('progressRemaining').textContent =
    p.estimated_remaining_seconds > 0 ? p.estimated_remaining_seconds + 's' : 'Calculating...';
  document.getElementById('progressScanned').textContent = p.repeaters_scanned || 0;
  document.getElementById('progressActive').textContent = p.repeaters_with_activity || 0;
}

function updateResults(results) {
  if (!results || results.length === 0) return;
  const tbody = document.getElementById('repeaterResultsBody');
  tbody.innerHTML = results.map(r => {
    const act = r.activity || {};
    const active = act.carrier_detected;
    return `<tr class="${active ? 'bg-emerald-500/5' : ''}">
      <td class="px-4 py-2.5 font-semibold text-slate-100 font-sans">${escHtml(r.callsign)}</td>
      <td class="px-4 py-2.5 font-mono text-xs text-slate-300">${(r.frequency / 1e6).toFixed(4)} MHz</td>
      <td class="px-4 py-2.5 text-center text-xs">
        <span class="${active ? 'text-emerald-400' : 'text-slate-600'}">${active ? 'Active' : 'Quiet'}</span>
      </td>
      <td class="px-4 py-2.5 text-right text-xs text-slate-400">${act.transmission_count || 0}</td>
      <td class="px-4 py-2.5 text-right text-xs text-slate-400">${act.activity_percentage ? act.activity_percentage.toFixed(1)+'%' : '0%'}</td>
      <td class="px-4 py-2.5 text-right text-xs text-slate-400">${act.average_signal_strength ? act.average_signal_strength.toFixed(1)+' dB' : '—'}</td>
    </tr>`;
  }).join('');
}

function escHtml(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
